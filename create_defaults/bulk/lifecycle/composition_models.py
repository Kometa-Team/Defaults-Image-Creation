"""Strict M3 values. Complete pixels are evidence, never approval or activation."""
import base64
from functools import lru_cache
import hashlib
from pathlib import Path

from jsonschema import Draft202012Validator
from ..common import BulkError,canonical,fingerprint,relative_path
from ..contracts.models import Document,decode_json
from ..definitions import StrictValidator,Definition
from ..planner import validate_manifest
from .identity_models import FLAGS

HEADER=dict(schema_version=1,protocol_version='1.0.0',scope='isolated-composition-fixture',**FLAGS)
MAX_BINARY=5*1024*1024  # JSON/base64 must fit the existing 8 MiB Package E object.
MAX_MEMBERS=32         # Prototype resource limit, never a visual tolerance.


def fail(code):raise BulkError('p4m3_'+code,'Composition blocked: '+code)


@lru_cache(maxsize=2)
def validator(kind):
    schema=decode_json((Path(__file__).parent/'schemas/composition-v1.schema.json').read_bytes())
    Draft202012Validator.check_schema(schema)
    return StrictValidator({'$defs':schema['$defs'],'$ref':'#/$defs/'+kind})


class CompositionValue(Document):
    def __init__(self,value):
        raw=canonical(value);value=decode_json(raw)
        if next(validator(self.KIND).iter_errors(value),None):fail('schema')
        self._check(value);object.__setattr__(self,'encoded',raw)


def json_value(raw):
    v=decode_json(raw.encode())
    if canonical(v).decode()!=raw:fail('noncanonical_context')
    return v


class BytesObject(CompositionValue):
    KIND='composition-bytes'

    @classmethod
    def make(cls,raw):
        if type(raw) is not bytes or not 0<len(raw)<=MAX_BINARY:fail('artifact_resource_bound')
        return cls.from_dict(dict(schema_version=1,kind=cls.KIND,sha256=hashlib.sha256(raw).hexdigest(),
            size=len(raw),encoding='base64',data=base64.b64encode(raw).decode('ascii')))

    def raw(self):
        v=self.to_dict()
        try:raw=base64.b64decode(v['data'],validate=True)
        except ValueError:fail('binary_encoding')
        if not 0<len(raw)<=MAX_BINARY or len(raw)!=v['size'] or hashlib.sha256(raw).hexdigest()!=v['sha256']:fail('binary_hash')
        if base64.b64encode(raw).decode('ascii')!=v['data']:fail('binary_canonical')
        return raw

    def _check(self,v):
        # raw() needs the immutable encoded field, so perform the same bounded
        # binary check here before the Document can be constructed.
        try:raw=base64.b64decode(v['data'],validate=True)
        except ValueError:fail('binary_encoding')
        if not 0<len(raw)<=MAX_BINARY or len(raw)!=v['size'] or hashlib.sha256(raw).hexdigest()!=v['sha256']:fail('binary_hash')
        if base64.b64encode(raw).decode('ascii')!=v['data']:fail('binary_canonical')


class CompositionEvidence(CompositionValue):
    KIND='composition-evidence'

    def _check(self,v):
        context=json_value(v['context_json']);runtime=json_value(v['runtime_json'])
        if type(context) is not dict or set(context)!={'candidate_sha256','impact_sha256','registry_sha256','operation','request_json','required_members','original_outputs','base_graph_sha256'}:fail('context_shape')
        json_value(context['request_json'])
        if context['operation']!=v['operation'] or context['required_members']!=v['required_members']:fail('context_binding')
        if type(runtime) is not dict or set(runtime)!={'renderer','native_libraries','implementation_sha256','reproducibility'}:fail('runtime_shape')
        if runtime['reproducibility']!='exact-environment-only':fail('environment_scope')
        required=v['required_members']
        if required!=sorted(set(required)) or not 0<len(required)<=MAX_MEMBERS:fail('membership')
        if [x['appearance'] for x in v['views']]!=['default','requested']:fail('appearance_membership')
        for view in v['views']:
            manifest=json_value(view['manifest_json']);validate_manifest(manifest)
            if manifest['sha256']!=view['manifest_sha256']:fail('manifest_pin')
            definitions=json_value(view['definitions_json'])
            for identity,d in definitions.items():
                if all(j['kind']=='poster' for j in manifest['jobs']) and Definition.create(d).id!=identity:fail('definition_identity')
            ids=[m['identity'] for m in view['members']]
            if ids!=required or set(definitions)!=set(required):fail('incomplete_members')
            if {j['poster_id'] for j in manifest['jobs']}!=set(required):fail('job_membership')
            by_id={j['poster_id']:j for j in manifest['jobs']}
            if len(by_id)!=len(manifest['jobs']):fail('duplicate_identity')
            for m in view['members']:
                job=by_id[m['identity']]
                if (m['job_id'],m['local_path'],m['public_path'],m['render_fingerprint'])!=(job['id'],job['local_relative'],job['remote_relative'],job['render_fingerprint']):fail('member_job_binding')
                relative_path(m['local_path'])
                if m['public_path'] is not None:relative_path(m['public_path'])
                if m['companions']!=sorted(set(m['companions'])) or not set(m['companions'])<=set(required)-{m['identity']}:fail('companion_membership')
                if m['parent_jobs']!=sorted(d['job_id'] for d in job['dependencies']):fail('parent_membership')
                if job['kind']=='poster' and (m['format'],m['mode'],m['dimensions'])!=('JPEG','RGB',[2000,3000]):fail('complete_poster_required')
                if job['kind']=='overlay' and (m['format']!='PNG' or m['mode']!='RGBA' or any(not 0<d<=b for d,b in zip(m['dimensions'],job['parameters']['box']))):fail('native_overlay_required')
            for m in view['members']:
                for c in m['companions']:
                    other=next(x for x in view['members'] if x['identity']==c)
                    if m['identity'] not in other['companions']:fail('asymmetric_companions')
            json_value(view['layout_json']);json_value(view['impact_json'])
            metrics=json_value(view['execution_json'])
            if type(metrics) is not list or not metrics or any(type(x) is not dict for x in metrics):fail('execution_shape')
