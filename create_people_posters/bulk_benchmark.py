"""Bounded, isolated canary benchmarks. Never starts a full regeneration."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

from bulk_regeneration_state import STYLES, atomic_json, resource_usage, sha, reject_links


class TimedConnection(sqlite3.Connection):
    sqlite_seconds=0.0
    commits=0
    def execute(self,*args,**kwargs):
        start=time.perf_counter()
        try:return super().execute(*args,**kwargs)
        finally:self.sqlite_seconds+=time.perf_counter()-start
    def executemany(self,*args,**kwargs):
        start=time.perf_counter()
        try:return super().executemany(*args,**kwargs)
        finally:self.sqlite_seconds+=time.perf_counter()-start
    def __exit__(self,*args):
        dirty=self.in_transaction;start=time.perf_counter()
        try:return super().__exit__(*args)
        finally:
            self.sqlite_seconds+=time.perf_counter()-start
            self.commits+=int(dirty)


def process_io():
    path=Path('/proc/self/io')
    return {line.split(':')[0]:int(line.split()[1]) for line in path.read_text().splitlines()} if path.exists() else {}


def case(source,output,workers,sample,styles,pin=None,require_readonly=False,selection=None):
    import bulk_regenerate as cli
    import bulk_regeneration_state as state
    connections=[]
    real=cli.database
    def database(root,readonly=False):
        if readonly:return real(root,readonly=True)
        path=Path(root)/state.STATE/'checkpoint.sqlite3';reject_links(path)
        db=sqlite3.connect(path,timeout=5,factory=TimedConnection)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA synchronous=FULL')
        connections.append(db);return db
    cli.database=database
    args=['--source',str(source),'--output',str(output),'--canary',str(sample),
          '--workers',str(workers),'--styles',*styles]
    if pin:args+=['--source-pin',str(pin)]
    if require_readonly:args+=['--require-readonly-source']
    if selection:args+=['--canary-selection',str(selection)]
    start=time.perf_counter();cpu=time.process_time();io_before=process_io()
    try:
        result=cli.main(args)
        if result:raise ValueError('Canary case failed; preserve its checkpoint and logs')
        seconds=time.perf_counter()-start;cpu_seconds=time.process_time()-cpu;io_after=process_io()
        poster_files={p.relative_to(output).as_posix():(p.stat().st_mtime_ns,sha(p))
                      for p in output.glob('*/*/Images/*.jpg')}
        resume=['--resume','--output',str(output),'--workers',str(workers)]
        if require_readonly:resume+=['--require-readonly-source']
        resume_start=time.perf_counter()
        if cli.main(resume):raise ValueError('Canary no-op resume failed')
        resume_seconds=time.perf_counter()-resume_start
        assert poster_files=={p.relative_to(output).as_posix():(p.stat().st_mtime_ns,sha(p)) for p in output.glob('*/*/Images/*.jpg')}
        receipts=[json.loads(p.read_text()) for p in (output/'.bulk/receipts').rglob('*.json')]
        sources={r['source']:r['timings'] for r in receipts}
        timing_totals={key:sum(row.get(key,0) for row in sources.values())
            for key in ('source_hash_before_seconds','source_hash_after_seconds','input_read_seconds','input_decode_seconds',
                        'renderer_initialization_seconds','render_seconds','font_render_seconds','compositing_and_geometry_seconds')}
        for key in ('jpeg_encoding_seconds','output_write_seconds','output_hash_seconds'):
            timing_totals[key]=sum(r['output_timings'][key] for r in receipts)
        value=dict(workers=workers,selected_people=len(sources),posters=len(receipts),seconds=seconds,
            posters_per_minute=len(receipts)*60/seconds,cpu_seconds=cpu_seconds,
            output_bytes=sum(r['bytes'] for r in receipts),resource_usage=resource_usage(),
            process_io_delta={key:io_after[key]-io_before[key] for key in io_before},
            timings=timing_totals,sqlite_seconds=sum(c.sqlite_seconds for c in connections),
            durable_commits=sum(c.commits for c in connections),noop_resume_seconds=resume_seconds,
            preserved_posters=len(poster_files),styles=styles,
            host=os.uname().nodename if os.name=='posix' else os.environ.get('COMPUTERNAME'),
            note='SQLite includes creation and no-op resume. Input read and decode are measured separately. Font timing includes name and COLLECTION calls; other geometry/compositing is measured by subtraction. Linux process I/O can include cache hits; collect host zpool latency separately.')
        atomic_json(output/'.bulk/benchmark.json',value)
        return value
    finally:cli.database=real


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['run','case'])
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--sample',type=int,default=16)
    parser.add_argument('--workers',type=int,nargs='+',default=[1,2])
    parser.add_argument('--styles',nargs='+',choices=STYLES,default=list(STYLES))
    parser.add_argument('--source-pin',type=Path)
    parser.add_argument('--require-readonly-source',action='store_true')
    parser.add_argument('--canary-selection',type=Path)
    args=parser.parse_args(argv)
    if not 10<=args.sample<=100 or any(not 1<=w<=8 for w in args.workers):
        parser.error('Benchmarks require 10..100 people and 1..8 workers')
    if args.command=='case':
        if len(args.workers)!=1:parser.error('case accepts exactly one worker count')
        case(args.source,args.output,args.workers[0],args.sample,args.styles,args.source_pin,args.require_readonly_source,args.canary_selection)
        return 0
    reject_links(args.output)
    if args.output.exists():raise ValueError('Benchmark root must be new; preserve earlier evidence')
    args.output.mkdir(parents=True)
    results=[]
    for workers in dict.fromkeys(args.workers):
        target=args.output/f'workers-{workers}'
        command=[sys.executable,'-B',str(Path(__file__).resolve()),'case','--source',str(args.source),
            '--output',str(target),'--workers',str(workers),'--sample',str(args.sample),'--styles',*args.styles]
        if args.source_pin:command+=['--source-pin',str(args.source_pin)]
        if args.require_readonly_source:command+=['--require-readonly-source']
        if args.canary_selection:command+=['--canary-selection',str(args.canary_selection)]
        # Separate processes make peak RAM and CPU attribution independent.
        result=subprocess.run(command)
        if result.returncode:raise ValueError('Benchmark child failed; no full run is authorized')
        results.append(json.loads((target/'.bulk/benchmark.json').read_text()))
    atomic_json(args.output/'benchmark-results.json',dict(cases=results,full_run_authorized=False))
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError) as error:
        print('ERROR: '+str(error),file=sys.stderr);raise SystemExit(1)
