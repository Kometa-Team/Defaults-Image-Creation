"""Offline native GitHub fixtures over real P3/P4 encoded-artifact consumers."""
import base64
from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
from unittest.mock import patch

from create_defaults.bulk.common import fingerprint
from create_defaults.bulk.contracts.destination_preflight.inventory import tree_sha
from create_defaults.bulk.contracts.translation_preflight.sources import blob_sha, lookup, parse
from create_defaults.bulk.languages import LanguageSnapshot
from create_defaults.bulk.lifecycle.github_observations import Target, FixtureObserver
from create_defaults.bulk.lifecycle.github_decisions import ObservationQuery, PackageSelection, FixtureDecisionConsumer, fixture_message
from create_defaults.phase4.tests import review_samples

SUBMITTER = dict(id=11, login='submitter', type='User')
MAINTAINER = dict(id=22, login='maintainer', type='User')
CONFIRMED = '2026-10-29T00:00:00Z'
DECIDED = '2026-10-29T00:01:00Z'
BASE = 'a' * 40
HEAD = 'b' * 40


def git_fixtures(target, files, *, principal=MAINTAINER, commit=BASE):
    prefix = 'repos/' + target.repository
    owner = target.repository.split('/')[0]
    metadata = dict(id=target.repository_id, full_name=target.repository,
        owner=dict(id=target.owner_id, login=owner, type='Organization'),
        permissions=dict(pull=True, triage=True, push=True, maintain=True, admin=False))
    role = 'write' if principal['id'] == SUBMITTER['id'] else 'maintain'
    values = {'user': (principal, {}), prefix: (metadata, {}),
        prefix + '/collaborators/' + principal['login'] + '/permission': (dict(user=principal, role_name=role, permission='write'), {})}
    for user, native_role in [(SUBMITTER, 'write'), (MAINTAINER, 'maintain')]:
        values[prefix + '/collaborators/' + user['login'] + '/permission'] = (dict(user=user, role_name=native_role, permission='write'), {})
    nested = {}
    for path, raw in files.items():
        parts = path.split('/')
        node = nested
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = raw

    def tree(node):
        entries = []
        for name, raw in sorted(node.items()):
            if type(raw) is dict:
                sha, mode, kind = tree(raw), '040000', 'tree'
            else:
                sha, mode, kind = blob_sha(raw), '100644', 'blob'
                values[prefix + '/git/blobs/' + sha] = (dict(sha=sha, size=len(raw), encoding='base64', content=base64.b64encode(raw).decode()), {})
            entries.append(dict(path=name, mode=mode, type=kind, sha=sha))
        sha = tree_sha([dict(name=e['path'], mode=e['mode'], sha=e['sha']) for e in entries])
        values[prefix + '/git/trees/' + sha] = (dict(sha=sha, tree=entries, truncated=False), {})
        return sha

    root = tree(nested)
    values[prefix + '/git/ref/heads/' + target.branch] = (dict(ref='refs/heads/' + target.branch, object=dict(sha=commit, type='commit')), {})
    values[prefix + '/git/commits/' + commit] = (dict(sha=commit, tree=dict(sha=root)), {})
    return values, root


def translation_snapshot():
    original = review_samples.english_snapshot()
    repo = original.snapshot.data['provenance']['repository']
    target = Target(repo, 101, 1101, 'main')
    _, tree = git_fixtures(target, dict(original.resources))
    data = original.snapshot.data
    snapshot = LanguageSnapshot.create(data['languages'], provenance=dict(data['provenance'], tree=tree), aliases=data['aliases'])
    return replace(original, snapshot=snapshot)


def artwork_inputs(row):
    snapshot = translation_snapshot()
    if len(row[2].to_dict()['required_members']) > 1:
        from create_defaults.phase4.tests.transaction_samples import cohort_inputs
        with patch.object(review_samples, 'english_snapshot', return_value=snapshot):
            return cohort_inputs(row)
    return review_samples.inputs(row, snapshot=snapshot)


