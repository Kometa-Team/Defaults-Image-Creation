"""Pipe and sanitize child diagnostics before console, file or caller delivery."""
from __future__ import annotations

import io
import os
from pathlib import Path
import subprocess
import sys
import threading

from create_people_posters.people_diagnostics import Diagnostic, DiagnosticError, RedactingStream, register_environment, sanitize_text

ROOT = Path(__file__).resolve().parent
MAX_OUTPUT = 16 * 1024 * 1024
_IN_GUARDED_WORKER = False


def guard_cli():
    """Direct CLIs also run behind an OS pipe, including native library writes."""
    from create_people_posters.people_diagnostics import protect_cli
    protect_cli()
    if _IN_GUARDED_WORKER:return
    # Register private dotenv values without changing precedence or serializing
    # configuration. The child still loads its normal runtime configuration.
    from dotenv import dotenv_values
    config = Path(os.getenv("PEOPLE_CONFIG_DIR") or ROOT / "config")
    path = config / ".env"
    if path.is_file():register_environment(dotenv_values(path))
    result = run_process([sys.executable, *sys.argv], cwd=Path.cwd(), tee=True)
    raise SystemExit(result.returncode)


def secure_argv(argv):
    if not argv or any(type(arg) is not str or sanitize_text(arg) != arg for arg in argv):
        raise ValueError("Unsafe subprocess arguments; credentials belong in runtime configuration")
    name = Path(argv[0]).name.casefold()
    if name.startswith("python") or name in {"py", "py.exe"}:
        for index, value in enumerate(argv[1:], 1):
            if value in {"-c", "-m"}:
                break
            if value.endswith(".py"):
                script = Path(value)
                script = script if script.is_absolute() else ROOT / script
                if script.resolve().parent == ROOT and script.name != "people_secure_cli.py":
                    return [*argv[:index], str(ROOT / "people_secure_cli.py"), "--worker", str(script), "--", *argv[index + 1:]]
                break
    return list(argv)


def run_process(argv, *, cwd=ROOT, env=None, tee=False, log_path=None, timeout=None):
    register_environment(env)
    command = secure_argv(argv)
    buffers = {name: io.StringIO() for name in ("stdout", "stderr")}
    errors = []
    failure = None
    handle = None
    if log_path is not None:
        log_path = Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handle = log_path.open("w", encoding="utf8")
    lock = threading.RLock()
    total = [0]
    class Sink:
        def __init__(self, name):self.name = name
        def write(self, text):
            with lock:
                buffers[self.name].write(text)
                if handle is not None:handle.write(text)
                if tee:getattr(sys, self.name).write(text)
        def flush(self):
            if handle is not None and not handle.closed:handle.flush()
    def read(pipe, name):
        stream = RedactingStream(Sink(name))
        try:
            while True:
                text = pipe.readline(4096)
                if not text:break
                with lock:
                    total[0] += len(text)
                    if total[0] > MAX_OUTPUT:
                        errors.append(True)
                        process.terminate()
                        break
                stream.write(text)
            stream.finish()
        except BaseException:
            errors.append(True)
        finally:
            pipe.close()
    process = None
    try:
        try:
            process = subprocess.Popen(command, cwd=cwd, env=env, text=True, encoding="utf8", errors="replace",
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            threads = [threading.Thread(target=read, args=(getattr(process, name), name), daemon=True)
                       for name in ("stdout", "stderr")]
            for thread in threads:thread.start()
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                failure = Diagnostic("process", "subprocess", "timeout", retryable=True, endpoint="process")
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
                code = 124
            for thread in threads:thread.join(timeout=5)
            if errors or any(thread.is_alive() for thread in threads):
                failure = Diagnostic("process", "subprocess", "internal_error", endpoint="process")
        except OSError:
            failure = Diagnostic("process", "subprocess", "configuration", endpoint="process")
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        if handle is not None:handle.close()
    if failure is not None:
        raise DiagnosticError(failure)
    return subprocess.CompletedProcess(list(argv), code, buffers["stdout"].getvalue(), buffers["stderr"].getvalue())
