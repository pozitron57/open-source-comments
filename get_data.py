#! /usr/bin/env python
#coding=utf8

import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from io import StringIO
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

import ruamel.yaml

from alerts import AlertDeliveryError, send_alert
from atomic_io import atomic_write_many_text
from history_store import (
    append_snapshot,
    field_on_or_before,
    load_history,
    serialize_history,
)

sys.stdout.reconfigure(encoding='utf-8')


GH_CREDENTIALS_PATH = '/home/slisakov/gh_credentials'
GITLAB_CREDENTIALS_PATH = '/home/slisakov/gitlab_credentials'
STARS_DIFF_DAYS = 30
STAR_DROP_WARNING_THRESHOLD = 20
FETCH_ATTEMPTS = 3
RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
MAX_API_RESPONSE_BYTES = 5 * 1024 * 1024


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
            if key in seen:
                raise RuntimeError('duplicate repository source: {}'.format(source))
            sources.append({'provider': 'github', 'api_url': github_api_url, 'url': str(source)})
            seen.add(key)
            continue

        gitlab_api_url = gitlab_repo_api_url(source)
        if gitlab_api_url:
            key = ('gitlab', gitlab_api_url)
            if key in seen:
                raise RuntimeError('duplicate repository source: {}'.format(source))
            sources.append({'provider': 'gitlab', 'api_url': gitlab_api_url, 'url': str(source)})
            seen.add(key)
            continue

        parsed = urlparse(str(source))
        if parsed.netloc.lower() in (
            'github.com',
            'www.github.com',
            'gitlab.com',
            'www.gitlab.com',
        ):
            raise RuntimeError('malformed repository source URL: {}'.format(source))

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


def retry_delay(headers, attempt):
    retry_after = headers.get('Retry-After') if headers else None
    if retry_after and str(retry_after).isdigit():
        return min(max(int(retry_after), 1), 60)
    return 2 ** (attempt - 1)


def fetch_json(url, headers, on_anomaly=None):
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=60) as response:
                raw_body = response.read(MAX_API_RESPONSE_BYTES + 1)
                if len(raw_body) > MAX_API_RESPONSE_BYTES:
                    raise RuntimeError(
                        'API response for {} exceeds {} bytes'.format(
                            url,
                            MAX_API_RESPONSE_BYTES,
                        )
                    )
                body = raw_body.decode('utf-8')
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
            error_headers = error.headers
        except (URLError, TimeoutError) as error:
            message = 'Could not fetch {}: {}'.format(
                url,
                getattr(error, 'reason', error),
            )
            if attempt == FETCH_ATTEMPTS:
                raise RuntimeError(message)
            error_headers = getattr(error, 'headers', None)

        retry_message = 'Temporary API error; retrying {}/{}: {}'.format(
            attempt + 1,
            FETCH_ATTEMPTS,
            message,
        )
        print(retry_message, file=sys.stderr)
        if on_anomaly:
            on_anomaly('API request required a retry', retry_message)
        time.sleep(retry_delay(error_headers, attempt))


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


def require_nonnegative_int(api_data, field, url):
    value = api_data.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError(
            'API field {} for {} must be a non-negative integer, got {!r}'.format(
                field,
                url,
                value,
            )
        )
    return value


def require_url(value, field, url):
    parsed = urlparse(str(value))
    if parsed.scheme != 'https' or not parsed.netloc:
        raise RuntimeError(
            'API field {} for {} is not a valid HTTPS URL: {!r}'.format(
                field,
                url,
                value,
            )
        )
    return str(value)


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
    raw_date = str(value)[:10]
    try:
        datetime.strptime(raw_date, '%Y-%m-%d')
    except ValueError:
        raise RuntimeError('API returned an invalid date: {!r}'.format(value))
    return raw_date.replace('-', '‑')


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


