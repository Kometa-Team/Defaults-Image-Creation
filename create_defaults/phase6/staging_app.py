"""Loopback-only generated-poster submission/review/staging prototype.

Fixture access codes identify two local test roles, not production identities.
The owned filesystem destination never selects a live repository or publisher.
"""
import argparse
import hashlib
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import stat
import tempfile
from threading import RLock

from PIL import Image

HERE = Path(__file__).resolve().parent
MAX_POST = 3 * 1024 * 1024


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Rejected(ValueError):
    def __init__(self, code, status=409):
        super().__init__(code)
        self.status = status


def regular(path):
    for part in (path, *path.parents):
        if part.exists():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise Rejected('linked_path')
    if not path.is_file():
        raise Rejected('missing_regular_file')
    return path.read_bytes()


class Staging:
    def __init__(self, fixtures, root, *, source_proof=lambda: None):
        self.fixtures, self.root = Path(fixtures).absolute(), Path(root).absolute()
        self.source_proof = source_proof
        self.lock = RLock()
        self.manifest_path = self.fixtures / 'ten-item-fixtures.json'
        raw = regular(self.manifest_path)
        self.manifest_hash = sha(raw)
        value = json.loads(raw)
        self.entries = {r['identity']: r for r in value['entries']}
        if len(self.entries) != 10 or sum(r['action']=='CREATE' for r in self.entries.values()) != 8 or sum(r['action']=='REPLACE' for r in self.entries.values()) != 2:
            raise Rejected('exact_ten_fixture_members_required')
        approve = json.loads(regular(self.fixtures / 'eight-create-visual-approval.json'))
        replacements = json.loads(regular(self.fixtures / 'two-replacement-visual-approval.json'))
        approved = {r['display_name']:r['sha256'] for r in approve['posters']}
        approved.update({r['display_name']:r['approved_sha256'] for r in replacements['replacements']})
        if any(approved.get(r['display_name']) != r['approved_sha256'] for r in self.entries.values()):
            raise Rejected('visual_approval_binding')
        paths = set()
        for row in self.entries.values():
            path = PurePosixPath(row['destination'])
            if len(path.parts) != 2 or path.parts[0] != 'playlist' or path.suffix != '.jpg' or path.name in ('.', '..') or '\\' in str(path) or str(path).casefold() in paths:
                raise Rejected('fixture_destination')
            paths.add(str(path).casefold())
            if sha(regular(self.fixtures / row['approved_file'])) != row['approved_sha256']:
                raise Rejected('fixture_approved_jpeg_changed')
        # A new owned root only: callers cannot adopt a live/existing destination.
        self.root.mkdir(parents=True, exist_ok=False)
        self.ownership = secrets.token_hex(32).encode()
        (self.root/'owned-staging.marker').write_bytes(self.ownership)
        self.destination = self.root / 'destination'
        shutil.copytree(self.fixtures / 'staging-baseline', self.destination)
        self.objects = self.root / 'objects'
        self.objects.mkdir()
        self.expected = self.inventory()
        self.baseline = dict(self.expected)
        if len(self.baseline) != 9:
            raise Rejected('nine_historical_fixture_preimages_required')
        for row in self.entries.values():
            actual = self.baseline.get(row['destination'])
            if row['precondition']['exists'] != (actual is not None) or actual != row['precondition']['sha256']:
                raise Rejected('fixture_preimage')
        self.submissions, self.sessions = {}, {}
        self.codes = {role:secrets.token_urlsafe(24) for role in ('contributor','maintainer')}
        self._save('fixture-access.json', dict(scope='local fixture roles only', access_codes=self.codes))
        self.source_proof()
        self.persist()

    def _save(self, name, value):
        raw = (json.dumps(value, indent=2) + '\n').encode()
        fd, temporary = tempfile.mkstemp(dir=self.root)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.root / name)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def inventory(self):
        result = {}
        for directory, dirs, files in os.walk(self.destination, followlinks=False):
            for name in dirs:
                child = Path(directory) / name
                info = child.lstat()
                if child.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
                    raise Rejected('linked_destination')
            for name in files:
                path = Path(directory) / name
                result[path.relative_to(self.destination).as_posix()] = sha(regular(path))
        return result

    def guard(self):
        if regular(self.root/'owned-staging.marker') != self.ownership or sha(regular(self.manifest_path)) != self.manifest_hash or self.inventory() != self.expected:
            raise Rejected('staging_or_fixture_drift')

    def persist(self):
        self._save('staging-receipts.json', dict(kind='offline-browser-staging-receipts', simulation=True,
            fixture_manifest_sha256=self.manifest_hash, submissions=list(self.submissions.values()),
            destination_inventory=self.expected, live_registry_reservations='PENDING', catalog_mappings='PENDING',
            publication_authorized=False, activation_authorized=False))

    def login(self, role, code):
        if role not in self.codes or not secrets.compare_digest(code, self.codes[role]):
            raise Rejected('invalid_fixture_access_code', 403)
        token = secrets.token_urlsafe(32)
        self.sessions[token] = dict(role=role, csrf=secrets.token_urlsafe(32))
        return token

    def object_bytes(self, submission):
        raw = regular(self.objects / (submission['sha256'] + '.jpg'))
        if sha(raw) != submission['sha256']:
            raise Rejected('preview_object_changed')
        return raw

    def submit(self, role, identity, raw):
        with self.lock:
            if role != 'contributor':
                raise Rejected('contributor_required', 403)
            self.guard()
            row = self.entries.get(identity)
            if row is None or sha(raw) != row['approved_sha256']:
                raise Rejected('unapproved_fixture_render', 400)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format != 'JPEG' or image.size != (2000,3000):
                    raise Rejected('poster_dimensions_or_format', 400)
                image.verify()
            if any(r['identity']==identity for r in self.submissions.values()):
                raise Rejected('fixture_already_submitted')
            object_path = self.objects / (row['approved_sha256'] + '.jpg')
            with object_path.open('xb') as stream:
                stream.write(raw)
            sid = secrets.token_hex(12)
            self.submissions[sid] = dict(id=sid, identity=identity, display_name=row['display_name'],
                destination=row['destination'], action=row['action'], sha256=row['approved_sha256'],
                status='preview', approved_sha256=None, receipt=None)
            self.persist()
            return self.submissions[sid]

    def approve(self, role, sid, expected_hash):
        with self.lock:
            if role != 'maintainer':
                raise Rejected('maintainer_required', 403)
            self.guard()
            item = self.submissions[sid]
            self.object_bytes(item)
            if item['status'] != 'preview' or expected_hash != item['sha256']:
                raise Rejected('stale_or_wrong_render_approval')
            item.update(status='approved', approved_sha256=expected_hash)
            self.persist()
            return item

    def stage(self, role, sid, expected_hash):
        with self.lock:
            if role != 'maintainer':
                raise Rejected('maintainer_required', 403)
            self.source_proof()
            self.guard()
            item = self.submissions[sid]
            raw = self.object_bytes(item)
            if item['status'] != 'approved' or item['approved_sha256'] != expected_hash or expected_hash != sha(raw):
                raise Rejected('exact_render_approval_required')
            row = self.entries[item['identity']]
            target = self.destination / row['destination']
            before = sha(regular(target)) if target.exists() else None
            if before != row['precondition']['sha256'] or target.exists() != row['precondition']['exists']:
                raise Rejected('create_or_replace_precondition')
            fd, temporary = tempfile.mkstemp(dir=self.root)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                # The application owns this root and serializes all mutations.
                self.guard()
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            if sha(regular(target)) != expected_hash:
                raise Rejected('destination_hash_mismatch')
            proposed = dict(self.expected, **{row['destination']:expected_hash})
            if self.inventory() != proposed:
                raise Rejected('unexpected_destination_change')
            self.source_proof()
            self.expected = proposed
            item.update(status='staged', receipt=dict(identity=item['identity'], destination=str(target),
                relative_path=row['destination'], action=row['action'], previous_sha256=before,
                approved_sha256=expected_hash, destination_sha256=sha(regular(target)), match=True,
                reviewer_role='fixture.maintainer', simulation=True, publication_authorized=False))
            self.persist()
            return item


