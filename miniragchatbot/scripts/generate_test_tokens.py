"""Mint the test-only `fin-001` token (finance, level 1) that mint_tokens.py does not provide.

mint_tokens.py stays as delivered. This helper signs with the same JWT_SECRET (environment,
then `.env`), the same claims and the same 7-day lifetime, and prints only the token.

    uv run python -m scripts.generate_test_tokens        # run from miniragchatbot/
"""

import argparse
import time

import jwt
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

TTL_SECONDS = 7 * 24 * 60 * 60  # the lifetime mint_tokens.py uses
TEST_USERS: dict[str, dict[str, str | int]] = {
    "fin-001": {"email": "fin@test.com", "department": "finance", "level": 1},
}


class TokenConfig(BaseSettings):
    """Only the signing secret: minting needs none of the server's provider settings."""

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_ignore_empty=True, hide_input_in_errors=True
    )

    jwt_secret: SecretStr


def mint(sub: str, secret: str) -> str:
    issued = int(time.time())
    claims = {"sub": sub, **TEST_USERS[sub], "iat": issued, "exp": issued + TTL_SECONDS}
    return jwt.encode(claims, secret, algorithm="HS256")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print a JWT for a test-only user.")
    parser.add_argument("sub", nargs="?", default="fin-001", choices=sorted(TEST_USERS))
    args = parser.parse_args(argv)
    print(mint(args.sub, TokenConfig().jwt_secret.get_secret_value()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
