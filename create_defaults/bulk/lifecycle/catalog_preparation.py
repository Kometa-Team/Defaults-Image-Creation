"""Exact staged catalog bytes. No production catalog writer or alternate loader."""
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import re
from pathlib import Path
import subprocess
import tempfile

import yaml

from ..common import atomic_bytes, canonical, confined, fingerprint, load_yaml, reject_links, SafeLoader
from ..contracts.models import decode_json
from ..definitions import load_definitions
from ..planner import Planner
from .previews import CompositionTrial, CompositionArchive
from .composition_models import MAX_BINARY
from .preparation_models import fail

ROOT=Path(__file__).resolve().parents[3]
CATALOG='create_defaults/bulk/catalog/'
FILES=('genre.yml','profiles.yml','index-v1.json')
MARKER=dict(kind='phase5-owned-offline-catalog',version=1,simulation=True,production_authorized=False)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def git(root,*args):
    result=subprocess.run(['git','-C',str(reject_links(root)),*args],capture_output=True,timeout=180)
    if result.returncode:fail('local_git')
    return result.stdout


class OwnedCatalog:
    """A newly created source fixture inside a live concrete composition trial.

    No path/URL/repository selector and no constructor adopting an existing root.
    Actual checked-in catalog bytes seed it; ownership is explicitly simulated.
    """
    def __init__(self,trial):
        if type(trial) is not CompositionTrial or trial._closed:fail('owned_trial_required')
        self.trial=trial;self.root=Path(tempfile.mkdtemp(prefix='m5-source-',dir=trial.root)).resolve()
        self.origin_head=git(ROOT,'rev-parse','HEAD').decode().strip()
        self.origin={name:(ROOT/CATALOG/name).read_bytes() for name in FILES}
        self.original_definitions={d.id:d.data for d in load_definitions([ROOT/CATALOG/'genre.yml'],profiles_path=ROOT/CATALOG/'profiles.yml')}
        self.original_index=decode_json(self.origin['index-v1.json'])
        self._validated_genre=sha(self.origin['genre.yml'])
        for name,raw in self.origin.items():
            actual=git(ROOT,'show',self.origin_head+':'+CATALOG+name)
            if actual.replace(b'\r\n',b'\n')!=raw.replace(b'\r\n',b'\n'):fail('dirty_source')
            atomic_bytes(confined(self.root,CATALOG+name),raw)
        atomic_bytes(self.root/'ownership.json',canonical(MARKER))
        git(self.root,'init','-b','main')
        for key,value in {'user.name':'Offline M5','user.email':'offline@invalid.local','core.autocrlf':'false',
                'core.hooksPath':str(self.root/'no-hooks')}.items():git(self.root,'config',key,value)
        git(self.root,'add','--','ownership.json',*(CATALOG+n for n in FILES))
        git(self.root,'commit','-m','Owned offline catalog preimage')

    def require(self):
        if type(self.trial) is not CompositionTrial or self.trial._closed:fail('closed_source')
        if not self.root.is_relative_to(self.trial.root) or not self.root.name.startswith('m5-source-') or decode_json((self.root/'ownership.json').read_bytes())!=MARKER:fail('source_ownership')
        if git(self.root,'remote').strip() or git(self.root,'branch','--show-current').decode().strip()!='main':fail('source_ownership')
        if Path(git(self.root,'rev-parse','--absolute-git-dir').decode().strip()).resolve()!=self.root/'.git':fail('source_ownership')
        if git(self.root,'status','--porcelain').strip():fail('stale_source')

    def observe(self):
        self.require()
        head=git(self.root,'rev-parse','HEAD').decode().strip()
        files={}
        for name in FILES:
            path=confined(self.root,CATALOG+name,must_exist=True);raw=path.read_bytes()
            if len(raw)>(MAX_BINARY if name=='index-v1.json' else 2_000_000) or git(self.root,'show',head+':'+CATALOG+name)!=raw:fail('source_blob')
            mode=git(self.root,'ls-tree',head,'--',CATALOG+name).decode().split()[0]
            if mode!='100644':fail('source_mode')
            files[name]=dict(sha256=sha(raw),git_blob=git(self.root,'rev-parse',head+':'+CATALOG+name).decode().strip())
        paths=set(tree_row.split(b'\t',1)[1].decode() for tree_row in git(self.root,'ls-tree','-r','-z',head).split(b'\0') if tree_row)
        if paths!={'ownership.json',*(CATALOG+n for n in FILES)}:fail('source_root')
        if (self.root/CATALOG/'profiles.yml').read_bytes()!=self.origin['profiles.yml']:fail('locked_profile')
        if files['genre.yml']['sha256']!=self._validated_genre:
            definitions={d.id:d.data for d in load_definitions([self.root/CATALOG/'genre.yml'],profiles_path=self.root/CATALOG/'profiles.yml')}
            if any(definitions.get(i)!=d for i,d in self.original_definitions.items()):fail('historical_catalog_change')
            if any(re.fullmatch(r'genre\.[0-9a-f]{32}',i) is None for i in definitions.keys()-self.original_definitions.keys()):fail('catalog_scope')
            self._validated_genre=files['genre.yml']['sha256']
        index=decode_json((self.root/CATALOG/'index-v1.json').read_bytes())
        if index['sha256']!=fingerprint({k:v for k,v in index.items() if k!='sha256'}):fail('catalog_index')
        if any(index['posters'].get(i)!=r for i,r in self.original_index['posters'].items()):fail('historical_index_change')
        return dict(repository='Kometa-Team/Defaults-Image-Creation',repository_id=1040960557,
            branch='main',commit=head,tree=git(self.root,'rev-parse',head+'^{tree}').decode().strip(),
            origin_commit=self.origin_head,files=files,simulation=True,production_authorized=False)


