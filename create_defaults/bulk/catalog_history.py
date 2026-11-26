"""Owned, authenticated catalog inputs for immutable historical replay only."""
from dataclasses import dataclass, field
from functools import lru_cache
import hashlib
from pathlib import Path, PurePosixPath
import subprocess
from tempfile import TemporaryDirectory

from .common import BulkError, reject_links
from .config import CATEGORIES, select_categories
from .definitions import load_definitions
from .contracts.expanded.resolution import Resolution, resolve


ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'create_defaults/bulk/catalog/'
MAX_BYTES = 2_000_000


def _fail(message):
    raise BulkError('historical_catalog_pin', message)


def _git(*args, data=None):
    result = subprocess.run(['git', *args], cwd=ROOT, input=data,
        capture_output=True, timeout=180)
    if result.returncode:
        _fail('Cannot read the authenticated historical catalog commit')
    return result.stdout


def load_pins():
    # Adoption's public package imports its inventory; defer this import until
    # the historical reader is initialized to avoid an import-order cycle.
    from .contracts.adoption.sources import load_pins as original
    return original()


def _bindings():
    # load_pins authenticates the unchanged original 299-source inventory.
    pins = load_pins()
    rows = tuple(sorted((row['path'], row['sha256'], row['text_lf'])
        for row in pins['files'] if row['path'].startswith(PREFIX)
        and '/' not in row['path'][len(PREFIX):] and row['path'].endswith('.yml')))
    if not rows or PREFIX+'playlist.yml' not in {row[0] for row in rows} or PREFIX+'profiles.yml' not in {row[0] for row in rows}:
        _fail('Historical catalog/profile membership is missing')
    return pins['source_commit'], rows


@lru_cache(maxsize=2)
def _blobs(commit, bindings):
    # Only immutable Git bytes are cached. No mutable catalog or checkout proof.
    expected = {name:(digest, text_lf) for name,digest,text_lf in bindings}
    tree = _git('ls-tree', '-r', '-z', commit, '--', *sorted(expected))
    entries = []
    for row in filter(None, tree.split(b'\0')):
        metadata, name = row.split(b'\t', 1)
        mode, kind, oid = metadata.split()
        if mode != b'100644' or kind != b'blob':
            _fail('Historical catalog requires regular committed files')
        entries.append((name.decode('utf8'), oid))
    if {name for name,_ in entries} != set(expected) or len(entries) != len(expected):
        _fail('Historical catalog tree membership differs from the original pins')
    encoded = _git('cat-file', '--batch', data=b''.join(oid+b'\n' for _,oid in entries))
    offset, result = 0, []
    for name,oid in entries:
        end = encoded.index(b'\n', offset)
        header = encoded[offset:end].split()
        if len(header) != 3 or header[:2] != [oid,b'blob']:
            _fail('Historical catalog object is missing')
        size = int(header[2]); offset = end+1
        if not 0 <= size <= MAX_BYTES:
            _fail('Historical catalog object exceeds the loader bound')
        raw = encoded[offset:offset+size]
        if len(raw) != size or encoded[offset+size:offset+size+1] != b'\n':
            _fail('Historical catalog object is incomplete')
        offset += size+1
        checksum,text_lf = expected[name]
        normalized = raw.replace(b'\r\n',b'\n') if text_lf else raw
        if hashlib.sha256(normalized).hexdigest() != checksum:
            _fail('Historical catalog blob differs from its original source pin: '+name)
        result.append((PurePosixPath(name).name,raw))
    if offset != len(encoded):
        _fail('Extra historical catalog object bytes')
    return tuple(result)


@dataclass(frozen=True)
class HistoricalResolution(Resolution):
    # Keep the private snapshot alive for as long as its source paths are used.
    _directory: object = field(default=None, repr=False, compare=False)
    _authority: tuple = field(default=(), repr=False, compare=False)

    def verify_current(self, identities=None):
        if _bindings() != self._authority:
            _fail('Historical catalog authority changed')
        # The unchanged verifier rereads exact snapshot files and rejects edits,
        # missing files, links and stale hashes, including after a prior proof.
        return super().verify_current(identities)


def resolve_historical(*, categories=None):
    """Use the normal loader/expander over the pinned pre-addition catalog."""
    authority = _bindings()
    directory = TemporaryDirectory(prefix='defaults-historical-catalog-')
    root = Path(directory.name)
    try:
        for name,raw in _blobs(*authority):
            (root/name).write_bytes(raw)
        if categories is None:
            paths = tuple(sorted(path for path in root.iterdir() if path.name != 'profiles.yml'))
        else:
            selected = select_categories(categories)
            paths = tuple(root/(category.lower()+'.yml') for category in CATEGORIES
                          if category in selected and category != 'Overlays')
        current = resolve(paths, profiles_path=root/'profiles.yml')
        result = HistoricalResolution(current.encoded,current.source_pins,directory,authority)
        result.verify_current()
        return result
    except BaseException:
        directory.cleanup()
        raise


def load_historical_catalog(categories):
    """Normal definition loader over authenticated pre-addition catalog inputs."""
    authority = _bindings()
    selected = select_categories(categories)
    with TemporaryDirectory(prefix='defaults-historical-definitions-') as folder:
        root = Path(folder)
        objects = _blobs(*authority)
        for name,raw in objects:
            (root/name).write_bytes(raw)
        paths = [root/(category.lower()+'.yml') for category in CATEGORIES
                 if category in selected and category != 'Overlays']
        for name,raw in objects:
            if reject_links(root/name).read_bytes() != raw:
                _fail('Historical catalog input changed before loading')
        definitions = load_definitions(paths,profiles_path=root/'profiles.yml')
        for name,raw in objects:
            if reject_links(root/name).read_bytes() != raw:
                _fail('Historical catalog input changed during definition loading')
        if _bindings() != authority:
            _fail('Historical catalog authority changed during definition loading')
        return definitions
