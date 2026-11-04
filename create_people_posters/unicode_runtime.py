"""Version-3 local Unicode successor seal; grants no CI/publication authority.

Historical v1/v2 manifests and their verifier remain independent and unchanged.
Operators verify the precomputed release; only developers explicitly emit a seal.
"""
import argparse
import json
from pathlib import Path
from bulk_regeneration_state import reject_links
from bulk_runtime import RUNTIME_FILES, release_digest
from unicode_labels import POLICY_SHA256, POLICY_VERSION, INTER_SHA256

PARENT='05ea93ba4b75a6c8fbd3755bdf817cb6c8485338'
MODULES=(*RUNTIME_FILES,'unicode_labels.py','unicode_review.py','unicode_runtime.py')
LICENSES=('OFL-Comfortaa.txt','OFL-Fuggles.txt','OFL-Inter.txt','OFL-Montserrat.txt')


def files(root):
    from create_people_poster import FONTS, ARTWORK
    return [*(root/n for n in MODULES),*(root/'fonts'/n for n in FONTS),
            *(root/'fonts'/n for n in LICENSES),*(root/'assets/people'/n for n in ARTWORK)]


def inventory(root):
    result={}
    for path in files(root):
        reject_links(path)
        if not path.is_file():raise ValueError('Missing Unicode runtime resource: '+str(path))
        result[path.relative_to(root).as_posix()]=release_digest(path)
    if result.get('fonts/Inter-Light.ttf')!=INTER_SHA256:
        raise ValueError('Inter bytes differ from the explicitly approved official Light 300')
    return result


def verify_release(root,path):
    root=Path(root)
    reject_links(path)
    value=json.loads(Path(path).read_text(encoding='utf8'))
    if (value.get('version')!=3 or value.get('profile')!=POLICY_VERSION
            or value.get('parent_commit')!=PARENT or value.get('unicode_policy_sha256')!=POLICY_SHA256
            or value.get('publication_authorized') is not False
            or value.get('ci_authorized') is not False):
        raise ValueError('Unknown Unicode successor release')
    expected=inventory(root)
    if value.get('files')!=expected:
        raise ValueError('Unicode runtime resource bytes or inventory changed')
    # Unexpected runtime resources must not silently enter a sealed container.
    # Historical Jost is allowed in a developer checkout, never a dependency.
    extra={p.relative_to(root).as_posix() for directory in ('fonts','assets/people')
           for p in (root/directory).glob('*') if p.is_file()}-set(expected)
    if extra-{'fonts/Jost.ttf','fonts/Jost-260.ttf','fonts/OFL-Jost.txt','fonts/README.md'}:
        raise ValueError('Unexpected Unicode runtime resource inventory')
    return value


def emit(root,path):
    root=Path(root)
    value=dict(version=3,profile=POLICY_VERSION,parent_commit=PARENT,
               unicode_policy_sha256=POLICY_SHA256,publication_authorized=False,
               ci_authorized=False,files=inventory(root))
    reject_links(path)
    with Path(path).open('x',encoding='utf8') as stream:
        json.dump(value,stream,indent=2,sort_keys=True)
        stream.write('\n')
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['verify','emit-local-successor'])
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--manifest',type=Path,required=True)
    args=parser.parse_args()
    value=verify_release(args.root,args.manifest) if args.command=='verify' else emit(args.root,args.manifest)
    print(json.dumps(dict(version=3,profile=value['profile'],files=len(value['files']),
                         inter_sha256=INTER_SHA256,publication_authorized=False,ci_authorized=False)))


if __name__=='__main__':main()