def github_commit_date(api_url, default_branch, token, on_anomaly=None):
    branch = quote(default_branch or 'master', safe='')
    commit_url = '{}/commits/{}'.format(api_url, branch)
    commit_data, _headers, _final_url = fetch_json(
        commit_url,
        github_headers(token),
        on_anomaly=on_anomaly,
    )
    commit_date = commit_data.get('commit', {}).get('committer', {}).get('date')
    if not commit_date:
        raise RuntimeError('API response for {} has no commit date'.format(commit_url))
    return api_date(commit_date)


def gitlab_commit_date(api_url, default_branch, token, on_anomaly=None):
    params = urlencode({'per_page': 1, 'ref_name': default_branch or 'master'})
    commit_url = '{}/repository/commits?{}'.format(api_url, params)
    commit_data, _headers, _final_url = fetch_json(
        commit_url,
        gitlab_headers(token),
        on_anomaly=on_anomaly,
    )
    if not commit_data:
        raise RuntimeError('API response for {} contains no commits'.format(commit_url))
    return api_date(commit_data[0].get('committed_date') or commit_data[0].get('created_at'))


def gitlab_open_issue_count(api_url, token, on_anomaly=None):
    url = '{}/issues_statistics?scope=all'.format(api_url)
    data, _headers, _final_url = fetch_json(
        url,
        gitlab_headers(token),
        on_anomaly=on_anomaly,
    )
    value = data.get('statistics', {}).get('counts', {}).get('opened')
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError(
            'API response for {} has invalid opened issue count: {!r}'.format(url, value)
        )
    return value


def gitlab_open_merge_request_count(api_url, token, on_anomaly=None):
    params = urlencode({'state': 'opened', 'per_page': 1})
    url = '{}/merge_requests?{}'.format(api_url, params)
    _data, headers, _final_url = fetch_json(
        url,
        gitlab_headers(token),
        on_anomaly=on_anomaly,
    )
    total = headers.get('X-Total')
    if total is None or not str(total).isdigit():
        raise RuntimeError('API response for {} has invalid X-Total header: {!r}'.format(url, total))
    return int(total)


def fetch_github_repo(source, token, item, on_anomaly=None):
    api_data, _headers, final_url = fetch_json(
        source['api_url'],
        github_headers(token),
        on_anomaly=on_anomaly,
    )
    require_api_fields(
        api_data,
        ('stargazers_count', 'created_at', 'open_issues_count', 'html_url'),
        source['api_url'],
    )
    stars = require_nonnegative_int(api_data, 'stargazers_count', source['api_url'])
    open_issues = require_nonnegative_int(api_data, 'open_issues_count', source['api_url'])
    canonical_url = require_url(api_data['html_url'], 'html_url', source['api_url'])
    canonical_api_url = github_repo_api_url(canonical_url)
    if not canonical_api_url:
        raise RuntimeError(
            'GitHub returned an invalid canonical repository URL for {}: {}'.format(
                source['api_url'],
                canonical_url,
            )
        )

    api_url = source['api_url']
    if (
        final_url.rstrip('/') != source['api_url'].rstrip('/')
        or canonical_api_url.rstrip('/') != source['api_url'].rstrip('/')
    ):
        api_url = canonical_api_url
        if replace_source_url(item, source['url'], canonical_url):
            move_notice = 'Repository moved: {} -> {}'.format(source['url'], canonical_url)
            print(move_notice)
            if on_anomaly:
                on_anomaly('Repository moved permanently', move_notice)

    default_branch = api_data.get('default_branch') or 'master'
    if not isinstance(default_branch, str):
        raise RuntimeError('GitHub returned an invalid default branch for {}'.format(api_url))
    last_commit = github_commit_date(api_url, default_branch, token, on_anomaly=on_anomaly)

    return {
        'provider': 'github',
        'stars': stars,
        'created': api_date(api_data.get('created_at')),
        'open_issues': open_issues,
        'license': github_license(api_data, item),
        'last_commit': last_commit,
    }