def _node(mapping,key):
    if not isinstance(mapping,yaml.MappingNode):fail('catalog_shape')
    rows=[value for name,value in mapping.value if name.value==key]
    if len(rows)!=1:fail('catalog_shape')
    return rows[0]


def _token(node,value):
    if not isinstance(node,yaml.ScalarNode) or node.style in ('|','>'):fail('structural_patch_unsupported')
    if isinstance(value,str):
        if '\n' in value or '\r' in value:fail('multiline_patch_unsupported')
        if node.style=="'":return "'"+value.replace("'","''")+"'"
        if node.style=='"':return json.dumps(value,ensure_ascii=False)
        text=yaml.safe_dump(value,allow_unicode=True,default_flow_style=True).removesuffix('...\n').strip()
        return text if '\n' not in text else json.dumps(value,ensure_ascii=False)
    if value is None:return 'null'
    if type(value) is bool:return 'true' if value else 'false'
    if type(value) in (int,float):return json.dumps(value,allow_nan=False)
    fail('structural_patch_unsupported')


def _edits(node,old,new):
    if old==new:return []
    if type(old) is dict and type(new) is dict:
        if set(old)!=set(new):fail('structural_patch_unsupported')
        return [edit for key in old for edit in _edits(_node(node,key),old[key],new[key])]
    if type(old) is list and type(new) is list:
        if not isinstance(node,yaml.SequenceNode) or len(old)!=len(new):fail('structural_patch_unsupported')
        return [edit for child,a,b in zip(node.value,old,new) for edit in _edits(child,a,b)]
    return [(node.start_mark.index,node.end_mark.index,_token(node,new))]


def splice(raw,edits):
    bom=b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    text=raw[len(bom):].decode('utf8');last=0;out=[]
    for start,end,replacement in sorted(edits):
        if start<last or not start<=end<=len(text):fail('overlapping_patch')
        out.extend((text[last:start].encode('utf8'),replacement.encode('utf8')));last=end
    out.append(text[last:].encode('utf8'))
    return bom+b''.join(out)


def patch_yaml(raw,desired):
    if len(raw)>2_000_000 or len(canonical(desired))>2_000_000:fail('catalog_bound')
    return _patch_yaml(raw,canonical(desired))


