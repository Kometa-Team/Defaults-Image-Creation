"""Audit/register a host-held ZFS snapshot inside an unprivileged helper container.

Native ZFS operations belong to the separately approved host script. This module
never creates, destroys, rolls back, releases or mounts any dataset/snapshot.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time

from bulk_regeneration_state import atomic_json, canonical, read_json, reject_links
from bulk_source import KNOWN_INPUTS, audit, source_identity, validate_pin


def register(root,registry,commit,snapshot,guid,host_path,hold_tag='kometa-people-bulk'):
    root=Path(root).resolve();registry=Path(registry).resolve()
    reject_links(root);reject_links(registry)
    if os.name!='posix' or not os.statvfs(root).f_flag & os.ST_RDONLY:
        raise ValueError('Snapshot must be mounted read-only before its audit')
    dataset, separator, snapshot_name = snapshot.partition('@')
    if (not re.fullmatch('[0-9a-f]{40}',commit) or not str(guid).isdigit()
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]*',dataset)
            or not separator or snapshot_name!='people-'+commit
            or hold_tag!='kometa-people-bulk'):
        raise ValueError('Unexpected approved source snapshot identity')
    host=Path(host_path)
    if (not host.is_absolute() or '..' in host.parts
            or host.parts[-3:]!=('.zfs','snapshot','people-'+commit)):
        raise ValueError('Snapshot host path must identify this exact commit snapshot')
    identity=source_identity(root)
    if identity['commit']!=commit:
        raise ValueError('Snapshot Git commit differs from the approved source commit')
    target=registry/(commit+'.json')
    if target.exists():
        saved=read_json(target);digest=saved.pop('pin_sha256')
        if canonical(saved)!=digest or saved['storage']['snapshot_guid']!=str(guid) or saved['source']['commit']!=commit:
            raise ValueError('Existing registry evidence differs; preserve it')
        if canonical(read_json(registry/(commit+'.audit.json')))!=saved['audit_sha256']:
            raise ValueError('Existing snapshot audit no longer verifies')
        return dict(saved,pin_sha256=digest)
    report=audit(root,progress=lambda n,t,c:print(f'[SNAPSHOT AUDIT] {n}/{t} {c}',flush=True))
    packed=dict(report,items=dict(count=len(report['items']),chunks=[report['items'][i:i+2048] for i in range(0,len(report['items']),2048)]))
    audit_path=registry/(commit+'.audit.json')
    if audit_path.exists() and read_json(audit_path)!=packed:
        raise ValueError('Existing audit differs; preserve its evidence')
    if not audit_path.exists():atomic_json(audit_path,packed)
    if report['failed'] or set(report['known_inputs'])!=set(KNOWN_INPUTS) or any(x!='verified' for x in report['known_inputs'].values()):
        raise ValueError('Snapshot integrity acceptance failed; snapshot/hold and audit are retained')
    value=dict(version=1,source=identity,protection='zfs-held-snapshot',
        audit_sha256=canonical(packed),inventory_sha256=report['inventory_sha256'],
        total=report['total'],verified=report['verified'],created=time.time(),
        storage=dict(snapshot=snapshot,snapshot_guid=str(guid),host_path=host_path,hold_tag=hold_tag))
    value['pin_sha256']=canonical(value)
    atomic_json(target,value)
    return value


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['identity','register','verify'])
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--registry',type=Path)
    parser.add_argument('--commit',required=True)
    parser.add_argument('--snapshot')
    parser.add_argument('--guid')
    parser.add_argument('--host-path')
    args=parser.parse_args(argv)
    if args.command=='identity':
        value=source_identity(args.source)
        if value['commit']!=args.commit:raise ValueError('Source commit changed before snapshot creation')
        print(json.dumps(value));return 0
    if not all((args.registry,args.snapshot,args.guid,args.host_path)):
        parser.error('register/verify require registry, snapshot, guid and host-path')
    if args.command=='register':
        value=register(args.source,args.registry,args.commit,args.snapshot,args.guid,args.host_path)
    else:
        value=validate_pin(args.source,args.registry/(args.commit+'.json'),True)
        if value['storage']!=dict(snapshot=args.snapshot,snapshot_guid=args.guid,host_path=args.host_path,hold_tag='kometa-people-bulk'):
            raise ValueError('Live ZFS identity differs from the pinned snapshot')
        report=read_json(args.registry/(args.commit+'.audit.json'))
        if canonical(report)!=value['audit_sha256']:
            raise ValueError('Snapshot audit report changed')
    print(json.dumps(value,indent=2))
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,KeyError) as error:
        print('ERROR: '+str(error),file=sys.stderr);raise SystemExit(1)