def fetch_gitlab_repo(source, token, item, on_anomaly=None):
    api_data, _headers, _final_url = fetch_json(
        source['api_url'],
        gitlab_headers(token),
        on_anomaly=on_anomaly,
    )
    require_api_fields(
        api_data,
        ('star_count', 'created_at'),
        source['api_url'],
    )
    stars = require_nonnegative_int(api_data, 'star_count', source['api_url'])
    default_branch = api_data.get('default_branch') or 'master'
    if not isinstance(default_branch, str):
        raise RuntimeError('GitLab returned an invalid default branch for {}'.format(source['api_url']))

    open_issues = gitlab_open_issue_count(source['api_url'], token, on_anomaly=on_anomaly)
    open_issues += gitlab_open_merge_request_count(
        source['api_url'],
        token,
        on_anomaly=on_anomaly,
    )
    last_commit = gitlab_commit_date(
        source['api_url'],
        default_branch,
        token,
        on_anomaly=on_anomaly,
    )

    return {
        'provider': 'gitlab',
        'stars': stars,
        'created': api_date(api_data.get('created_at')),
        'open_issues': open_issues,
        'license': gitlab_license(api_data, item),
        'last_commit': last_commit,
    }


def fetch_repo_stats(source, tokens, item, on_anomaly=None):
    if source['provider'] == 'github':
        return fetch_github_repo(
            source,
            tokens.get('github'),
            item,
            on_anomaly=on_anomaly,
        )
    if source['provider'] == 'gitlab':
        return fetch_gitlab_repo(
            source,
            tokens.get('gitlab'),
            item,
            on_anomaly=on_anomaly,
        )
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


class RepositoryEvents:
    def __init__(self, name):
        self.name = name
        self.messages = []
        self.emitted = set()

    def callback(self, source_url):
        def notify(kind, detail):
            self.notify(kind, detail, source_url)
        return notify

    def notify(self, kind, detail, source_url):
        message = '{}: {}'.format(kind, detail)
        if message not in self.messages:
            self.messages.append(message[:1000])
        if kind in self.emitted:
            return
        self.emitted.add(kind)

        try:
            send_alert(
                'open-source-comments repository warning: {}'.format(self.name),
                'Repository: {}\nSource: {}\nEvent: {}\n\n{}'.format(
                    self.name,
                    source_url,
                    kind,
                    detail,
                ),
            )
        except AlertDeliveryError as error:
            delivery_message = 'Alert delivery failed: {}'.format(error)
            if delivery_message not in self.messages:
                self.messages.append(delivery_message[:1000])
            print('ERROR: {}'.format(delivery_message), file=sys.stderr)

    def tooltip(self):
        return ' | '.join(self.messages)[:3000]


def set_update_warning(item, events, snapshot_date):
    if events.messages:
        item['update_warning'] = events.tooltip()
        item['update_warning_at'] = snapshot_date
    else:
        item.pop('update_warning', None)
        item.pop('update_warning_at', None)


def comparable_date(value):
    return str(value).replace('‑', '-') if value else None


