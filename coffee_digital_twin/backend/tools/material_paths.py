"""Shared guards for material tooling; formal test contents are out of bounds."""
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MATERIAL_ROOT = REPO_ROOT / "实验资料"


def allowed_path(path):
    path = Path(path).expanduser()
    # Check both the requested path and the resolved target (including junctions).
    for candidate in (path.absolute(), path.resolve()):
        if any(part.casefold().startswith("06_正式测试资料") for part in candidate.parts):
            raise ValueError("正式测试资料目录不允许工具读写")
    return path.resolve()


def sha256_file(path):
    import hashlib

    digest = hashlib.sha256()
    with allowed_path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
