"""Exact-file retention primitives. No production state is created by import/read."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import time
import uuid

from create_people_posters.people_workspaces import reject_links
from create_people_posters.people_recovery_storage import cleanup_lock


class RetentionBlocked(ValueError):
    pass


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
        allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def member(root, relative):
    if (not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative
            or relative.startswith('/') or any(p in {'', '.', '..'} for p in relative.split('/'))):
        raise RetentionBlocked('Unsafe retention member')
    root = Path(root).absolute()
    path = root.joinpath(*relative.split('/'))
    reject_links(path)
    if not path.resolve().is_relative_to(root.resolve()):
        raise RetentionBlocked('Retention member escaped root')
    return path


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
                mtime_ns=info.st_mtime_ns)


def inspect(path):
    path = Path(path)
    reject_links(path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise RetentionBlocked('Retention requires a single-link regular file')
    sha = hashlib.sha256()
    git = hashlib.sha1(b'blob '+str(before.st_size).encode()+b'\0')
    with path.open('rb') as stream:
        if identity(os.fstat(stream.fileno())) != identity(before):
            raise RetentionBlocked('Retention file identity changed')
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            sha.update(chunk); git.update(chunk)
        if identity(os.fstat(stream.fileno())) != identity(before):
            raise RetentionBlocked('Retention file changed while hashing')
    if identity(path.lstat()) != identity(before):
        raise RetentionBlocked('Retention file changed after hashing')
    return dict(identity(before), sha256=sha.hexdigest(), git_blob=git.hexdigest())


def read_json(path, maximum=32*1024*1024):
    path = Path(path); reject_links(path)
    if not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_size > maximum:
        raise RetentionBlocked('Invalid retention metadata file')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def atomic_json(path, value):
    path = Path(path); reject_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x', encoding='utf8', newline='\n') as stream:
            json.dump(value, stream, sort_keys=True, ensure_ascii=True, allow_nan=False, indent=2)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        reject_links(path)
        os.replace(temporary, path)
    except BaseException:
        # Retain incomplete own-state evidence; never clean unrelated temporaries.
        raise


def readonly_db(path):
    path = Path(path); reject_links(path)
    if not path.is_file():
        raise RetentionBlocked('Required publication ledger missing')
    db = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    return db


class Journal:
    """Durable JSON intents/receipts, using the existing state directory."""
    def __init__(self, directory):
        self.path = Path(directory)/'deletions.json'
        self.value = read_json(self.path) if self.path.exists() else {'version':1,'files':{}}
        if set(self.value) != {'version','files'} or self.value['version'] != 1:
            raise RetentionBlocked('Invalid deletion receipts')

    def intent(self, scope, root, row, proof):
        key=fingerprint([scope,str(root),row['path']])
        old=self.value['files'].get(key)
        record=dict(scope=scope,root=str(root),path=row['path'],sha256=row['sha256'],
            git_blob=row['git_blob'],bytes=row['bytes'],reason=row['reason'],state='intent',
            first_intent=time.time(),updated=time.time(),proof=proof)
        if old:
            if any(old[k]!=record[k] for k in ('scope','root','path','sha256','bytes')):
                raise RetentionBlocked('Deletion receipt contradicts approved member')
        else:
            self.value['files'][key]=record
            atomic_json(self.path,self.value)

    def mark(self, scope, root, path, state):
        if state not in {'deleted','missing_after_intent'}:
            raise RetentionBlocked('Unknown deletion state')
        key=fingerprint([scope,str(root),path])
        self.value['files'][key].update(state=state,updated=time.time())
        atomic_json(self.path,self.value)

    def close(self):
        pass


def journal_members(directory, scope, root):
    path=Path(directory)/'deletions.json'
    reject_links(path)
    if not path.exists(): return {}
    value=read_json(path)
    if value.get('version')!=1 or not isinstance(value.get('files'),dict):
        raise RetentionBlocked('Invalid deletion receipts')
    result={}
    for key,row in value['files'].items():
        if key!=fingerprint([row['scope'],row['root'],row['path']]):
            raise RetentionBlocked('Invalid receipt identity')
        if row['scope']==scope and row['root']==str(root):
            if row['state'] not in {'intent','deleted','missing_after_intent'}:
                raise RetentionBlocked('Invalid receipt state')
            result[row['path']]=row
    return result


@contextmanager
def processing_exclusion(config, scope, *, allow_existing=False):
    """Same O_EXCL/PID protocol as the existing batch orchestrator.

    Unknown/stale locks are never stolen. An interrupted cleaner may reconcile
    only its own recorded dead-process lease, under the OS cleaner lease.
    """
    config = Path(config).absolute()
    state = config/'state'; reject_links(state)
    if not state.is_dir(): raise RetentionBlocked('Persistent state root missing')
    directory = state/'verified-retention'; reject_links(directory)
    directory.mkdir(exist_ok=True)
    with cleanup_lock(directory):
        lease = state/'orchestrator.lock'; reject_links(lease)
        owner = directory/'processing-owner.json'
        if lease.exists() and allow_existing and lease.read_text(encoding='ascii').startswith(str(os.getpid())+' @ '):
            yield directory
            return
        if lease.exists():
            from create_people_posters.people_workspaces import process_alive
            previous = read_json(owner) if owner.exists() else {}
            text = lease.read_text(encoding='ascii')
            if (previous.get('scope') != scope or previous.get('lease') != text
                    or process_alive(previous.get('pid', -1))):
                raise RetentionBlocked('Processing lease present; retained')
            if lease.read_text(encoding='ascii') != text:
                raise RetentionBlocked('Processing lease changed; retained')
            lease.unlink()  # Exact, journal-owned dead cleaner lease only.
        token = f'{os.getpid()} @ retention-{uuid.uuid4().hex}'
        atomic_json(owner, dict(scope=scope, pid=os.getpid(), lease=token))
        try:
            descriptor = os.open(lease, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
        except FileExistsError:
            raise RetentionBlocked('Processor acquired shared exclusion; retained') from None
        with os.fdopen(descriptor, 'w', encoding='ascii') as stream:
            stream.write(token); stream.flush(); os.fsync(stream.fileno())
        try:
            yield directory
        finally:
            reject_links(lease)
            if lease.exists():
                if lease.read_text(encoding='ascii') != token:
                    raise RetentionBlocked('Processing lease ownership changed')
                lease.unlink()


def unlink_verified(root, row):
    """Only the exact inventoried file; never recursive delete or path globbing."""
    path = member(root, row['path'])
    current = inspect(path)
    if current != row['identity']:
        raise RetentionBlocked('File changed immediately before deletion')
    if os.name == 'nt':
        # Pin the file by handle, deny write/delete sharing, then delete that
        # handle's object after verifying its bytes. This closes rename races.
        import ctypes
        import msvcrt
        from ctypes import wintypes
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.CreateFileW.argtypes = [wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,
            wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        api.CreateFileW.restype = wintypes.HANDLE
        api.SetFileInformationByHandle.argtypes = [wintypes.HANDLE,ctypes.c_int,
            wintypes.LPVOID,wintypes.DWORD]
        api.SetFileInformationByHandle.restype = wintypes.BOOL
        handle = api.CreateFileW(str(path), 0x80000000|0x10000, 1, None, 3, 0x00200000, None)
        if handle == wintypes.HANDLE(-1).value:
            raise RetentionBlocked('Cannot exclusively pin deletion file')
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY)
        with os.fdopen(fd, 'rb') as stream:
            if identity(os.fstat(stream.fileno())) != {k:current[k] for k in identity(os.fstat(stream.fileno()))}:
                raise RetentionBlocked('Pinned deletion identity changed')
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != row['sha256'] or path.lstat().st_nlink != 1:
                raise RetentionBlocked('Pinned deletion bytes changed')
            flag = ctypes.c_ubyte(1)
            if not api.SetFileInformationByHandle(handle, 4, ctypes.byref(flag), ctypes.sizeof(flag)):
                raise RetentionBlocked('Pinned deletion refused by filesystem')
    else:
        parent = os.open(path.parent, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            info = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            if identity(info) != {k:current[k] for k in identity(info)} or info.st_nlink != 1:
                raise RetentionBlocked('Deletion identity changed')
            os.unlink(path.name, dir_fd=parent)
        finally: os.close(parent)
