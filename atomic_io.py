import os
import stat
import tempfile


def atomic_write_text(path, content, encoding='utf-8', default_mode=0o644):
    directory = os.path.dirname(path) or '.'
    os.makedirs(directory, exist_ok=True)
    mode = (
        stat.S_IMODE(os.stat(path).st_mode)
        if os.path.exists(path)
        else default_mode
    )
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            'w',
            dir=directory,
            encoding=encoding,
            delete=False,
        ) as temporary:
            temporary_path = temporary.name
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())

        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
        temporary_path = None

        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def atomic_write_many_text(files, encoding='utf-8'):
    originals = {}
    written = []
    for path in files:
        if os.path.exists(path):
            with open(path, 'r', encoding=encoding) as existing:
                originals[path] = (
                    existing.read(),
                    stat.S_IMODE(os.stat(path).st_mode),
                )
        else:
            originals[path] = None

    try:
        for path, content in files.items():
            atomic_write_text(path, content, encoding=encoding)
            written.append(path)
    except Exception:
        rollback_errors = []
        for path in reversed(written):
            try:
                original = originals[path]
                if original is None:
                    if os.path.exists(path):
                        os.unlink(path)
                else:
                    original_content, original_mode = original
                    atomic_write_text(
                        path,
                        original_content,
                        encoding=encoding,
                        default_mode=original_mode,
                    )
                    os.chmod(path, original_mode)
            except Exception as rollback_error:
                rollback_errors.append('{}: {}'.format(path, rollback_error))
        if rollback_errors:
            raise RuntimeError(
                'atomic write failed and rollback was incomplete: {}'.format(
                    '; '.join(rollback_errors)
                )
            )
        raise
