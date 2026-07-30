import importlib.util
import json
import sys
import types
import unittest
from unittest.mock import mock_open, patch
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

    ruamel_yaml.YAML = DummyYAML
    ruamel.yaml = ruamel_yaml
    sys.modules['ruamel'] = ruamel
    sys.modules['ruamel.yaml'] = ruamel_yaml


import get_data


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

    def read(self):
        return json.dumps(self.data).encode('utf-8')


class GetDataTests(unittest.TestCase):
    def test_github_redirect_updates_source_and_uses_canonical_api_url(self):
        old_url = 'https://github.com/imaegoo/twikoo'
        old_api_url = 'https://api.github.com/repos/imaegoo/twikoo'
        canonical_url = 'https://github.com/twikoojs/twikoo'
        canonical_api_url = 'https://api.github.com/repos/twikoojs/twikoo'
        source = {
            'provider': 'github',
            'api_url': old_api_url,
            'url': old_url,
        }
        item = {
            'source': old_url,
            'license': 'MIT',
        }
        repository_data = {
            'stargazers_count': 2200,
            'created_at': '2020-05-24T00:00:00Z',
            'open_issues_count': 10,
            'html_url': canonical_url,
            'default_branch': 'main',
            'license': {'spdx_id': 'MIT'},
        }
        commit_data = {
            'commit': {
                'committer': {
                    'date': '2026-07-30T00:00:00Z',
                },
            },
        }

        with patch(
            'get_data.fetch_json',
            side_effect=[
                (repository_data, {}, 'https://api.github.com/repositories/266566637'),
                (commit_data, {}, canonical_api_url + '/commits/main'),
            ],
        ) as fetch:
            stats = get_data.fetch_github_repo(source, None, item)

        self.assertEqual(item['source'], canonical_url)
        self.assertEqual(stats['stars'], 2200)
        self.assertEqual(
            stats['move_notice'],
            'Repository moved: {} -> {}'.format(old_url, canonical_url),
        )
        self.assertEqual(fetch.call_args_list[1].args[0], canonical_api_url + '/commits/main')

    def test_move_notices_are_written_for_the_updater(self):
        notice_file = '/tmp/open-source-comments-test-moves.txt'
        notices = [
            'Repository moved: https://github.com/old/repo -> https://github.com/new/repo',
        ]

        with patch.dict(
            'os.environ',
            {get_data.MOVE_NOTICE_FILE_ENV: notice_file},
        ):
            with patch('builtins.open', mock_open()) as output:
                get_data.write_move_notices(notices)

        output.assert_called_once_with(notice_file, 'w', encoding='utf-8')
        handle = output()
        handle.write.assert_any_call(notices[0])
        handle.write.assert_any_call('\n')

    def test_incomplete_redirect_response_is_an_error_not_zero_stars(self):
        source = {
            'provider': 'github',
            'api_url': 'https://api.github.com/repos/imaegoo/twikoo',
            'url': 'https://github.com/imaegoo/twikoo',
        }
        item = {
            'source': source['url'],
            'license': 'MIT',
        }

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

    def test_temporary_network_error_is_retried(self):
        response = FakeResponse(
            {'stargazers_count': 1},
            'https://api.github.com/repos/example/repository',
        )

        with patch('get_data.urlopen', side_effect=[URLError('temporary'), response]) as fetch:
            with patch('get_data.time.sleep') as sleep:
                data, _headers, final_url = get_data.fetch_json(
                    'https://api.github.com/repos/example/repository',
                    {},
                )

        self.assertEqual(data['stargazers_count'], 1)
        self.assertEqual(final_url, response.final_url)
        self.assertEqual(fetch.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_failed_repository_aborts_without_saving_partial_data(self):
        source = {
            'provider': 'github',
            'api_url': 'https://api.github.com/repos/example/repository',
            'url': 'https://github.com/example/repository',
        }
        data = {
            'example': {
                'source': source['url'],
            },
        }

        with patch('builtins.open', mock_open()):
            with patch.object(get_data.yaml, 'load', return_value=data, create=True):
                with patch('get_data.load_history', return_value={'projects': {}}):
                    with patch('get_data.repo_sources', return_value=[source]):
                        with patch(
                            'get_data.fetch_repo_stats',
                            side_effect=RuntimeError('API unavailable'),
                        ):
                            with patch('get_data.append_snapshot') as append_snapshot:
                                with patch('get_data.save_history') as save_history:
                                    with patch.object(get_data.yaml, 'dump', create=True) as dump:
                                        with patch('get_data.update_index_date') as update_index_date:
                                            result = get_data.main()

        self.assertEqual(result, 1)
        append_snapshot.assert_not_called()
        save_history.assert_not_called()
        dump.assert_not_called()
        update_index_date.assert_not_called()


if __name__ == '__main__':
    unittest.main()