@lru_cache(maxsize=4)
def _patch_yaml(raw,encoded_desired):
    desired=json.loads(encoded_desired)
    text=raw.decode('utf-8-sig');document=yaml.compose(text)
    values=yaml.load(text,Loader=SafeLoader)
    originals={value['id']:value for value in values['definitions']}
    definitions=_node(document,'definitions')
    if not isinstance(definitions,yaml.SequenceNode) or definitions.flow_style:fail('catalog_shape')
    nodes={_node(row,'id').value:row for row in definitions.value};edits=[];added=[]
    for identity,value in sorted(desired.items()):
        if identity in nodes:
            node=nodes[identity];old=originals[identity]
            if old.get('extends') is not None:fail('profile_patch_unsupported')
            edits.extend(_edits(node,old,value))
        else:added.append(value)
    result=splice(raw,edits)
    if added:
        # Only a NEW block is serialized. Existing bytes, including EOF comments,
        # remain verbatim. Root envelope/strict parsing is rechecked afterward.
        newline='\r\n' if b'\r\n' in raw else '\n'
        suffix=yaml.safe_dump(added,sort_keys=False,allow_unicode=True).replace('\n',newline).encode('utf8')
        result+=(b'' if result.endswith(b'\n') else newline.encode())+suffix
    return result


def patch_index(raw,required):
    if len(raw)>MAX_BINARY:fail('catalog_bound')
    return _patch_index(raw,tuple(sorted(required)))


def _json_encoded(value):return json.dumps(value,separators=(',',':'),ensure_ascii=True,allow_nan=False)


def _json_span(value,key):
    prefix='{'
    for name,item in value.items():
        start=len(prefix)+len(_json_encoded(name))+1
        if name==key:return start,start+len(_json_encoded(item))
        prefix+=_json_encoded(name)+':'+_json_encoded(item)+','
    fail('catalog_index_shape')


@lru_cache(maxsize=4)
def _patch_index(raw,required):
    value=decode_json(raw)
    # Accept only the existing compact index representation. Original strict
    # JSON parsing supplies structure; no second parser or whole-file rewrite.
    if raw.rstrip(b'\r\n')!=_json_encoded(value).encode():fail('catalog_index_shape')
    if set(value)!={'schema_version','posters','sha256'} or value['schema_version']!=1:fail('catalog_index')
    if value['sha256']!=fingerprint({k:v for k,v in value.items() if k!='sha256'}):fail('catalog_index')
    result=deepcopy(value);fresh={}
    for identity in sorted(required):
        record=dict(definition=identity,category='Genre',dependencies=[])
        if identity in value['posters']:
            if value['posters'][identity]!=record:fail('catalog_index_membership')
        else:result['posters'][identity]=record;fresh[identity]=record
    result.pop('sha256');checksum=fingerprint(result)
    pin_start,pin_end=_json_span(value,'sha256');_,posters_end=_json_span(value,'posters')
    edits=[(pin_start,pin_end,json.dumps(checksum))]
    if fresh:
        encoded=canonical(fresh).decode()[1:-1]
        edits.append((posters_end-1,posters_end-1,(',' if value['posters'] else '')+encoded))
    return splice(raw,edits)


