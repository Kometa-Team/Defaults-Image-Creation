"""Style-bound review, backup and approval bridge for the existing native backend.

Review/preflight use read-only SQLite plus an in-memory registration rehearsal.
No new publisher or artwork validator is implemented here.
"""
from contextlib import closing, contextmanager
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import sqlite3
import sys
from tempfile import TemporaryDirectory

from people_github import GitHubClient, REPOSITORIES, repository_mapping
from people_git_transport import NativePublication, SOURCE_MEMBERS, canonical, digest, need
from people_publication_state import PublicationState
from people_remote_inventory import RemoteInventory
from people_workspaces import reject_links
from publish_people_github import Publisher

# Repo names come from the existing canonical mapping, never from operator input.
STYLES = {s: REPOSITORIES[s] for s in ('bw', 'diiivoy', 'diiivoycolor', 'rainier', 'signature')}
SOURCE = Path(__file__).resolve().parent


def selected(style):
    need(style in STYLES and repository_mapping().get(style) == STYLES[style])
    return STYLES[style]


def view(root, style='bw'):
    selected(style)
    obj = object.__new__(PublicationState)
    obj.state = Path(root).absolute() / style
    reject_links(obj.state / 'publication_state.db')
    obj.db = sqlite3.connect((obj.state / 'publication_state.db').as_uri()+'?mode=ro', uri=True)
    obj.db.row_factory = sqlite3.Row
    return obj


def has(db, table):
    return db.execute('SELECT 1 FROM sqlite_master WHERE name=?', (table,)).fetchone() is not None


def publisher(ledger, style, client=None):
    inventory = type('InventoryView', (), dict(branch='master', repositories={style: selected(style)}))()
    return Publisher(client, inventory, ledger)


@contextmanager
def transient_inventory(client, style):
    # Reuse the existing inventory schema/cache on every supported platform.
    # This disposable cache is outside the production state, closed before cleanup.
    with TemporaryDirectory(prefix='people-readonly-') as folder:
        with closing(RemoteInventory(client,database=Path(folder)/'inventory.db',branch='master')) as inventory:
            inventory.repositories={style:selected(style)}
            yield inventory


def context(root, validation, style, ledger):
    repo = selected(style)
    path = Path(root) / 'reconciliation.json'
    reject_links(path); reject_links(validation)
    raw = path.read_bytes(); plan = json.loads(raw)
    validated = Path(validation).read_bytes(); result = json.loads(validated)
    need(hashlib.sha256(validated).hexdigest() == plan['validation_sha256'])
    need(result.get('valid') is True and result.get('read_only') is True and result.get('errors') == [])
    need(result.get('verified') == result.get('planned') == sum(p['local_jpegs'] for p in plan['styles'].values()))
    need(set(plan['styles']) == set(result.get('styles', [])) == set(STYLES))
    need(result.get('batch_id') == plan['batch'] and result.get('source_commit') == plan['source_commit'])
    unit = plan['styles'][style]; batch = unit['unit']
    need(not unit['filename_case_conflicts'] and re.fullmatch('[0-9a-f]{40}', unit['head']))
    rows = ledger.rows(batch)
    need(rows and len(rows) == unit['local_jpegs'] and ledger.unit_binding(rows) == unit['entries_sha256'])
    need(all(r['style'] == style and r['repo'] == repo and r['branch'] == 'master' for r in rows))
    bases = {r[0]: r[1] or None for r in ledger.db.execute(
        'SELECT path,sha FROM baselines WHERE batch=? AND repo=?', (batch, repo))}
    need(bases == unit['baselines'])
    return dict(style=style, repo=repo, batch=batch, plan=unit, rows=rows,
                reconciliation_sha256=hashlib.sha256(raw).hexdigest())


