"""Version 1 read-only observations. No approval, activation or write consumer.

Trust lives in controlled code + the existing CLI credential boundary, never in
serialized evidence. Fixture observers are permanently labelled synthetic.
Re-observation is mandatory; timestamps do not implement a permission TTL.
"""
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
from urllib.parse import parse_qs, urlsplit

from ..common import canonical, fingerprint, path_key
from ..config import branch_name, repository
from ..contracts.destination_preflight.inventory import tree_sha
from ..contracts.destination_preflight.paths import safe_path
from ..contracts.translation_preflight.sources import blob_sha, lookup, parse
from ..contracts.language_policy.models import timestamp
from ..remote import git_sha
from create_people_posters.github_inventory_core import complete_tree
from .github_observation_transport import _CLI, _Git, ObservationFailure, _failure

VERSION = '1.0.0'
MAX_MEMBERS = 100_000
MAX_PAGES = 20
ROLES = {'read', 'triage', 'write', 'maintain', 'admin'}


def _stamp(value):
    timestamp(value)
    return value


def _number(value):
    if type(value) is not int or not 0 < value < 2 ** 63:
        _failure('invalid', 'numeric_identity')
    return value


def _person(value):
    identifier = _number(value['id'])
    login = value['login']
    if (type(login) is not str or not re.fullmatch(r'[A-Za-z0-9-]{1,39}', login)
            or value['type'] != 'User'):
        _failure('unavailable', 'human_identity_unverified')
    return {'id': identifier, 'login': login}


@dataclass(frozen=True)
class Target:
    """Explicit reviewed selection; expected IDs are constraints, never facts."""

    repository: str
    repository_id: int
    owner_id: int
    branch: str
    root: str | None = None
    purpose: str = 'source'
    language: str = 'en'

    def __post_init__(self):
        if any(type(value) is not str or len(value) > bound for value, bound in (
                (self.repository, 256), (self.branch, 2048), (self.language, 63))):
            _failure('invalid', 'target_bound')
        repository(self.repository)
        _number(self.repository_id)
        _number(self.owner_id)
        branch_name(self.branch)
        if self.root is not None:
            safe_path(self.root)
        if self.purpose not in {'source', 'official-destination'}:
            _failure('unavailable', 'target_policy_unapproved')
        if self.purpose == 'official-destination' and (
                self.repository != 'Kometa-Team/Default-Images' or self.branch != 'master'
                or self.root is not None or self.language != 'en'):
            _failure('invalid', 'official_scope')
        if type(self.language) is not str or not re.fullmatch(r'[a-z]{2,3}(?:-[A-Za-z0-9]+)*', self.language):
            _failure('invalid', 'language_scope')


@dataclass(frozen=True)
class Observation:
    """Safe immutable audit data, deliberately not a grant or deserializable trust."""

    encoded: bytes

    @property
    def sha256(self):
        return hashlib.sha256(self.encoded).hexdigest()

    def to_dict(self):
        import json
        return json.loads(self.encoded)

    @property
    def publication_authorized(self):
        return False

    @property
    def readiness_authorized(self):
        return False

    @property
    def contract_approved(self):
        return False


