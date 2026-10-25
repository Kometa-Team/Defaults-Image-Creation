"""Conservative definition retirement; published artifacts are never deleted."""
from ..common import BulkError, fingerprint


def fail(code):
    raise BulkError('p4m6_'+code, 'Mapping/retirement blocked: '+code)


def validate_delete(index, entries, selected):
    """Require complete companions and no retained consumer of a removed output.

    Generated children cannot be retired until a persistent family-exclusion
    adapter exists. Removing an expanded row would simply regenerate it.
    """
    selected = set(selected)
    if not selected or not selected <= index.outputs.keys() or index.unresolved:
        fail('uncertain_dependency_impact')
    for identity in selected:
        entry = entries[identity]
        if entry['semantic']['role'] in {'group', 'family'}:
            fail('container_retirement_unsupported')
        if entry['semantic']['key'].startswith(('year:', 'rating:', 'separator:')):
            fail('persistent_generated_exclusion_required')
        if set(index.outputs[identity]['companions']) - selected:
            fail('required_companion')
        affected = index.impact([index.outputs[identity]['node']])
        if not affected['impact_complete'] or set(affected['affected_outputs']) - selected:
            fail('required_retained_consumer')
        if any(e['semantic']['parent'] == identity and i not in selected
               and e['tombstone_sha256'] is None for i, e in entries.items()):
            fail('required_retained_child')


def tombstone(operation, entry, retained):
    """A new immutable record, never an instruction to unlink local/remote bytes."""
    return dict(schema_version=1, kind='retained-definition-tombstone',
        operation_id=operation, identity=entry['id'], entry_sha256=fingerprint(entry),
        names=entry['names'], aliases=entry['aliases'], retained=retained,
        remote_delete_authorized=False, identity_reuse_authorized=False)
