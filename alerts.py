import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


class AlertDeliveryError(RuntimeError):
    pass


def _positive_int(value, default, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, 1), maximum)


def send_alert(subject, body, email=None, required=None):
    email = email if email is not None else os.environ.get('OSC_ALERT_EMAIL', '')
    email = email.strip()
    required = bool(email) if required is None else required

    subject = ' '.join(str(subject).splitlines()).strip()[:180]
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')
    message = (
        'Host: {}\n'
        'Time: {}\n\n'
        '{}'
    ).format(socket.gethostname(), timestamp, str(body).rstrip())
    print('ALERT: {}\n{}'.format(subject, message), file=sys.stderr)

    if not email:
        return False
    if '\n' in email or '\r' in email:
        raise AlertDeliveryError('OSC_ALERT_EMAIL contains a newline')

    command = shlex.split(os.environ.get('OSC_MAIL_COMMAND', 'mail'))
    executable = shutil.which(command[0]) if command else None
    if not executable and command and '/' not in command[0]:
        user_command = Path.home() / '.local' / 'bin' / command[0]
        if user_command.is_file() and os.access(user_command, os.X_OK):
            command[0] = str(user_command)
            executable = command[0]
    if not command or not executable:
        error = 'mail command is unavailable: {}'.format(command[0] if command else '(empty)')
        if required:
            raise AlertDeliveryError(error)
        print(error, file=sys.stderr)
        return False

    attempts = _positive_int(os.environ.get('OSC_ALERT_ATTEMPTS'), 3, 5)
    timeout = _positive_int(os.environ.get('OSC_ALERT_TIMEOUT'), 45, 120)
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            result = subprocess.run(
                command + ['-s', subject, email],
                input=message + '\n',
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
            if result.returncode == 0:
                return True
            last_error = 'mail exited with {}: {}'.format(
                result.returncode,
                result.stderr.strip()[-1000:],
            )
        except (OSError, subprocess.SubprocessError) as error:
            last_error = str(error)

        if attempt < attempts:
            time.sleep(attempt)

    error = 'could not deliver alert after {} attempt(s): {}'.format(
        attempts,
        last_error or 'unknown mail error',
    )
    if required:
        raise AlertDeliveryError(error)
    print(error, file=sys.stderr)
    return False
