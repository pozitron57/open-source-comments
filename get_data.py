#! /usr/bin/env python
#coding=utf8

import json
import os
import re
import sys
import time
from datetime import date, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

import ruamel.yaml

from history_store import append_snapshot, field_on_or_before, load_history, save_history

sys.stdout.reconfigure(encoding='utf-8')


GH_CREDENTIALS_PATH = '/home/slisakov/gh_credentials'
GITLAB_CREDENTIALS_PATH = '/home/slisakov/gitlab_credentials'
STARS_DIFF_DAYS = 30
FETCH_ATTEMPTS = 3
RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
MOVE_NOTICE_FILE_ENV = 'OSC_MOVE_NOTICE_FILE'


yaml = ruamel.yaml.YAML()
yaml.indent(mapping=4, sequence=4, offset=2)
yaml.preserve_quotes = True


def sources_list(data_item):
    sources = data_item.get('source')
    if not isinstance(sources, list):
        sources = [sources]
    return sources


def github_repo_api_url(source):
    parsed = urlparse(str(source))
    if parsed.netloc not in ('github.com', 'www.github.com'):
        return None

    parts = [part for part in parsed.path.split('/') if part]
    if len(parts) < 2:
        return None

    owner = parts[0]
    repo = re.sub(r'\.git$', '', parts[1])
    return 'https://api.github.com/repos/{}/{}'.format(owner, repo)


def gitlab_repo_api_url(source):
    parsed = urlparse(str(source))
    if parsed.netloc not in ('gitlab.com', 'www.gitlab.com'):
        return None

    parts = [part for part in parsed.path.split('/') if part]
    if '-' in parts:
        parts = parts[:parts.index('-')]
    if len(parts) < 2:
        return None

    parts[-1] = re.sub(r'\.git$', '', parts[-1])
    project_path = '/'.join(parts)
    return '{}://{}/api/v4/projects/{}'.format(
        parsed.scheme or 'https',
        parsed.netloc,
        quote(project_path, safe=''),
    )


def repo_sources(data_item):
    sources = []
    seen = set()
    for source in sources_list(data_item):
        github_api_url = github_repo_api_url(source)
        if github_api_url:
            key = ('github', github_api_url)
            if key not in seen:
                sources.append({'provider': 'github', 'api_url': github_api_url, 'url': str(source)})
                seen.add(key)
            continue

        gitlab_api_url = gitlab_repo_api_url(source)
        if gitlab_api_url:
            key = ('gitlab', gitlab_api_url)
            if key not in seen:
                sources.append({'provider': 'gitlab', 'api_url': gitlab_api_url, 'url': str(source)})
                seen.add(key)

    return sources


def token_from_file(path):
    if not os.path.exists(path):
        return None

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                return parts[1]
            if len(parts) == 1:
                return parts[0]
    return None


def fetch_json(url, headers):
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=60) as response:
                body = response.read().decode('utf-8')
                final_url = response.geturl()
                try:
                    return json.loads(body), response.headers, final_url
                except json.JSONDecodeError as error:
                    raise RuntimeError('API returned invalid JSON for {}: {}'.format(url, error))
        except HTTPError as error:
            body = error.read().decode('utf-8', errors='replace')
            message = 'API returned {} for {}: {}'.format(
                error.code,
                url,
                body.replace('\n', ' ')[:500],
            )
            if error.code not in RETRYABLE_HTTP_CODES or attempt == FETCH_ATTEMPTS:
                raise RuntimeError(message)
        except URLError as error:
            message = 'Could not fetch {}: {}'.format(url, error.reason)
            if attempt == FETCH_ATTEMPTS:
                raise RuntimeError(message)

        print(
            'Temporary API error; retrying {}/{}: {}'.format(
                attempt + 1,
                FETCH_ATTEMPTS,
                message,
            ),
            file=sys.stderr,
        )
        time.sleep(2 ** (attempt - 1))


def require_api_fields(api_data, fields, url):
    if not isinstance(api_data, dict):
        raise RuntimeError('API returned an unexpected response for {}'.format(url))

    missing = [field for field in fields if field not in api_data]
    if missing:
        raise RuntimeError(
            'API response for {} is missing required fields: {}'.format(
                url,
                ', '.join(missing),
            )
        )


def replace_source_url(item, old_url, new_url):
    sources = item.get('source')
    if isinstance(sources, list):
        for index, source in enumerate(sources):
            if str(source) == old_url:
                sources[index] = new_url
                return True
        return False

    if str(sources) == old_url:
        item['source'] = new_url
        return True
    return False


def write_move_notices(notices):
    notice_file = os.environ.get(MOVE_NOTICE_FILE_ENV)
    if not notice_file:
        return

    if notices:
        with open(notice_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(notices))
            f.write('\n')
    elif os.path.exists(notice_file):
        os.remove(notice_file)


def github_headers(token):
    headers = {
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'open-source-comments-updater',
    }
    if token:
        headers['Authorization'] = 'token {}'.format(token)
    return headers


