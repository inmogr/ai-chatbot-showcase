"""Scan every commit on every branch for secrets before submission (NFR-08).

    uv run python -m scripts.scan_secrets        # run from miniragchatbot/; exit 0 = clean

Every line added by any commit is matched against key and token patterns and against the exact
JWT_SECRET / *_API_KEY values of the local `.env`; a committed `.env` file is a finding too.
Findings name the commit, the file and the rule — never the matched value. Binary files (the
PDFs) are not decoded.
"""

import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

PATTERNS: dict[str, re.Pattern[str]] = {
    "groq api key": re.compile(r"\bgsk_[A-Za-z0-9]{20,}"),
    "openai-style api key": re.compile(r"\bsk-(?:proj-|ant-|or-)?[A-Za-z0-9_-]{20,}"),
    "google api key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
SECRET_NAME = re.compile(r"^(?:JWT_SECRET|[A-Z0-9_]+_API_KEY)$")
MIN_LITERAL_LENGTH = 8  # shorter values would match ordinary text
GIT_LOG = ["git", "log", "--all", "-p", "--no-color", "--no-ext-diff", "--unified=0"]
GIT_STAGED = ["git", "diff", "--cached", "--no-color", "--no-ext-diff", "--unified=0"]
STAGED = "staged"


@dataclass(frozen=True)
class Finding:
    commit: str
    path: str
    rule: str


def scan_text(text: str, literals: Mapping[str, str] | None = None) -> list[str]:
    """The names of the rules that match `text`."""
    rules = [name for name, pattern in PATTERNS.items() if pattern.search(text)]
    rules += [f"{name} value" for name, value in (literals or {}).items() if value in text]
    return rules


def scan_log(log: str, literals: Mapping[str, str] | None = None) -> list[Finding]:
    """Findings in `git log -p --format=commit:%H` output, in order and without duplicates."""
    findings: dict[Finding, None] = {}  # an ordered set
    commit = path = ""
    for line in log.splitlines():
        if line.startswith("commit:"):
            commit = line.removeprefix("commit:")
        elif line.startswith("diff --git "):
            path = line.rsplit(" b/", 1)[-1]
            if _is_env_file(path):
                findings[Finding(commit, path, "committed .env file")] = None
        elif line.startswith("+") and not line.startswith("+++ "):
            for rule in scan_text(line[1:], literals):
                findings[Finding(commit, path, rule)] = None
    return list(findings)


def scan_staged(diff: str, literals: Mapping[str, str] | None = None) -> list[Finding]:
    """Findings in `git diff --cached` output, labelled "staged" (not yet committed)."""
    return scan_log(f"commit:{STAGED}\n{diff}", literals)


def _is_env_file(path: str) -> bool:
    """`.env` and variants such as `.env.local`; the `.env.example` template is allowed."""
    name = Path(path).name
    return name == ".env" or (name.startswith(".env.") and name != ".env.example")


def local_secret_values(env_file: Path) -> dict[str, str]:
    """JWT_SECRET and *_API_KEY values set in `env_file`; held in memory, never printed."""
    if not env_file.is_file():
        return {}
    values: dict[str, str] = {}
    for line in env_file.read_text().splitlines():
        name, separator, value = line.partition("=")
        name, value = name.strip(), value.strip().strip("'\"")
        if separator and SECRET_NAME.match(name) and len(value) >= MIN_LITERAL_LENGTH:
            values[name] = value
    return values


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, errors="replace", check=True
    ).stdout


def main() -> int:
    env_file = Path(".env")
    if not env_file.is_file():
        print("warning: no .env here, so exact values are not checked; run from miniragchatbot/")
    literals = local_secret_values(env_file)
    log = _git(*GIT_LOG[1:], "--format=commit:%H")
    findings = scan_log(log, literals) + scan_staged(_git(*GIT_STAGED[1:]), literals)
    for finding in findings:
        print(f"{finding.commit[:12]}  {finding.path}  {finding.rule}")
    commits = sum(1 for line in log.splitlines() if line.startswith("commit:"))
    print(f"scanned {commits} commits on all branches + staged changes: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
