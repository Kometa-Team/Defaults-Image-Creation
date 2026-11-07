"""Read-only verification of a completed batch; never render or repair files."""
from contextlib import contextmanager, closing
import json
import os
from pathlib import Path
import sqlite3

from bulk_regeneration_state import (MARKER, canonical, database, read_inventory,
    reject_links)


@contextmanager
def validation_lock(root):
    path = root / '.bulk/runner.lock'
    reject_links(path)
    with path.open('rb') as stream:
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBRLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        except OSError as error:
            raise BlockingIOError('A renderer owns this batch; validate after it stops') from error
        yield


def validate(output):
    result = dict(read_only=True, valid=False, state='invalid', verified=0,
                  planned=0, errors=[], publication_authorized=False)
    try:
        root = Path(output).absolute()
        reject_links(root)
        with validation_lock(root), closing(database(root, readonly=True)) as db:
            db.execute('BEGIN')
            if [row[0] for row in db.execute('PRAGMA integrity_check')] != ['ok']:
                raise ValueError('Checkpoint integrity check failed')
            meta = {row[0]: json.loads(row[1]) for row in db.execute('SELECT key,value FROM meta')}
            manifest = meta['manifest']
            if (manifest.get('managed_by') != MARKER or manifest['output'] != str(root.resolve())
                    or canonical(manifest) != meta['manifest_hash']):
                raise ValueError('Batch manifest/checkpoint identity mismatch')
            if meta['state'] != 'completed':
                raise ValueError('Batch is not completed; inspect status/failures before validation')
            from bulk_regeneration_plan import renderer_version
            if manifest['renderer'] != renderer_version():
                raise ValueError('Validator runtime differs from the frozen renderer/workflow')
            rows = read_inventory(root)
            if canonical(rows) != manifest['inventory_sha256']:
                raise ValueError('Frozen inventory digest mismatch')
            selected = [row for row in rows if row['selected']]
            expected = {(row['number'], style) for row in selected for style in manifest['styles']}
            outputs = {(row['number'], row['style']): dict(row) for row in db.execute('SELECT * FROM outputs')}
            result['planned'] = len(expected)
            if outputs.keys() != expected or any(row['status'] != 'completed' for row in outputs.values()):
                raise ValueError('Checkpoint has missing, extra or incomplete outputs')
            from bulk_regenerate import validated_receipt
            from PIL import Image
            renderer_id = canonical(manifest['renderer'])
            for item in selected:
                for style in manifest['styles']:
                    receipt = validated_receipt(root, item, style, renderer_id, manifest['batch_id'])
                    if receipt is None:
                        raise ValueError('Receipt/hash/JPEG header mismatch: '+item['relative']+' / '+style)
                    row = outputs[item['number'], style]
                    if (row['path'] != receipt['output'] or row['sha256'] != receipt['sha256']
                            or row['bytes'] != receipt['bytes'] or row['error']):
                        raise ValueError('Receipt/checkpoint mismatch: '+receipt['output'])
                    if receipt['collection_calls'].get(style, 0) != (0 if style == 'bw' else 1):
                        raise ValueError('COLLECTION receipt contract mismatch: '+receipt['output'])
                    path = root / receipt['output']
                    with Image.open(path) as image:
                        image.verify()
                    with Image.open(path) as image:
                        image.load()
                    result['verified'] += 1
            actual = {path.relative_to(root).as_posix() for path in root.glob('*/*/Images/*.jpg')}
            if actual != {row['path'] for row in outputs.values()}:
                raise ValueError('Missing or unexpected JPEG files in the batch')
            result.update(valid=True, state='valid', batch_id=manifest['batch_id'],
                          source_commit=manifest['source_git']['head'], styles=manifest['styles'])
    except BlockingIOError as error:
        result.update(state='unavailable', errors=[str(error)])
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        result['errors'].append(str(error))
    return result
