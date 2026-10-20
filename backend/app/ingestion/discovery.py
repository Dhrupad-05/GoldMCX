"""Safe, read-only file discovery under a configured root."""
import hashlib
from collections.abc import Iterator
from pathlib import Path

from app.core.errors import InvalidInput


def validate_root(root: Path) -> Path:
    root = root.resolve()
    if not root.is_dir():
        raise InvalidInput(f"Configured source root does not exist or is not a directory: {root}")
    return root


def safe_iter_files(root: Path) -> Iterator[tuple[Path, str]]:
    """Yield (absolute_path, relative_path) without following links outside root."""
    root = validate_root(root)
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        resolved = p.resolve()
        # Reject symlinks or hardlink escapes out of the configured root.
        if not str(resolved).startswith(str(root)):
            continue
        yield resolved, resolved.relative_to(root).as_posix()


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            data = fh.read(chunk)
            if not data:
                break
            h.update(data)
    return h.hexdigest()
