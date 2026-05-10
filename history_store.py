import json
import os
import stat
import tempfile


HISTORY_PATH = 'apigh/history.json'
FIELDS = ['stars', 'open_issues', 'created', 'license', 'last_commit']


def empty_history():
    return {'version': 1, 'fields': FIELDS, 'dates': [], 'projects': {}}


def load_history(path=HISTORY_PATH):
    if not os.path.exists(path):
        return empty_history()

    with open(path, 'r', encoding='utf-8') as f:
        history = json.load(f)

    history.setdefault('version', 1)
    history.setdefault('fields', FIELDS)
    history.setdefault('dates', [])
    history.setdefault('projects', {})
    return history


def save_history(history, path=HISTORY_PATH):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    mode = stat.S_IMODE(os.stat(path).st_mode) if os.path.exists(path) else 0o644
    with tempfile.NamedTemporaryFile('w', dir=directory or '.', encoding='utf-8', delete=False) as tmp:
        tmp_name = tmp.name
        json.dump(history, tmp, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        tmp.write('\n')

    os.chmod(tmp_name, mode)
    os.replace(tmp_name, path)


def append_snapshot(history, snapshot_date, snapshot):
    if snapshot_date not in history['dates']:
        history['dates'].append(snapshot_date)
        history['dates'].sort()

    projects = history['projects']
    for project, values in snapshot.items():
        project_history = projects.setdefault(project, {})
        for field in FIELDS:
            if field not in values:
                continue

            events = project_history.setdefault(field, [])
            value = values[field]
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
