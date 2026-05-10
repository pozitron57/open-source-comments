#! /usr/bin/env python3

import glob
import json
import os
import re
import sys
from json.decoder import JSONDecodeError

from history_store import append_snapshot, empty_history, save_history, snapshot_for_date


def load_snapshots():
    snapshots = {}
    skipped = []
    for path in sorted(glob.glob('apigh/file_*')):
        snapshot_date = os.path.basename(path).replace('file_', '')
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', snapshot_date):
            continue

        with open(path, 'r', encoding='utf-8') as f:
            try:
                snapshots[snapshot_date] = json.load(f)
            except JSONDecodeError:
                skipped.append(path)

    if skipped:
        print('Skipped {} invalid daily snapshots'.format(len(skipped)), file=sys.stderr)
    return snapshots


def migrate():
    snapshots = load_snapshots()
    history = empty_history()
    for snapshot_date, snapshot in snapshots.items():
        append_snapshot(history, snapshot_date, snapshot)

    carried_projects = 0
    for snapshot_date, original in snapshots.items():
        restored = snapshot_for_date(history, snapshot_date)
        for project, values in original.items():
            restored_values = restored.get(project, {})
            for field, value in values.items():
                if restored_values.get(field) != value:
                    print('Snapshot mismatch for {}'.format(snapshot_date), file=sys.stderr)
                    return 1
        carried_projects += len(set(restored) - set(original))

    if carried_projects:
        print('Carried {} missing project snapshots forward'.format(carried_projects), file=sys.stderr)

    save_history(history)
    print('Wrote apigh/history.json from {} daily snapshots'.format(len(snapshots)))
    return 0


if __name__ == '__main__':
    raise SystemExit(migrate())
