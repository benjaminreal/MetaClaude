"""Small file helpers for private staging and no-clobber publication."""
from __future__ import annotations

import os
from pathlib import Path
import secrets
import shutil
import stat
import tempfile


def private_run_directory(prefix: str, parent: str | Path | None = None) -> Path:
    """Create a unique owner-private directory under ``parent`` or the temp root."""
    parent_path = Path(parent) if parent is not None else Path(tempfile.gettempdir())
    if not parent_path.exists():
        parent_path.mkdir(parents=True, mode=0o700)
    if not parent_path.is_dir():
        raise NotADirectoryError(f"staging parent is not a directory: {parent_path}")
    result = Path(tempfile.mkdtemp(prefix=prefix, dir=parent_path))
    os.chmod(result, 0o700)
    return result


def copy_private_file(source: str | Path, destination: str | Path) -> Path:
    """Atomically copy one file to a new mode-0600 destination."""
    source_path = Path(source)
    destination_path = Path(destination)
    parent = destination_path.parent if str(destination_path.parent) else Path(".")
    dir_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    dir_flags |= getattr(os, "O_CLOEXEC", 0)
    parent_fd = os.open(parent, dir_flags)
    destination_name = destination_path.name
    temp_name = f".private-copy-{secrets.token_hex(12)}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = None
    try:
        fd = os.open(temp_name, flags, 0o600, dir_fd=parent_fd)
        os.fchmod(fd, 0o600)
        with source_path.open("rb") as source_file, os.fdopen(fd, "wb", closefd=False) as target_file:
            shutil.copyfileobj(source_file, target_file)
            target_file.flush()
            os.fsync(fd)
        try:
            os.link(temp_name, destination_name, src_dir_fd=parent_fd,
                    dst_dir_fd=parent_fd, follow_symlinks=False)
        except FileExistsError:
            raise _existing_target_error(parent_fd, destination_name, destination_path)
        os.fsync(parent_fd)
    except BaseException:
        if fd is not None:
            try:
                os.unlink(temp_name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        raise
    finally:
        if fd is not None:
            os.close(fd)
        try:
            os.unlink(temp_name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        os.close(parent_fd)
    return destination_path


def privateize_tree(root: str | Path) -> None:
    """Set every regular file and directory below ``root`` to owner-only mode."""
    root_path = Path(root)
    root_mode = root_path.lstat().st_mode
    if not stat.S_ISDIR(root_mode):
        raise NotADirectoryError(f"private staging root is not a directory: {root_path}")
    for current, directories, files in os.walk(root_path, followlinks=False):
        current_path = Path(current)
        for name in directories:
            child = current_path / name
            mode = child.lstat().st_mode
            if not stat.S_ISDIR(mode):
                raise ValueError(f"private staging directory is not a directory: {child}")
            os.chmod(child, 0o700)
        for name in files:
            child = current_path / name
            mode = child.lstat().st_mode
            if not stat.S_ISREG(mode):
                raise ValueError(f"private staging file is not regular: {child}")
            os.chmod(child, 0o600)
    os.chmod(root_path, 0o700)


def _existing_target_error(parent_fd: int, name: str, target: Path) -> FileExistsError:
    try:
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return FileExistsError(f"output destination appeared during publication: {target}")
    if stat.S_ISLNK(current.st_mode):
        return FileExistsError(f"refusing symlink output destination: {target}")
    if not stat.S_ISREG(current.st_mode):
        return FileExistsError(f"refusing nonregular output destination: {target}")
    return FileExistsError(f"refusing to replace existing output: {target}")


def publish_private_file(path: str | Path, content: str | bytes) -> Path:
    """Atomically publish a new private file, refusing all existing targets.

    The completed 0600 temporary file is linked into place, which guarantees
    that publication never follows a symlink or replaces a destination that
    appeared concurrently. The target's parent directory must already exist.
    """
    target = Path(path)
    name = target.name
    if name in {"", ".", ".."}:
        raise ValueError("output destination must name a file")
    parent = target.parent if str(target.parent) else Path(".")
    dir_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    dir_flags |= getattr(os, "O_CLOEXEC", 0)
    parent_fd = os.open(parent, dir_flags)
    temp_name = f".private-output-{secrets.token_hex(12)}.tmp"
    temp_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    temp_flags |= getattr(os, "O_NOFOLLOW", 0)
    temp_fd = None
    try:
        try:
            os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise _existing_target_error(parent_fd, name, target)

        temp_fd = os.open(temp_name, temp_flags, 0o600, dir_fd=parent_fd)
        os.fchmod(temp_fd, 0o600)
        payload = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        with os.fdopen(temp_fd, "wb", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(temp_fd)
        try:
            os.link(temp_name, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd,
                    follow_symlinks=False)
        except FileExistsError:
            raise _existing_target_error(parent_fd, name, target)
        os.fsync(parent_fd)
    finally:
        if temp_fd is not None:
            os.close(temp_fd)
        try:
            os.unlink(temp_name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        os.close(parent_fd)
    return target
