"""Exact current Phase 3 snapshots; original canonical records remain sealed."""
import hashlib
import json
from ci import phase6_playlist_maintenance as pilot
from ci.people_storage_maintenance import regular
from create_defaults.bulk.common import fingerprint

HISTORICAL = {'destination-preflight-v1.json': '0a398f0818b161da689839af95491a36930ce910ee361998c0320e2014690e15', 'evidence-consumption-v1.json': '180f39b4c9ccea8a40d83b0b8ab8b7a5fe5a0cbf053b33fe9e0ac614742bac35', 'phase3-final-acceptance-v1.json': '20ebcd619420521c02b5706172c1d87a2c7ce43f098c5b534b099a3e4e528b2d', 'translation-preflight-v1.json': '90eb28e66917aea1e93c4e90cd70f2703506ad2a222b5f8df6981b453da092d6'}

def current_fixture(name):
    if name not in HISTORICAL:
        raise ValueError('Unknown Phase 3 canonical successor')
    pilot.verify_checkout()
    raw = regular(pilot.ROOT, 'create_defaults/phase3/tests/'+name).read_bytes().replace(b'\r\n', b'\n')
    before = json.loads(raw)
    if (hashlib.sha256(raw).hexdigest() != HISTORICAL[name]
            or fingerprint(before['evidence']) != before['sha256']):
        raise ValueError('Changed historical Phase 3 canonical record')
    value = json.loads(regular(pilot.ROOT, 'create_defaults/phase6/canonical/'+name).read_bytes())
    if (set(value) != {'predecessor_sha256', 'sha256', 'evidence'}
            or value['predecessor_sha256'] != HISTORICAL[name]
            or value['sha256'] != fingerprint(value['evidence'])):
        raise ValueError('Changed current Phase 3 canonical successor')
    # Recheck the full fresh physical cohort and HEAD at exit as well as entry.
    pilot.verify_checkout()
    return value
