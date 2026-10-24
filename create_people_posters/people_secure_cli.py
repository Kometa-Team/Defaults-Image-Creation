"""Run an existing People entry point behind the shared diagnostic boundary.

This keeps renderer source bytes/fingerprints unchanged: diagnostic protection
does not force completed posters to render again.
"""
from pathlib import Path
import runpy
import sys

_security_root = Path(__file__).resolve().parents[1]
if str(_security_root) not in sys.path:
    sys.path.insert(0, str(_security_root))
from create_people_posters.people_diagnostics import protect_cli


def main():
    protect_cli()
    if len(sys.argv) < 4 or sys.argv[1] not in {"--script", "--worker"} or sys.argv[3] != "--":
        raise ValueError("Expected an explicit People script and argument separator")
    root = Path(__file__).resolve().parent
    target = Path(sys.argv[2])
    target = target if target.is_absolute() else root / target
    if target.is_symlink() or target.resolve().parent != root or target.suffix != ".py" or target.name == Path(__file__).name:
        raise ValueError("Only repository People scripts may be launched")
    if not target.is_file():
        raise ValueError("People script is unavailable")
    from create_people_posters import people_process
    if sys.argv[1] == "--script":
        result = people_process.run_process([sys.executable, str(target), *sys.argv[4:]], tee=True)
        return result.returncode
    # Process-local state set by this validated adapter, never a caller-supplied
    # environment compatibility flag. Public service integrations use run_process
    # or --script; they must not expose the internal worker entry point.
    people_process._IN_GUARDED_WORKER = True
    sys.argv = [str(target), *sys.argv[4:]]
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    raise SystemExit(main())
