import json
import os
from datetime import date

from atomic_io import atomic_write_text

HISTORY_PATH = 'apigh/history.json'
FIELDS = [
    'stars',
    'stars_total',
    'stars_github',
    'stars_gitlab',
    'open_issues',
    'created',
    'license',
    'last_commit',
]
INTEGER_FIELDS = {
    'stars',
    'stars_total',
    'stars_github',
    'stars_gitlab',
    'open_issues',
}
DATE_FIELDS = {'created', 'last_commit'}


class HistoryValidationError(RuntimeError):
    pass


def empty_history():
    return {'version': 1, 'fields': FIELDS, 'dates': [], 'projects': {}}


def load_history(path=HISTORY_PATH):
    if not os.path.exists(path):
        return empty_history()

    with open(path, 'r', encoding='utf-8') as f:
        history = json.load(f)

    history.setdefault('version', 1)
    history['fields'] = FIELDS
    history.setdefault('dates', [])
    history.setdefault('projects', {})
    validate_history(history)
    return history


def _valid_date(value):
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _validate_field_value(project, field, value):
    if field in INTEGER_FIELDS:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise HistoryValidationError(
                '{}.{} must be a non-negative integer, got {!r}'.format(
                    project,
                    field,
                    value,
                )
            )
    elif field in DATE_FIELDS:
        normalized = str(value).replace('‑', '-')
        if value != 'undefined' and not _valid_date(normalized):
            raise HistoryValidationError(
                '{}.{} must be a date, got {!r}'.format(project, field, value)
            )
    elif field == 'license' and not isinstance(value, str):
        raise HistoryValidationError(
            '{}.license must be a string, got {!r}'.format(project, value)
        )


def validate_history(history, strict_values=False):
    if not isinstance(history, dict):
        raise HistoryValidationError('history root must be an object')
    if history.get('version') != 1:
        raise HistoryValidationError('unsupported history version: {}'.format(history.get('version')))

    dates = history.get('dates')
    projects = history.get('projects')
    if not isinstance(dates, list) or not all(_valid_date(value) for value in dates):
        raise HistoryValidationError('history dates must be ISO date strings')
    if dates != sorted(set(dates)):
        raise HistoryValidationError('history dates must be sorted and unique')
    if not isinstance(projects, dict):
        raise HistoryValidationError('history projects must be an object')

    known_dates = set(dates)
    for project, project_history in projects.items():
        if not isinstance(project, str) or not isinstance(project_history, dict):
            raise HistoryValidationError('invalid history entry for {!r}'.format(project))
        for field, events in project_history.items():
            if field not in FIELDS:
                raise HistoryValidationError('unknown history field {} for {}'.format(field, project))
            if not isinstance(events, list):
                raise HistoryValidationError('history events for {}.{} must be a list'.format(project, field))

            previous_date = None
            for event in events:
                if not isinstance(event, list) or len(event) != 2 or not _valid_date(event[0]):
                    raise HistoryValidationError('invalid event for {}.{}'.format(project, field))
                event_date = event[0]
                if event_date not in known_dates:
                    raise HistoryValidationError(
                        'event date {} is absent from history dates'.format(event_date)
                    )
                if previous_date is not None and event_date <= previous_date:
                    raise HistoryValidationError(
                        'events for {}.{} are not strictly ordered'.format(project, field)
                    )
                previous_date = event_date
                if strict_values:
                    _validate_field_value(project, field, event[1])


def serialize_history(history):
    validate_history(history)
    return json.dumps(history, ensure_ascii=False, sort_keys=True, indent=2) + '\n'


def save_history(history, path=HISTORY_PATH):
    atomic_write_text(path, serialize_history(history))


def append_snapshot(history, snapshot_date, snapshot):
    if not _valid_date(snapshot_date):
        raise HistoryValidationError('invalid snapshot date: {!r}'.format(snapshot_date))
    if not isinstance(snapshot, dict):
        raise HistoryValidationError('snapshot must be an object')

    if snapshot_date not in history['dates']:
        history['dates'].append(snapshot_date)
        history['dates'].sort()

    projects = history['projects']
    for project, values in snapshot.items():
        if not isinstance(project, str) or not isinstance(values, dict):
            raise HistoryValidationError('invalid snapshot entry for {!r}'.format(project))
        project_history = projects.setdefault(project, {})
        for field in FIELDS:
            if field not in values:
                continue

            events = project_history.setdefault(field, [])
            value = values[field]
            _validate_field_value(project, field, value)
            if events and events[-1][0] == snapshot_date:
                events[-1][1] = value
            elif not events or events[-1][1] != value:
                events.append([snapshot_date, value])


def value_on_or_before(events, snapshot_date):
    value = None
    for event_date, event_value in events:
        if event_date > snapshot_date:
            break
        value = event_value
    return value


def snapshot_for_date(history, snapshot_date):
    snapshot = {}
    for project, project_history in history['projects'].items():
        values = {}
        for field, events in project_history.items():
            value = value_on_or_before(events, snapshot_date)
            if value is not None:
                values[field] = value
        if values:
            snapshot[project] = values
    return snapshot


def field_on_or_before(history, project, field, snapshot_date):
    events = history['projects'].get(project, {}).get(field, [])
    return value_on_or_before(events, snapshot_date)


def latest_date(history):
    return max(history['dates']) if history['dates'] else None