class GitHubObserver:
    """Explicit supervised read-only session; no arbitrary transport injection.

    Installation-only credentials cannot authenticate /user. App/delegated grant
    boundaries and credential expiry times are not inferred from a public GET.
    Observations never resolve those missing operational policy decisions.
    """

    def __init__(self, target):
        if type(target) is not Target:
            _failure('invalid', 'target_type')
        self.target = target
        self._issued = {}
        # Defer CLI access until observation so missing credentials fail closed
        # as an inspectable result rather than an unredacted construction error.
        self._transport = None

    def _get(self, suffix):
        if self._transport is None:
            self._transport = _CLI(self.target.repository)
        expected = _FixtureTransport if type(self) is FixtureObserver else _CLI
        if type(self._transport) is not expected:
            _failure('invalid', 'transport_boundary')
        value, _ = self._transport.get(suffix if suffix == 'user' else
                                       'repos/' + self.target.repository + suffix)
        return value

    def _identity(self):
        principal = _person(self._get('user'))
        repo = self._get('')
        owner = repo['owner']
        if (repo['id'], owner['id']) != (self.target.repository_id, self.target.owner_id):
            _failure('revoked', 'repository_or_owner_changed')
        _number(repo['id'])
        _number(owner['id'])
        if repo['full_name'] != self.target.repository or owner['login'] != self.target.repository.split('/')[0]:
            _failure('invalid', 'repository_name_mismatch')
        if owner['type'] not in {'User', 'Organization'}:
            _failure('unavailable', 'owner_kind_unverified')
        flags = repo['permissions']
        names = ('pull', 'triage', 'push', 'maintain', 'admin')
        if type(flags) is not dict or any(type(flags.get(k)) is not bool for k in names):
            _failure('unavailable', 'permissions_unverified')
        if not flags['pull']:
            _failure('revoked', 'repository_read_revoked')
        permission = self._permission(principal)
        return dict(principal=principal, repository_id=repo['id'],
            repository=self.target.repository, owner_id=owner['id'], owner_kind=owner['type'],
            permissions={k: flags[k] for k in names}, principal_role=permission,
            credential_boundary='existing-gh-session',
            credential_expiry='unknown-reobserve-required',
            installation_or_delegation='unavailable-not-inferred',
            maintainer_authorization='unavailable-policy-undecided')

    def _permission(self, person):
        permission = self._get('/collaborators/' + person['login'] + '/permission')
        returned = _person(permission['user'])
        if returned != person:
            _failure('invalid', 'permission_identity_mismatch')
        role, level = permission['role_name'], permission['permission']
        if role not in ROLES or level not in {'read', 'write', 'admin', 'none'}:
            _failure('unavailable', 'role_policy_unknown')
        # Observe native values; do not map roles to approval/publication grants.
        return dict(user_id=person['id'], role_name=role, permission=level)

    def _pages(self, suffix):
        rows, seen = [], set()
        for page in range(1, MAX_PAGES + 1):
            endpoint = 'repos/' + self.target.repository + suffix + '?per_page=100&page=' + str(page)
            value, headers = self._transport.get(endpoint)
            if type(value) is not list or len(value) > 100:
                _failure('invalid', 'pagination_shape')
            for row in value:
                identifier = _number(row['id'])
                if identifier in seen:
                    _failure('invalid', 'pagination_duplicate')
                seen.add(identifier)
                rows.append(row)
            link = headers.get('link', '')
            if not link:
                if len(value) == 100:
                    # Fetch a sentinel page rather than trusting a missing Link.
                    continue
                return rows
            relations = {}
            expected = 'https://api.github.com/repos/' + self.target.repository + suffix
            for part in link.split(','):
                match = re.fullmatch(r'\s*<([^>]+)>;\s*rel="(next|prev|first|last)"\s*', part)
                if not match or match[2] in relations:
                    _failure('invalid', 'pagination_scope')
                parsed = urlsplit(match[1])
                parameters = parse_qs(parsed.query)
                if (parsed.scheme + '://' + parsed.netloc + parsed.path != expected or parsed.fragment
                        or set(parameters) != {'per_page', 'page'} or parameters['per_page'] != ['100']
                        or len(parameters['page']) != 1 or not re.fullmatch(r'[1-9][0-9]*', parameters['page'][0])):
                    _failure('invalid', 'pagination_scope')
                if len(parameters['page'][0]) > 6 or int(parameters['page'][0]) > MAX_PAGES:
                    _failure('unavailable', 'pagination_bound')
                relations[match[2]] = int(parameters['page'][0])
            if 'next' not in relations:
                if len(value) == 100:
                    continue
                return rows
            if relations['next'] != page + 1:
                _failure('invalid', 'pagination_scope')
            if not value:
                _failure('unavailable', 'pagination_incomplete')
        _failure('unavailable', 'pagination_bound')

    def _decisions(self, number):
        _number(number)
        pull = self._get('/pulls/' + str(number))
        base, head = pull['base'], pull['head']
        if (_number(pull['number']) != number or _number(base['repo']['id']) != self.target.repository_id
                or _number(base['repo']['owner']['id']) != self.target.owner_id or base['ref'] != self.target.branch):
            _failure('invalid', 'decision_repository')
        if pull['state'] not in {'open', 'closed'} or type(pull['merged']) is not bool or type(pull['draft']) is not bool:
            _failure('invalid', 'decision_state')
        author = _person(pull['user'])
        result = dict(id=_number(pull['id']), number=number, author_id=author['id'],
            state=pull['state'], merged=pull['merged'], draft=pull['draft'],
            updated_at=_stamp(pull['updated_at']), base_commit=git_sha(base['sha']),
            head_commit=git_sha(head['sha']), head_repository_id=_number(head['repo']['id']),
            reviews=[], comments=[])
        histories = []
        for kind, suffix in (('reviews', '/pulls/' + str(number) + '/reviews'),
                             ('comments', '/issues/' + str(number) + '/comments')):
            rows = self._pages(suffix)
            histories.append((suffix, fingerprint(rows)))
            for row in rows:
                person = _person(row['user'])
                identifier = _number(row['id'])
                # Re-read each current native object. List responses and copied
                # records alone do not establish current revision/state.
                detail_suffix = (suffix + '/' + str(identifier) if kind == 'reviews' else
                                 '/issues/comments/' + str(identifier))
                detail = self._get(detail_suffix)
                if fingerprint(detail) != fingerprint(row):
                    _failure('stale', 'decision_changed_during_read')
                expected_url = 'https://api.github.com/repos/' + self.target.repository
                if row['pull_request_url' if kind == 'reviews' else 'issue_url'] != expected_url + (
                        '/pulls/' if kind == 'reviews' else '/issues/') + str(number):
                    _failure('invalid', 'decision_binding')
                body = row['body']
                if type(body) is not str or len(body.encode('utf8')) > 1_000_000:
                    _failure('invalid', 'decision_body_bound')
                observed = dict(id=identifier, author_id=person['id'],
                    body_sha256=hashlib.sha256(body.encode('utf8')).hexdigest(),
                    revision_sha256=fingerprint(row))
                if kind == 'reviews':
                    if row['state'] not in {'APPROVED', 'CHANGES_REQUESTED', 'COMMENTED', 'DISMISSED', 'PENDING'}:
                        _failure('invalid', 'review_state')
                    pending = row['state'] == 'PENDING'
                    observed.update(state=row['state'], commit=None if pending and row['commit_id'] is None else git_sha(row['commit_id']),
                        matches_current_head=row['commit_id'] == head['sha'],
                        submitted_at=None if pending and row['submitted_at'] is None else _stamp(row['submitted_at']),
                        role=self._permission(person))
                else:
                    observed.update(created_at=_stamp(row['created_at']), updated_at=_stamp(row['updated_at']))
                result[kind].append(observed)
        for suffix, expected in histories:
            if fingerprint(self._pages(suffix)) != expected:
                _failure('stale', 'decision_history_changed_during_read')
        if fingerprint(pull) != fingerprint(self._get('/pulls/' + str(number))):
            _failure('stale', 'pull_changed_during_read')
        return result

    def _snapshot(self, paths, keys):
        git = _Git(self._transport)
        head, root_tree = git.head(self.target.branch)
        pages, calls, total = {}, [0], [0]

        def checked_tree(checksum, recursive=False):
            # Reuse complete_tree traversal, while forcing full, hash-checked
            # nonrecursive pages. Never use a partial recursive inventory.
            if recursive:
                return {'truncated': True}
            calls[0] += 1
            if calls[0] > 10_000:
                _failure('unavailable', 'tree_bound')
            value = git.tree(checksum, False)
            if value['truncated']:
                _failure('unavailable', 'tree_incomplete')
            entries = value['tree']
            total[0] += len(entries)
            if total[0] > MAX_MEMBERS:
                _failure('unavailable', 'tree_bound')
            names, normalized = set(), []
            for entry in entries:
                name = safe_path(entry['path'])
                if '/' in name or name in names:
                    _failure('invalid', 'tree_component')
                names.add(name)
                mode, kind = entry['mode'], entry['type']
                if (mode, kind) not in {('100644', 'blob'), ('100755', 'blob'), ('040000', 'tree')}:
                    _failure('invalid', 'unsafe_tree_mode')
                normalized.append(dict(name=name, mode=mode, sha=git_sha(entry['sha'])))
            if tree_sha(normalized) != checksum:
                _failure('invalid', 'tree_hash')
            pages[checksum] = normalized
            # Enforce depth and aggregate limits before helper expands more.
            if sum(len(p) for p in pages.values()) > MAX_MEMBERS:
                _failure('unavailable', 'tree_bound')
            return value

        # The shared helper owns traversal; this wrapper adds stricter provenance
        # and bounds. Git tree path lengths are checked before any persistence.
        entries = complete_tree(checked_tree, root_tree)
        inventory, aliases = {}, set()
        for entry in entries:
            path = safe_path(entry['path'])
            if len(path.split('/')) > 40 or len(inventory) >= MAX_MEMBERS:
                _failure('unavailable', 'tree_bound')
            key = path_key(path)
            if key in aliases:
                _failure('invalid', 'tree_alias')
            aliases.add(key)
            inventory[path] = dict(mode=entry['mode'], sha=git_sha(entry['sha']))
        selected = []
        for path in paths:
            safe_path(path)
            if self.target.root and not path.startswith(self.target.root + '/'):
                _failure('invalid', 'source_root_scope')
            entry = inventory.get(path)
            if entry is None:
                _failure('invalid', 'selected_file_missing')
            if entry['mode'] != '100644':
                _failure('invalid', 'selected_file_mode')
            value = git.blob(entry['sha'])
            if (value['sha'] != entry['sha'] or value['encoding'] != 'base64'
                    or type(value['content']) is not str or len(value['content']) > 11_000_000):
                _failure('invalid', 'blob_metadata')
            raw = base64.b64decode(''.join(value['content'].split()), validate=True)
            if (len(raw) > 8_000_000 or type(value['size']) is not int
                    or value['size'] != len(raw) or blob_sha(raw) != entry['sha']):
                _failure('invalid', 'blob_hash')
            traces = []
            if keys:
                data = parse(raw)
                for key in keys:
                    found, text, actual = lookup(data, key)
                    if not found or type(text) is not str or actual != key:
                        _failure('invalid', 'translation_key')
                    traces.append(dict(key=key, value_sha256=fingerprint(text)))
            selected.append(dict(path=path, blob=entry['sha'],
                sha256=hashlib.sha256(raw).hexdigest(), size=len(raw), values=traces))
        if git.head(self.target.branch) != (head, root_tree):
            _failure('stale', 'head_changed_during_read')
        return dict(branch=self.target.branch, root=self.target.root, language=self.target.language,
            purpose=self.target.purpose, commit=head, tree=root_tree,
            complete=True, inventory_entries=len(inventory),
            inventory_sha256=fingerprint(inventory), selected=selected)

    def observe(self, *, paths=(), translation_keys=(), pull_request=None):
        """Always fetch current facts; source key values/bodies are hashed only."""
        query = None
        try:
            if type(self) not in {GitHubObserver, FixtureObserver}:
                _failure('invalid', 'observer_type')
            if (type(paths) is not tuple or type(translation_keys) is not tuple
                    or len(paths) > 100 or len(set(paths)) != len(paths)
                    or len(translation_keys) > 100 or len(set(translation_keys)) != len(translation_keys)
                    or (translation_keys and not paths)):
                _failure('invalid', 'selection_scope')
            for path in paths:
                safe_path(path)
            if any(type(key) is not str or len(key) > 2048 for key in translation_keys):
                _failure('invalid', 'selection_scope')
            query = dict(paths=paths, translation_keys=translation_keys, pull_request=pull_request)
            if type(self) is GitHubObserver and type(self._transport) is _CLI:
                self._transport.begin()
            identity = self._identity()
            facts = dict(identity=identity, snapshot=self._snapshot(paths, translation_keys))
            if pull_request is not None:
                facts['decisions'] = self._decisions(pull_request)
            if _Git(self._transport).head(self.target.branch) != (
                    facts['snapshot']['commit'], facts['snapshot']['tree']):
                _failure('stale', 'head_changed_during_read')
            # Bracket the full operation with independently observed identity,
            # repository ownership and permission facts, not only branch HEAD.
            if identity != self._identity():
                _failure('revoked', 'identity_or_permissions_changed_during_read')
            return self._record('verified-current', 'observed', facts, query)
        except ObservationFailure as error:
            return self._record(error.status, error.reason, {}, None)
        except (Exception,):
            # Never include raw exception text, repr, nested causes or request data.
            return self._record('invalid', 'response_or_selection_invalid', {}, None)

    def _record(self, status, reason, facts, query):
        synthetic = type(self) is FixtureObserver
        timestamp = (self._fixture_timestamp if synthetic else
                     datetime.now(timezone.utc).isoformat(timespec='seconds'))
        value = dict(schema_version=1, kind='github-read-only-observation', issuer_version=VERSION,
            issuer='fixture' if synthetic else 'supervised-gh', synthetic=synthetic,
            status=status, reason=reason, observed_at=timestamp,
            target=self.target.__dict__, facts=facts,
            contract_approved=False, readiness_authorized=False, publication_authorized=False,
            operational_authority='unavailable',
            correlation_id=fingerprint(dict(target=self.target.__dict__, status=status,
                reason=reason, observed_at=timestamp, facts=facts))[:24])
        if synthetic and status == 'verified-current':
            value['status'] = 'synthetic-current'
        encoded = canonical(value)
        if len(encoded) > 2_000_000:
            value.update(status='unavailable', reason='evidence_bound', facts={})
            query = None
            encoded = canonical(value)
        observation = Observation(encoded)
        # Retain only bounded lifetime receipts, never a durable success cache.
        if len(self._issued) >= 16:
            self._issued.pop(next(iter(self._issued)))
        self._issued[id(observation)] = (observation, query)
        return observation

    def reobserve(self, previous):
        """Fresh network reads at use; archived/foreign evidence has no capability.

        Result is a point-in-time read, not a lock or authorization for a later
        write. No write API is exposed or called by this milestone.
        """
        issued = self._issued.get(id(previous))
        if (type(previous) is not Observation or issued is None or issued[0] is not previous
                or issued[1] is None):
            return self._record('unavailable', 'restart_or_foreign_evidence', {}, None)
        fresh = self.observe(**issued[1])
        old, current = previous.to_dict(), fresh.to_dict()
        if current['status'] not in {'verified-current', 'synthetic-current'}:
            return fresh
        if current['facts'] != old['facts']:
            if current['facts']['identity'] != old['facts']['identity']:
                return self._record('revoked', 'identity_or_permissions_changed', current['facts'], None)
            before, after = old['facts']['snapshot'], current['facts']['snapshot']
            if before['commit'] == after['commit'] and before['tree'] != after['tree']:
                return self._record('invalid', 'inconsistent_commit_tree', {}, None)
            return self._record('stale', 'facts_changed_reobserve_required', current['facts'], issued[1])
        return fresh

    def archive(self, observation, store):
        """Reuse an explicitly owned Package E object store; no new DB/schema.

        Saved observation data cannot be loaded as an authenticated capability.
        """
        from .package_e import SidecarStore
        issued = self._issued.get(id(observation))
        if type(store) is not SidecarStore or not issued or issued[0] is not observation:
            _failure('invalid', 'archive_boundary')
        return store.put_object(observation.encoded, expected_sha256=observation.sha256)


class FixtureObserver(GitHubObserver):
    """Deterministic offline response fixtures; can never claim real observation."""

    def __init__(self, target, responses):
        super().__init__(target)
        self._transport = _FixtureTransport(target.repository, responses)
        self._fixture_timestamp = '2000-01-01T00:00:00+00:00'


class _FixtureTransport:
    def __init__(self, repo, responses):
        from copy import deepcopy
        self.repo = repo
        self.responses = {key: deepcopy(value) for key, value in responses.items()}
        self.requests = []

    def get(self, endpoint):
        from copy import deepcopy
        self.requests.append(endpoint)
        if endpoint not in self.responses:
            _failure('unavailable', 'fixture_response_missing')
        value = self.responses[endpoint]
        if type(value) is list:
            if not value:
                _failure('unavailable', 'fixture_sequence_exhausted')
            value = value.pop(0)
        if type(value) is ObservationFailure:
            raise value
        return deepcopy(value)
