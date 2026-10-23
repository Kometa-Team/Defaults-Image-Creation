"""Complete Git closure, path attacks, native Git parity and exact names."""

from dataclasses import replace
import json
import subprocess

import pytest

from create_defaults.bulk.common import BulkError,canonical,fingerprint
from create_defaults.bulk.contracts.destination_preflight import evaluate,DestinationInventory,revalidate
from create_defaults.bulk.contracts.destination_preflight.inventory import tree_sha,git_object
from create_defaults.bulk.contracts.destination_preflight.paths import safe_path
from create_defaults.bulk.contracts.language_policy import DestinationEvidence
from create_defaults.phase3.tests.destination_samples import poster,scenario,inventory,USER,overlay_pair
from create_defaults.phase3.tests.test_destination_preflight import changed_evidence


def with_inventory(s,inv):
    value=s['evidence'].to_dict()
    value['target'].update(inventory_sha256=inv.sha256,baseline_commit=inv.to_dict()['commit'],baseline_tree=inv.to_dict()['tree'])
    return changed_evidence(s,value)|dict(inventory=inv,expected_inventory_sha256=inv.sha256)


@pytest.mark.parametrize('path,mode,code',[
    ('playlist/Élan.jpg','100644','existing_exact'),('playlist/élan.JPG','100644','existing_alias'),
    ('playlist/E\u0301lan.jpg','100644','existing_alias'),('Playlist/other.jpg','100644','existing_ancestor_alias'),
    ('playlist','120000','symlink_ancestor'),('playlist','160000','existing_file_ancestor'),
    ('playlist/Élan.jpg/child','100644','existing_directory')])
def test_inventory_collision_families_are_not_overwrite_permission(tmp_path,path,mode,code):
    item,lp=poster(tmp_path,filename='Élan.jpg')
    report=evaluate(**scenario((item,),lp,entries={path:mode})).to_dict()
    assert code in report['outputs'][0]['diagnostics']
    assert not report['simulation_eligible'] and report['outputs'][0]['status']=='blocked'


@pytest.mark.parametrize('path',[
    '../escape.jpg','a/../escape.jpg','/absolute.jpg','C:/drive.jpg','C:drive.jpg','//server/share.jpg','\\\\server\\share.jpg',
    'a\\escape.jpg','poster.jpg:stream','a//poster.jpg','./poster.jpg','.git/config','A/.GiT/config',
    'CON.jpg','aux.png','folder/LPT1.png','COM9/test.jpg','trailing./file.jpg','space /file.jpg',
    'bad\x00file.jpg','bad\x7ffile.jpg','%2e%2e/escape.jpg','a%2f..%2fescape.jpg','a/%5Cescape.jpg',
    'a/%00file.jpg','a/%252e%252e/escape.jpg','bad\ud800.jpg'])
def test_unsafe_path_and_encoding_are_rejected_without_normalization(path):
    with pytest.raises((BulkError,UnicodeError)):safe_path(path)


@pytest.mark.parametrize('field,attack',[('root','../escape'),('root','%2e%2e'),('root','.git'),('paths',['playlist/%2e%2e/Foo.jpg']),('branch','refs/%2e%2e/main')])
def test_unsafe_evidence_cannot_reach_a_target(tmp_path,field,attack):
    item,lp=poster(tmp_path);s=scenario((item,),lp)
    value=s['evidence'].to_dict();value['target'][field]=attack
    with pytest.raises(BulkError):evaluate(**changed_evidence(s,value))


@pytest.mark.parametrize('filename',['Été — Noël.jpg','E\u0301te\u0301.jpg','Name (One) + Two!.jpg','100% Real.jpg'])
def test_exact_canonical_source_filename_unicode_and_punctuation_preserved(tmp_path,filename):
    item,lp=poster(tmp_path,filename=filename)
    result=evaluate(**scenario((item,),lp,root='Chosen/Case')).to_dict()
    assert result['simulation_eligible']
    assert result['outputs'][0]['target_path']=='Chosen/Case/playlist/'+filename
    assert result['outputs'][0]['output']==item.subject.to_dict()['outputs'][0]


@pytest.mark.parametrize('other',['Élan.jpg','élan.JPG','E\u0301lan.jpg','Élan.jpg/child.jpg'])
def test_proposed_duplicate_alias_and_file_directory_collisions(tmp_path,other):
    a,lp=poster(tmp_path/'a',filename='Élan.jpg')
    b,lp_b=poster(tmp_path/'b',filename=other,identity='fixture.second')
    assert lp.sha256==lp_b.sha256
    if '/' not in other:
        # Frozen M1 mappings reject exact/case/Unicode duplicate path membership
        # before an invalid grant or attestation can even be constructed.
        with pytest.raises(BulkError):evaluate(**scenario((a,b),lp))
        return
    result=evaluate(**scenario((a,b),lp)).to_dict()
    assert any('proposed_collision' in r['diagnostics'] for r in result['outputs'])
    assert not result['simulation_eligible']


def test_private_and_public_membership_cannot_publish_private_output(tmp_path):
    private,lp=poster(tmp_path/'private',public=False)
    public,lp_b=poster(tmp_path/'public',identity='fixture.public')
    assert lp.sha256==lp_b.sha256
    s=scenario((private,public),lp)
    result=evaluate(**s).to_dict()
    assert result['simulation_eligible'] and len(result['outputs'])==2
    assert sum(r['status']=='private' for r in result['outputs'])==1
    assert len(result['target']['paths'])==1
    value=s['evidence'].to_dict();value['target']['paths'].append('private/Unauthorized.jpg')
    with pytest.raises(BulkError):evaluate(**changed_evidence(s,value))


