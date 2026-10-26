"""Safe, stage-specific failure evidence. Never inspect exception text or requests."""
from contextlib import contextmanager
from dataclasses import dataclass
import errno
import hashlib
import json
from pathlib import Path
import re
import uuid

from create_people_posters.people_diagnostics import DiagnosticError, sanitize_data, sanitize_text


def exception_type(error):
    cls = type(error)
    value = cls.__module__ + "." + cls.__name__
    return sanitize_text(value) if re.fullmatch(r"[\w.]{1,200}", value) else "unknown_exception"


def preserve_summary(path):
    """Retain a prior sanitized receipt before a retry replaces the latest one."""
    path = Path(path)
    if not path.exists():
        return
    raw = path.read_bytes()
    prior = json.loads(raw)
    from people_workspaces import atomic_json
    destination = path.parent / "history" / (path.stem + "-" + hashlib.sha256(raw).hexdigest() + ".json")
    if not destination.exists():
        atomic_json(destination, prior)


def failure_record(error, operation, identifier, *, correlation_id=None):
    if type(error) is PipelineFailure:
        return error.record
    evidence = getattr(error, "_people_failure", None)
    if type(evidence) is FailureEvidence:
        return evidence.record
    chain, frames, seen = [], [], set()
    current = error
    diagnostic = None
    resource = False
    while current is not None and id(current) not in seen and len(chain) < 8:
        seen.add(id(current))
        chain.append(exception_type(current))
        if type(current) is DiagnosticError:
            diagnostic = current.diagnostic
            transport = getattr(current, "_transport_failure", None)
            if type(transport) is FailureEvidence:
                chain.extend(transport.record["cause_chain"])
                frames.extend(transport.record["locations"])
                resource |= transport.record["category"] == "resource_exhaustion"
        resource |= isinstance(current, MemoryError) or (
            isinstance(current, OSError) and current.errno in {errno.ENOMEM, errno.ENOSPC})
        # ONNX uses generic RuntimeException/Fail for allocator errors. Match
        # fixed allocator signatures only; provider text never enters evidence.
        if exception_type(current).startswith("onnxruntime."):
            resource |= any(type(arg) is str and len(arg) < 65536 and re.search(
                r"(?i)(std::bad_alloc|out of memory|failed to allocate memory|BFCArena::AllocateRawInternal)", arg)
                is not None for arg in current.args)
        tb = current.__traceback__
        while tb is not None:
            # Locations without source lines/arguments/locals or absolute paths.
            frames.append({"file": Path(tb.tb_frame.f_code.co_filename).name,
                           "function": tb.tb_frame.f_code.co_name, "line": tb.tb_lineno})
            tb = tb.tb_next
        current = current.__cause__ or (None if current.__suppress_context__ else current.__context__)
    category, retryable = "unexpected_exception", True
    detail = None
    if resource:
        category = "resource_exhaustion"
    elif diagnostic:
        detail = diagnostic.to_dict()
        category = ("missing_person" if diagnostic.status == 404 and operation == "person_details"
                    else "unexpected_exception" if diagnostic.category == "internal_error" else "network_api")
        retryable = diagnostic.retryable or diagnostic.category in {"internal_error", "invalid_response"}
    elif any(t.startswith(("requests.", "urllib3.", "ssl.")) for t in chain) or isinstance(error, (TimeoutError, ConnectionError)):
        category = "network_api"
    elif isinstance(error, (FileNotFoundError, FileExistsError, PermissionError)):
        category, retryable = "filesystem", not isinstance(error, FileExistsError)
    elif operation == "image_decode" and isinstance(error, (OSError, ValueError, SyntaxError)):
        category, retryable = "image_decode", False
    elif isinstance(error, OSError):
        category = "filesystem"
    elif any(t.startswith("onnxruntime.") for t in chain):
        category = "model_inference"
    elif operation in {"model_inference", "output_validation"} and isinstance(error, ValueError):
        category = "model_inference"
    hints = {
        "unexpected_exception": "Inspect safe stack locations and dependency API compatibility; retain input and retry after repair.",
        "network_api": "Check API status/authentication and retry pending work; never record transport errors as a person miss.",
        "missing_person": "TMDB returned HTTP 404 for this person; verify the identifier before explicitly excluding it.",
        "image_decode": "Verify the retained image bytes and decoder; acquire a valid replacement only after review.",
        "model_inference": "Inspect model/runtime and preprocessing/output contracts; retry this retained input in isolation.",
        "resource_exhaustion": "Check free disk/RAM and runtime allocations; retry retained input in a fresh worker.",
        "filesystem": "Check destination permissions, free space and provenance; differing outputs require explicit overwrite.",
    }
    record = sanitize_data({"category": category, "exception_type": chain[0], "operation": operation,
                          "input_identifier": identifier, "cause_chain": chain, "locations": frames[-32:],
                          "retryable": retryable, "permanent_person_failure": category == "missing_person",
                          "correlation_id": correlation_id or (diagnostic.correlation_id if diagnostic else uuid.uuid4().hex),
                          "diagnostic": detail, "action": hints[category]})
    try:
        error._people_failure = FailureEvidence(record)
    except (AttributeError, TypeError):
        pass
    return record


class PipelineFailure(RuntimeError):
    def __init__(self, record):
        self.record = record
        super().__init__(failure_text(record))


@dataclass(frozen=True)
class FailureEvidence:
    record: dict


def failure_text(record):
    return sanitize_text(" ".join(f"{key}={record[key]}" for key in
                                 ("category", "exception_type", "operation", "input_identifier", "retryable", "correlation_id")))


@contextmanager
def failure_boundary(operation, identifier):
    try:
        yield
    except Exception as error:
        # Preserve the existing library exception contract. Only this closed
        # evidence enters logs/JSON; never serialize the attached raw exception.
        failure_record(error, operation, identifier)
        raise
