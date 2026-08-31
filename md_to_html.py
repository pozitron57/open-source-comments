#! /usr/bin/env python
# coding=utf8

'''
Render index.md into index.html.

index.md is split into named sections by `<!--osc:NAME-->` lines; index.html
carries a matching `<!--osc:NAME-->…<!--/osc:NAME-->` slot for each one. The
page structure lives in index.html, all prose lives in index.md, and rendering
is idempotent: running this again replaces the same slots.
'''

import os
import re
from datetime import date

import mistune
from mistune import create_markdown

import yaml

from atomic_io import atomic_write_text
from yaml_2_js import fields

SECTION_PATTERN = re.compile(r'^<!--osc:([a-z-]+)-->\s*$', re.M)

REQUIRED_SECTIONS = ('title', 'lead', 'prose', 'chart-head', 'table-head', 'comments')

markdown = create_markdown(renderer=mistune.HTMLRenderer(escape=False))


def replace_once(text, pattern, replacement, description, flags=0):
    updated, count = re.subn(
        pattern,
        lambda _match: replacement,
        text,
        count=1,
        flags=flags,
    )
    if count != 1:
        raise RuntimeError('could not locate exactly one {}'.format(description))
    return updated


def fill_slot(html_text, name, content):
    '''Fill every slot with this name; a name may legitimately appear twice.'''
    updated, count = re.subn(
        r'<!--osc:{0}-->.*?<!--/osc:{0}-->'.format(re.escape(name)),
        lambda _match: '<!--osc:{0}-->{1}<!--/osc:{0}-->'.format(name, content),
        html_text,
        flags=re.S,
    )
    if count < 1:
        raise RuntimeError('could not locate slot {!r}'.format(name))
    return updated


def split_sections(markdown_text):
    '''Split index.md on its `<!--osc:NAME-->` markers.'''
    parts = SECTION_PATTERN.split(markdown_text)
    if parts[0].strip():
        raise RuntimeError('index.md must start with a section marker')

    sections = {}
    for name, body in zip(parts[1::2], parts[2::2]):
        if name in sections:
            raise RuntimeError('duplicate section marker {!r} in index.md'.format(name))
        sections[name] = body.strip()

    missing = [name for name in REQUIRED_SECTIONS if not sections.get(name)]
    if missing:
        raise RuntimeError('index.md is missing sections: {}'.format(', '.join(missing)))
    return sections


def split_heading(rendered):
    '''Separate a leading <h1>/<h2> from the body that follows it.'''
    match = re.match(r'\s*(<h([12])\b.*?</h\2>)(.*)', rendered, flags=re.S)
    if not match:
        raise RuntimeError('section does not start with a heading')
    return match.group(1).strip(), match.group(3).strip()


def render_prose(markdown_text):
    '''One two-column block per `##` heading: heading rail, body beside it.'''
    blocks = re.split(r'^(?=## )', markdown_text, flags=re.M)
    blocks = [block.strip() for block in blocks if block.strip()]
    if not blocks:
        raise RuntimeError('the prose section has no headings')

    rendered = []
    for block in blocks:
        heading, body = split_heading(markdown(block))
        if not body:
            raise RuntimeError('prose block {!r} has no body'.format(heading))
        rendered.append(
            '<section class="prose-section">{}'
            '<div class="prose-section__body">{}</div></section>'.format(heading, body)
        )
    return ''.join(rendered)


def render_index(markdown_text, html_text, snapshot_date=None, systems=None, attributes=None):
    sections = split_sections(markdown_text)

    title, extra = split_heading(markdown(sections['title']))
    if extra:
        raise RuntimeError('the title section must contain only a heading')

    chart_heading, chart_caption = split_heading(markdown(sections['chart-head']))
    chart_caption = re.sub(r'^<p>(.*)</p>$', r'\1', chart_caption.strip(), flags=re.S)
    table_heading, _ = split_heading(markdown(sections['table-head']))
    comments_heading, comments_body = split_heading(markdown(sections['comments']))

    html_text = fill_slot(html_text, 'title', title)
    html_text = fill_slot(html_text, 'lead', markdown(sections['lead']).strip())
    html_text = fill_slot(html_text, 'prose', render_prose(sections['prose']))
    html_text = fill_slot(
        html_text,
        'chart-head',
        '{}<p class="section__caption">{}</p>'.format(chart_heading, chart_caption),
    )
    html_text = fill_slot(html_text, 'table-head', table_heading)
    html_text = fill_slot(
        html_text,
        'comments',
        '{}<div class="comments__lead">{}</div>'.format(comments_heading, comments_body),
    )

    # Counts are computed, never hard-coded, so they cannot drift from the data.
    html_text = fill_slot(html_text, 'systems', str(systems))
    html_text = fill_slot(html_text, 'attributes', str(attributes))
    html_text = fill_slot(html_text, 'all-count', str(attributes))
    # An attribute value cannot carry a marker comment, so rewrite it in place.
    html_text = replace_once(
        html_text,
        r'placeholder="Search \d+ systems"',
        'placeholder="Search {} systems"'.format(systems),
        'search placeholder',
    )

    stamp = str(snapshot_date or date.today())
    html_text = fill_slot(html_text, 'updated', stamp)
    html_text = replace_once(
        html_text,
        r'Last updated:[^\n<]*',
        'Last updated: {}'.format(stamp),
        'last-updated footer',
    )

    required_markers = (
        '<table id="results"',
        '<section id="isso-thread">',
        'stars-v-date.svg',
        'data.js',
        'star-history.js',
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
    with open('data.yaml', 'r', encoding='utf-8') as source:
        data = yaml.load(source, Loader=yaml.SafeLoader)

    snapshot_date = os.environ.get('OSC_EXPECT_SNAPSHOT_DATE') or date.today()
    atomic_write_text(
        'index.html',
        render_index(
            markdown_text,
            html_text,
            snapshot_date=snapshot_date,
            systems=len(data),
            attributes=len(fields),
        ),
    )
    print('index.html has been updated')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
