"""Fresh GitHub-only sparse source for a 20-person local Linux compatibility test.

This is a bounded test fixture, not the production source initializer or a
full-repository integrity audit. Production source pins require a complete audit.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from PIL import Image

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--selection',type=Path,required=True)
parser.add_argument('--destination',type=Path,required=True)
args=parser.parse_args()
selection=json.loads(args.selection.read_text(encoding='utf8'))
root=args.destination
if root.exists():raise SystemExit('Destination exists; preserve earlier test evidence')
if len(selection['items'])!=20:raise SystemExit('Exactly 20 explicit fixture inputs required')
environment=dict(os.environ,GIT_TERMINAL_PROMPT='0')
def git(*parts,input=None):
    return subprocess.run(['git','-c','core.autocrlf=false','-c','core.hooksPath=/dev/null',*parts],
        input=input,capture_output=True,check=True,env=environment).stdout
git('clone','--filter=blob:none','--no-checkout','--depth=1','--single-branch','--branch','master',
    '--no-tags','https://github.com/Kometa-Team/People-Images-transparent.git',str(root))
commit=selection['source']['commit']
if git('-C',str(root),'rev-parse','HEAD').decode().strip()!=commit:
    git('-C',str(root),'fetch','--depth=1','--filter=blob:none','origin',commit)
patterns=[]
for row in selection['items']:
    relative=row['relative']
    if '..' in relative.split('/') or relative.startswith('/') or '\\' in relative:
        raise SystemExit('Unsafe fixture path')
    patterns.append('/'+''.join('\\'+c if c in '*?[]\\' else c for c in relative))
git('-C',str(root),'sparse-checkout','init','--no-cone')
git('-C',str(root),'sparse-checkout','set','--no-cone','--stdin',input=('\n'.join(patterns)+'\n').encode())
git('-C',str(root),'checkout','--detach',commit)
verified=[]
for row in selection['items']:
    path=root/row['relative'];data=path.read_bytes()
    oid=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    if oid!=row['git_blob']:raise SystemExit('Git blob mismatch: '+row['relative'])
    with Image.open(path) as image:image.verify()
    with Image.open(path) as image:
        image.load();attributes=dict(dimensions=list(image.size),mode=image.mode)
    verified.append(dict(row,sha256=hashlib.sha256(data).hexdigest(),**attributes))
assert not git('-C',str(root),'status','--porcelain=v1').strip()
report=dict(scope='explicit-20-person-linux-compatibility-source',source_commit=commit,
    verified=verified,failures=[],full_repository_audit_completed=False,windows_sources_used=False)
(root.parent/'preparation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(dict(verified=len(verified),bytes=sum(r['size'] if isinstance(r['size'],int) else 0 for r in verified),source_commit=commit)))
