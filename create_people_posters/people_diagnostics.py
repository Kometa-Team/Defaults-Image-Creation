"""Credential-free diagnostic boundaries for People CLI and future service callers.

Network errors use closed records, never arbitrary exception serialization.
Text redaction is a final backstop, not permission to log request objects.
"""
from __future__ import annotations

import base64
import codecs
import copy
from functools import lru_cache
from dataclasses import dataclass
import html
import io
import json
import logging
import os
from pathlib import Path, PosixPath, WindowsPath
import re
import sys
import threading
from urllib.parse import quote, quote_plus, unquote, urlsplit, urlunsplit
import uuid
import zipfile

REDACTED = "[REDACTED]"
_FALLBACK_CORRELATION = uuid.uuid4().hex
WITHHELD = "[diagnostic unavailable; sensitive content withheld; correlation_id=" + _FALLBACK_CORRELATION + "]"
MAX_TEXT = 262144
_KEYS = frozenset({
    "apikey", "key", "tmdbkey", "tmdbapikey", "accesskey", "secretaccesskey",
    "awsaccesskeyid", "awssecretaccesskey", "awssecuritytoken", "awssessiontoken",
    "token", "accesstoken", "refreshtoken", "idtoken", "jwt", "clientsecret", "secret", "secrets", "password", "pass",
    "passwd", "pwd", "authorization", "proxyauthorization", "cookie", "cookies", "setcookie",
    "session", "sessionid", "sessioncookie", "xapikey", "xauthtoken", "xplextoken",
    "xamzsignature", "sharedaccesssignature", "apisignature", "credential", "credentials", "sas", "sastoken",
    "webhookurl", "authentication", "privatekey", "connectionstring",
})
_URL = re.compile(r"(?i)\b[a-z][a-z0-9+.-]{1,15}://[^\s<>\"']+")
_PAIR = re.compile(
    r"(?i)([\"']?([A-Za-z0-9_%.-]+)[\"']?\s*(?:=|:)\s*)"
    r"(?:\"([^\"]*)\"|'([^']*)'|(\[REDACTED\]|[^\s,;&)\]}<>]+))"
)
_HEADER = re.compile(r"(?im)((?:proxy-)?authorization|(?:set-)?cookie)\s*:\s*[^\r\n]+")
_AUTH = re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9+/_.=~%-]+")
_ENV_KEY = re.compile(r"(?i)(?:^|_)(?:API_?KEY|KEY|TOKEN|SECRET|PASSWORD|PASSWD|PASS|COOKIE|SESSION|CREDENTIALS?)(?:$|_)")
_variants: set[str] = set()
_lock = threading.RLock()


def sensitive_key(value: str) -> bool:
    if not isinstance(value, str):
        return True
    for _ in range(4):
        decoded = unquote(value)
        if decoded == value:
            break
        value = decoded
    normalized = re.sub(r"[^a-z0-9]", "", value.casefold())
    return normalized in _KEYS or normalized.endswith(("apikey", "token", "secret", "password", "passwd", "privatekey", "secretkey", "credential"))


