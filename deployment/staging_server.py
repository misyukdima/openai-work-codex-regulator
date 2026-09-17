#!/usr/bin/env python3
"""STAGING-ONLY ASGI composition for Regulator v3.0 MCP server.

WARNING: DEVELOPMENT / STAGING ONLY.
This module is explicitly intended for development and staging environments.
It uses EphemeralSubjectAuthStore with an in-memory ephemeral pepper and MUST NOT
be used as production credential storage. It does NOT store persistent Codex
credentials and does NOT perform quota authorization.

The server exposes the official Streamable HTTP MCP transport with OAuth 2.1 /
OIDC bearer verification. Callers without an authorized quota session receive
QUOTA_AUTH_REQUIRED (NEEDS_QUOTA_AUTH). No Codex subprocess is launched.
"""

from __future__ import annotations

import os
from pathlib import Path
import secrets
import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from plugin.production_runtime import (
    ProductionRuntimeConfig,
    build_production_app,
)
from plugin.quota_service import QuotaService, QuotaToolHandler
from plugin.subject_store import EphemeralSubjectAuthStore


def create_staging_app():
    """Construct the staging-only MCP ASGI application."""
    config = ProductionRuntimeConfig.from_environment()

    staging_auth_root = os.environ.get(
        "REGULATOR_STAGING_AUTH_ROOT",
        "/run/meciles-regulator/staging-auth",
    )

    # In-process ephemeral pepper generated fresh at process startup.
    # Never persisted to disk or exported to environment.
    pepper = secrets.token_bytes(32)

    store = EphemeralSubjectAuthStore(
        pepper=pepper,
        root=staging_auth_root,
    )
    if store.production_safe:
        raise RuntimeError("staging store must never claim production_safe=True")

    service = QuotaService(auth_store=store)
    handler = QuotaToolHandler(service)
    return build_production_app(handler, config)


# Exported ASGI app for uvicorn deployment.staging_server:app
app = create_staging_app()
