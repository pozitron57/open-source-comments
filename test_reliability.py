import os
import sys
import tempfile
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch


try:
    import yaml  # noqa: F401
except ModuleNotFoundError:
    yaml_module = types.ModuleType('yaml')
    yaml_module.SafeLoader = object
    yaml_module.load = lambda *_args, **_kwargs: None
    sys.modules['yaml'] = yaml_module

try:
    import mistune  # noqa: F401
except ModuleNotFoundError:
    mistune_module = types.ModuleType('mistune')

    class HTMLRenderer:
        def __init__(self, **_kwargs):
            pass

    def create_markdown(**_kwargs):
        return lambda value: '<p>{}</p>\n'.format(value)

    mistune_module.HTMLRenderer = HTMLRenderer
    mistune_module.create_markdown = create_markdown
    sys.modules['mistune'] = mistune_module

import alerts
import atomic_io
import dns_proxy
import history_store
import md_to_html
import validate_outputs
import yaml_2_js


class ReliabilityTests(unittest.TestCase):
    def test_history_rejects_unsorted_events(self):
        history = history_store.empty_history()
        history['dates'] = ['2026-07-29', '2026-07-30']
        history['projects'] = {
            'example': {
                'stars': [
                    ['2026-07-30', 2],
                    ['2026-07-29', 1],
                ],
            },
        }

        with self.assertRaisesRegex(history_store.HistoryValidationError, 'not strictly ordered'):
            history_store.validate_history(history)

    def test_multi_file_atomic_write_rolls_back_prior_file(self):
        with tempfile.TemporaryDirectory() as directory:
            first = os.path.join(directory, 'first.txt')
            second = os.path.join(directory, 'second.txt')
            atomic_io.atomic_write_text(first, 'old first\n')
            atomic_io.atomic_write_text(second, 'old second\n')
            real_write = atomic_io.atomic_write_text

            def fail_second(path, content, encoding='utf-8', default_mode=0o644):
                if path == second and content == 'new second\n':
                    raise OSError('disk full')
                return real_write(path, content, encoding=encoding, default_mode=default_mode)

            with patch('atomic_io.atomic_write_text', side_effect=fail_second):
                with self.assertRaisesRegex(OSError, 'disk full'):
                    atomic_io.atomic_write_many_text(
                        {
                            first: 'new first\n',
                            second: 'new second\n',
                        }
                    )

            with open(first, 'r', encoding='utf-8') as source:
                self.assertEqual(source.read(), 'old first\n')
            with open(second, 'r', encoding='utf-8') as source:
                self.assertEqual(source.read(), 'old second\n')

    def test_warning_is_rendered_as_star_tooltip(self):
        output = yaml_2_js.generate_data_js(
            {
                'example': {
                    'name': 'Example',
                    'source': 'https://github.com/example/repository',
                    'stars': 42,
                    'update_warning': "API failed after owner's rename",
                    'update_warning_at': '2026-07-30',
                },
            }
        )
        rows, columns = validate_outputs.parse_data_js(output)

        self.assertEqual(len(rows), 1)
        self.assertEqual(len(columns), len(yaml_2_js.fields))
        self.assertIn('stars-with-extra', rows[0][0])
        self.assertIn('Update warning on 2026-07-30', rows[0][0])
        self.assertIn('owner&#x27;s rename', rows[0][0])

    def test_markdown_renderer_refuses_missing_sections(self):
        with self.assertRaisesRegex(RuntimeError, 'exactly one'):
            md_to_html.render_index('# Title\n', '<html></html>')

    def test_alert_delivery_retries(self):
        failed = SimpleNamespace(returncode=1, stderr='temporary', stdout='')
        delivered = SimpleNamespace(returncode=0, stderr='', stdout='')
        environment = {
            'OSC_ALERT_EMAIL': 'user@example.com',
            'OSC_ALERT_ATTEMPTS': '3',
        }

        with patch.dict(os.environ, environment, clear=False):
            with patch('alerts.shutil.which', return_value='/usr/bin/mail'):
                with patch('alerts.subprocess.run', side_effect=[failed, delivered]) as run:
                    with patch('alerts.time.sleep') as sleep:
                        result = alerts.send_alert('subject', 'body')

        self.assertTrue(result)
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_dns_fallback_accepts_only_numeric_answers(self):
        answer = SimpleNamespace(
            returncode=0,
            stdout='alias.example.\n203.0.113.10\n',
            stderr='',
        )
        resolver = dns_proxy.Resolver()

        with patch('dns_proxy.subprocess.run', return_value=answer):
            address = resolver.resolve('example.com')

        self.assertEqual(address, '203.0.113.10')


if __name__ == '__main__':
    unittest.main()
