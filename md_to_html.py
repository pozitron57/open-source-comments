#! /usr/bin/env python
# coding=utf8

import re
import os
from datetime import date

import mistune
from mistune import create_markdown

from atomic_io import atomic_write_text


SHARE_HEADING = '## Share your experience'
PREAMBLE_START = '<div class="preamble">'
PREAMBLE_END = '</div>'
COMMENTS_START = '<div class="isso-comments">'
THREAD_MARKER = '<section id="isso-thread">'

markdown = create_markdown(renderer=mistune.HTMLRenderer(escape=False))


def replace_once(text, pattern, replacement, description, flags=0):
    updated, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError('could not locate exactly one {}'.format(description))
    return updated


def normalize_rendered_html(value):
    return re.sub(
        r'<p>(<img\b[^>]*?/?>)</p>',
        r'\1',
        value,
        flags=re.S,
    )


def render_index(markdown_text, html_text, snapshot_date=None):
    if markdown_text.count(SHARE_HEADING) != 1:
        raise RuntimeError('index.md must contain exactly one {!r}'.format(SHARE_HEADING))

    preamble_markdown, share_body = markdown_text.split(SHARE_HEADING, 1)
    preamble = normalize_rendered_html(markdown(preamble_markdown))
    share = normalize_rendered_html(markdown('{}{}'.format(SHARE_HEADING, share_body)))
    if not preamble.strip() or not share.strip():
        raise RuntimeError('rendered markdown section is empty')

    html_text = replace_once(
        html_text,
        r'{}.*?{}'.format(re.escape(PREAMBLE_START), re.escape(PREAMBLE_END)),
        '{}{}{}'.format(PREAMBLE_START, preamble, PREAMBLE_END),
        'preamble section',
        flags=re.S,
    )
    html_text = replace_once(
        html_text,
        r'{}.*?{}'.format(re.escape(COMMENTS_START), re.escape(THREAD_MARKER)),
        '{}{}{}'.format(COMMENTS_START, share, THREAD_MARKER),
        'comments section',
        flags=re.S,
    )
    html_text = replace_once(
        html_text,
        r'Last updated:[^\n<]*(?:<br>)?',
        'Last updated: {} <br>'.format(snapshot_date or date.today()),
        'last-updated footer',
    )

    required_markers = (
        '<table id="results"',
        THREAD_MARKER,
        'stars-v-date.svg',
        'data.js',
    )
    missing = [marker for marker in required_markers if marker not in html_text]
    if missing:
        raise RuntimeError('rendered index.html is missing: {}'.format(', '.join(missing)))
    return html_text


def main():
    with open('index.md', 'r', encoding='utf-8') as source:
        markdown_text = source.read()
    with open('index.html', 'r', encoding='utf-8') as source:
        html_text = source.read()

    snapshot_date = os.environ.get('OSC_EXPECT_SNAPSHOT_DATE') or date.today()
    atomic_write_text(
        'index.html',
        render_index(markdown_text, html_text, snapshot_date=snapshot_date),
    )
    print('index.html has been updated')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
