"""Bounded GET-only publication and CI proof. Never uses publisher mutations."""
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import unicodedata
from urllib.parse import quote

import requests
from create_people_posters.github_inventory_core import GitHubError, get_json, complete_tree
from create_people_posters.people_github import REPOSITORIES, auth_token
from create_people_posters.people_retention_state import RetentionBlocked

SOURCE_REPO = 'Kometa-Team/Defaults-Image-Creation'
WORKFLOWS = {'Default Poster Candidate Validation':45,'Lifecycle M6 Validation':11,
    'Lifecycle M7 Validation':11,'Dependency provenance maintenance':2,
    'People recovery storage regression':2}


class ReadOnlyGitHub:
    def __init__(self, session=None):
        self.session = session or requests.Session()
        self.session.headers.update({'Authorization':'Bearer '+auth_token(),
            'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})

    def get(self, repo, route):
        if repo not in {*REPOSITORIES.values(),SOURCE_REPO} or not route.startswith('/'):
            raise RetentionBlocked('GitHub repository/route outside retention allowlist')
        if any(c in route for c in ('\\','\r','\n','#')) or '..' in route.split('?')[0].split('/'):
            raise RetentionBlocked('Unsafe GitHub proof route')
        def bounded_sleep(seconds):
            if seconds>30: raise RetentionBlocked('Remote verification deferred by rate limit')
            time.sleep(seconds)
        try:
            return get_json(self.session, 'https://api.github.com/repos/'+repo+route,
                            sleep=bounded_sleep, attempts=3)
        except GitHubError as error:
            # The existing inventory walker discards the failed recursive
            # response and verifies every nonrecursive subtree instead.
            if (repo in REPOSITORIES.values()
                    and re.fullmatch(r'/git/trees/[0-9a-f]{40}\?recursive=1',route)
                    and error.status in {0,500,502,503,504}):
                raise
            raise RetentionBlocked('GitHub verification unavailable; retained') from None
        except Exception:
            raise RetentionBlocked('GitHub verification unavailable; retained') from None

    def head(self, repo):
        return self.get(repo, '/git/ref/heads/master')['object']['sha']

    def snapshot(self):
        result={}
        for style,repo in REPOSITORIES.items():
            head=self.head(repo)
            commit=self.get(repo,'/git/commits/'+head)
            tree=commit['tree']['sha']
            def get_tree(sha,recursive):
                return self.get(repo,'/git/trees/'+sha+('?recursive=1' if recursive else ''))
            rows=complete_tree(get_tree,tree)
            entries={r['path']:r for r in rows}
            if len(entries)!=len(rows): raise RetentionBlocked('Ambiguous remote tree paths')
            folded=[unicodedata.normalize('NFC',p).casefold() for p in entries]
            if len(set(folded))!=len(folded): raise RetentionBlocked('Ambiguous case in remote paths')
            result[repo]=dict(style=style,repo=repo,branch='master',head=head,tree=tree,entries=entries)
        self.confirm(result)
        return result

    def confirm(self, snapshot, repositories=None):
        for repo in repositories or snapshot.keys():
            if self.head(repo)!=snapshot[repo]['head']:
                raise RetentionBlocked('Remote head changed during verification; stop')

    def validate_ci(self, receipt, source_root):
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source_root,text=True).strip()
        tested=receipt.get('head')
        if not isinstance(tested,str) or not re.fullmatch('[0-9a-f]{40}',tested):
            raise RetentionBlocked('Invalid tested implementation HEAD')
        if tested!=head:
            parents=subprocess.check_output(['git','rev-list','--parents','-n','1','HEAD'],cwd=source_root,text=True).split()
            if len(parents)!=3 or parents[0]!=head or parents[2]!=tested:
                raise RetentionBlocked('CI receipt is not for this implementation HEAD or its exact merge')
            trees=subprocess.check_output(['git','rev-parse','HEAD^{tree}',tested+'^{tree}'],cwd=source_root,text=True).split()
            if len(trees)!=2 or trees[0]!=trees[1]:
                raise RetentionBlocked('Merged implementation differs from the tested file tree')
        # Legacy external submodule workspaces are outside People processing.
        # Every regular tracked source edit still fails closed.
        if subprocess.check_output(['git','status','--porcelain','--untracked-files=no','--ignore-submodules=all'],cwd=source_root):
            raise RetentionBlocked('Implementation changed after CI')
        from ci.people_retention_maintenance import verify_checkout, test_ids
        verify_checkout()
        names=set(); jobs={}; dependency=[]
        for run_id in receipt.get('run_ids',[]):
            if not isinstance(run_id,int) or run_id<=0: raise RetentionBlocked('Invalid CI run identifier')
            run=self.get(SOURCE_REPO,'/actions/runs/'+str(run_id))
            name=run.get('name')
            if (name not in WORKFLOWS or name in names or run.get('head_sha')!=tested
                    or run.get('status')!='completed' or run.get('conclusion')!='success'
                    or run.get('event')!='pull_request'):
                raise RetentionBlocked('Missing, stale or failed mandatory workflow')
            data=self.get(SOURCE_REPO,f'/actions/runs/{run_id}/jobs?per_page=100')
            selected=data['jobs']
            if (data['total_count']!=WORKFLOWS[name] or len(selected)!=WORKFLOWS[name]
                    or any(j['status']!='completed' or j['conclusion']!='success' for j in selected)):
                raise RetentionBlocked('Failed, cancelled, skipped or missing mandatory job')
            names.add(name); jobs[name]=[j['id'] for j in selected]
            if name=='Dependency provenance maintenance': dependency=selected
        if names!=set(WORKFLOWS): raise RetentionBlocked('All five mandatory workflows required')
        expected=set(test_ids())
        # Check actual hosted unittest IDs, not just a green job or local token.
        for job in dependency:
            result=subprocess.run(['gh','run','view','--repo',SOURCE_REPO,'--job',str(job['id']),'--log'],
                                  capture_output=True,text=True,encoding='utf8')
            if result.returncode: raise RetentionBlocked('Cannot verify mandatory retention test IDs')
            observed=set(re.findall(r'\((test_people_retention(?:_maintenance)?\.[^)]+)\) \.\.\. ok',result.stdout))
            if observed!=expected:
                raise RetentionBlocked('Missing, skipped or unexpected retention control ID')
        return dict(head=tested,implementation_head=head,workflows=jobs,retention_test_ids=sorted(expected),verified_utc=time.time())


def exact_entry(snapshot,repo,path,blob,size=None):
    if repo not in REPOSITORIES.values() or repo not in snapshot:
        raise RetentionBlocked('Publication repository is not authorized')
    row=snapshot[repo]['entries'].get(path)
    if (not row or row.get('mode')!='100644' or row.get('type')!='blob' or row.get('sha')!=blob
            or (size is not None and row.get('size')!=size)):
        raise RetentionBlocked('Published artwork missing or changed: '+repo+'/'+path)
    return dict(repo=repo,path=path,blob=blob,head=snapshot[repo]['head'],tree=snapshot[repo]['tree'])
