"""Browser-generated fixture lifecycle, deliberately separate from live authority.

The native registry rejects tombstone reuse. Only this owned staging catalog
supports restoration; this module grants no native registry/catalog capability.
"""
from copy import deepcopy
import io
import json
import os
import re
import secrets
import tempfile

import PIL

from create_defaults import create_poster as renderer
from create_defaults.bulk.definitions import load_definitions
from .staging_app import Rejected, Staging, regular, sha


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


class BrowserStaging(Staging):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        catalog = renderer.ROOT/'bulk/catalog'
        historical = load_definitions([catalog/'playlist.yml'], profiles_path=catalog/'profiles.yml')
        self.catalog = {d.id: dict(identity=d.id, destination=d.data['output']['remote_paths']['en'],
            status='active', sha256=self.baseline[d.data['output']['remote_paths']['en']],
            revision=1, references=[]) for d in historical}
        self.catalog_baseline = deepcopy(self.catalog)
        self.disposable = 'fixture.playlist.disposable'
        self.second = 'fixture.franchise.disposable'
        self.requests = deepcopy(self.entries)
        row = deepcopy(next(iter(self.entries.values())))
        row.update(identity=self.disposable, display_name='Disposable Playlist',
            destination='playlist/Disposable Playlist (Timeline Order).jpg', approved_sha256=None)
        row['render_request']['parameters']['out_name']='Disposable Playlist (Timeline Order)'
        self.requests[self.disposable]=row
        # An existing supported Franchise preset, without new compositing rules.
        franchise = load_definitions([catalog/'franchise.yml'], profiles_path=catalog/'profiles.yml')[0].data
        self.requests[self.second] = dict(identity=self.second, display_name='Disposable Franchise',
            destination='franchise/Disposable Franchise.jpg', approved_sha256=None,
            render_request=dict(parameters=deepcopy(franchise['composer']), composition_style='franchise-legacy'))
        self.logos = {}
        for r in self.requests.values():
            name=r['render_request']['parameters']['logo']
            self.logos[name]=sha(regular(renderer.ROOT/name))
            if r.get('source_png_sha256') and r['source_png_sha256'] != self.logos[name]:
                raise Rejected('source_logo_binding')
        self.persist()

    def persist(self):
        super().persist()
        if hasattr(self, 'catalog'):
            self._save('catalog.json', self.catalog)

    def guard(self):
        super().guard()
        if hasattr(self, 'catalog') and json.loads(regular(self.root/'catalog.json')) != self.catalog:
            raise Rejected('catalog_drift')

    def form_state(self):
        return dict(entries=list(self.requests.values()), logos=list(self.logos), catalog=self.catalog,
            styles=[dict(id='playlist-contained-v1', label='Playlist / Timeline Order',
                         caption=True, default_caption='TIMELINE ORDER', category='playlist'),
                    dict(id='franchise-legacy', label='Franchise / existing logo-only preset',
                         caption=False, default_caption='', category='franchise')],
            restoration_scope='owned staging catalog only; native tombstone reuse is blocked')

    def _object(self, raw):
        checksum=sha(raw)
        path=self.objects/(checksum+'.jpg')
        if path.exists():
            if regular(path) != raw: raise Rejected('object_collision')
        else:
            with path.open('xb') as stream: stream.write(raw)
        return checksum

    def generate(self, role, identity, style, logo, colour, caption):
        with self.lock:
            if role != 'contributor': raise Rejected('contributor_required', 403)
            self.source_proof()
            self.guard()
            if identity not in self.requests or logo not in self.logos:
                raise Rejected('unknown_fixture_or_logo', 400)
            row=self.requests[identity]
            expected_style=row['render_request']['composition_style']
            if style != expected_style: raise Rejected('style_not_supported_for_fixture', 400)
            if not isinstance(colour,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',colour):
                raise Rejected('six_digit_background_required',400)
            if not isinstance(caption,str) or len(caption)>40 or (style=='playlist-contained-v1' and not caption.strip()) or (style=='franchise-legacy' and caption):
                raise Rejected('selected_style_caption_requirements',400)
            params=deepcopy(row['render_request']['parameters'])
            params.update(logo=logo, base_color=colour, text=caption)
            assets={name:sha(regular(renderer.ROOT/name)) for name in
                {logo, params['font'], 'fades/'+renderer.FADES[params['gradient']]}}
            if assets[logo] != self.logos[logo]: raise Rejected('source_logo_changed')
            image, metadata=renderer.render_poster(renderer.PosterOptions(**params),
                asset_dir=renderer.ROOT, style=None if style=='franchise-legacy' else style)
            encoded=io.BytesIO()
            image.save(encoded,'JPEG',quality=100,subsampling=0)
            raw=encoded.getvalue()
            if assets != {name:sha(regular(renderer.ROOT/name)) for name in assets}:
                raise Rejected('render_asset_changed')
            self.guard()
            self.source_proof()
            current=deepcopy(self.catalog.get(identity))
            action='RESTORE' if current and current['status']=='retired' else 'REPLACE' if current else 'CREATE'
            checksum=self._object(raw)
            sid=secrets.token_hex(12)
            self.submissions[sid]=dict(id=sid, identity=identity, display_name=row['display_name'],
                destination=row['destination'], action=action, sha256=checksum, status='draft',
                approved_sha256=None, receipt=None, before=current,
                reference_sha256=row['approved_sha256'], reference_match=(checksum==row['approved_sha256']) if row['approved_sha256'] else None,
                render=dict(style=style, parameters=params, assets=assets, metadata=metadata,
                    pillow=PIL.__version__, renderer_sha256=sha(regular(renderer.ROOT/'create_poster.py'))),
                approval_digest=None)
            self.persist()
            return self.review(self.submissions[sid])

    def submit_generated(self, role, sid):
        with self.lock:
            if role != 'contributor': raise Rejected('contributor_required',403)
            self.guard()
            item=self.submissions[sid]
            self.object_bytes(item)
            if item['status'] != 'draft': raise Rejected('draft_required')
            item['status']='preview'
            self.persist()
            return self.review(item)

    def request_removal(self, role, identity):
        with self.lock:
            if role != 'contributor': raise Rejected('contributor_required',403)
            self.guard()
            if identity != self.disposable: raise Rejected('disposable_removal_only',403)
            before=deepcopy(self.catalog.get(identity))
            if not before or before['status']!='active': raise Rejected('active_poster_required')
            raw=regular(self.destination/before['destination'])
            sid=secrets.token_hex(12)
            self.submissions[sid]=dict(id=sid, identity=identity, display_name='Disposable Playlist',
                destination=before['destination'], action='REMOVE', sha256=self._object(raw),
                status='preview', approved_sha256=None, receipt=None, before=before,
                reference_sha256=None, reference_match=None, render=None, approval_digest=None)
            self.persist()
            return self.review(self.submissions[sid])

    def reference(self, role, active):
        with self.lock:
            if role != 'maintainer': raise Rejected('maintainer_required',403)
            if not isinstance(active,bool): raise Rejected('boolean_reference_required',400)
            self.guard()
            row=self.catalog.get(self.disposable)
            if not row or row['status']!='active': raise Rejected('active_poster_required')
            row['references']=['fixture.active-playlist'] if active else []
            row['revision']+=1
            self.persist()
            return row

    def review(self, item):
        if item['status']=='staged': return deepcopy(item)
        current=self.catalog.get(item['identity'])
        before=item['before']
        after=dict(identity=item['identity'], destination=item['destination'],
            status='retired' if item['action']=='REMOVE' else 'active',
            sha256=None if item['action']=='REMOVE' else item['sha256'],
            revision=(before['revision'] if before else 0)+1,
            references=deepcopy(before['references']) if before else [])
        if item['action']=='REMOVE': after['last_sha256']=item['sha256']
        checks=[dict(name='catalog precondition / identity / path', passed=current==before),
                dict(name='exact immutable preview JPEG', passed=sha(self.object_bytes(item))==item['sha256']),
                dict(name='destination preimage', passed=self.expected.get(item['destination'])==(before['sha256'] if before else None)),
                dict(name='no active references for removal', passed=item['action']!='REMOVE' or not (current or {}).get('references')),
                dict(name='approved reference bytes (main ten only)', passed=item['reference_match'] is not False)]
        if item['render']:
            checks.append(dict(name='fresh render assets',passed=all(sha(regular(renderer.ROOT/name))==digest
                for name,digest in item['render']['assets'].items())))
        value=deepcopy(item)
        value.update(checks=checks, catalog_change=dict(before=before,after=after),
            can_approve=all(r['passed'] for r in checks))
        value['review_digest']=sha(canonical(dict(sha256=item['sha256'],before=before,after=after,checks=checks)))
        return value

    def approve(self, role, sid, expected_hash, review_digest=None):
        with self.lock:
            if role != 'maintainer': raise Rejected('maintainer_required',403)
            self.guard()
            item=self.submissions[sid]
            review=self.review(item)
            if not review['can_approve']: raise Rejected('required_check_failed')
            if item['status']!='preview' or item['sha256']!=expected_hash or review['review_digest']!=review_digest:
                raise Rejected('stale_or_wrong_render_approval')
            item.update(status='approved',approved_sha256=expected_hash,approval_digest=review_digest)
            self.persist()
            return self.review(item)

    def stage(self, role, sid, expected_hash, review_digest=None):
        with self.lock:
            if role != 'maintainer': raise Rejected('maintainer_required',403)
            self.source_proof()
            self.guard()
            item=self.submissions[sid]
            review=self.review(item)
            if not review['can_approve']: raise Rejected('required_check_failed')
            if (item['status']!='approved' or item['approved_sha256']!=expected_hash or
                    item['approval_digest']!=review_digest or review['review_digest']!=review_digest):
                raise Rejected('exact_render_and_catalog_approval_required')
            raw=self.object_bytes(item)
            target=self.destination/item['destination']
            before_raw=regular(target) if target.exists() else None
            old_inventory,old_catalog=deepcopy(self.expected),deepcopy(self.catalog)
            try:
                target.parent.mkdir(exist_ok=True)
                if item['action']=='REMOVE':
                    target.unlink()
                    self.expected.pop(item['destination'])
                else:
                    fd,temporary=tempfile.mkstemp(dir=self.root)
                    try:
                        with os.fdopen(fd,'wb') as stream:
                            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
                        os.replace(temporary,target)
                    finally:
                        if os.path.exists(temporary): os.unlink(temporary)
                    self.expected[item['destination']]=expected_hash
                self.catalog[item['identity']]=review['catalog_change']['after']
                self._save('catalog.json',self.catalog)
                self.guard()
                self.source_proof()
            except BaseException:
                if before_raw is None: target.unlink(missing_ok=True)
                else: target.write_bytes(before_raw)
                self.expected,self.catalog=old_inventory,old_catalog
                self._save('catalog.json',self.catalog)
                raise
            item.update(status='staged',checks=review['checks'],catalog_change=review['catalog_change'],
                review_digest=review_digest,can_approve=False,receipt=dict(identity=item['identity'],destination=str(target),
                relative_path=item['destination'],action=item['action'],previous_sha256=sha(before_raw) if before_raw else None,
                destination_sha256=sha(regular(target)) if target.exists() else None,
                file_absent=not target.exists(),catalog_entry=deepcopy(self.catalog[item['identity']]),
                catalog_sha256=sha(regular(self.root/'catalog.json')),review_digest=review_digest,
                match=True,simulation=True,publication_authorized=False))
            self.persist()
            return deepcopy(item)
