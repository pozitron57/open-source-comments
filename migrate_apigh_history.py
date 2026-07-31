#! /usr/bin/env python3

import glob
import json
import os
import re
import sys
from json.decoder import JSONDecodeError

from alerts import AlertDeliveryError, send_alert
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
        raise RuntimeError(
            'Refusing to migrate with invalid daily snapshots: {}'.format(
                ', '.join(skipped[:20])
            )
        )
    if not snapshots:
        raise RuntimeError('No valid daily snapshots were found')
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
    try:
        raise SystemExit(migrate())
    except Exception as error:
        print('History migration failed: {}'.format(error), file=sys.stderr)
        try:
            send_alert(
                'open-source-comments history migration failed',
                str(error),
            )
        except AlertDeliveryError as alert_error:
            print('Alert delivery also failed: {}'.format(alert_error), file=sys.stderr)
        raise
