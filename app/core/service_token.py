"""Signed service-to-service tokens (Ed25519).

Python counterpart to Insight-Express.TS-1/src/middleware/serviceToken.ts.
Claim set and header name must stay in step with that file.

Each service holds its own private key and publishes a public key, so
compromising one service does not yield the means to impersonate another.
That is the property the previous shared secrets could not give.
"""

from __future__ import annotations

import base64
import json
import os
import time
import uuid
from functools import lru_cache

import jwt
from cryptography.hazmat.primitives import serialization
from fastapi import Header, HTTPException, status

ALG = "EdDSA"
TOKEN_TTL_SECONDS = 120
CLOCK_TOLERANCE_SECONDS = 30
HEADER_NAME = "x-service-token"


def _require_config() -> dict[str, str]:
    config = _config()
    if config is None:
        raise RuntimeError(
            "Service tokens are not configured. Set "
            + ", ".join(_REQUIRED_VARS)
            + "."
        )
    return config


# This service is open source and must run standalone, so the scheme is opt-in:
# configure all four variables and it enforces, leave them all unset and it does
# not. Partial configuration is rejected rather than treated as "off" — a
# half-configured deployment quietly accepting anonymous traffic is exactly the
# fail-open bug this scheme exists to remove.
_REQUIRED_VARS = (
    "SERVICE_NAME",
    "SERVICE_TOKEN_KID",
    "SERVICE_TOKEN_PRIVATE_KEY",
    "SERVICE_TOKEN_PUBLIC_KEYS",
)

# Resolved on first use, not at import. main.py calls load_dotenv() *after*
# importing the routers, so reading the environment at module scope here would
# always see it empty and silently decide the scheme was off.
@lru_cache(maxsize=1)
def _config() -> dict[str, str] | None:
    present = [name for name in _REQUIRED_VARS if os.environ.get(name)]

    if present and len(present) != len(_REQUIRED_VARS):
        missing = ", ".join(sorted(set(_REQUIRED_VARS) - set(present)))
        raise RuntimeError(
            f"Service tokens are partially configured — missing {missing}. "
            "Set all four to enforce, or none to run open."
        )

    if not present:
        return None

    return {name: os.environ[name] for name in _REQUIRED_VARS}


def enabled() -> bool:
    return _config() is not None


def service_name() -> str:
    """This service's identity: the `iss` it signs and the `aud` it accepts."""
    config = _config()
    return config["SERVICE_NAME"] if config else ""


@lru_cache(maxsize=1)
def _private_key():
    der = base64.b64decode(_require_config()["SERVICE_TOKEN_PRIVATE_KEY"])
    return serialization.load_der_private_key(der, password=None)


@lru_cache(maxsize=1)
def _public_key_registry() -> dict[str, dict[str, str]]:
    """kid -> {"service": ..., "key": <base64 SPKI DER>}.

    Adding a service is one entry. Rotation is a second entry under a new kid,
    which is what lets a key be replaced without a lockstep restart.
    """
    raw = _require_config()["SERVICE_TOKEN_PUBLIC_KEYS"]
    try:
        registry = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("SERVICE_TOKEN_PUBLIC_KEYS is not valid JSON.") from exc

    for kid, entry in registry.items():
        if not isinstance(entry, dict) or "service" not in entry or "key" not in entry:
            raise RuntimeError(f'SERVICE_TOKEN_PUBLIC_KEYS["{kid}"] must be {{service, key}}.')

    return registry


@lru_cache(maxsize=32)
def _public_key(kid: str):
    entry = _public_key_registry().get(kid)
    if entry is None:
        raise ValueError(f"Unknown service token kid: {kid}")
    return serialization.load_der_public_key(base64.b64decode(entry["key"]))


def mint_service_token(audience: str, scope: list[str]) -> str:
    """Mint a token for one specific recipient.

    The audience is mandatory: it is what stops a token minted for the converter
    being replayed against VisEngine, and why this needs one keypair per service
    rather than one secret per pair of services.
    """
    config = _require_config()
    now = int(time.time())
    return jwt.encode(
        {
            "iss": config["SERVICE_NAME"],
            "aud": audience,
            "scope": scope,
            "iat": now,
            "exp": now + TOKEN_TTL_SECONDS,
            "jti": str(uuid.uuid4()),
        },
        _private_key(),
        algorithm=ALG,
        headers={"kid": config["SERVICE_TOKEN_KID"]},
    )


def auth_headers(audience: str, scope: list[str]) -> dict[str, str]:
    return {HEADER_NAME: mint_service_token(audience, scope)}


def verify_service_token(token: str) -> dict:
    # The kid selects the key; it does not get to select the algorithm. The
    # algorithms list below is pinned, which is what prevents alg confusion
    # and the `none` algorithm.
    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except jwt.PyJWTError as exc:
        raise ValueError(f"Malformed service token: {exc}") from exc

    if not kid:
        raise ValueError("Service token has no kid")

    entry = _public_key_registry().get(kid)
    if entry is None:
        raise ValueError(f"Unknown service token kid: {kid}")

    try:
        payload = jwt.decode(
            token,
            _public_key(kid),
            algorithms=[ALG],
            audience=service_name(),
            issuer=entry["service"],
            leeway=CLOCK_TOLERANCE_SECONDS,
            options={"require": ["exp", "iat", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise ValueError(str(exc)) from exc

    # The kid identifies the key, but the issuer claim is what the caller
    # asserts. Binding them stops a service signing a token claiming to be
    # another one.
    if payload.get("iss") != entry["service"]:
        raise ValueError(f'Issuer {payload.get("iss")} does not match kid {kid}')

    return payload


def require_service_token(required_scope: str):
    """FastAPI dependency. Use as:

        router.include_router(ingest_router,
            dependencies=[Depends(require_service_token("climate:ingest"))])

    Passes through when the scheme is unconfigured, so a standalone checkout
    runs without keys. See _config() above for why that is opt-in rather than a
    silent default.
    """

    async def dependency(
        x_service_token: str | None = Header(default=None),
    ) -> dict | None:
        # Checked per request, not when this factory runs: the routers are
        # imported before load_dotenv(), so deciding here at import time would
        # cache "unconfigured" permanently.
        if not enabled():
            return None

        if not x_service_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
            )

        try:
            payload = verify_service_token(x_service_token)
        except ValueError:
            # Deliberately opaque: distinguishing "bad signature" from "unknown
            # kid" tells a caller which part of the guess was wrong.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
            )

        if required_scope not in payload.get("scope", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scope"
            )

        return payload

    return dependency