def gitlab_headers(token):
    headers = {
        'Accept': 'application/json',
        'User-Agent': 'open-source-comments-updater',
    }
    if token:
        headers['PRIVATE-TOKEN'] = token
    return headers


def api_date(value):
    if not value:
        return 'undefined'
    return value[:10].replace('-', '‑')


def github_license(api_data, item):
    license_data = api_data.get('license')
    if not license_data:
        return item.get('license') or 'undefined'

    return license_data.get('spdx_id') or license_data.get('name') or 'undefined'


def gitlab_license(api_data, item):
    license_data = api_data.get('license')
    if isinstance(license_data, dict):
        return license_data.get('key') or license_data.get('nickname') or license_data.get('name') or 'undefined'
    return item.get('license') or 'undefined'


def github_commit_date(api_url, default_branch, token):
    branch = quote(default_branch or 'master', safe='')
    commit_url = '{}/commits/{}'.format(api_url, branch)
    commit_data, _headers, _final_url = fetch_json(commit_url, github_headers(token))
    commit_date = commit_data.get('commit', {}).get('committer', {}).get('date')
    if not commit_date:
        raise RuntimeError('API response for {} has no commit date'.format(commit_url))
    return api_date(commit_date)


def gitlab_commit_date(api_url, default_branch, token):
    params = urlencode({'per_page': 1, 'ref_name': default_branch or 'master'})
    commit_url = '{}/repository/commits?{}'.format(api_url, params)
    commit_data, _headers, _final_url = fetch_json(commit_url, gitlab_headers(token))
    if not commit_data:
        return None
    return api_date(commit_data[0].get('committed_date') or commit_data[0].get('created_at'))


def gitlab_open_issue_count(api_url, token):
    url = '{}/issues_statistics?scope=all'.format(api_url)
    data, _headers, _final_url = fetch_json(url, gitlab_headers(token))
    return int(data.get('statistics', {}).get('counts', {}).get('opened') or 0)


def gitlab_open_merge_request_count(api_url, token):
    params = urlencode({'state': 'opened', 'per_page': 1})
    url = '{}/merge_requests?{}'.format(api_url, params)
    _data, headers, _final_url = fetch_json(url, gitlab_headers(token))
    total = headers.get('X-Total')
    return int(total) if total else 0


def fetch_github_repo(source, token, item):
    api_data, _headers, final_url = fetch_json(source['api_url'], github_headers(token))
    require_api_fields(
        api_data,
        ('stargazers_count', 'created_at', 'open_issues_count', 'html_url'),
        source['api_url'],
    )

    api_url = source['api_url']
    move_notice = None
    if final_url.rstrip('/') != source['api_url'].rstrip('/'):
        canonical_url = str(api_data['html_url'])
        canonical_api_url = github_repo_api_url(canonical_url)
        if not canonical_api_url:
            raise RuntimeError(
                'GitHub redirected {} to {}, but returned no valid canonical repository URL'.format(
                    source['api_url'],
                    final_url,
                )
            )
        api_url = canonical_api_url
        if replace_source_url(item, source['url'], canonical_url):
            move_notice = 'Repository moved: {} -> {}'.format(source['url'], canonical_url)
            print(move_notice)

    default_branch = api_data.get('default_branch') or 'master'
    last_commit = github_commit_date(api_url, default_branch, token)

    stats = {
        'provider': 'github',
        'stars': int(api_data['stargazers_count']),
        'created': api_date(api_data.get('created_at')),
        'open_issues': int(api_data['open_issues_count']),
        'license': github_license(api_data, item),
        'last_commit': last_commit,
    }
    if move_notice:
        stats['move_notice'] = move_notice
    return stats


def fetch_gitlab_repo(source, token, item):
    api_data, _headers, _final_url = fetch_json(source['api_url'], gitlab_headers(token))
    require_api_fields(
        api_data,
        ('star_count', 'created_at', 'open_issues_count'),
        source['api_url'],
    )
    default_branch = api_data.get('default_branch') or 'master'

    open_issues = gitlab_open_issue_count(source['api_url'], token)
    open_issues += gitlab_open_merge_request_count(source['api_url'], token)
    last_commit = gitlab_commit_date(source['api_url'], default_branch, token)

    return {
        'provider': 'gitlab',
        'stars': int(api_data['star_count']),
        'created': api_date(api_data.get('created_at')),
        'open_issues': open_issues,
        'license': gitlab_license(api_data, item),
        'last_commit': last_commit,
    }


def fetch_repo_stats(source, tokens, item):
    if source['provider'] == 'github':
        return fetch_github_repo(source, tokens.get('github'), item)
    if source['provider'] == 'gitlab':
        return fetch_gitlab_repo(source, tokens.get('gitlab'), item)
    raise RuntimeError('Unsupported repo provider: {}'.format(source['provider']))


def primary_repo_stats(stats):
    return stats[0]


