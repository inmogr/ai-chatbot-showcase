"""The test-only fin-001 token helper and the git-history secrets scan (PRD §3, NFR-08)."""

from pathlib import Path

import jwt
import pytest
from conftest import TEST_SECRET

from app.transport.websocket.auth import decode_claims
from scripts import generate_test_tokens, scan_secrets

ROOT = Path(__file__).resolve().parents[1]
# Built at runtime, so the history scan never meets a key-shaped literal in this file.
FAKE_GROQ_KEY = "gsk_" + "A1b2C3d4" * 6
FAKE_PRIVATE_KEY = "-----BEGIN " + "RSA PRIVATE KEY-----"
FAKE_JWT = jwt.encode({"sub": "x"}, "k" * 32, algorithm="HS256")


def test_generate_test_tokens_mints_fin001_accepted_by_server() -> None:
    claims = decode_claims(generate_test_tokens.mint("fin-001", TEST_SECRET), TEST_SECRET)
    assert (claims.sub, claims.department, claims.level) == ("fin-001", "finance", 1)


def test_generate_test_tokens_prints_only_the_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)  # the environment wins over .env
    assert generate_test_tokens.main([]) == 0
    printed = capsys.readouterr().out.strip()
    assert decode_claims(printed, TEST_SECRET).sub == "fin-001"
    assert TEST_SECRET not in printed  # unlike mint_tokens.py, the secret is never printed


def test_scan_text_flags_secrets_and_spares_placeholders() -> None:
    assert scan_secrets.scan_text(f"GROQ_API_KEY={FAKE_GROQ_KEY}") == ["groq api key"]
    assert scan_secrets.scan_text(f"token: {FAKE_JWT}") == ["jwt"]
    assert scan_secrets.scan_text(FAKE_PRIVATE_KEY) == ["private key"]
    literal = {"JWT_SECRET": "my-real-secret-value"}
    assert scan_secrets.scan_text("s = 'my-real-secret-value'", literal) == ["JWT_SECRET value"]
    assert scan_secrets.scan_text((ROOT / ".env.example").read_text()) == []
    assert scan_secrets.scan_text("a risk-assessment-for-every-department note") == []


def test_scan_log_reports_commit_path_and_rule_without_the_value() -> None:
    log = "\n".join(
        [
            "commit:" + "a" * 40,
            "diff --git a/app/x.py b/app/x.py",
            "+++ b/app/x.py",
            f"+KEY = '{FAKE_GROQ_KEY}'",
            "commit:" + "b" * 40,
            "diff --git a/.env b/.env",
            "+++ b/.env",
            "+JWT_SECRET=whatever",
        ]
    )
    findings = scan_secrets.scan_log(log)
    assert findings == [
        scan_secrets.Finding("a" * 40, "app/x.py", "groq api key"),
        scan_secrets.Finding("b" * 40, ".env", "committed .env file"),
    ]
    assert all(FAKE_GROQ_KEY not in str(finding) for finding in findings)


def test_scan_log_flags_env_variants_but_not_the_template() -> None:
    log = "\n".join(
        [
            "commit:" + "c" * 40,
            "diff --git a/.env.local b/.env.local",
            "diff --git a/miniragchatbot/.env b/miniragchatbot/.env",
            "diff --git a/.env.example b/.env.example",
        ]
    )
    assert [finding.path for finding in scan_secrets.scan_log(log)] == [
        ".env.local",
        "miniragchatbot/.env",
    ]


def test_staged_changes_are_scanned_too() -> None:
    # The index is labelled "staged", so a secret is caught before it is ever committed.
    staged = f"diff --git a/app/x.py b/app/x.py\n+++ b/app/x.py\n+KEY = '{FAKE_GROQ_KEY}'\n"
    assert scan_secrets.scan_staged(staged) == [
        scan_secrets.Finding("staged", "app/x.py", "groq api key")
    ]


def test_local_secret_values_reads_only_set_secrets(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\nJWT_SECRET=abcdefghijk\nGROQ_API_KEY=\nQDRANT_URL=http://x\nX_API_KEY=short\n"
    )
    assert scan_secrets.local_secret_values(env_file) == {"JWT_SECRET": "abcdefghijk"}
    assert scan_secrets.local_secret_values(tmp_path / "missing") == {}
