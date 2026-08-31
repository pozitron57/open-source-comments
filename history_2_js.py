#! /usr/bin/env python
# coding=utf8

'''
Convert apigh/history.json to star-history.js, the star series the interactive
chart on the page reads.

The chart needs one point list per project, not the full history: history.json
keeps every recorded change of eight fields for 64 projects, which is far too
much to ship to a browser. This script keeps only `stars`, drops the samples
plot-stars.py also drops, and downsamples each series to the points that are
visible at chart resolution.
'''

import datetime
import json

import yaml

from atomic_io import atomic_write_text
from history_store import load_history

# Carried over from plot-stars.py so the SVG and the interactive chart show the
# same seven series with the same line styles.
DEFAULT_SERIES = {
    'isso': 'solid',
    'commento': 'solid',
    'Waline': 'dotted',
    'staticman': 'dashed',
    'Artalk': 'solid',
    'remark': 'solid',
    'valine': 'dashdot',
}

# plot-stars.py skips this window for isso: the API reported a star count that
# was never real, and the spike dominates the plot.
BAD_WINDOW = {
    'isso': (datetime.date(2024, 3, 6), datetime.date(2024, 3, 12)),
}

MIN_DAYS = 30
MIN_RELATIVE_CHANGE = 0.03


def usable_points(history, project, strict=False):
    '''Star events for one project, without the samples the plot rejects.

    A few projects carry non-integer star values recorded before the history
    was validated; they are skipped. For the default series a bad value is an
    error instead, matching what plot-stars.py does for the same seven.
    '''
    events = history['projects'].get(project, {}).get('stars', [])
    window = BAD_WINDOW.get(project)
    points = []
    for event_date, value in events:
        if isinstance(value, bool) or not isinstance(value, int):
            if strict:
                raise RuntimeError(
                    'Invalid star history value for {} on {}: {!r}'.format(
                        project,
                        event_date,
                        value,
                    )
                )
            continue
        if value <= 0:
            continue
        if window:
            parsed = datetime.date.fromisoformat(event_date)
            if window[0] <= parsed <= window[1]:
                continue
        points.append([event_date, value])
    return points


def downsample(points, last_date):
    '''Keep the points that change the drawn line, plus the endpoints.

    A point survives when it is at least MIN_DAYS away from the last kept one
    or moves the value by at least MIN_RELATIVE_CHANGE. The last recorded value
    is carried forward to last_date so every series reaches the right edge.
    '''
    if not points:
        return []

    kept = [points[0]]
    for event_date, value in points[1:-1]:
        kept_date, kept_value = kept[-1]
        days = (
            datetime.date.fromisoformat(event_date)
            - datetime.date.fromisoformat(kept_date)
        ).days
        change = abs(value - kept_value) / max(kept_value, 1)
        if days >= MIN_DAYS or change >= MIN_RELATIVE_CHANGE:
            kept.append([event_date, value])

    if len(points) > 1 and kept[-1] != points[-1]:
        kept.append(points[-1])
    if kept[-1][0] != last_date:
        kept.append([last_date, kept[-1][1]])
    return kept


def generate_star_history_js(history, keys):
    last_date = max(history['dates']) if history['dates'] else None
    if last_date is None:
        raise RuntimeError('history contains no dates')

    unknown = [name for name in DEFAULT_SERIES if name not in keys]
    if unknown:
        raise RuntimeError(
            'default chart series missing from data.yaml: {}'.format(', '.join(unknown))
        )

    series = {}
    first_date = None
    for index, name in enumerate(keys):
        points = downsample(
            usable_points(history, name, strict=name in DEFAULT_SERIES),
            last_date,
        )
        if len(points) < 2:
            continue
        entry = {'p': points}
        dash = DEFAULT_SERIES.get(name)
        if dash:
            entry['d'] = dash
        series[index] = entry
        if first_date is None or points[0][0] < first_date:
            first_date = points[0][0]

    missing = [name for name in DEFAULT_SERIES if keys.index(name) not in series]
    if missing:
        raise RuntimeError(
            'no usable star history for default series: {}'.format(', '.join(missing))
        )

    default_rows = [keys.index(name) for name in DEFAULT_SERIES]

    return '\n'.join([
        'var osc_history = {};'.format(
            json.dumps(
                {str(index): entry for index, entry in sorted(series.items())},
                ensure_ascii=False,
                separators=(',', ':'),
            )
        ),
        'var osc_history_range = {};'.format(
            json.dumps({'first': first_date, 'last': last_date}, ensure_ascii=False)
        ),
        'var osc_history_default = {};'.format(json.dumps(default_rows)),
    ]) + '\n'


def main():
    with open('data.yaml', 'r', encoding='utf-8') as source:
        data = yaml.load(source, Loader=yaml.SafeLoader)
    atomic_write_text(
        'star-history.js',
        generate_star_history_js(load_history(), list(data)),
    )
    print('star-history.js has been updated')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
