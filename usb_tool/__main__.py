import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


MANIFEST = ".usb-tool-manifest.json"


def drives():
    if sys.platform == "win32":
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if mask & (1 << i):
                root = f"{chr(65+i)}:\\"
                if ctypes.windll.kernel32.GetDriveTypeW(root) == 2:
                    yield root
    elif Path("/proc/mounts").exists():
        for line in Path("/proc/mounts").read_text().splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0].startswith("/dev/") and parts[1].startswith(("/media/", "/run/media/")):
                yield parts[1].replace("\\040", " ")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def plan(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_dir():
        raise ValueError("source must be a directory")
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("source and destination must not overlap")
    files = []
    for root, dirs, names in os.walk(source, followlinks=False):
        for name in dirs + names:
            if (Path(root) / name).is_symlink():
                raise ValueError("symbolic links are not supported")
        for name in names:
            src = Path(root) / name
            rel = src.relative_to(source)
            if rel.as_posix() == MANIFEST:
                raise ValueError("source contains reserved manifest name")
            files.append((src, destination / rel, rel.as_posix()))
    return sorted(files, key=lambda entry: entry[2])


def copy(source, destination, dry_run=False):
    files = plan(source, destination)
    if dry_run:
        return [relative for _, _, relative in files]
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    records = []
    for src, target, relative in files:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".usb-copy-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as output, src.open("rb") as input_stream:
                shutil.copyfileobj(input_stream, output, 1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
            expected = digest(src)
            if digest(Path(tmp_name)) != expected:
                raise IOError(f"copy verification failed: {relative}")
            os.replace(tmp_name, target)
            records.append({"path": relative, "size": src.stat().st_size, "sha256": expected})
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
    manifest = destination / MANIFEST
    fd, temp = tempfile.mkstemp(prefix=".usb-manifest-", dir=destination)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"version": 1, "files": records}, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, manifest)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return [record["path"] for record in records]


def verify(source, destination):
    source, destination = Path(source), Path(destination)
    document = json.loads((destination / MANIFEST).read_text(encoding="utf-8"))
    if document.get("version") != 1:
        raise ValueError("unsupported manifest version")
    planned = {relative for _, _, relative in plan(source, destination)}
    listed = {record["path"] for record in document["files"]}
    if planned != listed or len(listed) != len(document["files"]):
        raise ValueError("manifest does not match source files")
    errors = []
    for record in document["files"]:
        relative = Path(record["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe manifest path")
        src, target = source / relative, destination / relative
        if not target.is_file() or target.is_symlink() or not src.is_file():
            errors.append(record["path"])
        elif src.stat().st_size != record["size"] or target.stat().st_size != record["size"] or digest(src) != record["sha256"] or digest(target) != record["sha256"]:
            errors.append(record["path"])
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verified USB file transfer")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    transfer = sub.add_parser("copy")
    transfer.add_argument("source")
    transfer.add_argument("destination")
    transfer.add_argument("--dry-run", action="store_true")
    check = sub.add_parser("verify")
    check.add_argument("source")
    check.add_argument("destination")
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            print("\n".join(drives()))
        elif args.command == "copy":
            print("\n".join(copy(args.source, args.destination, args.dry_run)))
        else:
            errors = verify(args.source, args.destination)
            if errors:
                print("\n".join(errors), file=sys.stderr)
                return 1
            print("Verified")
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())