@lru_cache(maxsize=1024)
def _secret_forms(value):
    raw = value.encode("utf8")
    forms = {value, quote(value, safe=""), quote_plus(value, safe=""), raw.hex(), raw.hex().upper(),
             base64.b64encode(raw).decode(), base64.urlsafe_b64encode(raw).decode(),
             json.dumps(value, ensure_ascii=True)[1:-1], repr(value)[1:-1]}
    if "://" in value:
        try:
            parsed = urlsplit(value)
            # A configured credential URL stays sensitive if a client removes
            # its query/fragment before reporting it (e.g. a webhook endpoint).
            forms.add(urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", "")))
        except ValueError:
            pass
    forms |= {x.rstrip("=") for x in tuple(forms)}
    forms |= {quote(x, safe="") for x in tuple(forms)}
    forms |= {re.sub(r"%[0-9A-F]{2}", lambda m: m[0].lower(), x) for x in tuple(forms)}
    # JSON unicode escapes can otherwise conceal an ASCII token in a report.
    forms.add("".join(f"\\u{ord(c):04x}" for c in value))
    return frozenset(x for x in forms if x)


def register_secret(value: str | None) -> None:
    """Register configured values before a client can issue a request."""
    if value is None or value == "":return
    if type(value) is not str or len(value) > 16384:
        raise ValueError("Invalid credential configuration")
    with _lock:
        _variants.update(_secret_forms(value))
        for segment in value.splitlines():
            if segment and segment != value:_variants.update(_secret_forms(segment))


def register_environment(environment=None) -> None:
    for key, value in (os.environ if environment is None else environment).items():
        if sensitive_key(key) or _ENV_KEY.search(key):
            register_secret(value)
        elif type(value) is str and "://" in value:
            try:
                parsed = urlsplit(value)
                if parsed.username is not None or parsed.password is not None:
                    register_secret(value)
                    register_secret(unquote(parsed.username or ""))
                    register_secret(unquote(parsed.password or ""))
            except ValueError:
                # A malformed credential URL cannot safely enter diagnostics.
                register_secret(value)


def _known(text: str) -> str:
    with _lock:
        variants = sorted(_variants, key=len, reverse=True)
    for value in variants:
        text = text.replace(value, REDACTED)
    return text


def _url(match) -> str:
    value = match[0]
    # Remove userinfo before parsing: known-value replacement may have inserted
    # brackets there, which urlsplit would otherwise mistake for an IPv6 host.
    scheme, rest = value.split("://", 1)
    boundary = re.search(r"[/?#]", rest)
    end = boundary.start() if boundary else len(rest)
    authority, tail = rest[:end], rest[end:]
    authority = authority.rsplit("@", 1)[-1]
    value = scheme + "://" + authority + tail
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"https", "http"} or not parsed.hostname:
        return "[URL withheld]"
    # Diagnostic URLs never need query strings, fragments or userinfo. Keep the
    # host and endpoint, rather than attempting to guess every provider's keys.
    host = parsed.hostname
    if ":" in host:
        host = "[" + host + "]"
    if parsed.port is not None:
        host += ":" + str(parsed.port)
    return urlunsplit((parsed.scheme, host, parsed.path, "", ""))


def _sanitize_text(text: str) -> str:
    if type(text) is not str or len(text) > MAX_TEXT:
        return WITHHELD
    register_environment()
    text = _known(text)
    # Strip authentication from a valid encoded URI BEFORE unquoting can turn
    # an encoded path space into a delimiter and strand its signed query tail.
    text = _URL.sub(_url, text)
    # Decode credential-bearing escaped diagnostics, not ordinary filenames or
    # safe percent characters. Work is explicitly bounded.
    for _ in range(4):
        decoded = unquote(text)
        if decoded == text:
            break
        if (any(sensitive_key(m[2]) for m in _PAIR.finditer(decoded)) or _AUTH.search(decoded)
                or (_URL.search(decoded) and not _URL.search(text))):
            text = _URL.sub(_url, decoded)
        else:
            break
    text = _URL.sub(_url, text)
    # Replace complete configured values before generic field parsing can split
    # a password containing spaces/punctuation and leave a recognizable suffix.
    text = _known(text)
    text = _HEADER.sub(lambda m: m[1] + ": " + REDACTED, text)
    text = _AUTH.sub("authorization " + REDACTED, text)
    text = _PAIR.sub(lambda m: m[1] + REDACTED if sensitive_key(m[2]) else m[0], text)
    return _known(text)


def sanitize_text(text) -> str:
    """Fail closed, including when a sanitizer/parser itself fails."""
    try:
        return _sanitize_text(text)
    except BaseException:
        return WITHHELD


