"""Git-owned Playlist reservations, separate from synthetic lifecycle records.

All writes are local compare-and-swap commits. No network write or publication
approval is created here. Production publication requires the reservation commit
to be present on the independently controlled catalog owner's main branch.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
from io import BytesIO
import os
from pathlib import Path
import re
import subprocess
import tempfile

from PIL import Image

from .common import BulkError, Conflict, canonical, fingerprint, path_key, reject_links
from .contracts.models import decode_json
from .definitions import load_definitions
from .lifecycle.catalog_preparation import patch_yaml, patch_index
from .lifecycle.identities import IdentityRegistry, validate_namespace
from .lifecycle.identity_models import entry_check, validator
from .library_sources import sealed, check_seal

REPOSITORY = 'Kometa-Team/Defaults-Image-Creation'
CATALOG = 'create_defaults/bulk/catalog/'
LEDGER = CATALOG+'reservations-v1.json'
PLAYLIST = CATALOG+'playlist.yml'
INDEX = CATALOG+'index-v1.json'
PROFILES = CATALOG+'profiles.yml'


def fail(code):
    raise BulkError('catalog_reservations_'+code, 'Catalog reservation rejected: '+code)


def git(root, *args, data=None, env=None):
    result = subprocess.run(['git', '-C', str(root), *args], input=data,
                            capture_output=True, env=env, timeout=180)
    if result.returncode:
        fail('git_or_cas')
    return result.stdout


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class Entries:
    values: tuple

    def to_dict(self):
        return dict(entries=list(self.values))


class _Allocator:
    """Storage bridge for the unchanged M2 allocator; no synthetic record minted."""
    def __init__(self, reserve):
        self._mutate = reserve

    allocate = IdentityRegistry.allocate


class CatalogReservations:
    def __init__(self, root, *, ref, owner, destination_root, destination_head):
        self.root = reject_links(root).resolve()
        self.destination_root = reject_links(destination_root).resolve()
        self.ref, self.owner = ref, deepcopy(owner)
        self.destination_head = destination_head
        if (set(owner) != {'repository', 'branch', 'environment'}
                or owner['repository'] != REPOSITORY or owner['branch'] != 'main'
                or owner['environment'] not in {'staging', 'production'}
                or re.fullmatch(r'refs/heads/[a-zA-Z0-9/_-]+', ref) is None
                or re.fullmatch('[0-9a-f]{40}', destination_head) is None):
            fail('owner')
        if owner['environment'] == 'production':
            origin = git(self.root, 'remote', 'get-url', 'origin').decode().strip()
            if ref != 'refs/heads/main' or origin not in {
                    'https://github.com/'+REPOSITORY+'.git',
                    'git@github.com:'+REPOSITORY+'.git'}:
                fail('production_owner')
        # Complete immutable Git namespace, including directories. Callers cannot
        # provide a filtered list or synthetic hashes for the public namespace.
        output = git(self.destination_root, 'ls-tree', '-r', '-t', '-z', destination_head)
        self.external = []
        for row in filter(None, output.split(b'\0')):
            meta, path = row.split(b'\t', 1)
            mode, kind, oid = meta.decode().split()
            if mode not in {'040000', '100644', '100755'} or kind not in {'tree', 'blob'}:
                fail('destination_mode')
            self.external.append(dict(namespace='public', path=path.decode('utf8'),
                kind='directory' if kind == 'tree' else 'file', sha256=fingerprint(dict(mode=mode, object=oid))))

    def head(self):
        return git(self.root, 'rev-parse', self.ref).decode().strip()

    def read(self, head, path):
        entry = git(self.root, 'ls-tree', head, '--', path).split(b'\0')[0]
        if not entry.startswith(b'100644 blob ') or not entry.rstrip(b'\n').endswith(b'\t'+path.encode()):
            fail('missing_or_nonregular_catalog')
        return git(self.root, 'show', head+':'+path)

    def _commit(self, head, files, message):
        # A private index avoids touching the contributor's worktree or index.
        with tempfile.TemporaryDirectory(prefix='catalog-reservation-index-') as folder:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(folder)/'index'),
                GIT_AUTHOR_NAME='Catalog reservation staging', GIT_COMMITTER_NAME='Catalog reservation staging',
                GIT_AUTHOR_EMAIL='catalog-reservations@users.noreply.github.com',
                GIT_COMMITTER_EMAIL='catalog-reservations@users.noreply.github.com')
            git(self.root, 'read-tree', head, env=env)
            for path, raw in files.items():
                oid = git(self.root, 'hash-object', '-w', '--stdin', data=raw).decode().strip()
                git(self.root, 'update-index', '--add', '--cacheinfo', '100644,'+oid+','+path, env=env)
            tree = git(self.root, 'write-tree', '--missing-ok', env=env).decode().strip()
            commit = git(self.root, 'commit-tree', tree, '-p', head, data=(message+'\n').encode(), env=env).decode().strip()
        result = subprocess.run(['git', '-C', str(self.root), 'update-ref', self.ref, commit, head], capture_output=True)
        if result.returncode:
            raise Conflict('Registry head changed; reread and retry the same token')
        return commit

    def bootstrap_staging(self, *, expected):
        if self.owner['environment'] != 'staging':
            fail('production_bootstrap_requires_reviewed_owner_commit')
        if self.head() != expected:
            raise Conflict('Registry head changed')
        if git(self.root, 'ls-tree', expected, '--', LEDGER).strip():
            fail('already_initialized')
        value = sealed(dict(version=1, kind='catalog-reservations', owner=self.owner,
            base_commit=expected, parent=expected, destination_head=self.destination_head,
            entries=[], requests=[], publication_authorized=False))
        return self._commit(expected, {LEDGER:canonical(value)+b'\n'}, 'Initialize staging catalog reservation owner')

    def _definitions(self, head):
        with tempfile.TemporaryDirectory(prefix='catalog-reservation-validate-') as folder:
            folder = Path(folder)
            for path in (PLAYLIST, PROFILES):
                (folder/Path(path).name).write_bytes(self.read(head, path))
            return {r.id:r.data for r in load_definitions([folder/'playlist.yml'], profiles_path=folder/'profiles.yml')}

    def state(self):
        head = self.head()
        value = check_seal(decode_json(self.read(head, LEDGER)))
        if (set(value) != {'version','kind','owner','base_commit','parent','destination_head','entries','requests','publication_authorized','sha256'}
                or value['version'] != 1 or value['kind'] != 'catalog-reservations'
                or value['owner'] != self.owner or value['publication_authorized'] is not False
                or value['destination_head'] != self.destination_head
                or len(value['entries']) != len(value['requests']) or len(value['entries']) > 4096
                or re.fullmatch('[0-9a-f]{40}', value['parent']) is None):
            fail('ledger')
        # A reviewed catalog PR may add a merge commit above the reservation
        # commits. Require ancestry, not an exact first-parent shape.
        git(self.root, 'merge-base', '--is-ancestor', value['parent'], head)
        event=git(self.root,'log','--no-merges','-1','--format=%H',head,'--',LEDGER).decode().strip()
        if (not event or self.read(event,LEDGER) != self.read(head,LEDGER)
                or git(self.root,'rev-parse',event+'^').decode().strip() != value['parent']):
            fail('reservation_history')
        if git(self.root,'ls-tree',value['parent'],'--',LEDGER).strip():
            previous=check_seal(decode_json(self.read(value['parent'],LEDGER)))
            old_entries={e['id']:e for e in previous['entries']}
            old_requests={r['token']:r for r in previous['requests']}
            current_entries={e['id']:e for e in value['entries']}
            current_requests={r['token']:r for r in value['requests']}
            if (previous['owner'] != value['owner'] or previous['base_commit'] != value['base_commit']
                    or len(value['requests']) != len(previous['requests'])+1
                    or any(current_entries.get(i)!=e for i,e in old_entries.items())
                    or any(current_requests.get(t)!=r for t,r in old_requests.items())):
                fail('reservation_history_erasure')
        elif value['entries'] or value['requests'] or value['base_commit'] != value['parent']:
            fail('bootstrap_history')
        entries = {e['id']:e for e in value['entries']}
        tokens = [r['token'] for r in value['requests']]
        if (len(entries) != len(value['entries']) or len(tokens) != len(set(tokens))
                or {r['identity'] for r in value['requests']} != set(entries)):
            fail('duplicate')
        definitions, initial = self._definitions(head), self._definitions(value['base_commit'])
        old_index = check_seal(decode_json(self.read(value['base_commit'], INDEX)))['posters']
        index = check_seal(decode_json(self.read(head, INDEX)))['posters']
        if (any(definitions.get(i) != d for i,d in initial.items())
                or any(index.get(i) != d for i,d in old_index.items())
                or set(definitions) != set(initial)|set(entries)
                or set(index) != set(old_index)|set(entries)
                or self.read(head, PROFILES) != self.read(value['base_commit'], PROFILES)):
            fail('historical_catalog_change')
        for row in value['requests']:
            if (set(row) != {'token','request','request_sha256','identity','definition_sha256','approved_jpeg_sha256'}
                    or row['request_sha256'] != fingerprint(row['request']) or row['identity'] not in entries):
                fail('request_binding')
            entry = entries[row['identity']]
            if next(validator('entry').iter_errors(entry), None):
                fail('entry_schema')
            entry_check(entry)
            definition = definitions[entry['id']]
            request=row['request']
            if (any(entry[k] != request[k] for k in ('category','semantic','variant','names'))
                    or entry['origin'] != 'assigned' or entry['historical_sha256'] is not None
                    or entry['category'] != 'Playlist' or entry['variant'] != 'timeline-order'
                    or entry['semantic']['role'] != 'single' or entry['semantic']['language'] != 'en'
                    or entry['original_names'] != entry['names'] or entry['aliases'] or entry['revision'] != 1
                    or row['approved_jpeg_sha256'] != request['approved_jpeg_sha256']
                    or fingerprint(definition) != row['definition_sha256']
                    or definition['color_assignment']['id'] != entry['id']+'.background'
                    or definition['composer']['logo'] != entry['names']['source']['path']
                    or definition['output']['remote_paths'] != {'en':entry['names']['public_path']}
                    or index.get(entry['id']) != dict(definition=entry['id'],category='Playlist',dependencies=[])
                    or sha(self.read(head, 'create_defaults/'+entry['names']['source']['path'])) != entry['names']['source']['sha256']):
                fail('mapping_binding')
        validate_namespace(Entries(tuple(value['entries'])), self.external)
        return head, value

    def reserve(self, *, category, semantic, variant, names, token, expected,
                definition, logo, approved_jpeg_sha256):
        semantic,names,definition=deepcopy(semantic),deepcopy(names),deepcopy(definition)
        if (category != 'Playlist' or variant != 'timeline-order'
                or semantic['role'] != 'single' or semantic['language'] != 'en'
                or not isinstance(token, str) or not 1 <= len(token) <= 200
                or re.fullmatch('[0-9a-f]{64}', approved_jpeg_sha256) is None):
            fail('scope')
        if type(logo) is not bytes or sha(logo) != names['source']['sha256'] or len(logo) > 20*1024*1024:
            fail('logo')
        with Image.open(BytesIO(logo)) as image:
            if image.format != 'PNG' or image.width*image.height > 25_000_000:
                fail('logo')
            image.verify()
        name = names['display_name']+' (Timeline Order).jpg'
        if (names['public_path'] != 'playlist/'+name or names['local_path'] != 'defaults-en/playlist/'+name
                or names['rendered_caption'] != 'TIMELINE ORDER'
                or not names['source']['path'].startswith('logos_playlist/')
                or not names['source']['path'].endswith('.png')):
            fail('names')
        context = dict(definition=definition, approved_jpeg_sha256=approved_jpeg_sha256)
        def mutate(token, request, expected, action):
            head, value = self.state()
            complete = dict(request, **context)
            request_hash = fingerprint(complete)
            for row in value['requests']:
                if row['token'] == token:
                    if row['request_sha256'] != request_hash:
                        raise Conflict('Idempotency token already binds a different request')
                    return dict(entry=deepcopy(next(e for e in value['entries'] if e['id']==row['identity'])), commit=head, reused=True)
            if head != expected:
                raise Conflict('Registry head changed')
            entry = action(deepcopy(value['entries']), None)
            if next(validator('entry').iter_errors(entry), None):
                fail('entry_schema')
            entry_check(entry)
            source = 'create_defaults/'+names['source']['path']
            paths = [p.decode('utf8') for p in git(self.root,'ls-tree','-r','--name-only','-z',head).split(b'\0') if p]
            if any(path_key(p)==path_key(source) for p in paths):
                raise Conflict('Source path is already owned; this API only adds new sources')
            value['entries'].append(entry)
            validate_namespace(Entries(tuple(value['entries'])), self.external)
            candidate = deepcopy(definition)
            candidate['id'] = entry['id']
            candidate['color_assignment']['id'] = entry['id']+'.background'
            candidate['composer']['logo'] = names['source']['path']
            if (candidate['display_name'] != names['display_name'] or candidate['category'] != category
                    or candidate['output']['remote_paths'] != {'en':names['public_path']}
                    or candidate['output']['filename'] != name or candidate['composer']['out_name']+'.jpg' != name
                    or candidate['dependencies'] != []):
                fail('definition_mapping')
            files = {PLAYLIST:patch_yaml(self.read(head,PLAYLIST),{entry['id']:candidate}),
                     INDEX:patch_index(self.read(head,INDEX),{entry['id']:candidate},category='Playlist'), source:logo}
            # Resolve profiles/defaults with the normal loader before the CAS.
            with tempfile.TemporaryDirectory(prefix='catalog-reservation-proposal-') as folder:
                folder=Path(folder)
                (folder/'playlist.yml').write_bytes(files[PLAYLIST])
                (folder/'profiles.yml').write_bytes(self.read(head,PROFILES))
                resolved={r.id:r.data for r in load_definitions([folder/'playlist.yml'],profiles_path=folder/'profiles.yml')}
            value['requests'].append(dict(token=token,request=complete,request_sha256=request_hash,
                identity=entry['id'],definition_sha256=fingerprint(resolved[entry['id']]),approved_jpeg_sha256=approved_jpeg_sha256))
            value['parent']=head
            value['entries'].sort(key=lambda e:e['id']);value['requests'].sort(key=lambda r:r['token'])
            value=sealed({k:v for k,v in value.items() if k!='sha256'})
            files[LEDGER]=canonical(value)+b'\n'
            commit=self._commit(head,files,'Reserve Playlist identity and mapping: '+token)
            return dict(entry=deepcopy(entry),commit=commit,reused=False)
        return _Allocator(mutate).allocate(category=category,semantic=semantic,variant=variant,
                                          names=names,token=token,expected=expected)

    def publication_inventory(self, approved_files, *, expected):
        """Bind assigned IDs to original operator prepare(), without approval."""
        head, value = self.state()
        if head != expected:
            raise Conflict('Registry head changed')
        if self.owner['environment'] == 'production':
            remote = git(self.root,'ls-remote','origin','refs/heads/main').decode().split()
            if not remote or remote[0] != head:
                fail('reservation_commit_not_published_on_catalog_main')
        entries={e['id']:e for e in value['entries']}
        if set(approved_files) != set(entries):
            fail('publication_membership')
        baseline=dict(repository='Kometa-Team/Default-Images',branch='master',head=self.destination_head,
            tree=git(self.destination_root,'rev-parse',self.destination_head+'^{tree}').decode().strip())
        rows=[]
        for row in value['requests']:
            identity=row['identity'];entry=entries[identity];path=reject_links(approved_files[identity])
            raw=path.read_bytes()
            if sha(raw)!=row['approved_jpeg_sha256']:
                fail('approved_jpeg_drift')
            with Image.open(BytesIO(raw)) as image:
                image.load()
                if (image.format,image.mode,image.size)!=('JPEG','RGB',(2000,3000)):
                    fail('jpeg')
            rows.append(dict(destination=entry['names']['public_path'],candidate_path=str(path),candidate_sha256=sha(raw),
                candidate_blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),
                published_sha256=None,published_blob='0'*40,hash_state='missing',technical_valid=True,
                difference_class='approved_playlist_addition',context_sha256=fingerprint(dict(registry_commit=head,identity=identity)),kind='poster',proposed_review_scope='individual'))
        return sealed(dict(baseline=baseline,registry_commit=head,registry_owner=self.owner,
            source_hashes={str(reject_links(p)):sha(Path(p).read_bytes()) for p in approved_files.values()},rows=rows))

    def prepare_publication(self, root, approved_files, *, expected):
        from .operator_publication import prepare
        from .library_sources import save
        inventory=self.publication_inventory(approved_files,expected=expected)
        policy=dict(version=1,scope='Exact reserved Playlist additions',registry_commit=expected,
            registry_owner=self.owner,allowed_additions=sorted(r['destination'] for r in inventory['rows']),
            merge_authorized=False,activation_authorized=False)
        save(Path(root)/'inventory.json',inventory)
        return prepare(inventory,policy,root)

    def stage_publication(self, root, *, expected):
        """Fresh registry, mapping and JPEG proof before every transport mutation."""
        from .operator_publication import stage
        from .library_sources import load_json
        root=reject_links(root)
        if self.owner['environment'] != 'production':
            fail('staging_cannot_write_network')
        inventory=check_seal(load_json(root/'inventory.json'))
        files={r['identity']:Path(next(row['candidate_path'] for row in inventory['rows']
            if row['destination']==r['request']['names']['public_path'])) for r in self.state()[1]['requests']}
        def guard(**_):
            if self.publication_inventory(files,expected=expected) != inventory:
                fail('stale_publication_inventory')
        guard()
        return stage(root,write_guard=guard)
