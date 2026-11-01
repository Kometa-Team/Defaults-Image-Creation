"""Closed M6 offline bindings. Integrity never creates operational authority."""
import json
from pathlib import Path
from functools import lru_cache

from ..common import BulkError,canonical,fingerprint
from ..contracts.models import Document,decode_json
from ..definitions import StrictValidator
from .preparation_models import Preparation,FLAGS,MAX_DOCUMENT

MODE='phase5-m6-offline-draft-transport'
HEADER=dict(schema_version=1,kind='phase5-offline-draft-binding',**FLAGS)


def fail(code):raise BulkError('p5m6_'+code,'Offline draft rejected: '+code)


@lru_cache(maxsize=1)
def validator():return StrictValidator(json.loads((Path(__file__).parent/'schemas/draft-transport-v1.schema.json').read_bytes()))


class DraftBinding(Document):
    def __init__(self,value):
        if len(canonical(value))>MAX_DOCUMENT:fail('document_bound')
        if next(validator().iter_errors(value),None) is not None:fail('binding_schema')
        if any(value[k] is not v for k,v in FLAGS.items()):fail('authority')
        preparation=Preparation.from_dict(value['preparation'])
        if value['preparation_sha256']!=preparation.sha256:fail('preparation_binding')
        from ..operator_publication import gate
        from ..library_sources import check_seal
        inventory=check_seal(value['inventory']);manifest=check_seal(value['manifest'])
        plan,auth=value['plan'],value['authorization'];members=gate(plan,auth)
        if (auth.get('test_only') is not True or auth['policy'].get('mode')!=MODE
                or auth['policy'].get('preparation_sha256')!=preparation.sha256
                or auth['candidate_manifest']!=manifest or manifest['inventory_sha256']!=inventory['sha256']
                or inventory['baseline']!=preparation.to_dict()['destination'] or manifest['withheld']):fail('authorization_binding')
        required=preparation.to_dict()['members']
        wanted={m['destination']:m for m in required if m['sha256']!=m['previous_sha256']}
        policy=auth['policy'];limits=preparation.to_dict()['plan']
        if (set(policy)!={'mode','preparation_sha256','catalog_sha256','technical_batch_limits'}
                or policy['catalog_sha256']!=value['catalog_sha256']
                or policy['technical_batch_limits']!={k:limits[k] for k in ('max_files','max_bytes')}
                or set(inventory)!={'baseline','rows','preparation_sha256','sha256'}
                or inventory['preparation_sha256']!=preparation.sha256):fail('policy_binding')
        expected_rows=[dict(destination=m['destination'],candidate_path=m['source'],candidate_sha256=m['sha256'],
            candidate_blob=m['git_blob'],published_sha256=m['previous_sha256'],published_blob=m['previous_git_blob'],
            hash_state='different',technical_valid=True,difference_class='phase5-native-reviewed',
            context_sha256=preparation.sha256,kind='poster') for m in required if m['sha256']!=m['previous_sha256']]
        if inventory['rows']!=expected_rows:fail('inventory_membership')
        if len(members)!=len(wanted) or {m['destination'] for m in members}!=set(wanted):fail('incomplete_membership')
        keys=('source','size','sha256','git_blob','previous_sha256','previous_git_blob')
        for m in members:
            if (any(m[k]!=wanted[m['destination']][k] for k in keys)
                    or m.get('context_sha256')!=preparation.sha256 or m.get('rename_from')
                    or m.get('kind')!='poster'):fail('artwork_linkage')
        if plan['baseline']!=preparation.to_dict()['destination']:fail('destination_binding')
        if value['catalog_sha256']!=preparation.to_dict()['catalog_sha256']:fail('catalog_binding')
        object.__setattr__(self,'encoded',canonical(value))

    @classmethod
    def from_bytes(cls,raw):
        if type(raw) is not bytes:fail('document_type')
        value=cls.from_dict(decode_json(raw))
        if value.encoded!=raw:fail('canonical')
        return value


def publish_operational(*args,**kwargs):fail('production_unavailable')