@dataclass(frozen=True)
class CatalogPatch:
    source: OwnedCatalog
    observation_json: str
    document_json: str

    @property
    def sha256(self):return fingerprint(json.loads(self.document_json))

    def verify(self,desired):
        if type(self.source) is not OwnedCatalog or self.source.observe()!=json.loads(self.observation_json):fail('stale_source')
        value=json.loads(self.document_json);archive=CompositionArchive(self.source.trial.config.cache_dir,readonly=True)
        if (set(value)!={'version','kind','source','members','definitions_sha256','files',
                'unchanged_definitions_sha256','unchanged_jobs','simulation','production_authorized'}
                or type(value['version']) is not int or value['version']!=1
                or value['kind']!='phase5-owned-catalog-patch' or value['simulation'] is not True
                or value['production_authorized'] is not False):fail('catalog_schema')
        if (value['source']!=json.loads(self.observation_json) or value['members']!=sorted(desired)
                or value['definitions_sha256']!=fingerprint(desired) or set(value['files'])!=set(FILES)):fail('catalog_membership')
        current={n:confined(self.source.root,CATALOG+n,must_exist=True).read_bytes() for n in FILES}
        expected=dict(current,**{'genre.yml':patch_yaml(current['genre.yml'],desired),
            'index-v1.json':patch_index(current['index-v1.json'],desired)})
        for name,row in value['files'].items():
            if name not in FILES:fail('catalog_root')
            if sha(archive.read_bytes(row['before_object']))!=row['before_sha256'] or sha(archive.read_bytes(row['after_object']))!=row['after_sha256']:fail('catalog_object')
            if archive.read_bytes(row['before_object'])!=current[name] or archive.read_bytes(row['after_object'])!=expected[name]:fail('catalog_postimage')
        return value


def prepare_catalog(source,desired,*,cancel=None,checkpoint=lambda name:None):
    if type(source) is not OwnedCatalog:fail('source_ownership')
    if not desired or any(re.fullmatch(r'genre\.[0-9a-f]{32}',i) is None or d.get('id')!=i or d.get('category')!='Genre' or d.get('generator') is not None for i,d in desired.items()):fail('catalog_scope')
    observation=source.observe();checkpoint('before_catalog')
    if cancel is not None and cancel():fail('cancelled')
    raw={n:confined(source.root,CATALOG+n,must_exist=True).read_bytes() for n in FILES}
    stage=confined(source.trial.root,'m5-catalog/'+fingerprint(dict(source=observation,desired=desired)))
    stage.mkdir(parents=True,exist_ok=True)
    before=load_definitions([source.root/CATALOG/'genre.yml'],profiles_path=source.root/CATALOG/'profiles.yml')
    old={d.id:d.data for d in before}
    # Original metadata planner must agree with the complete preimage lookup.
    expanded,_,_=Planner().expand(before)
    index=decode_json(raw['index-v1.json'])
    if {i for i,r in index['posters'].items() if r['category']=='Genre'}!=set(expanded):fail('catalog_index_membership')
    post=dict(raw);post['genre.yml']=patch_yaml(raw['genre.yml'],desired)
    post['index-v1.json']=patch_index(raw['index-v1.json'],desired)
    for name,data in post.items():atomic_bytes(stage/name,data,replace=True)
    after=load_definitions([stage/'genre.yml'],profiles_path=stage/'profiles.yml')
    expected=dict(old,**desired)
    if {d.id:d.data for d in after}!=expected:fail('unintended_definition_change')
    jobs,families,_=Planner().expand(after)
    if families or set(jobs)!=set(expected):fail('unintended_job_change')
    if any(jobs[i].data!=old[i] for i in old if i not in desired):fail('unrelated_job_change')
    new_index=decode_json(post['index-v1.json'])
    if {i for i,r in new_index['posters'].items() if r['category']=='Genre'}!=set(jobs):fail('catalog_index_membership')
    if any(new_index['posters'][i]!=r for i,r in index['posters'].items()):fail('unrelated_index_change')
    checkpoint('after_postimage')
    if cancel is not None and cancel():fail('cancelled')
    if source.observe()!=observation:fail('stale_source')
    archive=CompositionArchive(source.trial.config.cache_dir)
    value=dict(version=1,kind='phase5-owned-catalog-patch',source=observation,members=sorted(desired),
        definitions_sha256=fingerprint(desired),files={n:dict(before_sha256=sha(raw[n]),after_sha256=sha(post[n]),
            before_object=archive.put_bytes(raw[n]),after_object=archive.put_bytes(post[n])) for n in FILES},
        unchanged_definitions_sha256=fingerprint({i:d for i,d in old.items() if i not in desired}),
        unchanged_jobs=len(old.keys()-desired.keys()),simulation=True,production_authorized=False)
    archive.put_json(value)
    return CatalogPatch(source,canonical(observation).decode(),canonical(value).decode())
