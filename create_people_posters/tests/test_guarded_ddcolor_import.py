"""Guarded DDColor startup accepts only the known PyTorch handler identities."""
import io
import json
import logging
import os
from pathlib import Path
import sys
import types

import pytest
from PIL import Image

from create_people_posters import people_diagnostics as secure
from create_people_posters.people_process import run_process

SECRET = "NOT_A_REAL_DDCOLOR_GUARDED_IMPORT_CREDENTIAL"
HANDLERS = '''
import logging, sys
class _StderrHandler(logging.Handler):
    @property
    def stream(self): return sys.stderr
    def emit(self, record):
        try:
            self.stream.write(self.format(record) + '\\n')
            self.stream.flush()
        except Exception:
            self.handleError(record)
class LazyTraceHandler(logging.StreamHandler):
    pass
'''


@pytest.fixture
def torch_logging(monkeypatch):
    module = types.ModuleType("torch._logging._internal")
    exec(HANDLERS, module.__dict__)
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return module


@pytest.mark.parametrize("name", ["_StderrHandler", "LazyTraceHandler"])
def test_known_torch_handlers_retain_final_redaction(name, torch_logging, monkeypatch):
    target = io.StringIO()
    monkeypatch.setattr(sys, "stderr", target)
    cls = getattr(torch_logging, name)
    handler = cls() if name == "_StderrHandler" else cls(target)
    secure.register_secret(SECRET)
    handler = secure.secure_handler(handler)
    assert isinstance(handler.formatter, secure.RedactingFormatter)
    record = logging.LogRecord("torch", logging.ERROR, "source.py", 1, "failure %s", (SECRET,), None)
    record.payload = {"api_key": SECRET}
    try:
        raise RuntimeError(SECRET)
    except RuntimeError:
        record.exc_info = sys.exc_info()
    handler.emit(record)
    assert "failure" in target.getvalue() and SECRET not in target.getvalue()


@pytest.mark.parametrize("name", ["_StderrHandler", "LazyTraceHandler"])
def test_torch_handler_identity_cannot_be_forged_by_name_or_subclass(name, torch_logging):
    cls = getattr(torch_logging, name)
    forged = type(name, (logging.Handler,), {"__module__": torch_logging.__name__})
    subclass = type("Child", (cls,), {})
    for handler in (forged(), subclass()):
        with pytest.raises(ValueError, match="Unsupported logging destination"):
            secure.secure_handler(handler)


@pytest.mark.parametrize("name", ["_StderrHandler", "LazyTraceHandler"])
def test_torch_handler_destination_failure_cannot_dump_raw_record(name, torch_logging, monkeypatch):
    class Broken:
        def write(self, text): raise OSError(SECRET)
        def flush(self): pass
    capture = io.StringIO()
    cls = getattr(torch_logging, name)
    handler = cls() if name == "_StderrHandler" else cls(Broken())
    secure.register_secret(SECRET)
    handler = secure.secure_handler(handler)
    monkeypatch.setattr(sys, "stderr", Broken() if name == "_StderrHandler" else capture)
    record = logging.LogRecord("torch", logging.ERROR, "source.py", 1, SECRET, (), None)
    handler.emit(record)
    assert SECRET not in capture.getvalue()
    # Even a failing fallback sink must suppress the raw record/exception.
    monkeypatch.setattr(sys, "stderr", capture)
    handler.handleError(record)
    assert "diagnostic content withheld" in capture.getvalue() and SECRET not in capture.getvalue()


def test_actual_guarded_ddcolor_cli_imports_vendor_with_torch_handlers_without_inference(tmp_path):
    root = Path(__file__).resolve().parents[2]
    script = root / "create_people_posters/colorize_noncolor_ddcolor.py"
    packages = tmp_path / "packages"
    internal = packages / "torch/_logging"
    internal.mkdir(parents=True)
    (internal / "__init__.py").write_text("", encoding="utf8")
    (internal / "_internal.py").write_text(HANDLERS, encoding="utf8")
    (packages / "torch/__init__.py").write_text('''
import logging
from ._logging._internal import _StderrHandler, LazyTraceHandler
import os
console = logging.getLogger('torch.offline')
console.setLevel(logging.INFO)
console.propagate = False
console.addHandler(_StderrHandler())
trace = logging.getLogger('torch.offline.trace')
trace.setLevel(logging.INFO)
trace.propagate = False
trace.addHandler(LazyTraceHandler(open(os.environ['OFFLINE_TRACE_PATH'], 'w', encoding='utf8')))
''', encoding="utf8")
    vendor = tmp_path / "vendor/DDColor/ddcolor"
    vendor.mkdir(parents=True)
    (vendor / "__init__.py").write_text('''
import logging, os, sys, torch
from create_people_posters import people_process, people_diagnostics
assert people_process._IN_GUARDED_WORKER
assert isinstance(sys.stderr, people_diagnostics.RedactingStream)
for name in ('torch.offline', 'torch.offline.trace'):
    logger = logging.getLogger(name)
    assert all(isinstance(h.formatter, people_diagnostics.RedactingFormatter) for h in logger.handlers)
    try: raise RuntimeError(os.environ['TMDB_KEY'])
    except RuntimeError: logger.exception('DDColor dependency import succeeded %s', os.environ['TMDB_KEY'])
print('DDCOLOR_GUARDED_IMPORT_OK')
raise SystemExit(0)  # Import-only fixture: never reach model loading/inference.
''', encoding="utf8")
    config = tmp_path / "batch"
    inputs = config / "Downloads/other"
    inputs.mkdir(parents=True)
    Image.new("RGB", (8, 8), (120, 120, 120)).save(inputs / "synthetic.png")
    checkpoint = config / ".orch/tmdb.done.json"
    checkpoint.parent.mkdir()
    checkpoint.write_text('{"completed": true}', encoding="utf8")
    before = checkpoint.read_bytes()
    env = dict(os.environ, TMDB_KEY=SECRET, PEOPLE_CONFIG_DIR=str(config),
        COLORIZE_VENDOR_DIR=str(tmp_path / "vendor"), COLORIZE_DDCOLOR_VENDOR_DIR=str(vendor.parent),
        COLORIZE_DDCOLOR_MODELS_DIR=str(tmp_path / "models"),
        COLORIZE_INPUT_OTHER=str(inputs), COLORIZE_OUTPUT_COLOR=str(tmp_path / "output"),
        PYTHONPATH=str(packages) + os.pathsep + str(root), OFFLINE_TRACE_PATH=str(tmp_path / "torch.log"))
    result = run_process([sys.executable, str(script)], env=env, cwd=script.parent, timeout=30)
    assert result.returncode == 0 and "DDCOLOR_GUARDED_IMPORT_OK" in result.stdout
    assert "DDColor dependency import succeeded" in result.stderr
    assert SECRET not in result.stdout + result.stderr + (tmp_path / "torch.log").read_text()
    assert checkpoint.read_bytes() == before and (inputs / "synthetic.png").is_file()
    assert not list((tmp_path / "output").glob("*"))
    assert not list((tmp_path / "models").glob("**/*.bin"))