def server_for(app, port=0):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, status, raw, content='application/json', headers=()):
            self.send_response(status)
            self.send_header('Content-Type',content)
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'")
            for key,value in headers:
                self.send_header(key,value)
            self.end_headers()
            self.wfile.write(raw)

        def json(self, value, status=200, headers=()):
            self.send(status,json.dumps(value).encode(),headers=headers)

        def session(self):
            jar=cookies.SimpleCookie(self.headers.get('Cookie',''))
            token=jar.get('staging_session')
            value=app.sessions.get(token.value if token else '')
            if value is None:
                raise Rejected('fixture_login_required',401)
            return value

        def do_GET(self):
            try:
                if self.path=='/':
                    self.send(200,(HERE/'staging_app.html').read_bytes(),'text/html; charset=utf-8')
                elif self.path=='/staging_app.js':
                    self.send(200,(HERE/'staging_app.js').read_bytes(),'text/javascript; charset=utf-8')
                elif self.path=='/api/state':
                    session=self.session()
                    with app.lock:
                        app.guard()
                        self.json(dict(**session, **app.form_state(),
                            submissions=[app.review(item) for item in app.submissions.values()]))
                elif self.path.startswith('/preview/'):
                    self.session()
                    item=app.submissions[self.path.removeprefix('/preview/')]
                    self.send(200,app.object_bytes(item),'image/jpeg')
                elif self.path.startswith('/current/'):
                    self.session()
                    item=app.submissions[self.path.removeprefix('/current/')]
                    self.send(200,app.object_bytes(dict(sha256=item['current_preview_sha256'])),'image/jpeg')
                elif self.path.startswith('/catalog-preview/'):
                    self.session()
                    with app.lock:
                        app.guard()
                        item=app.catalog[self.path.removeprefix('/catalog-preview/')]
                        if item['status']!='active': raise Rejected('active_poster_required')
                        raw=regular(app.destination/item['destination'])
                        if sha(raw)!=item['sha256']: raise Rejected('catalog_file_mismatch')
                        self.send(200,raw,'image/jpeg')
                else:
                    self.json(dict(error='not_found'),404)
            except (Rejected,KeyError) as error:
                self.json(dict(error=str(error)),getattr(error,'status',404))

        def do_POST(self):
            try:
                origin='http://127.0.0.1:'+str(self.server.server_port)
                if self.headers.get('Host') != '127.0.0.1:'+str(self.server.server_port) or self.headers.get('Origin') != origin:
                    raise Rejected('same_origin_required',403)
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=MAX_POST or self.headers.get('Content-Type')!='application/json':
                    raise Rejected('bounded_json_required',400)
                data=json.loads(self.rfile.read(length))
                if self.path=='/api/login':
                    token=app.login(data['role'],data['code'])
                    self.json(dict(ok=True),headers=[('Set-Cookie','staging_session='+token+'; HttpOnly; SameSite=Strict; Path=/')])
                    return
                session=self.session()
                if not secrets.compare_digest(self.headers.get('X-CSRF-Token',''),session['csrf']):
                    raise Rejected('csrf_required',403)
                if self.path=='/api/generate':
                    result=app.generate_request(session['role'],intent=data['intent'],title=data.get('title',''),
                        identity=data.get('identity'),style=data.get('style'),logo=data.get('logo'),
                        upload=data.get('upload'),colour=data.get('colour'),caption=data.get('caption',''))
                elif self.path=='/api/submit':
                    result=app.submit_generated(session['role'],data['id'])
                elif self.path=='/api/remove':
                    result=app.request_removal(session['role'],data['identity'],data['reason'])
                elif self.path=='/api/reference':
                    result=app.reference(session['role'],data['active'])
                elif self.path=='/api/approve':
                    result=app.approve(session['role'],data['id'],data['sha256'],data.get('review_digest'))
                elif self.path=='/api/stage':
                    result=app.stage(session['role'],data['id'],data['sha256'],data.get('review_digest'))
                else:
                    raise Rejected('unknown_action',404)
                self.json(result)
            except (Rejected,KeyError,ValueError,TypeError,OSError) as error:
                self.json(dict(error=str(error)),getattr(error,'status',400))
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures',type=Path,default=HERE/'staging_fixtures')
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--expected-head',required=True)
    args=parser.parse_args(argv)
    from ci.phase6_playlist_maintenance import verify_checkout
    proof=lambda:verify_checkout(expected_head=args.expected_head)
    from .staging_lifecycle import BrowserStaging
    app=BrowserStaging(args.fixtures,args.state,source_proof=proof)
    server=server_for(app,args.port)
    app._save('server.json',dict(url='http://127.0.0.1:'+str(server.server_port),pid=os.getpid(),candidate_commit=args.expected_head))
    print('Offline staging: http://127.0.0.1:'+str(server.server_port),flush=True)
    print('Local fixture access codes: '+str(app.root/'fixture-access.json'),flush=True)
    server.serve_forever()


if __name__=='__main__':
    main()
