"""Verify the archived discussion artifacts; optionally extract to a new directory."""

import argparse
import hashlib
import json
import tarfile
from pathlib import Path, PurePosixPath


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract", type=Path, help="New output directory; must not exist")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / "manifest.json").read_text())
    archive = root / manifest["archive"]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["archive_sha256"]:
        raise SystemExit("Archive checksum mismatch")
    expected = {row["path"]: row for row in manifest["files"]}
    if len(expected) != manifest["file_count"]:
        raise SystemExit("Manifest has duplicate paths or an inconsistent count")
    if args.extract is not None and args.extract.exists():
        raise SystemExit("Extraction destination must not already exist")
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        names = [member.name for member in members]
        if len(set(names)) != len(names) or set(names) != set(expected):
            raise SystemExit("Archive inventory differs from manifest")
        for member in members:
            path = PurePosixPath(member.name)
            if (
                not member.isfile()
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in member.name
                or ":" in member.name
            ):
                raise SystemExit(f"Unsafe archive entry: {member.name}")
            row = expected[member.name]
            with bundle.extractfile(member) as stream:
                digest = hashlib.sha256(stream.read()).hexdigest()
            if member.size != row["bytes"] or digest != row["sha256"]:
                raise SystemExit(f"File checksum mismatch: {member.name}")
        # Validate every entry before writing any files. Do not execute archived code.
        if args.extract is not None:
            args.extract.mkdir(parents=True, exist_ok=False)
            for member in members:
                target = args.extract.joinpath(*PurePosixPath(member.name).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(member) as stream:
                    target.write_bytes(stream.read())
    print(f"Verified {len(expected)} files; archive and individual checksums match.")
    if args.extract is not None:
        print(f"Extracted to {args.extract.resolve()}")


if __name__ == "__main__":
    main()
