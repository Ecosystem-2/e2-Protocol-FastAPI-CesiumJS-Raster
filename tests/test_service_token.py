# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Cross-language golden vector for the Ed25519 service-token scheme.

The token below was minted by Node (jose) in Insight-Express.TS-1 and is
committed verbatim. If a change to either side breaks interoperability — a
different claim name, a different DER encoding, a swapped algorithm — this test
fails instead of the deploy.

The keypair is a throwaway generated for this file. It is not used anywhere.
"""

import importlib

import pytest

# Minted by:
#   new SignJWT({scope:["climate:read"]})
#     .setProtectedHeader({alg:"EdDSA", kid:"express-api-testvector"})
#     .setIssuer("express-api").setAudience("hob-fastapi")
#     .setIssuedAt(1758000000).setExpirationTime(1758000120)
GOLDEN_TOKEN = (
    "eyJhbGciOiJFZERTQSIsImtpZCI6ImV4cHJlc3MtYXBpLXRlc3R2ZWN0b3IifQ"
    ".eyJzY29wZSI6WyJjbGltYXRlOnJlYWQiXSwiaXNzIjoiZXhwcmVzcy1hcGkiLCJhdWQiOiJo"
    "b2ItZmFzdGFwaSIsImlhdCI6MTc1ODAwMDAwMCwiZXhwIjoxNzU4MDAwMTIwLCJqdGkiOiIw"
    "MDAwMDAwMC0wMDAwLTQwMDAtODAwMC0wMDAwMDAwMDAwMDAifQ"
    ".Is-VpNIhg1xJjDhV6kUFyuePc18vTNdMXy-cYfhVH9veJGyObe6sLzW7zcPVPrHLlDMGA8xj"
    "uzf-Gjz_cVcLDg"
)

GOLDEN_PUBLIC_SPKI = "MCowBQYDK2VwAyEAE7unnevs4nJH9RIJRgQQ2f2cSzjhR8QlIvEICjOrXyA="

PUBLIC_KEYS = (
    '{"express-api-testvector":'
    '{"service":"express-api","key":"' + GOLDEN_PUBLIC_SPKI + '"}}'
)


@pytest.fixture
def configured(monkeypatch):
    """Load the module with a full token configuration in the environment.

    _config() is lru_cached, so the cache is cleared rather than the module
    reimported — reimporting would leave two copies of the cache alive.
    """
    # Stays hob-fastapi while the service is called e2-visengine-service: the golden
    # token's `aud` sits inside the signature, so the fixture has to address this
    # service by the name Express used when it minted the vector.
    monkeypatch.setenv("SERVICE_NAME", "hob-fastapi")
    monkeypatch.setenv("SERVICE_TOKEN_KID", "hob-fastapi-testvector")
    monkeypatch.setenv("SERVICE_TOKEN_PRIVATE_KEY", "unused-for-verification")
    monkeypatch.setenv("SERVICE_TOKEN_PUBLIC_KEYS", PUBLIC_KEYS)

    from app.core import service_token

    service_token._config.cache_clear()
    service_token._public_key_registry.cache_clear()
    service_token._public_key.cache_clear()
    yield service_token
    service_token._config.cache_clear()
    service_token._public_key_registry.cache_clear()
    service_token._public_key.cache_clear()


def test_verifies_a_node_minted_token(configured, monkeypatch):
    # The vector has a fixed iat/exp so the signature stays stable, which means
    # expiry has to be ignored. Everything else is checked for real.
    real_decode = configured.jwt.decode

    def decode_ignoring_expiry(*args, **kwargs):
        kwargs.setdefault("options", {})["verify_exp"] = False
        return real_decode(*args, **kwargs)

    monkeypatch.setattr(configured.jwt, "decode", decode_ignoring_expiry)

    payload = configured.verify_service_token(GOLDEN_TOKEN)

    assert payload["iss"] == "express-api"
    assert payload["aud"] == "hob-fastapi"
    assert payload["scope"] == ["climate:read"]


def test_rejects_an_unknown_kid(configured):
    tampered = GOLDEN_TOKEN.replace(
        "eyJhbGciOiJFZERTQSIsImtpZCI6ImV4cHJlc3MtYXBpLXRlc3R2ZWN0b3IifQ",
        # {"alg":"EdDSA","kid":"not-a-real-kid"}
        "eyJhbGciOiJFZERTQSIsImtpZCI6Im5vdC1hLXJlYWwta2lkIn0",
    )
    with pytest.raises(ValueError, match="Unknown service token kid"):
        configured.verify_service_token(tampered)


def test_rejects_an_unsigned_token(configured):
    # alg=none with the signature stripped. Pinning algorithms=[EdDSA] is what
    # stops this being accepted.
    header_and_body = GOLDEN_TOKEN.rsplit(".", 1)[0]
    none_header = "eyJhbGciOiJub25lIiwia2lkIjoiZXhwcmVzcy1hcGktdGVzdHZlY3RvciJ9"
    unsigned = none_header + "." + header_and_body.split(".", 1)[1] + "."
    with pytest.raises(ValueError):
        configured.verify_service_token(unsigned)


def test_unconfigured_environment_runs_open(monkeypatch):
    for name in (
        "SERVICE_NAME",
        "SERVICE_TOKEN_KID",
        "SERVICE_TOKEN_PRIVATE_KEY",
        "SERVICE_TOKEN_PUBLIC_KEYS",
    ):
        monkeypatch.delenv(name, raising=False)

    from app.core import service_token

    service_token._config.cache_clear()
    try:
        assert service_token.enabled() is False
    finally:
        service_token._config.cache_clear()


def test_partial_configuration_is_an_error(monkeypatch):
    # The whole point: half-configured must not silently mean "open".
    monkeypatch.setenv("SERVICE_NAME", "hob-fastapi")
    for name in (
        "SERVICE_TOKEN_KID",
        "SERVICE_TOKEN_PRIVATE_KEY",
        "SERVICE_TOKEN_PUBLIC_KEYS",
    ):
        monkeypatch.delenv(name, raising=False)

    from app.core import service_token

    service_token._config.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="partially configured"):
            service_token.enabled()
    finally:
        service_token._config.cache_clear()
