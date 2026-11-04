"""CI-only immutable Jost profile; never imports or changes a production runtime.

Tests and CI guards remain in the current checkout. Only People production module
imports/resources come from the exact retained PR63 commit. New Unicode tests run
separately against current sources and must never select this profile.
"""
from contextlib import contextmanager
import importlib.abc
import importlib.util
import logging
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = '05ea93ba4b75a6c8fbd3755bdf817cb6c8485338'


def selections(paths):
    result = []
    for arg in paths:
        if arg.startswith('@'):
            result.extend(selections(Path(arg[1:]).read_text(encoding='utf8').splitlines()))
        elif arg != '--':
            result.append(arg.replace('\\', '/'))
    return result


class Finder(importlib.abc.MetaPathFinder):
    def __init__(self, modules):
        self.modules = modules

    def find_spec(self, fullname, path=None, target=None):
        name = fullname.removeprefix('create_people_posters.')
        if name in self.modules and fullname in {name, 'create_people_posters.'+name}:
            return importlib.util.spec_from_file_location(fullname, self.modules[name])
        return None


def _close_profile_log_handlers(root):
    """Release only root file handlers owned by this historical temp profile."""
    logger = logging.getLogger()
    root = root.resolve()
    for handler in tuple(logger.handlers):
        if (isinstance(handler, logging.FileHandler)
                and Path(handler.baseFilename).resolve().is_relative_to(root)):
            logger.removeHandler(handler)
            handler.close()


@contextmanager
def historical_people_profile(paths):
    selected = selections(paths)
    if any('create_people_posters/unicode/' in p for p in selected):
        raise ValueError('Unicode tests cannot use the historical Jost profile')
    active = any(p.split('::')[0].rstrip('/') in {'create_people_posters',
        'create_people_posters/tests'} or p.startswith('create_people_posters/tests/')
        for p in selected)
    if not active:
        yield {'name': 'current-checkout'}
        return
    from ci.phase5_m5_maintenance import unicode_adapter
    unicode_adapter().verify(ROOT)
    raw = subprocess.check_output(['git', 'ls-tree', '-r', '-z', BASE,
        '--', 'create_people_posters'], cwd=ROOT)
    entries = []
    for row in filter(None, raw.split(b'\0')):
        metadata, encoded = row.split(b'\t', 1)
        mode, kind, oid = metadata.split()
        name = encoded.decode('utf8')
        path = Path(name)
        if path.parts[0] != 'create_people_posters' or '..' in path.parts:
            raise ValueError('Invalid historical People resource path')
        if mode != b'100644' or kind != b'blob':
            raise ValueError('Historical People profile requires regular files')
        if 'tests' not in path.parts:
            entries.append((name, oid))
    with tempfile.TemporaryDirectory(prefix='ci-people-jost-') as folder:
        root = Path(folder)
        for name, oid in entries:
            dest = root/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(subprocess.check_output(['git', 'cat-file', 'blob',
                oid.decode('ascii')], cwd=ROOT))
        people = root/'create_people_posters'
        modules = {p.stem: p for p in people.glob('*.py') if p.name != '__init__.py'}
        if any(name in sys.modules or 'create_people_posters.'+name in sys.modules
               for name in modules):
            raise ValueError('Refusing mixed current/historical People modules')
        finder = Finder(modules)
        sys.meta_path.insert(0, finder)
        try:
            yield {'name': 'historical-jost-pr63', 'commit': BASE,
                   'current_successor_verified': True}
        finally:
            sys.meta_path.remove(finder)
            _close_profile_log_handlers(root)