def case(row, label, *, category=None, scope='artwork'):
    trial, context, composition, _ = row
    inputs = artwork_inputs(row)
    snapshot = translation_snapshot()
    source_files = {}
    mapping = []
    for view in composition.to_dict()['views']:
        for source in view['sources']:
            local = (trial.config.asset_dir / source['path']).resolve()
            remote = 'assets/' + source['path']
            source_files[remote] = local.read_bytes()
            if (remote, str(local)) not in mapping:
                mapping.append((remote, str(local)))
    for path in (*context.candidate.paths, context.candidate.profiles_path):
        local = Path(path).resolve()
        remote = local.relative_to(trial.root).as_posix()
        source_files[remote] = local.read_bytes()
        mapping.append((remote, str(local)))
    proposal = Target('Fixture/Creation', 201, 1201, 'main')
    source = Target('Fixture/Proposed', 202, 1202, 'proposal')
    translation = Target('Fixture/Translations', 101, 1101, 'main')
    destination_value = inputs.phase3_inputs['destination_inputs']['evidence'].to_dict()['target']
    repo = destination_value['repository']
    destination = Target(repo['name'], repo['repository_id'], repo['owner_id'], destination_value['branch'], root=destination_value['root'])
    queries = {}
    for label_, principal in [('submitter', SUBMITTER), ('maintainer', MAINTAINER)]:
        values, _ = git_fixtures(proposal, {}, principal=principal)
        prefix = 'repos/' + proposal.repository
        metadata = values[prefix][0]
        pull = dict(id=303, number=7, user=SUBMITTER, state='open', merged=False, draft=False, updated_at=CONFIRMED,
            base=dict(repo=metadata, ref='main', sha=BASE), head=dict(repo=dict(id=source.repository_id), sha=HEAD))
        values.update({prefix + '/pulls/7': (pull, {}),
            prefix + '/pulls/7/reviews?per_page=100&page=1': ([], {}),
            prefix + '/issues/7/comments?per_page=100&page=1': ([], {}),
            prefix + '/collaborators/maintainer/permission': (dict(user=MAINTAINER, role_name='maintain', permission='write'), {})})
        queries[label_] = ObservationQuery(FixtureObserver(proposal, values), pull_request=7)
    values, _ = git_fixtures(source, source_files, commit=HEAD)
    queries['source'] = ObservationQuery(FixtureObserver(source, values), paths=tuple(sorted(source_files)))
    values, _ = git_fixtures(translation, dict(translation_snapshot().resources))
    resources = dict(snapshot.resources)
    keys = tuple(sorted({lookup(parse(resources[v['resource_path']]), v['key'])[2]
                         for item in inputs.phase3_inputs['inputs'] if item.selection is not None
                         for v in item.selection.to_dict()['values']}))
    queries['translation'] = ObservationQuery(FixtureObserver(translation, values), paths=tuple(sorted(dict(translation_snapshot().resources))), translation_keys=keys)
    values, tree = git_fixtures(destination, {}, commit=destination_value['baseline_commit'])
    assert tree == destination_value['baseline_tree']
    queries['destination'] = ObservationQuery(FixtureObserver(destination, values))
    consumer = FixtureDecisionConsumer(trial, queries, submitter_id=11, maintainer_id=22, source_files=tuple(mapping))
    category = category or context.registry.view().entry(composition.to_dict()['required_members'][0])['category']
    variants = tuple(sorted({context.registry.view().entry(i)['variant'] for i in composition.to_dict()['required_members']}))
    selection = PackageSelection.current(category, variants=None if scope == 'contract' else variants)
    binding = consumer.prepare(selection, inputs=inputs if scope == 'artwork' else None,
        review_id='synthetic.review.m3-' + fingerprint(label)[:24] if scope == 'artwork' else None, scope=scope)
    result = dict(trial=trial, row=row, consumer=consumer, queries=queries, inputs=inputs, selection=selection, binding=binding, scope=scope)
    install(result)
    return result


def install(case, *, action='approve', mutate=None):
    binding = case['binding']
    prefix = 'repos/' + case['queries']['submitter'].observer.target.repository
    comment = dict(id=505, user=SUBMITTER, body=fixture_message(binding, stage='submitter', action='confirm'),
        created_at=CONFIRMED, updated_at=CONFIRMED, issue_url='https://api.github.com/' + prefix + '/issues/7')
    reference = dict(id=comment['id'], revision_sha256=fingerprint(comment))
    review = dict(id=404, user=MAINTAINER, state='APPROVED' if action == 'approve' else 'CHANGES_REQUESTED',
        body=fixture_message(binding, stage='maintainer', action=action, confirmation=reference),
        commit_id=HEAD, submitted_at=DECIDED, pull_request_url='https://api.github.com/' + prefix + '/pulls/7')
    if mutate:
        mutate(comment, review)
    for role in ('submitter', 'maintainer'):
        values = case['queries'][role].observer._transport.responses
        values[prefix + '/issues/7/comments?per_page=100&page=1'] = ([deepcopy(comment)], {})
        values[prefix + '/issues/comments/505'] = (deepcopy(comment), {})
        values[prefix + '/pulls/7/reviews?per_page=100&page=1'] = ([deepcopy(review)], {})
        values[prefix + '/pulls/7/reviews/404'] = (deepcopy(review), {})
    case['confirmation'], case['review'] = comment, review


