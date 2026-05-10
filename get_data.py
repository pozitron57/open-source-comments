#! /usr/bin/env python
#coding=utf8

import json
import os
import re
import sys
from datetime import date, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

import ruamel.yaml

from history_store import append_snapshot, field_on_or_before, load_history, save_history

sys.stdout.reconfigure(encoding='utf-8')


GH_CREDENTIALS_PATH = '/home/slisakov/gh_credentials'
STARS_DIFF_DAYS = 14


yaml = ruamel.yaml.YAML()
yaml.indent(mapping=4, sequence=4, offset=2)
yaml.preserve_quotes = True


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


def github_source(data_item):
    sources = data_item.get('source')
    if not isinstance(sources, list):
        sources = [sources]

    for source in sources:
        api_url = github_repo_api_url(source)
        if api_url:
            return api_url
    return None


def github_token():
    if not os.path.exists(GH_CREDENTIALS_PATH):
        return None

    with open(GH_CREDENTIALS_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                return parts[1]
            if len(parts) == 1:
                return parts[0]
    return None


def fetch_json(url, token):
    headers = {
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'open-source-comments-updater',
    }
    if token:
        headers['Authorization'] = 'token {}'.format(token)

    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode('utf-8'))
    except HTTPError as error:
        body = error.read().decode('utf-8', errors='replace')
        raise RuntimeError('GitHub API returned {} for {}: {}'.format(error.code, url, body))
    except URLError as error:
        raise RuntimeError('Could not fetch {}: {}'.format(url, error.reason))


def github_date(value):
    if not value:
        return 'undefined'
    return value[:10].replace('-', '‑')


def repo_license(api_data):
    license_data = api_data.get('license')
    if not license_data:
        return 'undefined'

    return license_data.get('spdx_id') or license_data.get('name') or 'undefined'


def commit_date(api_url, default_branch, token):
    branch = quote(default_branch or 'master', safe='')
    commit_url = '{}/commits/{}'.format(api_url, branch)
    commit_data = fetch_json(commit_url, token)
    return github_date(commit_data.get('commit', {}).get('committer', {}).get('date'))


def update_index_date(snapshot_date):
    with open('index.html', 'r', encoding='utf-8') as f:
        text = f.read()

    text = re.sub('Last updated:.*', 'Last updated: {} <br>'.format(snapshot_date), text)

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(text)


def main():
    snapshot_date = str(date.today())
    comparison_date = str(date.today() - timedelta(days=STARS_DIFF_DAYS))
    token = github_token()

    with open('data.yaml', 'r', encoding='utf-8') as f:
        data = yaml.load(f)

    history = load_history()
    snapshot = {}

    print('{:<27}{:<8}{:<6}{:<7}{}'.format('Name', 'Stars', 'Δ★', 'I+PR', 'Created'))
    for name, item in data.items():
        if 'pelican_static' in name:
            continue

        api_url = github_source(item)
        if not api_url:
            continue

        try:
            api_data = fetch_json(api_url, token)
        except RuntimeError as error:
            print('{}: {}'.format(name, error), file=sys.stderr)
            continue

        stars = int(api_data.get('stargazers_count') or 0)
        created = github_date(api_data.get('created_at'))
        open_issues = int(api_data.get('open_issues') or 0)
        license_name = repo_license(api_data)
        default_branch = api_data.get('default_branch') or 'master'

        last_commit = item.get('last_committed')
        try:
            last_commit = commit_date(api_url, default_branch, token)
        except RuntimeError as error:
            print('{}: {}'.format(name, error), file=sys.stderr)

        old_stars = field_on_or_before(history, name, 'stars', comparison_date)
        if old_stars is not None and int(old_stars) > 0 and stars:
            stars_diff = stars - int(old_stars)
        else:
            stars_diff = '?'

        item['stars'] = stars
        item['stars_dif'] = stars_diff
        item['open_issues'] = open_issues
        item['created'] = created
        item['license'] = license_name
        if last_commit:
            item['last_committed'] = last_commit

        snapshot[name] = {
            'stars': stars,
            'created': created,
            'open_issues': open_issues,
            'license': license_name,
        }
        if last_commit:
            snapshot[name]['last_commit'] = last_commit

        print('{:<27}{:<8}{:<6}{:<7}{}'.format(name, stars, stars_diff, open_issues, created))

    append_snapshot(history, snapshot_date, snapshot)
    save_history(history)

    with open('data.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(data, stream=f)

    update_index_date(snapshot_date)


if __name__ == '__main__':
    main()
