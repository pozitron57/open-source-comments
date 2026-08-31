#!/usr/bin/env python3

import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import date

import yaml

from history_store import latest_date, load_history
from yaml_2_js import fields


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def parse_data_js(text):
    match = re.fullmatch(
        r'var osc_data = (\[.*\]);\nvar cols = (\[.*\]);\nvar col_keys = (\[.*\]);\n',
        text,
        flags=re.S,
    )
    require(match is not None, 'data.js has an unexpected structure')
    return (
        json.loads(match.group(1)),
        json.loads(match.group(2)),
        json.loads(match.group(3)),
    )


def parse_star_history_js(text):
    match = re.fullmatch(
        r'var osc_history = (\{.*\});\n'
        r'var osc_history_range = (\{.*\});\n'
        r'var osc_history_default = (\[.*\]);\n',
        text,
        flags=re.S,
    )
    require(match is not None, 'star-history.js has an unexpected structure')
    return (
        json.loads(match.group(1)),
        json.loads(match.group(2)),
        json.loads(match.group(3)),
    )


FONT_SUBSET_PATH = 'css/fonts/archivo-subset.txt'


def report_font_coverage(rows):
    """Warn about table text the subset font cannot draw.

    The web font is cut down to the characters the page actually renders, so a
    newly added description can introduce one the font lacks. That degrades to a
    fallback glyph rather than breaking anything, so this reports instead of
    failing the update.
    """
    if not os.path.exists(FONT_SUBSET_PATH):
        return

    with open(FONT_SUBSET_PATH, 'r', encoding='utf-8') as source:
        covered = set(source.read().rstrip('\n'))

    uncovered = sorted({
        character
        for row in rows
        for cell in row
        for character in cell
        if character.isprintable() and character not in covered
    })
    if uncovered:
        print(
            'Note: {} character(s) in data.js are outside the font subset and '
            'will use a fallback glyph: {}'.format(
                len(uncovered),
                ' '.join('{} (U+{:04X})'.format(c, ord(c)) for c in uncovered),
            )
        )


def main():
    with open('data.yaml', 'r', encoding='utf-8') as source:
        data = yaml.load(source, Loader=yaml.SafeLoader)
    require(isinstance(data, dict) and data, 'data.yaml must contain a non-empty mapping')
    require(
        all(isinstance(name, str) and isinstance(item, dict) for name, item in data.items()),
        'data.yaml contains an invalid entry',
    )

    with open('data.js', 'r', encoding='utf-8') as source:
        rows, columns, keys = parse_data_js(source.read())
    require(keys == fields, 'data.js column keys do not match yaml_2_js.fields')
    require(len(rows) == len(data), 'data.js row count does not match data.yaml')
    require(
        all(isinstance(row, list) and len(row) == len(fields) for row in rows),
        'data.js contains a row with the wrong number of columns',
    )
    require(
        len(columns) == len(fields)
        and all(isinstance(column, dict) and set(column) == {'title'} for column in columns),
        'data.js column metadata is invalid',
    )

    for index, item in enumerate(data.values()):
        if item.get('update_warning'):
            star_cell = rows[index][0]
            require('stars-with-extra' in star_cell, 'warning row has no star marker')
            require('Update warning on' in star_cell, 'warning row has no tooltip')

    history = load_history()
    expected_date = os.environ.get('OSC_EXPECT_SNAPSHOT_DATE', str(date.today()))
    require(
        latest_date(history) == expected_date,
        'history latest date is {}, expected {}'.format(latest_date(history), expected_date),
    )

    with open('index.html', 'r', encoding='utf-8') as source:
        html = source.read()
    require(html.count('<table id="results"') == 1, 'index.html table marker is invalid')
    require(html.count('<section id="isso-thread">') == 1, 'index.html comments marker is invalid')
    require(
        html.count('Last updated: {}'.format(expected_date)) == 1,
        'index.html update date is missing or duplicated',
    )
    require(
        all(asset in html for asset in ('data.js', 'star-history.js', 'stars-v-date.svg')),
        'index.html misses generated assets',
    )

    with open('star-history.js', 'r', encoding='utf-8') as source:
        series, star_range, default_rows = parse_star_history_js(source.read())
    require(series, 'star-history.js contains no series')
    require(
        all(
            key.isdigit() and 0 <= int(key) < len(rows) and len(entry.get('p', [])) >= 2
            for key, entry in series.items()
        ),
        'star-history.js contains an invalid series',
    )
    require(
        star_range.get('last') == expected_date,
        'star-history.js ends on {}, expected {}'.format(star_range.get('last'), expected_date),
    )
    require(
        default_rows and all(str(row) in series for row in default_rows),
        'star-history.js is missing a default chart series',
    )

    report_font_coverage(rows)

    require(os.path.getsize('stars-v-date.svg') > 10000, 'stars-v-date.svg is unexpectedly small')
    root = ET.parse('stars-v-date.svg').getroot()
    require(root.tag.endswith('svg'), 'stars-v-date.svg has an invalid root element')

    print(
        'Validated {} rows, {} columns, {} history dates, {} chart series, HTML and SVG'.format(
            len(rows),
            len(columns),
            len(history['dates']),
            len(series),
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
