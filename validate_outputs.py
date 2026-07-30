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
        r'var osc_data = (\[.*\]);\nvar cols = (\[.*\]);\n',
        text,
        flags=re.S,
    )
    require(match is not None, 'data.js has an unexpected structure')
    return json.loads(match.group(1)), json.loads(match.group(2))


def main():
    with open('data.yaml', 'r', encoding='utf-8') as source:
        data = yaml.load(source, Loader=yaml.SafeLoader)
    require(isinstance(data, dict) and data, 'data.yaml must contain a non-empty mapping')
    require(
        all(isinstance(name, str) and isinstance(item, dict) for name, item in data.items()),
        'data.yaml contains an invalid entry',
    )

    with open('data.js', 'r', encoding='utf-8') as source:
        rows, columns = parse_data_js(source.read())
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
    require('data.js' in html and 'stars-v-date.svg' in html, 'index.html misses generated assets')

    require(os.path.getsize('stars-v-date.svg') > 10000, 'stars-v-date.svg is unexpectedly small')
    root = ET.parse('stars-v-date.svg').getroot()
    require(root.tag.endswith('svg'), 'stars-v-date.svg has an invalid root element')

    print(
        'Validated {} rows, {} columns, {} history dates, HTML and SVG'.format(
            len(rows),
            len(columns),
            len(history['dates']),
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