def display_star_stats(stats):
    winner = max(stats, key=lambda repo: repo['stars'])
    other_repos = [repo for repo in stats if repo is not winner and repo['stars']]
    other_stars = sum(repo['stars'] for repo in other_repos)
    other_providers = [repo['provider'] for repo in other_repos]
    stars_total = sum(repo['stars'] for repo in stats)
    provider_stars = {}
    for repo in stats:
        provider = repo['provider']
        provider_stars[provider] = provider_stars.get(provider, 0) + repo['stars']
    return winner['stars'], other_stars, winner['provider'], other_providers, stars_total, provider_stars


def old_provider_stars(history, name, provider, comparison_date, current_stars, provider_count):
    provider_field = 'stars_{}'.format(provider)
    old_stars = field_on_or_before(history, name, provider_field, comparison_date)
    if old_stars is not None:
        return int(old_stars)

    old_display_stars = field_on_or_before(history, name, 'stars', comparison_date)
    if old_display_stars is not None and (provider == 'github' or provider_count == 1):
        return int(old_display_stars)

    provider_events = history['projects'].get(name, {}).get(provider_field, [])
    if provider_events:
        return int(provider_events[0][1])

    return current_stars


def stars_diff(history, name, comparison_date, provider_stars):
    diff = 0
    for provider, current_stars in provider_stars.items():
        old_stars = old_provider_stars(
            history,
            name,
            provider,
            comparison_date,
            current_stars,
            len(provider_stars),
        )
        if old_stars is None:
            return '?'
        if old_stars == current_stars:
            continue
        if old_stars > 0:
            diff += current_stars - old_stars
            continue
        if current_stars == 0:
            continue
        return '?'

    return diff


def update_index_date(snapshot_date):
    with open('index.html', 'r', encoding='utf-8') as f:
        text = f.read()

    text = re.sub('Last updated:.*', 'Last updated: {} <br>'.format(snapshot_date), text)

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(text)


def main():
    snapshot_date = str(date.today())
    comparison_date = str(date.today() - timedelta(days=STARS_DIFF_DAYS))
    tokens = {
        'github': token_from_file(GH_CREDENTIALS_PATH),
        'gitlab': token_from_file(GITLAB_CREDENTIALS_PATH),
    }

    with open('data.yaml', 'r', encoding='utf-8') as f:
        data = yaml.load(f)

    history = load_history()
    snapshot = {}
    errors = []
    move_notices = []

    print('{:<27}{:<8}{:<6}{:<7}{}'.format('Name', 'Stars', 'Δ★', 'I+PR', 'Created'))
    for name, item in data.items():
        if 'pelican_static' in name:
            continue

        sources = repo_sources(item)
        if not sources:
            continue

        stats = []
        for source in sources:
            try:
                repo_stats = fetch_repo_stats(source, tokens, item)
                move_notice = repo_stats.pop('move_notice', None)
                if move_notice:
                    move_notices.append(move_notice)
                stats.append(repo_stats)
            except RuntimeError as error:
                message = '{} ({}): {}'.format(name, source['url'], error)
                errors.append(message)
                print('ERROR: {}'.format(message), file=sys.stderr)

        if len(stats) != len(sources):
            continue

        primary_stats = primary_repo_stats(stats)
        stars, stars_extra, stars_provider, stars_extra_providers, stars_total, provider_stars = display_star_stats(stats)
        stars_dif = stars_diff(history, name, comparison_date, provider_stars)

        item['stars'] = stars
        item['stars_dif'] = stars_dif
        item['open_issues'] = primary_stats['open_issues']
        item['created'] = primary_stats['created']
        item['license'] = primary_stats['license']
        item['stars_provider'] = stars_provider
        if stars_extra:
            item['stars_extra'] = stars_extra
            item['stars_extra_provider'] = ','.join(stars_extra_providers)
        else:
            item.pop('stars_extra', None)
            item.pop('stars_extra_provider', None)
        if primary_stats['last_commit']:
            item['last_committed'] = primary_stats['last_commit']

        snapshot[name] = {
            'stars': stars,
            'stars_total': stars_total,
            'created': primary_stats['created'],
            'open_issues': primary_stats['open_issues'],
            'license': primary_stats['license'],
        }
        for provider, provider_stars_value in provider_stars.items():
            snapshot[name]['stars_{}'.format(provider)] = provider_stars_value
        if primary_stats['last_commit']:
            snapshot[name]['last_commit'] = primary_stats['last_commit']

        print('{:<27}{:<8}{:<6}{:<7}{}'.format(name, stars, stars_dif, primary_stats['open_issues'], primary_stats['created']))

    if errors:
        write_move_notices([])
        print(
            '\nUpdate aborted: {} repository API request(s) failed. '
            'No data or history files were changed.'.format(len(errors)),
            file=sys.stderr,
        )
        return 1

    append_snapshot(history, snapshot_date, snapshot)
    save_history(history)

    with open('data.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(data, stream=f)

    update_index_date(snapshot_date)
    write_move_notices(move_notices)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
