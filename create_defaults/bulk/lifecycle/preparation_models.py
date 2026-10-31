"""Closed offline preparation values; hashes are integrity, never authority."""
from functools import lru_cache
import json
from pathlib import Path
import re

from ..common import BulkError, canonical, fingerprint, relative_path
from ..contracts.models import Document, decode_json
from ..definitions import StrictValidator

MAX_DOCUMENT = 2_000_000
MAX_EVENTS = 2000
MAX_FILES = 300
MAX_BYTES = 200 * 1024**2
FLAGS = dict(simulation=True, record_only=True, authenticated=False,
    operation_accepted=False, applied=False, artwork_approved=False,
    contract_approved=False, ready=False, active=False,
    production_enforcement=False, publication_authorized=False,
    remote_writes_authorized=False, merge_authorized=False)
HEADER = dict(schema_version=1, kind='phase5-offline-preparation', **FLAGS)


def fail(code):
    raise BulkError('p5m5_'+code, 'Offline preparation rejected: '+code)


def hash_value(value):
    if not isinstance(value,str) or re.fullmatch('[0-9a-f]{64}',value) is None:
        fail('hash')
    return value


@lru_cache(maxsize=1)
def validator():
    return StrictValidator(json.loads((Path(__file__).parent/'schemas/preparation-v1.schema.json').read_bytes()))


class Preparation(Document):
    def __init__(self,value):
        encoded=canonical(value)
        if len(encoded)>MAX_DOCUMENT:fail('schema')
        error=next(validator().iter_errors(value),None)
        if error is not None:
            # Schema paths contain only this closed format's field names and
            # bounded array positions, never submitted values or raw errors.
            raise BulkError('p5m5_schema','Offline preparation schema rejected: '+str(list(error.absolute_path))[:120]+' ('+error.validator+')')
        if any(value[k] is not expected for k,expected in FLAGS.items()):fail('authority')
        members=value['members'];ids=[m['identity'] for m in members]
        if not ids or ids!=sorted(set(ids)) or ids!=value['required_members']:fail('membership')
        if any(re.fullmatch(r'genre\.[0-9a-f]{32}',i) is None for i in ids):fail('cohort')
        from .models import HeadRef
        for head in value['native_heads']:HeadRef.from_dict(head)
        paths=[]
        for member in members:
            relative_path(member['destination']);paths.append(member['destination'])
            for key in ('sha256','receipt_sha256','object_sha256','receipt_object_sha256'):
                hash_value(member[key])
            if member['size']<1 or member['size']>MAX_BYTES:fail('artifact_bound')
        from ..library_publication import validate_paths
        validate_paths([dict(destination=p) for p in paths])
        from ..library_sources import check_seal
        check_seal(value['manifest']);check_seal(value['plan'])
        if value['plan']['publication_manifest_sha256']!=value['manifest']['sha256']:fail('plan_binding')
        upload=[dict(m) for m in members if m['sha256']!=m['previous_sha256']]
        expected=[dict(destination=m['destination'],source=m['source'],sha256=m['sha256'],size=m['size'],
            previous_sha256=m['previous_sha256'],git_blob=m['git_blob'],previous_git_blob=m['previous_git_blob'],
            context_sha256=value['snapshot_sha256']) for m in upload]
        if value['manifest']['members']!=sorted(expected,key=lambda m:m['destination']):fail('manifest_omission')
        actual=[m for b in value['plan']['batches'] for m in b['members']]
        if actual!=value['manifest']['members']:fail('batch_omission')
        if value['manifest']['exact_matches_skipped']!=[m['destination'] for m in members if m['sha256']==m['previous_sha256']]:fail('exact_membership')
        if [b['sequence'] for b in value['plan']['batches']]!=list(range(1,len(value['plan']['batches'])+1)):fail('batch_sequence')
        if (value['plan']['baseline']!=value['destination'] or value['manifest']['baseline']!=value['destination']
                or value['plan']['max_files']>MAX_FILES or value['plan']['max_bytes']>MAX_BYTES
                or value['plan']['max_pack_bytes']>MAX_BYTES+MAX_BYTES//4+1024*1024):fail('batch_limits')
        for b in value['plan']['batches']:
            if (b['membership_sha256']!=fingerprint(b['members']) or b['bytes']!=sum(m['size'] for m in b['members'])
                    or len(b['members'])>value['plan']['max_files'] or b['bytes']>value['plan']['max_bytes']):fail('batch_limits')
        for key in ('snapshot_sha256','catalog_sha256','registry_sha256','review_sha256','phase3_sha256'):
            hash_value(value[key])
        if fingerprint(value['native_heads'])!=value['native_heads_sha256']:fail('native_cas_binding')
        object.__setattr__(self,'encoded',encoded)

    @classmethod
    def from_bytes(cls,raw):
        if type(raw) is not bytes or len(raw)>MAX_DOCUMENT:fail('document_bound')
        result=cls.from_dict(decode_json(raw))
        if result.encoded!=raw:fail('noncanonical')
        return result


def diagnostic(error,operation):
    # Never retain raw exception text, submitted headers, stderr or chained URLs.
    category=error.code if isinstance(error,BulkError) and re.fullmatch('[a-z0-9_]{1,80}',error.code) else 'preparation_failure'
    return dict(category=category,operation_sha256=hash_value(operation),
        correlation_id=fingerprint(dict(operation=operation,category=category))[:32])


def commit_operational(*args,**kwargs):
    fail('production_unavailable')
