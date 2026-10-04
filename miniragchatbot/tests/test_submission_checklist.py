"""Submission checks: offline suite, files and env template, README content (FR-31…FR-33)."""

import os
import re
import subprocess
import sys
from pathlib import Path

from app.config import IngestConfig, ServerConfig

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README_SUBMISSION.md"
SELF = "tests/test_submission_checklist.py::test_offline_suite_requires_no_external_services"
DEAD_PROXY = "http://127.0.0.1:9"  # nothing listens on the discard port, so any HTTP call fails
REQUIRED_FILES = (
    "README_SUBMISSION.md",
    ".env.example",
    "pyproject.toml",
    "uv.lock",
    "requirements.txt",
    "mint_tokens.py",
    "test_client.html",
    "app/main.py",
    "scripts/ingest.py",
    "scripts/generate_test_tokens.py",
    "scripts/scan_secrets.py",
)
BRIEF_SECTIONS = (  # the brief's "What to submit" list, in its order
    "How to run the ingestion script",
    "How to run the server",
    "How to test",
    "Chunking strategy",
    "RBAC approach",
    "Async / parallel approach",
    "One thing I would improve",
    "One tradeoff",
)
EXTRA_SECTIONS = (
    "LLM provider",
    "How to swap the provider",
    "Assumptions",
    "Limits and timeouts",
    "Test notice",
    "Known limitations",
)
PLANNING_ID = re.compile(r"\b(?:[A-Z]{1,3}-\d{2,3}|E\d{2}|K\d{2})\b")  # e.g. D-77, U-01, E15


def readme_headings() -> list[str]:
    return re.findall(r"^## (.+)$", README.read_text(), flags=re.MULTILINE)


def readme_section(title: str) -> str:
    """The body under the `## ` heading that starts with `title`, up to the next `## `."""
    parts = re.split(r"^## ", README.read_text(), flags=re.MULTILINE)
    return next(part for part in parts if part.startswith(title))


def env_template_entries() -> dict[str, str]:
    """NAME → value for every `NAME=value` line of .env.example, commented out or not."""
    entries: dict[str, str] = {}
    for line in (ROOT / ".env.example").read_text().splitlines():
        match = re.match(r"^#?\s*([A-Z][A-Z0-9_]*)=(.*)$", line.strip())
        if match:
            entries[match.group(1)] = match.group(2).strip()
    return entries


def test_offline_suite_requires_no_external_services(tmp_path: Path) -> None:
    # NFR-15: re-run the default suite with an empty model cache, the Hugging Face offline
    # switches and a dead proxy for every HTTP client — no Docker, model, key or network.
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "HF_HOME": str(tmp_path / "hf"),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "NO_PROXY": "",
        **{name: DEAD_PROXY for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")},
        **{name: DEAD_PROXY for name in ("http_proxy", "https_proxy", "all_proxy")},
    }
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--deselect", SELF],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-2000:]
    assert re.search(r"\d+ passed", done.stdout)


def test_submission_files_and_env_template_present() -> None:
    assert [name for name in REQUIRED_FILES if not (ROOT / name).is_file()] == []
    entries = env_template_entries()
    settings = {name.upper() for name in ServerConfig.model_fields | IngestConfig.model_fields}
    assert sorted(settings - entries.keys()) == []  # every setting is documented
    assert "change-me" in entries["JWT_SECRET"]
    api_keys = [value for name, value in entries.items() if name.endswith("_API_KEY")]
    assert all(value == "" or value.endswith("...") for value in api_keys)  # placeholders only
    assert ".env" in (ROOT / ".gitignore").read_text().split()


def test_readme_submission_contains_required_sections() -> None:
    headings = readme_headings()
    for number, title in enumerate(BRIEF_SECTIONS, start=1):
        assert headings[number - 1].startswith(f"{number}. {title}"), headings[number - 1]
    for title in EXTRA_SECTIONS:
        assert any(heading.startswith(title) for heading in headings), title
    assert PLANNING_ID.findall(README.read_text()) == []  # no internal planning labels


def test_readme_commands_point_at_real_modules() -> None:
    modules = set(re.findall(r"python -m scripts\.(\w+)", README.read_text()))
    assert {"ingest", "ws_probe", "generate_test_tokens"} <= modules
    assert sorted(name for name in modules if not (ROOT / "scripts" / f"{name}.py").is_file()) == []


def test_readme_documents_provider_selection_rationale() -> None:
    provider = readme_section("LLM provider")
    default_model = ServerConfig.model_fields["groq_model"].default
    assert env_template_entries()["GROQ_MODEL"] == default_model
    for claim in (
        "Groq",
        default_model,
        "free",
        "tool",
        "reasoning",
        "does not retain customer data for inference by default",
        "4 role-filtered excerpts",
        "OCR and embeddings run locally",
        "LLM_PROVIDER=ollama",
    ):
        assert claim in provider, claim
    lowered = README.read_text().lower()
    for overclaim in ("zero retention", "zero data retention", "does not train", "never train"):
        assert overclaim not in lowered