def test_missing_inventory_and_missing_subtree_fail_closed(tmp_path):
    item,lp=poster(tmp_path);s=scenario((item,),lp,entries={'existing/child.jpg':'100644'})
    result=evaluate(**(s|dict(inventory=None,expected_inventory_sha256=None))).to_dict()
    assert result['inventory_status']=='unavailable' and not result['complete'] and not result['simulation_eligible']
    value=s['inventory'].to_dict()
    value['pages']=[p for p in value['pages'] if p['sha']==value['tree']]
    incomplete=DestinationInventory.from_dict(value)
    result=evaluate(**with_inventory(s,incomplete)).to_dict()
    assert result['inventory_status']=='incomplete' and result['missing_tree_pages']
    assert not result['complete'] and not result['simulation_eligible']


@pytest.mark.parametrize('mutation',['tree-content','commit-content','commit-tree','duplicate-page','duplicate-entry','unreachable-tree','unsafe-component','encoded-component','missing-root'])
def test_inventory_object_hash_closure_and_unsafe_names(mutation):
    inv=inventory(USER,'Main',{'existing/a.jpg':'100644'})
    value=inv.to_dict()
    if mutation=='tree-content':value['pages'][0]['entries'][0]['sha']='f'*40
    elif mutation=='commit-content':value['commit_hex']+='00'
    elif mutation=='commit-tree':value['tree']='f'*40
    elif mutation=='duplicate-page':value['pages'].append(value['pages'][0])
    elif mutation=='duplicate-entry':value['pages'][0]['entries']*=2
    elif mutation=='unreachable-tree':
        empty=dict(sha=tree_sha([]),entries=[]);value['pages'].append(empty)
    elif mutation in ['unsafe-component','encoded-component']:
        page=value['pages'][0];page['entries'][0]['name']='a/b' if mutation=='unsafe-component' else '%2e%2e'
    else:value['pages']=[]
    if mutation=='missing-root':
        partial=DestinationInventory.from_dict(value)
        from create_defaults.bulk.contracts.destination_preflight.inventory import expand
        assert expand(partial.to_dict())[1]==[value['tree']]
    else:
        with pytest.raises(BulkError):
            altered=DestinationInventory.from_dict(value)
            from create_defaults.bulk.contracts.destination_preflight.inventory import expand
            expand(altered.to_dict())


def test_git_tree_encoding_matches_native_git_and_uses_git_sort_order():
    rows=[dict(name='foo.bar',mode='100644',sha='a'*40),dict(name='foo',mode='040000',sha='b'*40),
          dict(name='Élan',mode='120000',sha='c'*40)]
    ordered=sorted(rows,key=lambda r:(r['name']+('/' if r['mode']=='040000' else '')).encode())
    raw=b''.join(r['mode'].lstrip('0').encode()+b' '+r['name'].encode()+b'\x00'+bytes.fromhex(r['sha']) for r in ordered)
    actual=subprocess.check_output(['git','hash-object','-t','tree','--stdin'],input=raw).decode().strip()
    assert tree_sha(rows)==actual
    assert tree_sha(list(reversed(rows)))==actual


def test_cross_language_full_target_alias_and_direct_collision_index(tmp_path):
    from create_defaults.bulk.contracts.destination_preflight.paths import CollisionIndex
    item,lp=poster(tmp_path,filename='Élan.jpg')
    other=dict(language='fr',repository=USER,branch='Main',root=None,paths=['playlist/E\u0301lan.JPG'])
    result=evaluate(**scenario((item,),lp,extra_mappings=[other])).to_dict()
    assert 'cross_language_alias' in result['blockers']
    for path in ['playlist/élan.jpg','playlist/E\u0301lan.JPG']:
        assert CollisionIndex({'playlist/Élan.jpg':dict(mode='100644')}).diagnostics(path)==['existing_alias']


def test_target_baseline_changes_with_identical_entries_invalidate_evidence(tmp_path):
    item,lp=poster(tmp_path);s=scenario((item,),lp);report=evaluate(**s)
    value=s['inventory'].to_dict()
    raw=bytes.fromhex(value['commit_hex'])+b'\nNew commit, unchanged tree\n'
    value.update(commit_hex=raw.hex(),commit=git_object('commit',raw))
    advanced=DestinationInventory.from_dict(value)
    updated=with_inventory(s,advanced)
    new=evaluate(**updated)
    assert new.sha256!=report.sha256 and new.to_dict()['dependency_sha256']!=report.to_dict()['dependency_sha256']
    assert advanced.to_dict()['tree']==s['inventory'].to_dict()['tree']
    assert not new.to_dict()['simulation_eligible']  # Old independent grant cannot replay.
    with pytest.raises(BulkError):revalidate(report,expected_sha256=report.sha256,**updated)


@pytest.mark.parametrize('point',[1,2,3])
def test_interruption_never_returns_partial_complete_evidence(point):
    items,lp=overlay_pair();s=scenario(items,lp)
    count=0
    def cancel():
        nonlocal count
        count+=1;return count>=point
    with pytest.raises(BulkError,match='interrupted'):evaluate(**s,cancel=cancel)
