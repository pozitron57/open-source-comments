import importlib.util
import json
import sys
import types
import unittest
from unittest.mock import Mock, mock_open, patch
from urllib.error import URLError


try:
    ruamel_spec = importlib.util.find_spec('ruamel.yaml')
except ModuleNotFoundError:
    ruamel_spec = None

if ruamel_spec is None:
    ruamel = types.ModuleType('ruamel')
    ruamel_yaml = types.ModuleType('ruamel.yaml')

    class DummyYAML:
        preserve_quotes = False

        def indent(self, **_kwargs):
            pass

        def dump(self, _data, stream):
            stream.write('{}\n')

    ruamel_yaml.YAML = DummyYAML
    ruamel.yaml = ruamel_yaml
    sys.modules['ruamel'] = ruamel
    sys.modules['ruamel.yaml'] = ruamel_yaml


import get_data
from history_store import empty_history


class FakeResponse:
    def __init__(self, data, final_url):
        self.data = data
        self.final_url = final_url
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def geturl(self):
        return self.final_url

    def read(self, _limit=None):
        return json.dumps(self.data).encode('utf-8')


class GetDataTests(unittest.TestCase):
    def test_github_redirect_updates_source_and_notifies_immediately(self):
        old_url = 'https://github.com/imaegoo/twikoo'
        old_api_url = 'https://api.github.com/repos/imaegoo/twikoo'
        canonical_url = 'https://github.com/twikoojs/twikoo'
        canonical_api_url = 'https://api.github.com/repos/twikoojs/twikoo'
        source = {
            'provider': 'github',
            'api_url': old_api_url,
            'url': old_url,
        }
        item = {'source': old_url, 'license': 'MIT'}
        repository_data = {
            'stargazers_count': 2200,
            'created_at': '2020-05-24T00:00:00Z',
            'open_issues_count': 10,
            'html_url': canonical_url,
            'default_branch': 'main',
            'license': {'spdx_id': 'MIT'},
        }
        commit_data = {
            'commit': {'committer': {'date': '2026-07-30T00:00:00Z'}},
        }
        notify = Mock()

        with patch(
            'get_data.fetch_json',
            side_effect=[
                (repository_data, {}, 'https://api.github.com/repositories/266566637'),
                (commit_data, {}, canonical_api_url + '/commits/main'),
            ],
        ) as fetch:
            stats = get_data.fetch_github_repo(
                source,
                None,
                item,
                on_anomaly=notify,
            )

        self.assertEqual(item['source'], canonical_url)
        self.assertEqual(stats['stars'], 2200)
        notify.assert_called_once_with(
            'Repository moved permanently',
            'Repository moved: {} -> {}'.format(old_url, canonical_url),
        )
        self.assertEqual(fetch.call_args_list[1].args[0], canonical_api_url + '/commits/main')

    def test_incomplete_redirect_response_is_an_error_not_zero_stars(self):
        source = {
            'provider': 'github',
            'api_url': 'https://api.github.com/repos/imaegoo/twikoo',
            'url': 'https://github.com/imaegoo/twikoo',
        }
        item = {'source': source['url'], 'license': 'MIT'}

        with patch(
            'get_data.fetch_json',
            return_value=(
                {
                    'message': 'Moved Permanently',
                    'url': 'https://api.github.com/repositories/266566637',
                },
                {},
                source['api_url'],
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, 'missing required fields'):
                get_data.fetch_github_repo(source, None, item)

    def test_temporary_network_error_notifies_and_is_retried(self):
        response = FakeResponse(
            {'stargazers_count': 1},
            'https://api.github.com/repos/example/repository',
        )
        notify = Mock()

        with patch('get_data.urlopen', side_effect=[URLError('temporary'), response]) as fetch:
            with patch('get_data.time.sleep') as sleep:
                data, _headers, final_url = get_data.fetch_json(
                    'https://api.github.com/repos/example/repository',
                    {},
                    on_anomaly=notify,
                )

        self.assertEqual(data['stargazers_count'], 1)
        self.assertEqual(final_url, response.final_url)
        self.assertEqual(fetch.call_count, 2)
        sleep.assert_called_once_with(1)
        self.assertEqual(notify.call_count, 1)
        self.assertIn('retrying 2/3', notify.call_args.args[1])

    def test_failed_repository_is_frozen_while_other_repository_updates(self):
        failed_source = {
            'provider': 'github',
            'api_url': 'https://api.github.com/repos/example/repository',
            'url': 'https://github.com/example/repository',
        }
        working_source = {
            'provider': 'github',
            'api_url': 'https://api.github.com/repos/working/repository',
            'url': 'https://github.com/working/repository',
        }
        data = {
            'example': {
                'source': failed_source['url'],
                'stars': 42,
                'stars_dif': 1,
            },
            'working': {
                'source': working_source['url'],
                'stars': 10,
            },
        }
        history = empty_history()
        working_stats = {
            'provider': 'github',
            'stars': 20,
            'created': '2020‑01‑01',
            'open_issues': 3,
            'license': 'MIT',
            'last_commit': '2026‑07‑30',
        }

        with patch('builtins.open', mock_open()):
            with patch.object(get_data.yaml, 'load', return_value=data, create=True):
                with patch('get_data.load_history', return_value=history):
                    with patch(
                        'get_data.repo_sources',
                        side_effect=[[failed_source], [working_source]],
                    ):
                        with patch(
                            'get_data.fetch_repo_stats',
                            side_effect=[
                                RuntimeError('API unavailable'),
                                working_stats,
                            ],
                        ):
                            with patch('get_data.send_alert') as send_alert:
                                with patch('get_data.atomic_write_many_text') as atomic_write:
                                    result = get_data.main()

        self.assertEqual(result, 0)
        self.assertEqual(data['example']['stars'], 42)
        self.assertIn('API unavailable', data['example']['update_warning'])
        self.assertIn('update_warning_at', data['example'])
        self.assertEqual(data['working']['stars'], 20)
        self.assertNotIn('update_warning', data['working'])
        send_alert.assert_called_once()
        atomic_write.assert_called_once()
        self.assertEqual(history['dates'], [str(get_data.date.today())])
        self.assertEqual(
            history['projects']['working']['stars'][-1][1],
            20,
        )

    def test_repository_identity_change_is_flagged_and_frozen(self):
        history = empty_history()
        history['dates'] = ['2026-07-29']
        history['projects'] = {
            'example': {
                'created': [['2026-07-29', '2020‑01‑01']],
            },
        }
        notify = Mock()

        safe = get_data.check_repository_changes(
            history,
            'example',
            '2026-07-30',
            {
                'created': '2021‑01‑01',
                'license': 'MIT',
                'last_commit': '2026‑07‑30',
            },
            {'github': 100},
            notify,
        )

        self.assertFalse(safe)
        self.assertEqual(notify.call_args.args[0], 'Repository identity changed')

    def test_malformed_known_repository_url_is_not_silently_ignored(self):
        with self.assertRaisesRegex(RuntimeError, 'malformed repository'):
            get_data.repo_sources({'source': 'https://github.com/only-owner'})


if __name__ == '__main__':
    unittest.main()
