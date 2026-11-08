"""Echo v0.1.0 source entry. Uses the selected Python, never a fixed machine path."""
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
INITIAL_CACHE_HOME = os.environ.get("XDG_CACHE_HOME")
DLL_HANDLES = []


def cache_directory():
    """Return a per-user runtime directory; ECHO_CACHE_DIR is an explicit override."""
    override = os.environ.get("ECHO_CACHE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(INITIAL_CACHE_HOME) if INITIAL_CACHE_HOME else Path.home() / ".cache"
    return base / "Echo" / "v0.1.0"


def configure_runtime():
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Echo v0.1.0 requires Python 3.12 with Tcl/Tk support.")
    runtime = cache_directory()
    for name in ("tmp", "cache", "matplotlib"):
        (runtime / name).mkdir(parents=True, exist_ok=True)
    for name in ("TMP", "TEMP", "TMPDIR"):
        os.environ[name] = str(runtime / "tmp")
    os.environ["XDG_CACHE_HOME"] = str(runtime / "cache")
    os.environ["MPLCONFIGDIR"] = str(runtime / "matplotlib")
    # Preserve the validated process-local numeric-library setting.
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[name] = "1"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    # Conda is optional. For its Windows Python, derive DLL locations from the
    # running interpreter rather than requiring activation or a particular drive.
    prefix = Path(sys.prefix)
    if os.name == "nt" and (prefix / "conda-meta").is_dir():
        directories = [prefix / part for part in (
            ".", "Library/mingw-w64/bin", "Library/usr/bin", "Library/bin", "Scripts", "bin"
        ) if (prefix / part).is_dir()]
        os.environ["PATH"] = os.pathsep.join(map(str, directories)) + os.pathsep + os.environ.get("PATH", "")
        for directory in directories:
            DLL_HANDLES.append(os.add_dll_directory(str(directory)))
    modules = str(ROOT / "p0b")
    if modules not in sys.path:
        sys.path.insert(0, modules)
    return runtime


def main():
    try:
        configure_runtime()
    except OSError as exc:
        raise SystemExit(f"Cannot prepare Echo runtime cache: {exc}. Set ECHO_CACHE_DIR to a writable directory.") from exc
    import gui
    return gui.main()


if __name__ == "__main__":
    raise SystemExit(main())
