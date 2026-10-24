"""Deterministic isolated metadata vector; never historical output fabrication."""
from unittest.mock import patch
from uuid import UUID
from create_defaults.bulk.lifecycle.identities import IdentityRegistry
from create_defaults.phase3.tests.destination_samples import inventory,USER


def vector(root):
    inv=inventory(USER,'Main',{'existing/Reserved.jpg':'100644'})
    registry=IdentityRegistry.create(root,'synthetic-canonical',inventory=inv,expected_inventory_sha256=inv.sha256)
    names=dict(display_name='Synthetic Pokémon',rendered_caption='TIMELINE ORDER',source=dict(path='logos_playlist/Arrowverse.png',sha256='a'*64),
        local_path='defaults-en/playlist/Synthetic Pokémon.jpg',public_path='playlist/Synthetic Pokémon.jpg')
    with patch('create_defaults.bulk.lifecycle.identities.uuid4',return_value=UUID('11111111-1111-4111-8111-111111111111')):
        entry=registry.allocate(category='Playlist',semantic=dict(parent=None,key='synthetic-content',role='single',language='en'),variant='timeline-order',names=names,token='allocate',expected=registry.view().head)
    names=dict(names,display_name='Synthetic Changed',public_path='playlist/Synthetic pokémon!.jpg')
    registry.revise(entry['id'],names,entry_revision=1,token='revise',expected=registry.view().head)
    return dict(snapshots=[v.snapshot.to_dict() for v in registry.history()],
        records=[r.to_dict() for r in registry.operations.history(registry.operation_id)],
        events=[e.to_dict() for e in registry.operations.journal()],inspection=registry.operations.inspect())