def contract_case(trial, label, *, category='Genre'):
    """Decision/contract protocol tests need no artwork or visual authority."""
    selection = PackageSelection.current(category)
    selection.select(whole_package=True)
    proposal = Target('Fixture/Creation', 201, 1201, 'main')
    source = Target('Fixture/Proposed', 202, 1202, 'proposal')
    queries = {}
    for label_, principal in [('submitter', SUBMITTER), ('maintainer', MAINTAINER)]:
        values, _ = git_fixtures(proposal, {}, principal=principal)
        prefix = 'repos/' + proposal.repository
        pull = dict(id=303, number=7, user=SUBMITTER, state='open', merged=False, draft=False, updated_at=CONFIRMED,
            base=dict(repo=values[prefix][0], ref='main', sha=BASE), head=dict(repo=dict(id=source.repository_id), sha=HEAD))
        values.update({prefix+'/pulls/7':(pull,{}), prefix+'/pulls/7/reviews?per_page=100&page=1':([],{}),
            prefix+'/issues/7/comments?per_page=100&page=1':([],{})})
        queries[label_] = ObservationQuery(FixtureObserver(proposal, values), pull_request=7)
    contract_root = Path(__file__).resolve().parents[3]/'create_defaults/bulk/contracts'
    release = json.loads((contract_root/'categories/data/release-v1.json').read_text())
    entry = next(v for v in release['entries'] if v['category'] == category)
    names = {entry['contract_path'],entry['rules_path'],'categories/data/release-v1.json','categories/data/review-registry-v1.json'}
    source_files = {'create_defaults/bulk/contracts/'+name:(contract_root/name).read_bytes() for name in names}
    values, _ = git_fixtures(source, source_files, commit=HEAD)
    queries['source'] = ObservationQuery(FixtureObserver(source, values), paths=tuple(sorted(source_files)))
    translation = Target('Fixture/Translations', 101, 1101, 'main')
    values, _ = git_fixtures(translation, {'en.yml':b'caption: Fixture\n'})
    queries['translation'] = ObservationQuery(FixtureObserver(translation, values), paths=('en.yml',), translation_keys=('caption',))
    destination = Target('Kometa-Team/Default-Images', 102, 1102, 'master', purpose='official-destination')
    values, _ = git_fixtures(destination, {})
    queries['destination'] = ObservationQuery(FixtureObserver(destination, values))
    consumer = FixtureDecisionConsumer(trial, queries, submitter_id=11, maintainer_id=22)
    binding = consumer.prepare(selection, scope='contract')
    result = dict(trial=trial,consumer=consumer,queries=queries,selection=selection,binding=binding,scope='contract')
    install(result)
    return result


def consume(case, **kwargs):
    return case['consumer'].consume(case['binding'], confirmation_id=505, review_id=404, scope=case['scope'], **kwargs)


def change_proposal(case, change):
    prefix = 'repos/' + case['queries']['submitter'].observer.target.repository
    for label in ('submitter', 'maintainer'):
        change(case['queries'][label].observer._transport.responses, prefix)


def export_native(case, receipt, *, unavailable=None):
    """Export actual fixture bytes/owned worker rows, never a visual approval."""
    selected = os.getenv('M3_NATIVE_EXPORT')
    if not selected:
        return
    root = Path(__file__).resolve().parents[3]
    directory = (root / selected).resolve()
    assert directory == (root/'config/ci-validation/phase5-m3/native').resolve()
    directory.mkdir(parents=True, exist_ok=True)
    from create_defaults.bulk.lifecycle.previews import CompositionArchive
    from create_defaults.bulk.common import canonical
    archive = CompositionArchive(case['trial'].config.cache_dir, readonly=True)
    evidence = archive.load(case['row'][2].sha256, context=case['inputs'].composition)
    category = case['selection'].category
    rows = []
    for view in evidence.to_dict()['views']:
        for member in view['members']:
            raw = archive.read_bytes(member['object_sha256'])
            name = category + '-' + view['appearance'] + '-' + fingerprint(member['identity'])[:16] + ('.jpg' if member['format'] == 'JPEG' else '.png')
            (directory/name).write_bytes(raw)
            worker_receipt = json.loads(archive.store.read_object(member['receipt_object_sha256']))
            with archive.store.read_connection() as db:
                worker = dict(db.execute('SELECT * FROM jobs WHERE id=?', (worker_receipt['job_id'],)).fetchone())
            rows.append(dict(file=name, member=member, receipt=worker_receipt, worker=worker))
    assert (receipt is None) == (unavailable is not None)
    (directory/(category+'.json')).write_bytes(canonical(dict(composition_sha256=evidence.sha256,
        composition=evidence.to_dict(), consumption_receipt=receipt.to_dict() if receipt else None,
        decision_status='unavailable' if unavailable else 'synthetic-consumed',
        unavailable=unavailable, rows=rows)))