def safe_exception(error: BaseException) -> str:
    """No __str__, repr, args, request, response text, chain or local variables."""
    try:
        if type(error) is DiagnosticError:
            return error.diagnostic.text()
        if (type(error).__name__ == "GitHubError" and type(error).__module__ in
                {"github_inventory_core", "create_people_posters.github_inventory_core"}
                and len(error.args) == 1 and type(error.args[0]) is str):
            # Closed application conflict categories, without remote paths or
            # arbitrary transport text. Preserve the existing safety guidance.
            for phrase in ("Concurrent edit", "previously verified", "README", "unexpected blob"):
                if phrase in error.args[0]:return phrase + "; local files retained; operator review required"
        if type(error).__module__ == "PIL" and type(error).__name__ == "UnidentifiedImageError":
            return "cannot identify image; error_category=invalid_image"
        if type(error) in {ValueError, FileExistsError} and len(error.args) == 1 and type(error.args[0]) is str:
            message = error.args[0]
            for phrase in ("Unsupported input format", "Ambiguous input basenames"):
                if message.startswith(phrase):return phrase
            if message.startswith("Preserved original differs: "):
                # This is an application archive conflict, not provider text.
                # Only a local absolute path may supplement its fixed category.
                path = message.removeprefix("Preserved original differs: ").split(";", 1)[0]
                if path.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", path):
                    return "Preserved original differs: " + sanitize_text(path)
                return "Preserved original differs; local files retained"
            if message.startswith("Keep existing staged output "):
                return "Existing staged output; explicit overwrite required"
        if type(error) is RuntimeError and len(error.args) == 1 and type(error.args[0]) is str:
            # Preserve actionable, fixed operator guidance without forwarding
            # arbitrary provider messages, URLs, headers or exception repr.
            message = error.args[0]
            if "weights unavailable" in message:return "weights unavailable; verify the local model cache"
            if "Model checksum mismatch" in message:
                return "Model checksum mismatch; verify the local model cache"
            provider = re.search(r"Requested (CPU|CUDA|ROCM|CoreML)ExecutionProvider", message)
            if provider:return "Requested " + provider[1] + "ExecutionProvider unavailable; verify the runtime"
            stage = re.match(r"(ddcolor|rembg|render) exited ([0-9]{1,3})\b", message)
            if stage and 0 <= int(stage[2]) <= 255:return stage[1] + " exited " + str(int(stage[2]))
            if "REMOVE_BG_OVERWRITE" in message:
                return "REMOVE_BG_OVERWRITE=true required for existing background output"
            if "missing model weights" in message.casefold():
                return "missing model weights; verify the local model cache"
            match = re.search(r"poster generation failed with exit code ([0-9]{1,3})\b", message)
            if match and 0 <= int(match[1]) <= 255:
                return "poster generation failed with exit code " + str(int(match[1]))
        categories = {("ssl", "SSLError"): "tls", ("requests.exceptions", "SSLError"): "tls",
                      ("urllib3.exceptions", "SSLError"): "tls",
                      ("requests.exceptions", "Timeout"): "timeout",
                      ("requests.exceptions", "ConnectionError"): "connection",
                      ("requests.exceptions", "HTTPError"): "http_error"}
        for cls in type(error).__mro__:
            category = categories.get((cls.__module__, cls.__name__))
            if category:
                return "error_category=" + category + " correlation_id=" + _FALLBACK_CORRELATION
        for cls, label in ((TimeoutError, "timeout"), (ConnectionError, "connection"),
                           (FileNotFoundError, "file_not_found"), (PermissionError, "permission"),
                           (OSError, "io_error"), (ValueError, "invalid_data"),
                           (KeyboardInterrupt, "cancelled")):
            if isinstance(error, cls):
                return "error_category=" + label + " correlation_id=" + _FALLBACK_CORRELATION
        return "error_category=internal_error correlation_id=" + _FALLBACK_CORRELATION
    except BaseException:
        return WITHHELD


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Closed allowlist; values never come from request/exception repr."""
    provider: str
    operation: str
    category: str
    status: int | None = None
    retryable: bool = False
    endpoint: str = "image"
    correlation_id: str | None = None
    PROVIDERS = {"TMDB", "Google", "GitHub", "image", "model", "process"}
    CATEGORIES = {"tls", "timeout", "connection", "rate_limit", "authentication", "server_error",
                  "client_error", "invalid_response", "configuration", "cancelled", "internal_error"}
    OPERATIONS = {"search_person", "person_images", "person_details", "popular_people", "download_image",
                  "image_search", "request", "model_download", "subprocess", "configuration"}
    ENDPOINTS = {"/3/search/person", "/3/person/{person_id}/images", "/3/person/{person_id}",
                 "/3/person/popular", "/t/p/original/{image}", "/customsearch/v1", "/repos/{repository}",
                 "image", "model", "process", "/3/configuration/{resource}"}

    def __post_init__(self):
        if (any(type(v) is not str for v in (self.provider, self.operation, self.category, self.endpoint))
                or self.provider not in self.PROVIDERS or self.operation not in self.OPERATIONS or self.category not in self.CATEGORIES
                or self.endpoint not in self.ENDPOINTS or type(self.retryable) is not bool
                or (self.status is not None and (type(self.status) is not int or not 100 <= self.status <= 599))):
            raise ValueError("Invalid diagnostic record")
        correlation_id = uuid.uuid4().hex if self.correlation_id is None else self.correlation_id
        if type(correlation_id) is not str or not re.fullmatch(r"[0-9a-f]{32}", correlation_id):
            raise ValueError("Invalid diagnostic correlation")
        if self.retryable != (self.category in {"tls", "timeout", "connection", "rate_limit", "server_error"}):
            raise ValueError("Diagnostic retryability contradicts its category")
        if self.status is not None:
            expected = ("rate_limit" if self.status == 429 else "authentication" if self.status in {401, 403}
                        else "server_error" if self.status >= 500 else "client_error")
            if self.category != expected:
                raise ValueError("Diagnostic category contradicts its HTTP status")
        object.__setattr__(self, "correlation_id", correlation_id)

    def to_dict(self):
        return {key: sanitize_text(value) if type(value) is str else value
                for key in self.__slots__ for value in (getattr(self, key),)}

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != set(cls.__slots__):
            raise ValueError("Invalid diagnostic fields")
        return cls(**value)

    def text(self):
        return sanitize_text(" ".join(f"{key}={value}" for key, value in self.to_dict().items()))


class DiagnosticError(RuntimeError):
    def __init__(self, diagnostic: Diagnostic):
        if type(diagnostic) is not Diagnostic:
            raise ValueError("Invalid diagnostic")
        self.diagnostic = diagnostic
        super().__init__(diagnostic.text())


def sanitize_data(value, *, _depth=0):
    """Diagnostic data only. Never serialize arbitrary objects or configuration."""
    if _depth > 16:
        return WITHHELD
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float:
        return value if value == value and abs(value) != float("inf") else WITHHELD
    if type(value) is str:
        return sanitize_text(value)
    if type(value) in {PosixPath, WindowsPath}:
        return sanitize_text(str(value))
    if isinstance(value, BaseException):
        return safe_exception(value)
    if type(value) is Diagnostic:
        return value.to_dict()
    if type(value) is dict and len(value) <= 4096:
        return {sanitize_text(k): REDACTED if sensitive_key(k) else sanitize_data(v, _depth=_depth + 1)
                for k, v in value.items() if type(k) is str}
    if type(value) in (list, tuple) and len(value) <= 4096:
        return [sanitize_data(v, _depth=_depth + 1) for v in value]
    return "[unsupported diagnostic object]"


def diagnostic_json(value) -> str:
    try:
        return json.dumps(sanitize_data(value), ensure_ascii=True, allow_nan=False)
    except BaseException:
        return json.dumps({"error": WITHHELD})


def diagnostic_html(value) -> str:
    return "<!doctype html><meta charset=utf-8><pre>" + html.escape(diagnostic_json(value)) + "</pre>"


def support_bundle(path: Path, reports: dict) -> None:
    """Explicit text/structured diagnostics only; no env, file trees or binaries."""
    if type(reports) is not dict or not reports or len(reports) > 64:
        raise ValueError("Invalid support report selection")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, report in reports.items():
            if type(name) is not str or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name):
                raise ValueError("Invalid support report name")
            archive.writestr(name + ".json", diagnostic_json(report).encode("utf8"))


class RedactingFormatter(logging.Formatter):
    def __init__(self, original=None):
        super().__init__()
        self.original = original or logging.Formatter("%(levelname)s %(message)s")

    def format(self, record):
        try:
            clean = copy.copy(record)
            clean.msg = sanitize_text(record.msg) if type(record.msg) is str else sanitize_data(record.msg)
            clean.args = tuple(sanitize_data(x) for x in record.args) if type(record.args) is tuple else sanitize_data(record.args)
            clean.exc_info = clean.exc_text = clean.stack_info = None
            if record.exc_info:
                # Format safe category/context, never the original traceback.
                clean.msg = str(clean.msg) + " [" + safe_exception(record.exc_info[1]) + "]"
            for key, value in tuple(clean.__dict__.items()):
                if key not in {"msg", "args", "exc_info", "exc_text", "stack_info"}:
                    clean.__dict__[key] = REDACTED if sensitive_key(key) else sanitize_data(value)
            return sanitize_text(self.original.format(clean))
        except BaseException:
            return WITHHELD


def secure_handler(handler):
    from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
    if type(handler) not in {logging.StreamHandler, logging.FileHandler, logging.NullHandler,
                             RotatingFileHandler, TimedRotatingFileHandler} and handler is not logging.lastResort:
        raise ValueError("Unsupported logging destination; secure adapter required")
    if not isinstance(handler.formatter, RedactingFormatter):
        handler.setFormatter(RedactingFormatter(handler.formatter))
    # logging.Handler.handleError normally dumps the original record on stderr.
    def handle_error(record):
        try:
            sys.stderr.write("[logging destination failed; diagnostic content withheld; correlation_id=" + _FALLBACK_CORRELATION + "]\n")
        except BaseException:
            pass
    handler.handleError = handle_error
    return handler


def protect_logging():
    for logger in (logging.getLogger(), *(v for v in logging.Logger.manager.loggerDict.values() if isinstance(v, logging.Logger))):
        for handler in logger.handlers:
            secure_handler(handler)
    if logging.lastResort is not None:
        secure_handler(logging.lastResort)


class _BinaryStream:
    def __init__(self, owner):
        self.owner = owner
        self.decoder = codecs.getincrementaldecoder("utf8")("replace")

    def write(self, value):
        if type(value) is not bytes:
            raise TypeError("Expected bytes")
        self.owner.write(self.decoder.decode(value))
        return len(value)

    def flush(self):
        self.owner.flush()


class RedactingStream(io.TextIOBase):
    """Buffer complete lines so split write() calls cannot disclose a token."""
    def __init__(self, target):
        self.target, self.pending = target, ""
        self.discarding = False
        self.lock = threading.RLock()
        self.binary = _BinaryStream(self)

    @property
    def encoding(self): return "utf-8"
    @property
    def errors(self): return "replace"
    @property
    def buffer(self): return self.binary
    def writable(self): return True
    def isatty(self): return False

    def write(self, value):
        if type(value) is not str:
            raise TypeError("Expected text")
        with self.lock:
            self.pending += value
            while "\n" in self.pending:
                line, self.pending = self.pending.split("\n", 1)
                if self.discarding:
                    self.discarding = False
                else:
                    self.target.write(sanitize_text(line) + "\n")
            if len(self.pending) > MAX_TEXT:
                self.target.write(WITHHELD + "\n")
                self.pending = ""
                self.discarding = True
        return len(value)

    def flush(self):
        # A flush is not a record boundary. Do not disclose partial secrets.
        self.target.flush()

    def finish(self):
        with self.lock:
            if self.pending:
                self.target.write(WITHHELD + "\n")
                self.pending = ""
            self.target.flush()

    def reconfigure(self, **kwargs):
        # Encoding changes never unwrap the redacting boundary.
        if type(self.target) is io.TextIOWrapper:
            self.target.reconfigure(**kwargs)


def protect_cli():
    """Install before loading clients/models. Does not run on module import."""
    register_environment()
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        if not isinstance(stream, RedactingStream):
            if type(stream) is io.TextIOWrapper:
                stream.reconfigure(encoding="utf-8", errors="backslashreplace")
            setattr(sys, name, RedactingStream(stream))
    protect_logging()
    original_add = logging.Logger.addHandler
    if not getattr(original_add, "_people_secure", False):
        def add_handler(logger, handler):
            original_add(logger, secure_handler(handler))
        add_handler._people_secure = True
        logging.Logger.addHandler = add_handler
    def exception_hook(kind, error, traceback):
        sys.stderr.write(safe_exception(error) + "\n")
    sys.excepthook = exception_hook
    threading.excepthook = lambda args: exception_hook(args.exc_type, args.exc_value, args.exc_traceback)
    sys.unraisablehook = lambda args: sys.stderr.write("error_category=unraisable_error correlation_id=" + _FALLBACK_CORRELATION + "\n")
    import atexit
    atexit.register(lambda: [getattr(sys, name).finish() for name in ("stdout", "stderr") if isinstance(getattr(sys, name), RedactingStream)])
