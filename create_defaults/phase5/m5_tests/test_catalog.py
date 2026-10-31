"""P5-T20 raw catalog bytes, original loader and exact effective-job deltas."""
from copy import deepcopy
import json

import pytest
from create_defaults.bulk.common import BulkError
from create_defaults.bulk.catalog import load_catalog
from create_defaults.bulk.lifecycle.catalog_preparation import OwnedCatalog,CATALOG,prepare_catalog,patch_yaml,patch_index,git
from create_defaults.bulk.lifecycle.previews import CompositionTrial,CompositionArchive


def definition():
    value=deepcopy(next(d.data for d in load_catalog(['Genre']) if d.data['composer']['logo']))
    value['id']='genre.'+'1'*32
    return value


def commit(source):
    git(source.root,'add','--',*(CATALOG+n for n in ('genre.yml','index-v1.json','profiles.yml')))
    git(source.root,'commit','-m','Explicit owned source fixture revision')


@pytest.fixture
def source():
    with CompositionTrial() as trial:yield OwnedCatalog(trial)


def seed(source,value,*,decorated=False):
    path=source.root/CATALOG/'genre.yml'
    raw=path.read_bytes()
    if decorated:raw=b'\xef\xbb\xbf# Unicode Pok\xc3\xa9mon comment\r\n'+raw.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
    path.write_bytes(patch_yaml(raw,{value['id']:value}))
    index=source.root/CATALOG/'index-v1.json';index.write_bytes(patch_index(index.read_bytes(),{value['id']:value}))
    commit(source)


def test_P5_T20_new_block_preserves_all_preimage_bytes_and_lookup(source):
    desired=definition();old=(source.root/CATALOG/'genre.yml').read_bytes()
    patch=prepare_catalog(source,{desired['id']:desired})
    row=patch.verify({desired['id']:desired})['files']['genre.yml']
    after=CompositionArchive(source.trial.config.cache_dir,readonly=True).read_bytes(row['after_object'])
    assert after.startswith(old) and row['before_sha256']!=row['after_sha256']
    assert (source.root/CATALOG/'genre.yml').read_bytes()==old


@pytest.mark.parametrize('field,value',[('display_name','Literal Pokémon (A & B)!'),('display_name',"Literal 'quote'"),('display_name','true')])
def test_P5_T20_scalar_patch_preserves_BOM_CRLF_comments_and_other_bytes(source,field,value):
    desired=definition();seed(source,desired,decorated=True)
    path=source.root/CATALOG/'genre.yml';before=path.read_bytes()
    desired[field]=value
    patch=prepare_catalog(source,{desired['id']:desired})
    after=CompositionArchive(source.trial.config.cache_dir,readonly=True).read_bytes(patch.verify({desired['id']:desired})['files']['genre.yml']['after_object'])
    assert after.startswith(b'\xef\xbb\xbf# Unicode Pok\xc3\xa9mon comment\r\n')
    assert after.count(b'\r\n')==before.count(b'\r\n') and value.encode() in after
    assert path.read_bytes()==before


@pytest.mark.parametrize('mutation',['duplicate','unknown','traversal','historical','profile','missing_index','index_hash'])
def test_P5_T20_strict_or_unowned_catalog_changes_fail(source,mutation):
    path=source.root/CATALOG/'genre.yml';raw=path.read_bytes()
    if mutation=='duplicate':path.write_bytes(b'schema_version: 1\n'+raw)
    elif mutation=='unknown':path.write_bytes(raw+b'unknown_field: true\n')
    elif mutation=='traversal':path.write_bytes(raw.replace(b'directory: genre',b'directory: ../escape',1))
    elif mutation=='historical':path.write_bytes(raw.replace(b'display_name: other',b'display_name: altered',1))
    elif mutation=='profile':(source.root/CATALOG/'profiles.yml').write_bytes(b'unknown: true\n')
    else:
        index=source.root/CATALOG/'index-v1.json';value=json.loads(index.read_bytes())
        if mutation=='missing_index':value['posters'].pop(next(i for i,r in value['posters'].items() if r['category']=='Genre'))
        else:value['sha256']='0'*64
        index.write_text(json.dumps(value),encoding='utf8')
    commit(source)
    desired=definition()
    with pytest.raises(BulkError):prepare_catalog(source,{desired['id']:desired})


def test_P5_T21_stale_source_commit_invalidates_prepared_patch(source):
    desired=definition();patch=prepare_catalog(source,{desired['id']:desired})
    git(source.root,'commit','--allow-empty','-m','New authoritative source epoch')
    with pytest.raises(BulkError,match='stale_source'):patch.verify({desired['id']:desired})


@pytest.mark.parametrize('mutation',['retired','Network','generator','historical_id'])
def test_P5_T15_unsupported_catalog_cohort(source,mutation):
    value=definition()
    if mutation=='Network':value['category']='Network'
    elif mutation=='generator':value['generator']={'name':'unsupported'}
    else:value['id']='historical-or-retired'
    with pytest.raises(BulkError,match='catalog_scope'):prepare_catalog(source,{value['id']:value})


def test_P5_T20_unknown_source_root_is_not_accepted(source):
    with pytest.raises(BulkError,match='source_ownership'):prepare_catalog(source.root,{})


@pytest.mark.parametrize('boundary',['before_catalog','after_postimage'])
def test_P5_T22_catalog_faults_leave_original_source_unchanged(source,boundary):
    before=(source.root/CATALOG/'genre.yml').read_bytes();desired=definition()
    def checkpoint(name):
        if name==boundary:raise RuntimeError('injected')
    with pytest.raises(RuntimeError):prepare_catalog(source,{desired['id']:desired},checkpoint=checkpoint)
    assert before==(source.root/CATALOG/'genre.yml').read_bytes()


def test_P5_T22_cancelled_staging_retains_source(source):
    desired=definition()
    with pytest.raises(BulkError,match='cancelled'):prepare_catalog(source,{desired['id']:desired},cancel=lambda:True)
