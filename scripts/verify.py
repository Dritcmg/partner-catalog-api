"""Run focused checks and write public evidence without workstation metadata."""

import hashlib
import importlib.metadata as metadata
import json
import os
import platform
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "artifacts"
PUBLIC = ROOT / "evidence"


def fingerprint() -> str:
    paths = []
    for folder in ["partner_catalog", "tests", "scripts"]:
        paths.extend((ROOT / folder).rglob("*.py"))
    paths.extend(
        ROOT / name for name in ["pyproject.toml", "requirements.txt", "requirements-dev.txt"]
    )
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


def run(name: str, arguments: list[str]) -> dict:
    process = subprocess.run(
        [sys.executable, "-m", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    (PRIVATE / f"{name}.log").write_text(process.stdout + process.stderr, encoding="utf-8")
    return {"command": "python -m " + " ".join(arguments), "exit_code": process.returncode}


def source_secret_findings() -> list[dict]:
    findings = []
    patterns = [
        r"github_pat_[A-Za-z0-9_]{30,}",
        r"gh[pousr]_[A-Za-z0-9]{24,}",
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        r"(?:postgres(?:ql)?|redis)://[^\s/:]+:[^\s/@]+@",
    ]
    for folder in ["partner_catalog", "tests", "scripts", "docs", ".github", ".vscode"]:
        for path in (ROOT / folder).rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            for number, line in enumerate(content.splitlines(), 1):
                if any(re.search(pattern, line) for pattern in patterns):
                    findings.append({"path": path.relative_to(ROOT).as_posix(), "line": number})
    return findings


def main() -> int:
    PRIVATE.mkdir(exist_ok=True)
    PUBLIC.mkdir(exist_ok=True)
    checks = {
        "lint": run("lint", ["ruff", "check", "."]),
        "format": run("format", ["ruff", "format", "--check", "."]),
        "tests": run(
            "tests",
            [
                "pytest",
                "-q",
                "--junitxml=artifacts/junit.xml",
                "--cov=partner_catalog",
                "--cov-report=json:artifacts/coverage.json",
                "--cov-report=term-missing",
            ],
        ),
        "dependency_audit": run(
            "audit",
            [
                "pip_audit",
                "-r",
                "requirements-dev.txt",
                "--format=json",
                "--output=artifacts/audit.json",
            ],
        ),
    }
    tree = ET.parse(PRIVATE / "junit.xml")
    suites = list(tree.getroot().iter("testsuite"))
    tests = {
        key: sum(int(suite.get(key, "0")) for suite in suites)
        for key in ["tests", "failures", "errors", "skipped"]
    }
    for node in tree.iter():
        for key in ["hostname", "timestamp", "file"]:
            node.attrib.pop(key, None)
    if checks["tests"]["exit_code"] == 0:
        tree.write(PUBLIC / "junit.xml", encoding="utf-8", xml_declaration=True)
    coverage_path = PRIVATE / "coverage.json"
    totals = (
        json.loads(coverage_path.read_text(encoding="utf-8"))["totals"]
        if coverage_path.exists()
        else None
    )
    findings = source_secret_findings()
    passed = all(check["exit_code"] == 0 for check in checks.values()) and not findings
    result = {
        "project": "partner-catalog-api",
        "status": "PASSED" if passed else "FAILED",
        "generated_at": datetime.now(UTC).isoformat(),
        "python_version": platform.python_version(),
        "source_fingerprint_sha256": fingerprint(),
        "checks": checks,
        "tests": tests,
        "coverage": {
            key: totals[key]
            for key in [
                "covered_lines",
                "num_statements",
                "percent_covered",
                "covered_branches",
                "num_branches",
            ]
        }
        if totals
        else None,
        "secret_signature_findings": findings,
        "versions": {
            name: metadata.version(name)
            for name in ["fastapi", "pydantic", "SQLAlchemy", "pytest", "ruff", "pip-audit"]
        },
        "scope": "Synthetic-data API/SQLite integration tests; no production or company systems.",
        "limitations": [
            "No live deployment or load benchmark.",
            "Single development API key, no identity provider or tenant authorization.",
            "Secret patterns are a focused scan, not a universal guarantee.",
        ],
    }
    (PUBLIC / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "tests": tests,
                "checks": checks,
                "secret_findings": len(findings),
            }
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
