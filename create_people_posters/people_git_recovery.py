"""One-use, explicitly approved recovery of an unchanged blocked native window.

Uses the existing inventory, publisher, locks, validation and README recovery.
No split, replan, credential argument or original-approval replacement is supported.
"""
from contextlib import closing, contextmanager
from pathlib import Path
import argparse
import hashlib
import json
import os
import signal
import sys

from people_github import GitHubClient
from people_git_transport import NativePublication, canonical, digest, need
from people_native_operator import (configure, context, fingerprints, memory,
    output_path, publisher, selected, transient_inventory, view)
from people_publication_state import PublicationState
from people_remote_inventory import RemoteInventory
from people_workspaces import reject_links
from publish_people_github import Publisher

# Bind the already deployed host lease here; never substitute or remove it.
LEASE=Path('/publication-writer.lease')


@contextmanager
def writer_lease(path=None):
    path=LEASE if path is None else path
    reject_links(path);need(path.is_file())
    with path.open('r+b' if os.name=='nt' else 'rb') as stream:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:
            if os.name=='nt':stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(stream.fileno(),fcntl.LOCK_UN)


def read_json(path):
    need(path is not None);reject_links(path)
    raw=path.read_bytes();return json.loads(raw),hashlib.sha256(raw).hexdigest()


def check_backup(args,info,sha,recorded):
    backup,actual=read_json(args.backup_receipt);need(sha==actual)
    need((backup['style'],backup['repo'],backup['batch'])==(args.style,info['repo'],info['batch']))
    need(backup['source_state_unmodified'] is True and backup['native_object_workspace_excluded'] is True)
    if not recorded:need(backup['source_checksums']==fingerprints(args.state,args.validation,args.style))


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('operation',choices=['review','recover','verify'])
    ap.add_argument('--style',required=True,choices=['diiivoycolor','rainier','signature'])
    ap.add_argument('--state',type=Path,default=Path('/state'))
    ap.add_argument('--validation',type=Path,default=Path('/validation.json'))
    ap.add_argument('--approval',type=Path,required=True)
    ap.add_argument('--backup-receipt',type=Path,required=True)
    ap.add_argument('--window',type=int)
    ap.add_argument('--output',type=Path)
    ap.add_argument('--recovery',type=Path)
    args=ap.parse_args(argv);selected(args.style)
    contract,approval=read_json(args.approval)
    if args.operation!='review':
        value,sha=read_json(args.recovery)
        need(sha==digest(value)==os.getenv('PEOPLE_GIT_RECOVERY_SHA256',''))
        if args.operation=='recover':
            need(os.getenv('PEOPLE_PUBLICATION_MODE')=='native-git-v2'
                 and os.getenv('PEOPLE_GIT_APPROVAL_SHA256','')==approval)
    # Also protects read-only review against a competing deployed writer.
    with writer_lease(), closing(view(args.state,args.style)) as original, writer_lease(original.state/'publication.lock'):
        info=context(args.state,args.validation,args.style,original)
        with closing(memory(original)) as rehearsed:
            configure(rehearsed,info,contract)
            backend=NativePublication(publisher(rehearsed,args.style),contract=contract,approval=approval)
            if args.operation=='review':
                _,backup_sha=read_json(args.backup_receipt)
                check_backup(args,info,backup_sha,False)
                value=backend.recovery_review(info['batch'],args.window,backup_sha)
                client=GitHubClient()
                need(client.head(info['repo'],'master')[0] in {value['parent'],value['tip']})
                output_path(args.output,args.state)
                with args.output.open('xb') as out:out.write(canonical(value));out.flush();os.fsync(out.fileno())
                print(json.dumps(dict(recovery_sha256=digest(value),read_only=True,publication_started=False)))
                return
            backend.validate(info['batch'],recovery=value)
            check_backup(args,info,value['backup_sha256'],bool(rehearsed.git_recovery(info['batch'],info['repo'],digest(value))))
            if args.operation=='verify':
                with transient_inventory(GitHubClient(),args.style) as inventory:
                    checked=NativePublication(Publisher(inventory.client,inventory,rehearsed),contract=contract,approval=approval)
                    checked.validate(info['batch'],recovery=value);checked.audit_artwork(info['batch'])
                    need(rehearsed.verified(info['batch']))
                    print(json.dumps(dict(verified=len(info['rows']),style=args.style,read_only=True)))
                return
        # NativePublication takes the same per-style kernel lock below. It must
        # not be re-entered while this read-only handle owns it.
    # Reacquire the global lease before writable state; native validation and
    # exact CAS repeat all state/ownership checks under the per-style lock.
    with writer_lease(), closing(PublicationState(args.state/args.style)) as ledger:
        client=GitHubClient()
        with closing(RemoteInventory(client,database=args.state/args.style/'people_inventory.db',branch='master')) as inventory:
            inventory.repositories={args.style:info['repo']}
            result=NativePublication(Publisher(client,inventory,ledger),contract=contract,approval=approval).publish(info['batch'],recovery=value)
            print(json.dumps(result))


def cli(argv=None):
    def interrupt(signum,frame):raise KeyboardInterrupt()
    previous=signal.signal(signal.SIGTERM,interrupt)
    try:main(argv);return 0
    except KeyboardInterrupt:print('[STOP] Graceful interruption; preserve recovery receipt and resume.');return 130
    except Exception:
        # Exact closed facts, if any, are in the journal. Never interpolate an
        # arbitrary exception, credential, command, URL or provider response.
        print('[STOP] category=recovery_authorization_state_or_transport',file=sys.stderr);return 1
    finally:signal.signal(signal.SIGTERM,previous)


if __name__=='__main__':raise SystemExit(cli())
