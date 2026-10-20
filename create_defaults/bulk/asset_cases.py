"""Case-exact asset validation and byte-bound historical case migrations."""

from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path, PurePosixPath

from .common import BulkError, fingerprint, relative_path, sha256


LEDGER = Path(__file__).parent / 'catalog/asset-case-migrations-v1.json'


def exact(root, relative):
    """Enumerate real directory entries; Windows accessibility is insufficient."""
    current = Path(root)
    relative_path(relative)
    if current.resolve() == LEDGER.parents[2].resolve():
        check_authority()
    declared = declarations().get(relative.casefold())
    if declared and declared != relative:
        raise BulkError('asset_case', 'Authoritative source spelling is ' + declared + ', not ' + relative)
    for part in PurePosixPath(relative).parts:
        if part in {'', '.', '..'} or '/' in part or '\\' in part:
            raise BulkError('unsafe_path', 'Case validation requires a confined relative path')
        if not current.is_dir():
            raise BulkError('missing_asset', 'Missing asset directory: ' + str(current))
        with os.scandir(current) as entries:
            names = [p.name for p in entries if p.name.casefold() == part.casefold()]
        if len(names) > 1:
            raise BulkError('case_collision', 'Multiple physical paths differ only in capitalization: ' + str(current / part))
        if names != [part]:
            raise BulkError('asset_case' if names else 'missing_asset',
                            'Declared ' + str(current / part) + '; physical spelling: ' + repr(names))
        current /= part
    return current


@lru_cache(maxsize=1)
def ledger():
    if not LEDGER.exists():
        return {}
    value = json.loads(LEDGER.read_text(encoding='utf-8'))
    if value.get('sha256') != fingerprint({k: v for k, v in value.items() if k != 'sha256'}):
        raise BulkError('case_ledger', 'Case migration ledger changed')
    return value


@lru_cache(maxsize=1)
def declarations():
    paths = ledger().get('authoritative_sources', [])
    result = {}
    for path in paths:
        key = path.casefold()
        if key in result and result[key] != path:
            raise BulkError('case_ledger', 'Authoritative input case collision')
        result[key] = path
    return result


@lru_cache(maxsize=1)
def check_authority():
    value = ledger()
    raw = (LEDGER.parents[2] / 'create_default_posters.ps1').read_bytes() if value else b''
    # Git may check text out with LF or CRLF. Accept only that reversible
    # representation change; any actual input-definition edit invalidates the seal.
    lf = raw.replace(b'\r\n', b'\n')
    identities = {hashlib.sha256(body).hexdigest() for body in (raw, lf, lf.replace(b'\n', b'\r\n'))}
    if value and value['source_ps1_sha256'] not in identities:
        raise BulkError('stale_authority', 'Authoritative PS1 input changed; refresh and verify the case index against current definitions')
    return True


@lru_cache(maxsize=1)
def migrations():
    result = {}
    value = ledger()
    if not value:
        return result
    for item in value['migrations']:
        if item['from'].casefold() != item['to'].casefold() or item['from'] == item['to'] or item['from'] in result:
            raise BulkError('case_ledger', 'Only unique byte-preserving case corrections are permitted')
        result[item['from']] = item
    return result


def canonical(relative):
    return migrations().get(relative, {}).get('to', relative)


def historical(root, relative, expected_sha256=None):
    """Read old evidence through an explicit SHA-bound ledger, never a fuzzy lookup."""
    record = migrations().get(relative)
    target = exact(root, record['to'] if record else relative)
    if record and (sha256(target) != record['sha256'] or
                   expected_sha256 is not None and expected_sha256 != record['sha256']):
        raise BulkError('case_ledger', 'Historical case alias bytes differ from the original source')
    return target


def overlay_relative(source, destination):
    """Canonical output basename comes solely from the declared source asset."""
    return str(PurePosixPath(destination).parent / PurePosixPath(canonical(source)).name)


def replacement(previous, current):
    """Permit only a ledger-proven overlay task identity/path case transition."""
    if previous.payload.get('kind') != 'overlay' or current.payload.get('kind') != 'overlay':
        return False
    old_source = previous.payload['parameters']['input']
    record = migrations().get(old_source)
    if not record or current.payload['parameters']['input'] != record['to']:
        return False
    if current.local_relative != overlay_relative(old_source, previous.local_relative):
        return False
    if previous.local_relative.casefold() != current.local_relative.casefold():
        return False
    payload = json.loads(json.dumps(previous.payload))
    payload['parameters']['input'] = record['to']
    for item in payload['inputs']:
        if item['path'] == old_source:
            if item['sha256'] != record['sha256']:
                return False
            item['path'] = record['to']
    return payload == current.payload and tuple(previous.dependencies) == tuple(current.dependencies)