def check_repository_changes(history, name, snapshot_date, primary_stats, provider_stars, notify):
    safe_to_update = True
    old_created = field_on_or_before(history, name, 'created', snapshot_date)
    if (
        old_created not in (None, 'undefined')
        and primary_stats['created'] not in (None, 'undefined')
        and old_created != primary_stats['created']
    ):
        message = 'creation date changed from {} to {}'.format(
            old_created,
            primary_stats['created'],
        )
        notify('Repository identity changed', message)
        safe_to_update = False

    old_license = field_on_or_before(history, name, 'license', snapshot_date)
    if (
        old_license not in (None, 'undefined', 'NOASSERTION')
        and primary_stats['license'] not in (None, 'undefined', 'NOASSERTION')
        and old_license != primary_stats['license']
    ):
        notify(
            'Repository license changed',
            'license changed from {} to {}'.format(old_license, primary_stats['license']),
        )

    old_commit = field_on_or_before(history, name, 'last_commit', snapshot_date)
    if (
        old_commit
        and primary_stats['last_commit']
        and comparable_date(primary_stats['last_commit']) < comparable_date(old_commit)
    ):
        notify(
            'Latest commit date moved backwards',
            'latest commit changed from {} to {}'.format(
                old_commit,
                primary_stats['last_commit'],
            ),
        )

    for provider, current_stars in provider_stars.items():
        provider_field = 'stars_{}'.format(provider)
        old_stars = field_on_or_before(history, name, provider_field, snapshot_date)
        if old_stars is None and provider == 'github':
            old_stars = field_on_or_before(history, name, 'stars', snapshot_date)
        if old_stars is None:
            continue

        old_stars = int(old_stars)
        if old_stars - current_stars >= STAR_DROP_WARNING_THRESHOLD:
            notify(
                '{} star count decreased'.format(provider),
                '{} stars decreased from {} to {}'.format(
                    provider,
                    old_stars,
                    current_stars,
                ),
            )
        elif (
            old_stars > 0
            and current_stars - old_stars >= 1000
            and current_stars >= old_stars * 2
        ):
            notify(
                '{} star count jumped unexpectedly'.format(provider),
                '{} stars jumped from {} to {}'.format(
                    provider,
                    old_stars,
                    current_stars,
                ),
            )
    return safe_to_update


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
    repository_issues = []

    print('{:<27}{:<8}{:<6}{:<7}{}'.format('Name', 'Stars', 'Δ★', 'I+PR', 'Created'))
    for name, item in data.items():
        if 'pelican_static' in name:
            continue

        events = RepositoryEvents(name)
        try:
            sources = repo_sources(item)
        except Exception as error:
            message = '{}: invalid repository configuration: {}'.format(name, error)
            repository_issues.append(message)
            events.notify(
                'Invalid repository configuration',
                message,
                item.get('source'),
            )
            set_update_warning(item, events, snapshot_date)
            print('ERROR: {}'.format(message), file=sys.stderr)
            continue
        if not sources:
            set_update_warning(item, events, snapshot_date)
            continue

        stats = []
        for source in sources:
            notify = events.callback(source['url'])
            try:
                repo_stats = fetch_repo_stats(
                    source,
                    tokens,
                    item,
                    on_anomaly=notify,
                )
                stats.append(repo_stats)
            except Exception as error:
                message = '{} ({}): {}'.format(name, source['url'], error)
                repository_issues.append(message)
                notify('Repository update failed', message)
                print('ERROR: {}'.format(message), file=sys.stderr)

        if len(stats) != len(sources):
            set_update_warning(item, events, snapshot_date)
            continue

        try:
            primary_stats = primary_repo_stats(stats)
            (
                stars,
                stars_extra,
                stars_provider,
                stars_extra_providers,
                stars_total,
                provider_stars,
            ) = display_star_stats(stats)
            stars_dif = stars_diff(history, name, comparison_date, provider_stars)
            safe_to_update = check_repository_changes(
                history,
                name,
                snapshot_date,
                primary_stats,
                provider_stars,
                events.callback(item.get('source')),
            )
        except Exception as error:
            events.notify(
                'Could not process repository result',
                str(error),
                item.get('source'),
            )
            safe_to_update = False
        if not safe_to_update:
            message = '{}: repository result was not trusted; previous values retained'.format(name)
            repository_issues.append(message)
            set_update_warning(item, events, snapshot_date)
            print('ERROR: {}'.format(message), file=sys.stderr)
            continue

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
        set_update_warning(item, events, snapshot_date)

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

    if repository_issues:
        print(
            '\nUpdate completed with {} repository warning(s). '
            'Affected repositories retained their previous trusted values and were marked in the table.'.format(
                len(repository_issues)
            ),
            file=sys.stderr,
        )

    append_snapshot(history, snapshot_date, snapshot)
    yaml_output = StringIO()
    yaml.dump(data, stream=yaml_output)
    atomic_write_many_text(
        {
            'data.yaml': yaml_output.getvalue(),
            'apigh/history.json': serialize_history(history),
        }
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