def configure(ledger, info, contract=None):
    """Configure only an existing control or a fully reviewed virgin inventory."""
    batch, repo = info['batch'], info['repo']
    ledger.reliability_schema(); ledger.git_schema()
    old = ledger.db.execute('SELECT * FROM publication_controls WHERE batch=? AND repo=?', (batch, repo)).fetchone()
    prior = ledger.db.execute('SELECT contract FROM publication_git_controls WHERE batch=? AND repo=? ORDER BY rowid LIMIT 1',
                              (batch, repo)).fetchone()
    if old:
        # Existing migrated histories need their original native authority chain.
        # BW's pre-native continuation retains its frozen compatibility bridge.
        need(prior is not None)
        origin_review = json.loads(prior[0])['origin_review_sha256']
        settings = json.loads(old['settings'])
        expected = old['origin_head']
    else:
        need(not any(r['status'] != 'pending' or r['last_attempt'] or r['commit_sha'] for r in info['rows']))
        need(not ledger.db.execute('SELECT 1 FROM publication_units WHERE batch=? AND repo=?', (batch, repo)).fetchone())
        origin_review = ledger.legacy_review(batch, repo)
        expected = info['plan']['head']
        settings = publisher(ledger, info['style']).reliable_settings()
    need(re.fullmatch('[0-9a-f]{64}', origin_review))
    os.environ.update(PEOPLE_RELIABLE_PUBLISH='true', PEOPLE_PUBLICATION_BACKEND='git-v2',
        PEOPLE_PUBLICATION_EXPECTED_HEAD=expected, PEOPLE_PUBLICATION_LEGACY_REVIEW_SHA256=origin_review,
        PEOPLE_PUBLICATION_AUTHOR_NAME=settings['author'], PEOPLE_PUBLICATION_AUTHOR_EMAIL=settings['email'],
        PEOPLE_GITHUB_WRITE_INTERVAL=str(settings['write_interval']), PEOPLE_PUBLICATION_MAX_ATTEMPTS=str(settings['max_attempts']),
        PEOPLE_PUBLICATION_MAX_WAIT=str(settings['max_wait']), PEOPLE_PUBLICATION_MAX_ELAPSED=str(settings['max_elapsed']))
    if contract is not None:
        need(contract['repo'] == repo and contract['batch'] == batch and contract['branch'] == 'master')
        need(contract['reconciliation_sha256'] == info['reconciliation_sha256'])
        need(contract['origin_head'] == expected and contract['origin_review_sha256'] == origin_review)
        need(contract['settings_sha256'] == hashlib.sha256(json.dumps(settings, sort_keys=True, separators=(',', ':')).encode()).hexdigest())
    return ledger.reliability_control(batch, repo, expected, settings, origin_review)


def memory(original):
    obj = object.__new__(PublicationState); obj.state = original.state
    obj.db = sqlite3.connect(':memory:'); obj.db.row_factory = sqlite3.Row
    original.db.backup(obj.db)
    return obj


def review(ledger, info, limit):
    control = configure(ledger, info); batch, repo = info['batch'], info['repo']
    prior = ledger.db.execute('SELECT approval,contract FROM publication_git_controls WHERE batch=? AND repo=? ORDER BY rowid DESC LIMIT 1',
                              (batch, repo)).fetchone()
    previous = ''
    if prior:
        previous = prior[0]
        NativePublication(publisher(ledger, info['style']), contract=json.loads(prior[1]), approval=previous).validate(batch)
    rows = ledger.rows(batch, repo); published = [r for r in rows if r['status'] == 'published']
    units = [dict(r) for r in ledger.db.execute("SELECT * FROM publication_units WHERE batch=? AND repo=? AND unit!='readme' ORDER BY unit", (batch, repo))]
    return dict(version=2, backend='git-pack-v2', batch=batch, repo=repo, branch='master',
        origin_head=control['origin_head'], origin_review_sha256=os.environ['PEOPLE_PUBLICATION_LEGACY_REVIEW_SHA256'],
        reconciliation_sha256=info['reconciliation_sha256'], rows_binding=ledger.unit_binding(rows),
        initial_head=control['head'], initial_published_paths=[r['path'] for r in published], published_rows_sha256=digest(published),
        units_sha256=digest(units), settings_sha256=hashlib.sha256(control['settings'].encode()).hexdigest(),
        source_bindings={n:hashlib.sha256((SOURCE/n).read_bytes()).hexdigest() for n in SOURCE_MEMBERS},
        target_source_bytes=1_500_000_000, max_pack_bytes=1_850_000_000, max_posters=limit, git_timeout=7200, previous_approval=previous)


