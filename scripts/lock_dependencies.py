"""Capture the tested environment as exact versions without writing local paths."""

import importlib.metadata as metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def runtime_dependencies() -> set[str]:
    pending = ["fastapi", "pydantic", "SQLAlchemy", "uvicorn"]
    found: set[str] = set()
    while pending:
        name = canonicalize_name(pending.pop())
        if name in found:
            continue
        found.add(name)
        for raw in metadata.requires(name) or []:
            requirement = Requirement(raw)
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                pending.append(requirement.name)
    return found


def write_lock(path: Path, packages: set[str]) -> None:
    lines = ["# Exact versions from the verified Python 3.12 environment."]
    lines += [f"{name}=={metadata.version(name)}" for name in sorted(packages)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_lock(ROOT / "requirements.txt", runtime_dependencies())
    installed = {
        canonicalize_name(distribution.metadata["Name"])
        for distribution in metadata.distributions()
        if canonicalize_name(distribution.metadata["Name"]) not in {"pip", "setuptools"}
    }
    write_lock(ROOT / "requirements-dev.txt", installed)
    print("Exact runtime and development dependency files written.")
