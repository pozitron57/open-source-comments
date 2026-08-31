#! /usr/bin/env python
#coding=utf8

'''
Convert data.yaml to data.js
'''

import json
import re
from html import escape

import yaml
from markdown import markdown

from atomic_io import atomic_write_text

fields = [
    'stars',
    'stars_dif',
    'name',
    'source',
    'open_issues',
    'demo',
    'js_kB',
    'css_kB',
    'language',
    'db',
    'markdown_support',
    'social_network_login',
    'anonymous_comments',
    'edit',
    'vote',
    'moderation',
    'nested_comments',
    'mail_notification',
    'antispam',
    'bad_words_list',
    'use_cookies',
    'avatar',
    'provided_hosting',
    'collapse_comments',
    'sort',
    'docker',
    'paging',
    'rate_limit',
    'hide_long_threads',
    'import_from_wordpress',
    'import_from_disqus',
    'english_documentation',
    'dependency',
    'webmention',
    'display_images',
    'license',
    'rss',
    'static',
    'created',
   #'updated', # What's this date?
    'last_committed',
   #'unmaintained', #or Maintaned?
    'description',
]

fields_dic={
    'stars':                 'Stars',
    'stars_dif':             'Stars&nbsp;in last&nbsp;month',
    'name':                  'Name',
    'source':                'Source code',
    'demo':                  'Demo & examples',
    'js_kB':                 'js, kB',
    'css_kB':                'css, kB',
    'language':              'Language',
    'db':                    'Database',
    'mail_notification':     'Mail notification',
    'edit':                  'User can edit',
    'vote':                  'User can vote',
    'antispam':              'Antispam',
    'bad_words_list':        'Bad words list',
    'use_cookies':           'Uses cookies',
    'avatar':                'Avatar',
    'markdown_support':      'Markdown support',
    'moderation':            'Moderation',
    'dependency':            'Dependencies',
    'webmention':            'Supports Webmention',
    'nested_comments':       'Nested comments',
    'provided_hosting':      'Can host for you',
    'collapse_comments':     'Collapse comments',
    'sort':                  'Configurable order',
    'rate_limit':            'Comment rate limit',
    'docker':                'Docker container',
    'paging':                'Paging',
    'hide_long_threads':     'Hide long threads',
    'anonymous_comments':    'Anonymous comments',
    'social_network_login':  'Social network login',
    'import_from_wordpress': 'Import from wordpress',
    'import_from_disqus':    'Import from disqus',
    'english_documentation': 'English documentation',
    'rss':                   'RSS',
    'display_images':        'Display images',
    'static':                'Static',
    'description':           'Description',
    'updated':               'Updated (y‑m‑d)',
    'last_committed':        'Updated (y‑m‑d)',
    'created':               'Created (y‑m‑d)',
    'license':               'License',
    'open_issues':           'Open issues + PR',
    'unmaintained':          'Unmaintained',
}

def source_urlify(x):
    values = x if isinstance(x, list) else [x]
    links = []
    for index, value in enumerate(values):
        value = str(value)
        safe_value = escape(value, quote=True)
        if 'github.com' in value:
            links.append('<a href="{}">github</a>'.format(safe_value))
        elif 'gitlab.com' in value:
            links.append('<a href="{}">gitlab</a>'.format(safe_value))
        elif re.match(r'^https?://', value):
            label = '[{}]'.format(index + 1) if isinstance(x, list) else 'link'
            links.append('<a href="{}">{}</a>'.format(safe_value, label))
        else:
            links.append(markdown_inline(value))
    return ', '.join(links)


def markdown_inline(value):
    rendered = markdown(str(value))
    rendered = re.sub(r'^<p>', '', rendered)
    rendered = re.sub(r'</p>\s*$', '', rendered)
    return rendered

def provider_title(provider):
    labels = {
        'github': 'GitHub',
        'gitlab': 'GitLab',
    }
    providers = [labels.get(part, part) for part in str(provider).split(',') if part]
    if len(providers) == 1:
        return providers[0]
    if providers:
        return 'other repositories'
    return 'other repository'

def stars_urlify(item):
    stars = item.get('stars', '?')
    extra = item.get('stars_extra')
    warning = item.get('update_warning')
    titles = []
    if extra not in (None, '', 0, '0'):
        titles.append(
            '+{} stars on {}'.format(
                extra,
                provider_title(item.get('stars_extra_provider')),
            )
        )
    if warning:
        warning_date = item.get('update_warning_at', 'unknown date')
        titles.append('Update warning on {}: {}'.format(warning_date, warning))

    if not titles:
        return urlify(stars)

    return '<span class="stars-with-extra" title="{}">{}<span class="stars-extra"></span></span>'.format(
        escape(' | '.join(titles), quote=True),
        escape(str(stars)),
    )


def urlify(x):
    values = x if isinstance(x, list) else [x]
    rendered = []
    for index, value in enumerate(values):
        value = str(value)
        if re.match(r'^https?://', value):
            label = '[{}]'.format(index + 1) if isinstance(x, list) else 'demo'
            rendered.append(
                '<a href="{}">{}</a>'.format(escape(value, quote=True), label)
            )
        else:
            rendered.append(markdown_inline(value))
    return ', '.join(rendered)


def generate_data_js(data):
    if not isinstance(data, dict):
        raise RuntimeError('data.yaml root must be a mapping')

    rows = []
    for name, item in data.items():
        if not isinstance(item, dict):
            raise RuntimeError('data.yaml entry {!r} must be a mapping'.format(name))
        row = []
        for field in fields:
            if field == 'stars':
                row.append(stars_urlify(item))
            elif field == 'source':
                row.append(source_urlify(item[field]) if field in item else '?')
            elif field in item:
                row.append(urlify(item[field]))
            else:
                row.append('?')
        rows.append(row)

    output = ['var osc_data = [']
    output.extend(
        '{}{}'.format(
            json.dumps(row, ensure_ascii=False),
            ',' if index < len(rows) - 1 else '',
        )
        for index, row in enumerate(rows)
    )
    output.append('];')
    output.append('var cols = {};'.format(
        json.dumps(
            [{'title': fields_dic[field]} for field in fields],
            ensure_ascii=False,
        )
    ))
    output.append('var col_keys = {};'.format(json.dumps(fields, ensure_ascii=False)))
    return '\n'.join(output) + '\n'


def main():
    with open('data.yaml', 'r', encoding='utf-8') as source:
        data = yaml.load(source, Loader=yaml.SafeLoader)
    atomic_write_text('data.js', generate_data_js(data))
    print('data.js has been updated')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