def fingerprints(root, validation, style):
    selected(style); root = Path(root)
    paths = [root/'reconciliation.json', *sorted((root/style).rglob('*'))]
    result = {}
    for p in paths:
        if p.is_file() and 'native-git-v2' not in p.relative_to(root).parts:
            reject_links(p)
            # Windows prevents reading our locked byte. The kernel lease is
            # neither a receipt nor recoverable ownership; never copy/delete it.
            if p.name == 'publication.lock': continue
            result[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    reject_links(validation); result['@validation'] = hashlib.sha256(Path(validation).read_bytes()).hexdigest()
    return result


def output_path(path, state):
    need(path is not None); reject_links(path)
    need(not path.absolute().is_relative_to(state.absolute()))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('operation', choices=['review','status','backup','preflight','migrate','run','verify'])
    ap.add_argument('--style', default=os.getenv('PEOPLE_GIT_STYLE', 'bw'))
    ap.add_argument('--state', type=Path, default=Path('/state'))
    ap.add_argument('--validation', type=Path, default=Path('/validation.json'))
    ap.add_argument('--approval', type=Path); ap.add_argument('--output', type=Path)
    ap.add_argument('--backup-receipt', type=Path); ap.add_argument('--max-posters', type=int, default=0)
    args = ap.parse_args(argv); selected(args.style)
    with closing(view(args.state, args.style)) as original:
        info = context(args.state, args.validation, args.style, original)
        batch, repo = info['batch'], info['repo']
        if args.operation == 'status':
            counts = original.reliability_progress(batch, repo) if has(original.db, 'publication_units') else {
                s:sum(r['status'] == s for r in info['rows']) for s in ('published','pending','failed')}
            print(json.dumps(dict(style=args.style, repository=repo, batch=batch, counts=counts,
                readme=original.readme_state(batch,repo)['status'], read_only=True))); return
        if args.operation == 'backup':
            output_path(args.output, args.state)
            with original.publication_lock():
                before = fingerprints(args.state,args.validation,args.style)
                args.output.mkdir(parents=True, exist_ok=False)
                for name in before:
                    if name == '@validation': continue
                    source=args.state/name; dest=args.output/'state'/name; dest.parent.mkdir(parents=True,exist_ok=True)
                    if source.suffix == '.db':
                        with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src, sqlite3.connect(dest) as dst: src.backup(dst)
                    else: shutil.copyfile(source,dest)
                need(before == fingerprints(args.state,args.validation,args.style))
                shutil.copyfile(args.validation,args.output/'validation.json')
                value=dict(version=3,style=args.style,repo=repo,batch=batch,source_checksums=before,
                           source_state_unmodified=True,native_object_workspace_excluded=True,kernel_lease_excluded=True)
                (args.output/'BACKUP.json').write_bytes(canonical(value))
                print(json.dumps(dict(style=args.style,backup_receipt_sha256=digest(value),artwork_writes=False))); return
        with closing(memory(original)) as rehearsed:
            if args.operation == 'review':
                need(0 <= args.max_posters <= 100000); output_path(args.output,args.state)
                value=review(rehearsed,info,args.max_posters)
                args.output.parent.mkdir(parents=True,exist_ok=True)
                with args.output.open('xb') as dest: dest.write(canonical(value)); dest.flush(); os.fsync(dest.fileno())
                print(json.dumps(dict(style=args.style,review_sha256=digest(value),publication_started=False))); return
            need(args.approval is not None); reject_links(args.approval)
            raw=args.approval.read_bytes(); contract=json.loads(raw); sha=hashlib.sha256(raw).hexdigest()
            configure(rehearsed,info,contract)
            backend=NativePublication(publisher(rehearsed,args.style),contract=contract,approval=sha)
            _, control, windows=backend.validate(batch)
        if args.operation in {'run','migrate'}:
            need(os.getenv('PEOPLE_PUBLICATION_MODE') == 'native-git-v2' and os.getenv('PEOPLE_GIT_APPROVAL_SHA256') == sha)
        if args.operation in {'migrate','run'}:
            # Do not create/open writable state until every selected binding and approval passes.
            with original.publication_lock():
                if args.operation == 'migrate':
                    need(args.backup_receipt is not None); reject_links(args.backup_receipt)
                    backup=json.loads(args.backup_receipt.read_bytes())
                    need((backup['style'],backup['repo'],backup['batch']) == (args.style,repo,batch))
                    need(backup['source_state_unmodified'] is True and backup['source_checksums'] == fingerprints(args.state,args.validation,args.style))
                    need(GitHubClient().head(repo,'master')[0] == contract['initial_head'])
                else:
                    need(has(original.db,'publication_git_controls') and original.db.execute(
                        'SELECT 1 FROM publication_git_controls WHERE batch=? AND repo=? AND approval=?',(batch,repo,sha)).fetchone())
                if args.operation == 'migrate':
                    with closing(PublicationState(args.state/args.style)) as ledger:
                        configure(ledger,info,contract)
                        NativePublication(publisher(ledger,args.style),contract=contract,approval=sha).validate(batch)
                    print(json.dumps(dict(style=args.style,migration_registered=True,artwork_writes=False))); return
            # Existing backend takes the same kernel lock for the complete publication.
            client=GitHubClient()
            with closing(PublicationState(args.state/args.style)) as ledger, closing(
                    RemoteInventory(client,database=args.state/args.style/'people_inventory.db',branch='master')) as inventory:
                inventory.repositories={args.style:repo}
                result=NativePublication(Publisher(client,inventory,ledger),contract=contract,approval=sha).publish(batch)
                print(json.dumps(result)); return
        client=GitHubClient()
        head, tree=client.head(repo,'master'); allowed={control['head']}
        allowed.update(w['tip'] for n,w in windows if w['stage'] in {'push_intent','pushed','remote_verified'})
        # Reuse the backend's correlated, repository-specific README recovery audit.
        if head not in allowed:
            with closing(memory(original)) as checked:
                configure(checked,info,contract)
                with transient_inventory(client,args.style) as inventory:
                    p=Publisher(client,inventory,checked)
                    NativePublication(p,contract=contract,approval=sha).audit_artwork(batch)
        for n,w in windows:
            if w['tree'] and head == w['tip']: need(tree == w['tree'])
        if args.operation == 'verify':
            with closing(memory(original)) as checked:
                configure(checked,info,contract)
                with transient_inventory(client,args.style) as inventory:
                    NativePublication(Publisher(client,inventory,checked),contract=contract,approval=sha).audit_artwork(batch)
                    need(checked.verified(batch))
            print(json.dumps(dict(style=args.style,verified=len(info['rows']),head=head,read_only=True))); return
        workflow=client.request('GET',f'/repos/{repo}/actions/workflows/readme.yml')
        need(workflow.get('state') == 'active' and workflow.get('path') == '.github/workflows/readme.yml')
        print(json.dumps(dict(style=args.style,repository=repo,preflight=True,read_only=True,head=head,actions_write_qualified=False)))


def cli(argv=None):
    def interrupt(signum,frame): raise KeyboardInterrupt()
    old=signal.signal(signal.SIGTERM,interrupt)
    try: main(argv); return 0
    except KeyboardInterrupt: print('[STOP] Graceful interruption; preserve state and resume.'); return 130
    except Exception as error:
        status=getattr(error,'status',0); status=status if type(status) is int and 0 <= status <= 599 else 0
        print('[STOP] category=style_state_or_approval http_status='+str(status),file=sys.stderr); return 1
    finally: signal.signal(signal.SIGTERM,old)


if __name__ == '__main__': raise SystemExit(cli())
