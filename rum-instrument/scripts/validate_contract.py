#!/usr/bin/env python3
"""Validate a rum-instrument .rum/plan.json contract using only the standard library."""

from __future__ import annotations

import argparse
import ast
import copy
from datetime import date
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
from typing import Any
from urllib.parse import urlsplit


RECEIVER_MODES = {"public_dataway", "datakit"}
TARGET_DISPOSITIONS = {"planned", "existing", "instrumented", "skipped", "blocked", "failed"}
FINAL_TARGET_DISPOSITIONS = {"existing", "instrumented", "skipped", "blocked", "failed"}
REFERENCE_PREFIXES = ("template:", "env:", "existing:", "runtime:")
PROMPT_PROVIDED_REFERENCE = "prompt:provided"
DEPENDENCY_ACTIONS = {"preserve", "add", "upgrade", "remove", "none", "blocked"}
APPROVAL_BASES = {
    "plan_only_request",
    "explicit_implementation_request",
    "revision_review",
}
PLAN_ONLY_INTENTS = {"audit", "plan", "validate"}
IMPLEMENTATION_INTENTS = {"implement", "repair"}
REVIEW_REQUIRED_DEPENDENCY_ACTIONS = {"upgrade", "remove"}
OPTIONAL_SIGNAL_ALIASES = {
    "anr": "anr",
    "canvasreplay": "canvas_replay",
    "freeze": "freeze",
    "log": "logs",
    "logs": "logs",
    "nativecrash": "native_crash",
    "remoteconfig": "remote_config",
    "trace": "tracing",
    "traces": "tracing",
    "tracing": "tracing",
    "replay": "replay",
    "sessionreplay": "replay",
    "uiblock": "ui_block",
    "webview": "webview",
}
CORE_SIGNALS = {"rum"}
OPTIONAL_SIGNAL_STATUSES = {
    "disabled",
    "enabled",
    "existing",
    "omitted",
    "preserve",
}
ARTIFACT_STATUSES = {
    "configure",
    "disabled",
    "existing",
    "generate",
    "omitted",
    "preserve",
    "upload",
}
ARTIFACT_CONTROL_FIELDS = {
    "action",
    "configure",
    "decision",
    "enabled",
    "generate",
    "mode",
    "status",
    "upload",
}
CONTROL_PLANE_CATALOGS = {
    "https://urls.guance.com/",
    "https://urls.truewatch.com/",
}
TESTING_CONTROL_PLANE_CATALOG = "builtin_testing"
TESTING_AI_API_ENDPOINT = "https://testing-ft2x-ai-api.dataflux.cn"
TLS_VERIFICATION_MODES = {"verified", "disabled_for_testing"}
CONTROL_PLANE_STATUSES = {"catalog_resolved", "resolved", "blocked"}
CLIENT_TOKEN_AVAILABILITY = {"planned", "existing", "persisted"}
CLIENT_TOKEN_SINK_FORMATS = {"dotenv", "json", "properties", "xcconfig"}
CLIENT_TOKEN_SINK_SCOPES = {"repository", "external"}
APPLICATION_TYPES = {
    "web",
    "miniapp",
    "android",
    "ios",
    "custom",
    "reactnative",
    "harmonyos",
}
APPLICATION_TYPE_SOURCES = {"user", "ai_api", "repository"}
APPLICATION_TYPE_VERIFICATIONS = {
    "matched",
    "mismatched",
    "not_applicable",
    "pending",
}
GENERATED_PATH_PARTS = {
    ".gradle",
    "build",
    "deriveddata",
    "dist",
    "node_modules",
    "oh_modules",
    "pods",
    "unpackage",
    "vendor",
}
FORBIDDEN_PLANNED_PATH_PARTS = {
    ".agents",
    ".claude",
    ".codex",
    ".cursor",
    ".git",
    ".rum",
}
FORBIDDEN_PLANNED_PATH_PREFIXES = {
    (".config", "agents", "skills"),
    (".github", "skills"),
    (".opencode", "skills"),
    (".pi", "skills"),
}
ENV_REFERENCE_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")
RUNTIME_CONFIG_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$"
)
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
READINESS_CHECKS = {"rum_collector", "network_reachability"}
READINESS_STATUSES = {"blocked", "unknown", "verified"}
SENSITIVE_FIELDS = {
    "accesstoken",
    "apikey",
    "apikeys",
    "apikeysource",
    "apikeyvalue",
    "authorization",
    "authorizationheader",
    "authorizationheaders",
    "clienttoken",
    "clienttokensource",
    "clienttokenvalue",
    "cookie",
    "cookies",
    "password",
    "refreshtoken",
    "secret",
    "secretenvironmentvalue",
    "secretenvironmentvalues",
    "secretvalue",
    "setcookie",
    "temporaryauthorizationcode",
    "temporaryauthcode",
}
PAYLOAD_FIELDS = {
    "capturedtelemetry",
    "requestbody",
    "responsebody",
    "telemetrypayload",
}
SAFE_PAYLOAD_DECLARATIONS = {
    "disabled",
    "excluded",
    "not_collected",
    "redacted",
}
SENSITIVE_REFERENCE_FIELDS = {"source", "input", "runtime"}
SENSITIVE_REFERENCE_METADATA_FIELDS = {
    "availability",
    "behavior",
    "confidence",
    "description",
    "persistence",
    "provenance",
}
PROMPT_PROVIDED_SENSITIVE_FIELDS = {
    "temporaryauthorizationcode",
    "temporaryauthcode",
}


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_source(
    value: Any,
    location: str,
    errors: list[str],
    *,
    allow_literal: bool,
    allow_prompt_provided: bool = False,
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{location} must be an object")
        return

    source = value.get("source")
    literal = value.get("value")
    if source is not None and literal is not None:
        errors.append(f"{location} must contain source or value, not both")
        return
    if source is not None:
        if not is_nonempty_string(source):
            errors.append(f"{location}.source must be a non-empty string")
        elif not is_valid_reference(source) and not (
            allow_prompt_provided and source == PROMPT_PROVIDED_REFERENCE
        ):
            errors.append(
                f"{location}.source must be a structured template, env, existing, or runtime reference"
                + (" or prompt:provided" if allow_prompt_provided else "")
            )
        return
    if allow_literal and is_nonempty_string(literal):
        return
    errors.append(f"{location} must contain a non-empty source" + (" or value" if allow_literal else ""))


def reference_identity(value: Any) -> tuple[str, str] | None:
    if not isinstance(value, dict):
        return None
    if is_nonempty_string(value.get("source")):
        return "source", value["source"]
    if is_nonempty_string(value.get("value")):
        return "value", value["value"]
    return None


def validate_application_id_input(
    value: Any,
    errors: list[str],
) -> tuple[str | None, tuple[str, str] | None]:
    if not isinstance(value, dict):
        errors.append("request.application_id_input must be an object")
        return None, None

    kind = value.get("kind")
    if kind == "scalar":
        reference = value.get("reference")
        validate_source(
            reference,
            "request.application_id_input.reference",
            errors,
            allow_literal=True,
        )
        return kind, reference_identity(reference)
    if kind == "map":
        references = value.get("references")
        if not isinstance(references, dict) or not references:
            errors.append("request.application_id_input.references must be a non-empty object")
            return kind, None
        identities: set[tuple[str, str]] = set()
        for key, reference in references.items():
            location = f"request.application_id_input.references.{key}"
            if not is_nonempty_string(key):
                errors.append("request.application_id_input.references keys must be non-empty strings")
                continue
            validate_source(reference, location, errors, allow_literal=True)
            identity = reference_identity(reference)
            if identity in identities:
                errors.append(f"{location} duplicates another Application ID input reference")
            elif identity:
                identities.add(identity)
        return kind, None

    errors.append("request.application_id_input.kind must be scalar or map")
    return None, None


def normalize_field_name(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def is_valid_reference(reference: Any, *, client_token: bool = False) -> bool:
    if not is_nonempty_string(reference):
        return False
    prefix, separator, locator = reference.partition(":")
    if not separator or not locator:
        return False
    if prefix == "template":
        return not client_token and bool(ENV_REFERENCE_PATTERN.fullmatch(locator))
    if prefix == "env":
        return bool(ENV_REFERENCE_PATTERN.fullmatch(locator))
    if prefix == "runtime":
        return bool(
            ENV_REFERENCE_PATTERN.fullmatch(locator)
            or RUNTIME_CONFIG_PATTERN.fullmatch(locator)
        )
    if prefix == "existing":
        return any(marker in locator for marker in ("/", "#", ":"))
    return False


def is_source_reference(value: Any) -> bool:
    if is_nonempty_string(value):
        return is_valid_reference(value)
    if not isinstance(value, dict) or "value" in value:
        return False
    if not set(value).issubset(SENSITIVE_REFERENCE_FIELDS | SENSITIVE_REFERENCE_METADATA_FIELDS):
        return False
    references = [value[field] for field in SENSITIVE_REFERENCE_FIELDS if field in value]
    return bool(references) and all(
        is_valid_reference(reference)
        for reference in references
    )


def is_prompt_provided_reference(value: Any) -> bool:
    if value == PROMPT_PROVIDED_REFERENCE:
        return True
    if not isinstance(value, dict) or "value" in value:
        return False
    if not set(value).issubset(SENSITIVE_REFERENCE_FIELDS | SENSITIVE_REFERENCE_METADATA_FIELDS):
        return False
    references = [value[field] for field in SENSITIVE_REFERENCE_FIELDS if field in value]
    return references == [PROMPT_PROVIDED_REFERENCE]


def validate_signal_decision(
    value: Any,
    location: str,
    errors: list[str],
) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        raw_status = value
    elif isinstance(value, dict):
        if set(value) != {"status"}:
            errors.append(
                f"{location} object must contain only the status control field"
            )
            return False
        raw_status = value.get("status")
    else:
        errors.append(
            f"{location} must be a boolean, status string, or single-status object"
        )
        return False
    if not is_nonempty_string(raw_status):
        errors.append(f"{location} status must be a non-empty string")
        return False
    status = normalize_field_name(raw_status)
    if status not in OPTIONAL_SIGNAL_STATUSES:
        errors.append(
            f"{location} status must be enabled, disabled, existing, omitted, or preserve"
        )
        return False
    return status == "enabled"


def validate_artifact_decision(
    value: Any,
    location: str,
    errors: list[str],
) -> bool:
    if isinstance(value, str):
        raw_status = value
    elif isinstance(value, dict):
        controls = ARTIFACT_CONTROL_FIELDS & set(value)
        if len(controls) != 1 or controls not in ({"status"}, {"action"}):
            errors.append(
                f"{location} must contain exactly one status or action control field"
            )
            return False
        raw_status = value[next(iter(controls))]
    else:
        errors.append(f"{location} must be a status string or object")
        return False
    if not is_nonempty_string(raw_status):
        errors.append(f"{location} status must be a non-empty string")
        return False
    status = normalize_field_name(raw_status)
    if status not in ARTIFACT_STATUSES:
        errors.append(
            f"{location} status must be configure, disabled, existing, generate, "
            "omitted, preserve, or upload"
        )
        return False
    return status in {"configure", "generate", "upload"}


def validate_target_review_scope(
    target: dict[str, Any],
    location: str,
    errors: list[str],
    *, modern: bool = False,
) -> list[str]:
    existing = target.get("existing_instrumentation")
    existing_signals: set[str] = set()
    if isinstance(existing, dict):
        raw_existing_signals = existing.get("signals")
        if not isinstance(raw_existing_signals, list):
            errors.append(f"{location}.existing_instrumentation.signals must be an array")
        else:
            for signal in raw_existing_signals:
                if not is_nonempty_string(signal):
                    errors.append(
                        f"{location}.existing_instrumentation.signals must contain only non-empty strings"
                    )
                    continue
                canonical = OPTIONAL_SIGNAL_ALIASES.get(normalize_field_name(signal))
                if canonical:
                    existing_signals.add(canonical)
                elif normalize_field_name(signal) not in CORE_SIGNALS:
                    errors.append(
                        f"{location}.existing_instrumentation.signals contains "
                        f"unsupported signal {signal}"
                    )

    profile = target.get("profile")
    profile_signals = profile.get("signals") if isinstance(profile, dict) else None
    if not isinstance(profile_signals, dict):
        errors.append(f"{location}.profile.signals must be an object")
        profile_signals = {}

    planned = target.get("disposition") == "planned"
    reasons: list[str] = []
    core_rum_enabled = False
    for signal, decision in profile_signals.items():
        if not is_nonempty_string(signal):
            errors.append(f"{location}.profile.signals keys must be non-empty strings")
            continue
        normalized = normalize_field_name(signal)
        canonical = OPTIONAL_SIGNAL_ALIASES.get(normalized)
        if canonical is None and normalized not in CORE_SIGNALS:
            errors.append(f"{location}.profile.signals.{signal} is not a supported signal")
            continue
        enabled = validate_signal_decision(
            decision,
            f"{location}.profile.signals.{signal}",
            errors,
        )
        if normalized in CORE_SIGNALS:
            core_rum_enabled = enabled
        if (
            planned
            and canonical
            and canonical not in existing_signals
            and enabled
        ):
            if not (modern and scope_authorized(target, f"signal:{canonical}")):
                reasons.append(f"{location}: new optional signal {canonical}")
    if planned and not core_rum_enabled:
        errors.append(
            f"{location}.profile.signals.rum must be enabled for a planned RUM target"
        )

    artifacts = target.get("artifacts")
    if isinstance(artifacts, dict):
        for artifact, decision in artifacts.items():
            if not is_nonempty_string(artifact):
                errors.append(f"{location}.artifacts keys must be non-empty strings")
                continue
            enabled = validate_artifact_decision(
                decision,
                f"{location}.artifacts.{artifact}",
                errors,
            )
            if planned and enabled and not (modern and scope_authorized(target, f"artifact:{artifact}")):
                reasons.append(
                    f"{location}: new release artifact scope {artifact}"
                )
    return reasons


def is_safe_payload_declaration(value: Any) -> bool:
    if value is None or value is False:
        return True
    return isinstance(value, str) and value.strip().lower() in SAFE_PAYLOAD_DECLARATIONS


def validate_sensitive_values(value: Any, location: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                continue
            nested_location = f"{location}.{key}" if location else key
            normalized = normalize_field_name(key)
            if normalized in PAYLOAD_FIELDS and not is_safe_payload_declaration(nested):
                errors.append(f"{nested_location} must not be persisted")
                continue
            if (
                normalized in SENSITIVE_FIELDS
                and not is_source_reference(nested)
                and not (
                    normalized in PROMPT_PROVIDED_SENSITIVE_FIELDS
                    and is_prompt_provided_reference(nested)
                )
                and not is_safe_payload_declaration(nested)
            ):
                errors.append(
                    f"{nested_location} must contain only a non-secret source reference or disabled/redacted declaration"
                )
                continue
            validate_sensitive_values(nested, nested_location, errors)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            validate_sensitive_values(nested, f"{location}[{index}]", errors)


def validate_nonempty_string_list(value: Any, location: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{location} must be a non-empty array")
        return
    if any(not is_nonempty_string(item) for item in value):
        errors.append(f"{location} must contain only non-empty strings")


def validate_datakit_readiness(
    value: Any,
    location: str,
    errors: list[str],
) -> str | None:
    if not isinstance(value, dict):
        errors.append(f"{location} must be an object for DataKit mode")
        return None
    status = value.get("status")
    if status not in READINESS_STATUSES:
        errors.append(f"{location}.status must be blocked, unknown, or verified")
    checks = value.get("checks")
    if not isinstance(checks, dict):
        errors.append(f"{location}.checks must be an object")
        return status if status in READINESS_STATUSES else None
    missing = sorted(READINESS_CHECKS - set(checks))
    extra = sorted(set(checks) - READINESS_CHECKS)
    if missing:
        errors.append(f"{location}.checks is missing: {', '.join(missing)}")
    if extra:
        errors.append(f"{location}.checks contains unsupported checks: {', '.join(extra)}")
    check_statuses: set[str] = set()
    for check_name in sorted(READINESS_CHECKS & set(checks)):
        check = checks[check_name]
        check_location = f"{location}.checks.{check_name}"
        if not isinstance(check, dict):
            errors.append(f"{check_location} must be an object")
            continue
        check_status = check.get("status")
        if check_status not in READINESS_STATUSES:
            errors.append(
                f"{check_location}.status must be blocked, unknown, or verified"
            )
            continue
        check_statuses.add(check_status)
        evidence = check.get("evidence", [])
        handoff = check.get("handoff", [])
        if not isinstance(evidence, list) or any(
            not is_nonempty_string(item) for item in evidence
        ):
            errors.append(f"{check_location}.evidence must be an array of non-empty strings")
            evidence = []
        if not isinstance(handoff, list) or any(
            not is_nonempty_string(item) for item in handoff
        ):
            errors.append(f"{check_location}.handoff must be an array of non-empty strings")
            handoff = []
        if check_status == "verified" and not evidence:
            errors.append(f"{check_location}.evidence is required when status=verified")
        if check_status in {"unknown", "blocked"} and not handoff:
            errors.append(f"{check_location}.handoff is required when status={check_status}")
    if status == "verified" and check_statuses != {"verified"}:
        errors.append(f"{location}.status=verified requires every readiness check to be verified")
    if status == "unknown" and "blocked" in check_statuses:
        errors.append(f"{location}.status must be blocked when a readiness check is blocked")
    return status if status in READINESS_STATUSES else None


def _client_token_reference_key(reference: Any) -> str | None:
    source = reference.get("source") if isinstance(reference, dict) else None
    if not isinstance(source, str):
        return None
    if source.startswith(("runtime:", "env:")):
        return source.split(":", 1)[1]
    if source.startswith("existing:") and "#" in source:
        return source.rsplit("#", 1)[1]
    return None


def validate_client_token_sink(
    value: Any,
    location: str,
    reference: Any,
    errors: list[str],
) -> tuple[str, str, str] | None:
    if not isinstance(value, dict):
        errors.append(f"{location} must be an object")
        return None
    if set(value) != {"path", "format", "scope", "key"}:
        errors.append(
            f"{location} must contain only path, format, scope, and key"
        )
        return None
    path = value.get("path")
    sink_format = value.get("format")
    scope = value.get("scope")
    key = value.get("key")
    if not is_nonempty_string(path) or "\n" in path or "\r" in path:
        errors.append(f"{location}.path must be a non-empty single-line string")
    else:
        path_value = Path(path)
        if ".." in path_value.parts or ".git" in path_value.parts:
            errors.append(f"{location}.path must not traverse parents or .git")
        if scope == "repository" and path_value.is_absolute():
            errors.append(f"{location}.path must be repository-relative")
        if scope == "external" and not path_value.is_absolute():
            errors.append(f"{location}.path must be absolute for an external sink")
    if sink_format not in CLIENT_TOKEN_SINK_FORMATS:
        errors.append(
            f"{location}.format must be dotenv, json, properties, or xcconfig"
        )
    if scope not in CLIENT_TOKEN_SINK_SCOPES:
        errors.append(f"{location}.scope must be repository or external")
    if not is_nonempty_string(key):
        errors.append(f"{location}.key must be a non-empty string")
    expected_key = _client_token_reference_key(reference)
    if is_nonempty_string(key) and key != expected_key:
        errors.append(
            f"{location}.key does not match the Client Token source reference"
        )
    if (
        not is_nonempty_string(path)
        or sink_format not in CLIENT_TOKEN_SINK_FORMATS
        or scope not in CLIENT_TOKEN_SINK_SCOPES
        or not is_nonempty_string(key)
    ):
        return None
    return path, sink_format, scope


def validate_https_origin(value: Any, location: str, errors: list[str]) -> None:
    if not isinstance(value, dict) or "value" not in value:
        return
    endpoint = value.get("value")
    if not is_nonempty_string(endpoint):
        return
    if not is_valid_origin(endpoint, {"https"}):
        errors.append(f"{location}.value must be an HTTPS origin")


def is_valid_origin(value: str, schemes: set[str]) -> bool:
    parsed = urlsplit(value)
    try:
        parsed.port
    except ValueError:
        return False
    return not (
        parsed.scheme not in schemes
        or not parsed.netloc
        or parsed.hostname is None
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or any(
            character.isspace() or ord(character) < 32
            for character in parsed.netloc
        )
    )


def validate_http_origin(value: Any, location: str, errors: list[str]) -> None:
    if not isinstance(value, dict) or "value" not in value:
        return
    endpoint = value.get("value")
    if not is_nonempty_string(endpoint):
        return
    if not is_valid_origin(endpoint, {"http", "https"}):
        errors.append(f"{location}.value must be an HTTP(S) origin")


def validate_control_plane(value: Any, errors: list[str]) -> str | None:
    location = "request.receiver.control_plane"
    if not isinstance(value, dict):
        errors.append(f"{location} must be an object")
        return None

    status = value.get("status")
    if status not in CONTROL_PLANE_STATUSES:
        errors.append(
            f"{location}.status must be catalog_resolved, resolved, or blocked"
        )

    temporary_code = value.get("temporary_authorization_code")
    if temporary_code is not None:
        validate_source(
            temporary_code,
            f"{location}.temporary_authorization_code",
            errors,
            allow_literal=False,
            allow_prompt_provided=True,
        )
        if isinstance(temporary_code, dict):
            source = temporary_code.get("source")
            if (
                is_nonempty_string(source)
                and not source.startswith(REFERENCE_PREFIXES)
                and source != PROMPT_PROVIDED_REFERENCE
            ):
                errors.append(
                    f"{location}.temporary_authorization_code.source must be prompt:provided or a template, env, existing, or runtime reference"
                )
            if "value" in temporary_code:
                errors.append(f"{location}.temporary_authorization_code must never contain a value")

    if value.get("api_key_persistence") != "memory_only":
        errors.append(f"{location}.api_key_persistence must be memory_only")

    if status in {"catalog_resolved", "resolved"}:
        catalog = value.get("catalog")
        tls_verification = value.get("tls_verification", "verified")
        if tls_verification not in TLS_VERIFICATION_MODES:
            errors.append(
                f"{location}.tls_verification must be verified or disabled_for_testing"
            )
        if catalog in CONTROL_PLANE_CATALOGS:
            if value.get("test_only") is True:
                errors.append(
                    f"{location}.test_only is valid only with catalog=builtin_testing"
                )
            if "catalog_source" in value:
                errors.append(
                    f"{location}.catalog_source is not supported"
                )
            if tls_verification != "verified":
                errors.append(
                    f"{location}.tls_verification must remain verified for official catalogs"
                )
        elif catalog == TESTING_CONTROL_PLANE_CATALOG:
            if value.get("test_only") is not True:
                errors.append(
                    f"{location}.test_only must be true for catalog=builtin_testing"
                )
            if "catalog_source" in value:
                errors.append(
                    f"{location}.catalog_source is not supported for the built-in testing site"
                )
            if value.get("site_code") != "testing":
                errors.append(
                    f"{location}.site_code must be testing for catalog=builtin_testing"
                )
        else:
            errors.append(
                f"{location}.catalog must be an official catalog URL or builtin_testing"
            )
        if not is_nonempty_string(value.get("site_code")):
            errors.append(f"{location}.site_code must be a non-empty string")
        validate_source(
            value.get("ai_api_endpoint"),
            f"{location}.ai_api_endpoint",
            errors,
            allow_literal=True,
        )
        ai_api_endpoint = value.get("ai_api_endpoint")
        if (
            not isinstance(ai_api_endpoint, dict)
            or not is_nonempty_string(ai_api_endpoint.get("value"))
            or "source" in ai_api_endpoint
        ):
            errors.append(
                f"{location}.ai_api_endpoint must contain the literal catalog-matched value"
            )
        validate_https_origin(
            ai_api_endpoint,
            f"{location}.ai_api_endpoint",
            errors,
        )
        if (
            catalog == TESTING_CONTROL_PLANE_CATALOG
            and isinstance(ai_api_endpoint, dict)
            and ai_api_endpoint.get("value") != TESTING_AI_API_ENDPOINT
        ):
            errors.append(
                f"{location}.ai_api_endpoint.value must be "
                f"{TESTING_AI_API_ENDPOINT} for catalog=builtin_testing"
            )
        if value.get("exchange_path") != "/api/v1/account/accesskey/exchange":
            errors.append(
                f"{location}.exchange_path must be /api/v1/account/accesskey/exchange"
            )
        if value.get("application_lookup_path") != "/api/v1/rum/app/get":
            errors.append(f"{location}.application_lookup_path must be /api/v1/rum/app/get")
    elif status == "blocked":
        validate_nonempty_string_list(value.get("blockers"), f"{location}.blockers", errors)
    return status if status in CONTROL_PLANE_STATUSES else None


def validate_application_types(
    value: Any,
    slots: Any,
    disposition: Any,
    location: str,
    errors: list[str],
    warnings: list[str],
    *,
    receiver_mode: str | None = None,
    control_plane_status: str | None = None,
) -> list[str]:
    review_reasons: list[str] = []
    if not isinstance(value, dict):
        errors.append(f"{location}.application_types must be an object")
        return review_reasons
    declared_slots = set(slots) if isinstance(slots, list) else set()
    extra_slots = sorted(set(value) - declared_slots)
    if extra_slots:
        errors.append(
            f"{location}.application_types contains undeclared slots: {', '.join(extra_slots)}"
        )

    for slot in slots if isinstance(slots, list) else []:
        descriptor = value.get(slot)
        descriptor_location = f"{location}.application_types.{slot}"
        if descriptor is None:
            if disposition == "blocked":
                warnings.append(f"{descriptor_location} remains unresolved")
            else:
                errors.append(f"{location}.application_types is missing slot {slot}")
            continue
        if not isinstance(descriptor, dict):
            errors.append(f"{descriptor_location} must be an object")
            continue
        if descriptor.get("value") not in APPLICATION_TYPES:
            errors.append(
                f"{descriptor_location}.value must be a supported RUM application type"
            )
        if descriptor.get("source") not in APPLICATION_TYPE_SOURCES:
            errors.append(
                f"{descriptor_location}.source must be user, ai_api, or repository"
            )
        if descriptor.get("confidence") not in {"high", "medium", "low"}:
            errors.append(f"{descriptor_location}.confidence must be high, medium, or low")
        verification = descriptor.get("verification")
        api_value = descriptor.get("api_value")
        if verification not in APPLICATION_TYPE_VERIFICATIONS:
            errors.append(
                f"{descriptor_location}.verification must be matched, mismatched, "
                "not_applicable, or pending"
            )
        if api_value is not None and api_value not in APPLICATION_TYPES:
            errors.append(
                f"{descriptor_location}.api_value must be null or a supported RUM application type"
            )
        if receiver_mode == "datakit":
            if verification != "not_applicable" or api_value is not None:
                errors.append(
                    f"{descriptor_location} must use verification=not_applicable and "
                    "api_value=null for DataKit"
                )
        elif receiver_mode == "public_dataway":
            if control_plane_status == "catalog_resolved":
                if verification not in {"pending", "matched", "mismatched"}:
                    errors.append(
                        f"{descriptor_location}.verification must be pending, matched, "
                        "or mismatched before control-plane resolution"
                    )
            elif control_plane_status == "resolved":
                if verification not in {"matched", "mismatched"}:
                    errors.append(
                        f"{descriptor_location}.verification must be matched or mismatched "
                        "when control_plane.status=resolved"
                    )
                if api_value not in APPLICATION_TYPES:
                    errors.append(
                        f"{descriptor_location}.api_value is required when "
                        "control_plane.status=resolved"
                    )
            if verification == "matched" and api_value != descriptor.get("value"):
                errors.append(
                    f"{descriptor_location}.verification=matched requires api_value "
                    "to equal value"
                )
            if verification == "mismatched":
                if api_value == descriptor.get("value") or api_value not in APPLICATION_TYPES:
                    errors.append(
                        f"{descriptor_location}.verification=mismatched requires a "
                        "different supported api_value"
                    )
                else:
                    review_reasons.append(
                        f"{descriptor_location}: user application type differs from AI API"
                    )
    return review_reasons


def validate_platform_application_types(
    target: dict[str, Any],
    disposition: Any,
    location: str,
    errors: list[str],
) -> None:
    if disposition == "blocked":
        return
    platform = target.get("platform")
    variants = target.get("variants")
    application_types = target.get("application_types")
    slots = target.get("application_id_slots")
    if (
        platform != "apple"
        or not isinstance(variants, list)
        or not isinstance(application_types, dict)
        or not isinstance(slots, list)
    ):
        return

    for slot in slots:
        if not isinstance(slot, str):
            continue
        lowered = slot.lower()
        expected_type = None
        if (
            lowered == "macos"
            or lowered.startswith("macos-")
            or ("macos" in variants and len(variants) == 1)
        ):
            expected_type = "custom"
        elif (
            lowered in {"ios", "tvos"}
            or lowered.startswith("ios-")
            or lowered.startswith("tvos-")
        ):
            expected_type = "ios"
        if expected_type is None:
            continue
        descriptor = application_types.get(slot)
        actual_type = descriptor.get("value") if isinstance(descriptor, dict) else None
        if actual_type is not None and actual_type != expected_type:
            errors.append(
                f"{location}.application_types.{slot}.value must be {expected_type} "
                "for the declared Apple variant"
            )


def validate_planned_file(value: Any, location: str, errors: list[str]) -> None:
    if not is_nonempty_string(value):
        errors.append(f"{location} must be a non-empty repository-relative path")
        return
    if "\\" in value:
        errors.append(f"{location} must use repository-relative POSIX separators")
        return

    path = PurePosixPath(value)
    if path.as_posix() != value:
        errors.append(f"{location} must use a canonical repository-relative path")
    if path.is_absolute() or value == "." or ".." in path.parts:
        errors.append(f"{location} must stay within the repository")
    if any(part.lower() in GENERATED_PATH_PARTS for part in path.parts):
        errors.append(f"{location} must not point into a generated or dependency directory")
    if any(part.lower() in FORBIDDEN_PLANNED_PATH_PARTS for part in path.parts):
        errors.append(f"{location} must not point into a repository control directory")
    lowered_parts = tuple(part.lower() for part in path.parts)
    if any(
        lowered_parts[: len(prefix)] == prefix
        for prefix in FORBIDDEN_PLANNED_PATH_PREFIXES
    ):
        errors.append(f"{location} must not point into an Agent Skill control directory")


def validate_dependency_decision(
    value: Any,
    location: str,
    errors: list[str],
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{location} must be an object")
        return
    action = value.get("action")
    if action not in DEPENDENCY_ACTIONS:
        errors.append(
            f"{location}.action must be preserve, add, upgrade, remove, none, or blocked"
        )
        return
    if action not in {"preserve", "add", "upgrade"}:
        return
    for field in ("package", "owner", "version", "compatibility"):
        if not is_nonempty_string(value.get(field)):
            errors.append(f"{location}.{field} must be a non-empty string")
    sources = value.get("official_sources")
    if not isinstance(sources, list) or not sources:
        errors.append(f"{location}.official_sources must be a non-empty array")
    else:
        for source in sources:
            parsed = urlsplit(source) if is_nonempty_string(source) else None
            if (
                parsed is None
                or parsed.scheme != "https"
                or not parsed.netloc
                or parsed.username
                or parsed.password
            ):
                errors.append(
                    f"{location}.official_sources must contain only HTTPS URLs"
                )
                break
    verified_at = value.get("verified_at")
    try:
        verified_date = date.fromisoformat(verified_at)
    except (TypeError, ValueError):
        errors.append(f"{location}.verified_at must be an ISO date")
    else:
        if verified_date > date.today():
            errors.append(f"{location}.verified_at must not be in the future")


def validate_planned_changes(
    value: Any,
    target_ids: set[str],
    planned_target_ids: set[str],
    errors: list[str],
) -> None:
    if not isinstance(value, list):
        errors.append("planned_changes must be an array")
        return
    if planned_target_ids and not value:
        errors.append("planned_changes must not be empty when targets have disposition=planned")
        return

    covered_targets: set[str] = set()
    used_orders: set[int] = set()
    file_receipts: dict[str, tuple[Any, Any]] = {}
    for index, change in enumerate(value):
        location = f"planned_changes[{index}]"
        if not isinstance(change, dict):
            errors.append(f"{location} must be an object")
            continue

        target_id = change.get("target_id")
        if not is_nonempty_string(target_id):
            errors.append(f"{location}.target_id must be a non-empty string")
        elif target_id not in target_ids:
            errors.append(f"{location}.target_id references an unknown target_id")
        elif target_id not in planned_target_ids:
            errors.append(f"{location}.target_id must reference a target with disposition=planned")
        else:
            covered_targets.add(target_id)

        validate_planned_file(change.get("file"), f"{location}.file", errors)
        before = change.get("before_sha256")
        prepared = change.get("prepared_sha256")
        if "before_sha256" in change and not (
            before == "missing" or isinstance(before, str) and SHA256_PATTERN.fullmatch(before)
        ):
            errors.append(f"{location}.before_sha256 must be a SHA-256 digest or missing")
        if "prepared_sha256" in change and (
            not isinstance(prepared, str) or not SHA256_PATTERN.fullmatch(prepared)
            or before is None or before == prepared
        ):
            errors.append(f"{location}.prepared_sha256 requires a distinct result digest and before_sha256")
        filename = change.get("file")
        if isinstance(filename, str):
            receipt = (before, prepared)
            if filename in file_receipts and file_receipts[filename] != receipt:
                errors.append(f"{location}: changes to one file must share its before/prepared digests")
            file_receipts[filename] = receipt
        order = change.get("order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 1:
            errors.append(f"{location}.order must be a positive integer")
        elif order in used_orders:
            errors.append(f"{location}.order duplicates {order}")
        else:
            used_orders.add(order)

        for field in ("purpose", "risk", "rollback"):
            if not is_nonempty_string(change.get(field)):
                errors.append(f"{location}.{field} must be a non-empty string")
        validate_nonempty_string_list(change.get("edits"), f"{location}.edits", errors)
        validate_nonempty_string_list(change.get("validation"), f"{location}.validation", errors)

        validate_dependency_decision(
            change.get("dependency_decision"),
            f"{location}.dependency_decision",
            errors,
        )

    for target_id in sorted(planned_target_ids - covered_targets):
        errors.append(f"target {target_id} has no planned change")


def plan_review_digest(plan: Any) -> str:
    """Bind a review receipt to one exact substantive plan revision."""
    canonical = copy.deepcopy(plan)
    approval = canonical.get("approval")
    revision = approval.get("revision") if isinstance(approval, dict) else None
    reviewed_overlaps = (
        approval.get("reviewed_overlaps", []) if isinstance(approval, dict) else []
    )
    canonical["approval"] = {
        "revision": revision,
        "reviewed_overlaps": reviewed_overlaps,
    }
    for batch in canonical.get("batches", []):
        receipt = batch.get("approval", {})
        batch["approval"] = {"revision": receipt.get("revision"), "reviewed_overlaps": receipt.get("reviewed_overlaps", [])}
    payload = json.dumps(
        canonical,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def validate_revision_review(
    plan: dict[str, Any],
    approval: dict[str, Any],
    errors: list[str],
) -> None:
    location = "approval"
    reviewed_digest = approval.get("reviewed_plan_sha256")
    if not is_nonempty_string(reviewed_digest) or not SHA256_PATTERN.fullmatch(
        reviewed_digest
    ):
        errors.append(
            f"{location}.reviewed_plan_sha256 must be a sha256:<64 lowercase hex> digest"
        )
    elif reviewed_digest != plan_review_digest(plan):
        errors.append(
            f"{location}.reviewed_plan_sha256 does not match this plan revision"
        )
    overlaps = approval.get("reviewed_overlaps")
    if not isinstance(overlaps, list):
        errors.append(f"{location}.reviewed_overlaps must be an array")
        return
    planned_files = {
        change.get("file")
        for change in plan.get("planned_changes", [])
        if isinstance(change, dict) and is_nonempty_string(change.get("file"))
    }
    seen: set[str] = set()
    for index, overlap in enumerate(overlaps):
        overlap_location = f"{location}.reviewed_overlaps[{index}]"
        if not isinstance(overlap, dict) or set(overlap) != {"file", "sha256"}:
            errors.append(
                f"{overlap_location} must contain only file and sha256"
            )
            continue
        file_name = overlap.get("file")
        validate_planned_file(file_name, f"{overlap_location}.file", errors)
        if is_nonempty_string(file_name):
            if file_name in seen:
                errors.append(f"{overlap_location}.file is duplicated")
            elif file_name not in planned_files:
                errors.append(
                    f"{overlap_location}.file must identify a planned change"
                )
            seen.add(file_name)
        digest = overlap.get("sha256")
        if not is_nonempty_string(digest) or not SHA256_PATTERN.fullmatch(digest):
            errors.append(
                f"{overlap_location}.sha256 must be a sha256:<64 lowercase hex> digest"
            )


def _validate_plan_legacy(plan: Any, phase: str, *, modern: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(plan, dict):
        return ["plan must be a JSON object"], warnings
    if plan.get("schema_version") != 2:
        errors.append("schema_version must be 2")

    repository = plan.get("repository")
    if not isinstance(repository, dict):
        errors.append("repository must be an object")
    else:
        for field in ("root", "commit"):
            if not is_nonempty_string(repository.get(field)):
                errors.append(f"repository.{field} must be a non-empty string")
        if not isinstance(repository.get("initial_status"), list):
            errors.append("repository.initial_status must be an array")

    request = plan.get("request")
    receiver: Any = None
    receiver_mode: str | None = None
    datakit_readiness_status: str | None = None
    receiver_client_tokens: dict[str, Any] = {}
    receiver_client_token_sinks: set[tuple[str, str, str]] = set()
    external_client_token_sink = False
    control_plane_status: str | None = None
    control_plane_catalog: str | None = None
    control_plane_tls_verification: str | None = None
    application_id_kind: str | None = None
    scalar_application_id: tuple[str, str] | None = None
    request_intent: str | None = None
    if not isinstance(request, dict):
        errors.append("request must be an object")
    else:
        if request.get("intent") not in PLAN_ONLY_INTENTS | IMPLEMENTATION_INTENTS:
            errors.append("request.intent must be audit, plan, implement, validate, or repair")
        else:
            request_intent = request["intent"]
        receiver = request.get("receiver")
        raw_request_fields = sorted(
            {
                "datawayUrl",
                "datakitUrl",
                "clientToken",
                "temporaryAuthCode",
                "applicationType",
                "appId",
            }
            & set(request)
        )
        if raw_request_fields:
            errors.append(
                "request must normalize raw prompt fields into receiver and targets: "
                + ", ".join(raw_request_fields)
            )
        application_id_kind, scalar_application_id = validate_application_id_input(
            request.get("application_id_input"),
            errors,
        )

    if not isinstance(receiver, dict):
        errors.append("request.receiver must be an object")
    else:
        mode = receiver.get("mode")
        receiver_mode = mode if mode in RECEIVER_MODES else None
        if mode not in RECEIVER_MODES:
            errors.append("request.receiver.mode must be public_dataway or datakit")
        validate_source(receiver.get("endpoint"), "request.receiver.endpoint", errors, allow_literal=True)
        validate_http_origin(
            receiver.get("endpoint"),
            "request.receiver.endpoint",
            errors,
        )
        if mode == "public_dataway":
            client_tokens = receiver.get("client_tokens")
            if client_tokens is None:
                client_tokens = {}
            elif not isinstance(client_tokens, dict):
                errors.append("request.receiver.client_tokens must be an object")
                client_tokens = {}
            receiver_client_tokens = client_tokens
            for slot, client_token in client_tokens.items():
                location = f"request.receiver.client_tokens.{slot}"
                if not is_nonempty_string(slot):
                    errors.append(
                        "request.receiver.client_tokens keys must be non-empty strings"
                    )
                    continue
                validate_source(client_token, location, errors, allow_literal=False)
                source = client_token.get("source") if isinstance(client_token, dict) else None
                if is_nonempty_string(source) and not is_valid_reference(
                    source,
                    client_token=True,
                ):
                    errors.append(
                        f"{location}.source must be a structured env, existing, or runtime reference"
                    )
                if isinstance(client_token, dict) and "value" in client_token:
                    errors.append(f"{location} must never contain a value")
                availability = (
                    client_token.get("availability")
                    if isinstance(client_token, dict)
                    else None
                )
                if availability not in CLIENT_TOKEN_AVAILABILITY:
                    errors.append(
                        f"{location}.availability must be planned, existing, or persisted"
                    )
                sink = (
                    client_token.get("sink")
                    if isinstance(client_token, dict)
                    else None
                )
                sink_identity = validate_client_token_sink(
                    sink,
                    f"{location}.sink",
                    client_token,
                    errors,
                )
                if sink_identity is not None:
                    receiver_client_token_sinks.add(sink_identity)
                    external_client_token_sink = (
                        external_client_token_sink
                        or sink_identity[2] == "external"
                    )
            if "client_token" in receiver:
                errors.append(
                    "request.receiver.client_token is obsolete; use slot-keyed client_tokens"
                )
            control_plane_status = validate_control_plane(
                receiver.get("control_plane"),
                errors,
            )
            control_plane = receiver.get("control_plane")
            if isinstance(control_plane, dict):
                control_plane_catalog = control_plane.get("catalog")
                control_plane_tls_verification = control_plane.get(
                    "tls_verification",
                    "verified",
                )
        elif "client_token" in receiver or "client_tokens" in receiver:
            errors.append(
                "request.receiver.client_tokens is valid only for public_dataway"
            )
        if mode == "datakit" and "control_plane" in receiver:
            errors.append("request.receiver.control_plane is valid only for public_dataway")
        if mode == "datakit" and "readiness" in receiver:
            datakit_readiness_status = validate_datakit_readiness(
                receiver.get("readiness"),
                "request.receiver.readiness",
                errors,
            )
        elif mode == "datakit":
            datakit_readiness_status = "unknown"
            warnings.append(
                "DataKit readiness is not recorded; local implementation may proceed, "
                "but remote ingestion remains unverified"
            )
        elif "readiness" in receiver:
            errors.append("request.receiver.readiness is valid only for datakit")
        if len(receiver_client_token_sinks) > 1 and not modern:
            errors.append(
                "request.receiver.client_tokens must use one shared sink path, "
                "format, and scope"
            )

        forbidden_input_fields = {
            "datawayUrl",
            "datakitUrl",
            "clientToken",
            "temporaryAuthCode",
            "applicationType",
            "appId",
        }
        present = sorted(forbidden_input_fields & set(receiver))
        if present:
            errors.append(
                "request.receiver must use normalized fields; found raw prompt fields: " + ", ".join(present)
            )

    targets = plan.get("targets")
    if not isinstance(targets, list) or not targets:
        errors.append("targets must be a non-empty array")
        targets = []

    target_ids: set[str] = set()
    planned_target_ids: set[str] = set()
    blocked_target_ids: set[str] = set()
    application_id_owners: dict[tuple[str, str], str] = {}
    application_id_slots: list[tuple[str, str, tuple[str, str] | None]] = []
    application_slot_owners: dict[str, str] = {}
    active_receiver_slots: set[str] = set()
    material_review_reasons: list[str] = []
    if external_client_token_sink and not (modern and scope_authorized(plan, "external_sink")):
        material_review_reasons.append("external Client Token sink")
    for index, target in enumerate(targets):
        location = f"targets[{index}]"
        if not isinstance(target, dict):
            errors.append(f"{location} must be an object")
            continue

        target_id = target.get("id")
        if not is_nonempty_string(target_id):
            errors.append(f"{location}.id must be a non-empty string")
        elif target_id in target_ids:
            errors.append(f"{location}.id duplicates {target_id}")
        else:
            target_ids.add(target_id)

        for field in ("path", "platform"):
            if not is_nonempty_string(target.get(field)):
                errors.append(f"{location}.{field} must be a non-empty string")
        for field in ("variants", "evidence", "application_id_slots", "official_sources", "blockers"):
            if not isinstance(target.get(field), list):
                errors.append(f"{location}.{field} must be an array")

        disposition = target.get("disposition")
        if disposition not in TARGET_DISPOSITIONS:
            errors.append(f"{location}.disposition is invalid")
        elif disposition == "planned" and is_nonempty_string(target_id):
            planned_target_ids.add(target_id)
        elif disposition in {"blocked", "failed"} and is_nonempty_string(target_id):
            blocked_target_ids.add(target_id)
        blockers = target.get("blockers")
        if (
            isinstance(blockers, list)
            and blockers
            and is_nonempty_string(target_id)
        ):
            blocked_target_ids.add(target_id)

        slots = target.get("application_id_slots")
        application_ids = target.get("application_ids")
        if not isinstance(application_ids, dict):
            errors.append(f"{location}.application_ids must be an object")
            application_ids = {}
        if isinstance(slots, list):
            if len(slots) != len(set(slot for slot in slots if isinstance(slot, str))):
                errors.append(f"{location}.application_id_slots must not contain duplicates")
            for slot in slots:
                if not is_nonempty_string(slot):
                    errors.append(f"{location}.application_id_slots must contain non-empty strings")
                    continue
                current_slot_owner = target_id or location
                if disposition != "blocked" and slot in application_ids:
                    previous_slot_owner = application_slot_owners.get(slot)
                    if previous_slot_owner and previous_slot_owner != current_slot_owner:
                        errors.append(
                            f"{location}.application_id_slots.{slot} duplicates the repository-wide slot owned by {previous_slot_owner}; use target-specific slot names"
                        )
                    else:
                        application_slot_owners[slot] = current_slot_owner
                if slot not in application_ids:
                    application_id_slots.append((target_id or location, slot, None))
                    if disposition != "blocked":
                        errors.append(f"{location}.application_ids is missing slot {slot}")
                    else:
                        warnings.append(f"{location} remains blocked on Application ID slot {slot}")
                        blockers = target.get("blockers")
                        if not isinstance(blockers, list) or not any(
                            isinstance(blocker, str) and slot in blocker for blocker in blockers
                        ):
                            errors.append(f"{location}.blockers must identify missing slot {slot}")
                    continue
                if disposition != "blocked":
                    active_receiver_slots.add(slot)
                validate_source(
                    application_ids[slot],
                    f"{location}.application_ids.{slot}",
                    errors,
                    allow_literal=True,
                )
                reference = application_ids[slot]
                identity = reference_identity(reference)
                application_id_slots.append((target_id or location, slot, identity))
                if identity:
                    owner = application_id_owners.get(identity)
                    current_owner = f"{target_id or location}:{slot}"
                    if owner:
                        errors.append(
                            f"{location}.application_ids.{slot} reuses the Application ID reference owned by {owner}"
                        )
                    else:
                        application_id_owners[identity] = current_owner
        extra_slots = sorted(set(application_ids) - set(slots if isinstance(slots, list) else []))
        if extra_slots:
            errors.append(f"{location}.application_ids contains undeclared slots: {', '.join(extra_slots)}")
        material_review_reasons.extend(
            validate_application_types(
                target.get("application_types"),
                slots,
                disposition,
                location,
                errors,
                warnings,
                receiver_mode=receiver_mode,
                control_plane_status=control_plane_status,
            )
        )
        validate_platform_application_types(
            target,
            disposition,
            location,
            errors,
        )
        if (
            receiver_mode == "public_dataway"
            and target.get("platform") == "cpp"
            and disposition != "blocked"
        ):
            errors.append(
                f"{location} must be blocked because the current C++ adapter supports only DataKit"
            )

        for field in ("existing_instrumentation", "profile", "receiver_mapping", "privacy", "artifacts"):
            if not isinstance(target.get(field), dict):
                errors.append(f"{location}.{field} must be an object")
        material_review_reasons.extend(
            validate_target_review_scope(target, location, errors, modern=modern)
        )
        if not target.get("evidence"):
            warnings.append(f"{location} has no repository evidence")
        if disposition == "planned" and not target.get("official_sources"):
            warnings.append(f"{location} has no recorded official source")

    if application_id_kind == "scalar" and scalar_application_id:
        scalar_assignments = [
            (target_id, slot)
            for target_id, slot, identity in application_id_slots
            if identity == scalar_application_id
        ]
        unresolved_slots = [
            (target_id, slot)
            for target_id, slot, identity in application_id_slots
            if identity is None or identity == scalar_application_id
        ]
        if len(unresolved_slots) > 1 and scalar_assignments:
            errors.append(
                "request.application_id_input scalar is ambiguous across multiple unresolved Application ID slots; "
                "leave it unassigned and block those targets until target-specific IDs are provided"
            )
        elif len(unresolved_slots) > 1:
            warnings.append(
                "scalar Application ID input remains unassigned because multiple target-specific slots are unresolved"
            )
        elif len(unresolved_slots) == 1 and not scalar_assignments:
            target_id, slot = unresolved_slots[0]
            errors.append(
                f"request.application_id_input scalar must be assigned to the only unresolved slot {target_id}:{slot}"
            )
        elif not unresolved_slots:
            warnings.append("scalar Application ID input is unused because all target slots use existing references")

    if receiver_mode == "public_dataway":
        actual_token_slots = set(receiver_client_tokens)
        if control_plane_status == "blocked":
            if actual_token_slots:
                errors.append(
                    "request.receiver.client_tokens must be omitted while the control plane is blocked"
                )
        elif control_plane_status in {"catalog_resolved", "resolved"}:
            missing_token_slots = sorted(active_receiver_slots - actual_token_slots)
            extra_token_slots = sorted(actual_token_slots - active_receiver_slots)
            if missing_token_slots:
                errors.append(
                    "request.receiver.client_tokens is missing active Application ID slots: "
                    + ", ".join(missing_token_slots)
                )
            if extra_token_slots:
                errors.append(
                    "request.receiver.client_tokens contains unknown or blocked slots: "
                    + ", ".join(extra_token_slots)
                )
            expected_availability = (
                {"planned", "existing"}
                if control_plane_status == "catalog_resolved"
                else {"existing", "persisted"}
            )
            for slot, reference in receiver_client_tokens.items():
                availability = (
                    reference.get("availability")
                    if isinstance(reference, dict)
                    else None
                )
                if availability not in expected_availability:
                    expected = (
                        "planned or existing"
                        if control_plane_status == "catalog_resolved"
                        else "existing or persisted"
                    )
                    errors.append(
                        f"request.receiver.client_tokens.{slot}.availability must be "
                        f"{expected} when control_plane.status={control_plane_status}"
                    )

    planned_changes = plan.get("planned_changes")
    validate_planned_changes(planned_changes, target_ids, planned_target_ids, errors)
    dependency_actions = {
        change.get("dependency_decision", {}).get("action")
        for change in (planned_changes if isinstance(planned_changes, list) else [])
        if isinstance(change, dict)
        and isinstance(change.get("dependency_decision"), dict)
        and not (modern and change["dependency_decision"].get("action") in REVIEW_REQUIRED_DEPENDENCY_ACTIONS and (
            compatible_upgrade(change["dependency_decision"])
            or scope_authorized(change, "dependency")
        ))
    }
    for field in ("validation", "risks", "handoff"):
        if not isinstance(plan.get(field), list):
            errors.append(f"{field} must be an array")

    approval = plan.get("approval")
    if not isinstance(approval, dict):
        errors.append("approval must be an object")
    else:
        status = approval.get("status")
        if status not in {"pending", "approved"}:
            errors.append("approval.status must be pending or approved")
        basis = approval.get("basis")
        if basis not in APPROVAL_BASES:
            errors.append(
                "approval.basis must be plan_only_request, "
                "explicit_implementation_request, or revision_review"
            )
        approval_blockers = approval.get("blockers")
        if not isinstance(approval_blockers, list):
            errors.append("approval.blockers must be an array")
            approval_blockers = []
        elif any(not is_nonempty_string(item) for item in approval_blockers):
            errors.append(
                "approval.blockers must contain only non-empty strings"
            )
        if status == "pending" and basis == "revision_review":
            errors.append(
                "approval.basis=revision_review requires approval.status=approved"
            )
        if status == "approved" and basis == "plan_only_request":
            errors.append(
                "approval.basis=plan_only_request requires approval.status=pending"
            )
        revision = approval.get("revision")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            errors.append("approval.revision must be a positive integer")
        if basis == "revision_review":
            validate_revision_review(plan, approval, errors)
        elif "reviewed_plan_sha256" in approval or "reviewed_overlaps" in approval:
            errors.append(
                "approval.reviewed_plan_sha256 and reviewed_overlaps are valid only "
                "for revision_review"
            )

        if request_intent in PLAN_ONLY_INTENTS:
            if status == "pending" and basis != "plan_only_request":
                errors.append(
                    "a pending plan-only request requires approval.basis=plan_only_request"
                )
            if status == "approved" and basis != "revision_review":
                errors.append(
                    "a plan-only request can be approved only by revision_review"
                )
        elif request_intent in IMPLEMENTATION_INTENTS:
            if basis == "plan_only_request":
                errors.append(
                    "an implementation request cannot use approval.basis=plan_only_request"
                )
            if (
                status == "pending"
                and basis == "explicit_implementation_request"
                and not approval_blockers
            ):
                errors.append(
                    "a pending explicit implementation request must list approval.blockers"
                )

        implementation_blockers: list[str] = []
        if blocked_target_ids:
            implementation_blockers.append(
                "blocked or failed targets: " + ", ".join(sorted(blocked_target_ids))
            )
        if control_plane_status == "blocked":
            implementation_blockers.append("the control plane is blocked")
        if "blocked" in dependency_actions:
            implementation_blockers.append("a dependency decision is blocked")
        if approval_blockers:
            implementation_blockers.append("approval.blockers is not empty")

        if status == "approved" and implementation_blockers:
            errors.append(
                "approval.status cannot be approved while implementation is blocked: "
                + "; ".join(implementation_blockers)
            )

        if basis == "explicit_implementation_request" and status == "approved":
            review_reasons: list[str] = []
            risky_dependency_actions = sorted(
                dependency_actions & REVIEW_REQUIRED_DEPENDENCY_ACTIONS
            )
            if risky_dependency_actions:
                review_reasons.append(
                    "dependency " + "/".join(risky_dependency_actions)
                )
            if control_plane_catalog == TESTING_CONTROL_PLANE_CATALOG and not (modern and scope_authorized(plan, "testing_site")):
                review_reasons.append("testing control-plane override")
            if control_plane_tls_verification == "disabled_for_testing" and not (modern and scope_authorized(plan, "disabled_tls")):
                review_reasons.append("disabled TLS verification")
            review_reasons.extend(sorted(set(material_review_reasons)))
            if review_reasons:
                errors.append(
                    "explicit implementation authorization cannot cover material-risk "
                    "changes; use pending approval with blockers, then revision_review: "
                    + ", ".join(review_reasons)
                )

        if phase == "implement" and status != "approved":
            errors.append("implementation requires approval.status=approved")
        if (
            phase == "implement"
            and receiver_mode == "public_dataway"
            and control_plane_status not in {"catalog_resolved", "resolved"}
        ):
            errors.append(
                "implementation requires a resolved Public DataWay site"
            )
        if (
            phase == "implement"
            and receiver_mode == "datakit"
            and datakit_readiness_status != "verified"
        ):
            warnings.append(
                "DataKit receiver readiness is not verified; complete local "
                "instrumentation and retain collector/reachability checks as handoff"
            )
        if phase == "implement" and implementation_blockers:
            errors.append(
                "implementation cannot start while blockers remain: "
                + "; ".join(implementation_blockers)
            )

    validate_sensitive_values(plan, "", errors)
    return errors, warnings


def _validate_control_plane_state_legacy(
    state: Any,
    plan: dict[str, Any],
    *,
    repository: Path | None = None,
    state_path: Path | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(state, dict):
        return ["control-plane state must be an object"], warnings
    if state.get("schema_version") != 1:
        errors.append("control-plane state schema_version must be 1")
    if state.get("kind") != "rum_control_plane_state":
        errors.append("control-plane state kind must be rum_control_plane_state")
    if state.get("plan_digest") != plan_review_digest(plan):
        errors.append("control-plane state plan_digest does not match this plan")

    receiver = plan.get("request", {}).get("receiver", {})
    control_plane = receiver.get("control_plane", {})
    site = state.get("site")
    if not isinstance(site, dict):
        errors.append("control-plane state site must be an object")
    else:
        expected_ai_api = (
            control_plane.get("ai_api_endpoint", {}).get("value")
            if isinstance(control_plane, dict)
            and isinstance(control_plane.get("ai_api_endpoint"), dict)
            else None
        )
        for state_field, expected in (
            ("catalog", control_plane.get("catalog") if isinstance(control_plane, dict) else None),
            ("code", control_plane.get("site_code") if isinstance(control_plane, dict) else None),
            ("ai_api", expected_ai_api),
        ):
            if site.get(state_field) != expected:
                errors.append(
                    f"control-plane state site.{state_field} does not match the plan"
                )

    network_preflight = state.get("network_preflight")
    if (
        not isinstance(network_preflight, dict)
        or network_preflight.get("status") != "passed"
    ):
        errors.append("control-plane state requires a passed credential-free network preflight")
    else:
        for endpoint in ("dataway", "ai_api"):
            result = network_preflight.get(endpoint)
            if not isinstance(result, dict) or result.get("status") != "reachable":
                errors.append(
                    f"control-plane state network_preflight.{endpoint} must be reachable"
                )

    credential_resolution = state.get("credential_resolution")
    if not isinstance(credential_resolution, dict):
        errors.append("control-plane state credential_resolution must be an object")
    else:
        if credential_resolution.get("status") != "resolved":
            errors.append("control-plane state credential_resolution.status must be resolved")
        if credential_resolution.get("api_key_persistence") != "memory_only":
            errors.append(
                "control-plane state credential_resolution.api_key_persistence must be memory_only"
            )

    expected_tokens = receiver.get("client_tokens")
    expected_slots = set(expected_tokens) if isinstance(expected_tokens, dict) else set()
    state_tokens = state.get("client_tokens")
    if not isinstance(state_tokens, dict):
        errors.append("control-plane state client_tokens must be an object")
        state_tokens = {}
    if set(state_tokens) != expected_slots:
        errors.append("control-plane state client token slots do not match the plan")
    for slot in sorted(expected_slots & set(state_tokens)):
        expected_reference = expected_tokens.get(slot)
        state_reference = state_tokens.get(slot)
        if not isinstance(state_reference, dict):
            errors.append(f"control-plane state client_tokens.{slot} must be an object")
            continue
        if (
            not isinstance(expected_reference, dict)
            or state_reference.get("source") != expected_reference.get("source")
        ):
            errors.append(
                f"control-plane state client_tokens.{slot}.source does not match the plan"
            )
        if state_reference.get("availability") != "persisted":
            errors.append(
                f"control-plane state client_tokens.{slot}.availability must be persisted"
            )

    plan_types: dict[str, dict[str, Any]] = {}
    plan_app_ids: dict[str, str] = {}
    for target in plan.get("targets", []):
        if not isinstance(target, dict) or target.get("disposition") != "planned":
            continue
        application_ids = target.get("application_ids")
        if isinstance(application_ids, dict):
            for slot, descriptor in application_ids.items():
                identity = reference_identity(descriptor)
                if slot not in expected_slots or identity is None:
                    continue
                kind, value = identity
                if kind != "value":
                    errors.append(
                        f"Public DataWay implementation requires a concrete Application ID "
                        f"value in the plan for slot {slot}"
                    )
                elif slot in plan_app_ids and plan_app_ids[slot] != value:
                    errors.append(
                        f"plan contains conflicting Application IDs for slot {slot}"
                    )
                else:
                    plan_app_ids[slot] = value
        application_types = target.get("application_types")
        if not isinstance(application_types, dict):
            continue
        for slot, descriptor in application_types.items():
            if slot in plan_types and plan_types[slot] != descriptor:
                errors.append(
                    f"plan contains conflicting application type descriptors for slot {slot}"
                )
            elif isinstance(descriptor, dict):
                plan_types[slot] = descriptor

    applications = state.get("applications")
    if not isinstance(applications, dict):
        errors.append("control-plane state applications must be an object")
        applications = {}
    if set(applications) != expected_slots:
        errors.append("control-plane state application slots do not match the plan")
    approval = plan.get("approval")
    revision_reviewed = (
        isinstance(approval, dict)
        and approval.get("basis") == "revision_review"
        and approval.get("status") == "approved"
    )
    for slot in sorted(expected_slots & set(applications)):
        application = applications.get(slot)
        if not isinstance(application, dict):
            errors.append(f"control-plane state applications.{slot} must be an object")
            continue
        if application.get("token_expired") is not False:
            errors.append(
                f"control-plane state applications.{slot}.token_expired must be false"
            )
        if application.get("client_token_available") is not True:
            errors.append(
                f"control-plane state applications.{slot}.client_token_available must be true"
            )
        expected_app_id = plan_app_ids.get(slot)
        if expected_app_id is not None and application.get("app_id") != expected_app_id:
            errors.append(
                f"control-plane state applications.{slot}.app_id does not match the plan"
            )
        api_type = application.get("api_app_type")
        if api_type not in APPLICATION_TYPES:
            errors.append(
                f"control-plane state applications.{slot}.api_app_type is unsupported"
            )
            continue
        descriptor = plan_types.get(slot)
        if not isinstance(descriptor, dict):
            errors.append(
                f"control-plane state applications.{slot} has no planned application type"
            )
            continue
        planned_type = descriptor.get("value")
        expected_selected_source = (
            "user" if descriptor.get("source") == "user" else "ai_api"
        )
        if application.get("selected_app_type") != planned_type:
            errors.append(
                f"control-plane state applications.{slot}.selected_app_type "
                "does not match the plan"
            )
        if application.get("selected_app_type_source") != expected_selected_source:
            errors.append(
                f"control-plane state applications.{slot}.selected_app_type_source "
                "does not match the plan"
            )
        expected_mismatch = bool(
            descriptor.get("source") == "user" and api_type != planned_type
        )
        if application.get("type_mismatch") is not expected_mismatch:
            errors.append(
                f"control-plane state applications.{slot}.type_mismatch is inconsistent"
            )
        if api_type == planned_type:
            continue
        accepted_mismatch = (
            descriptor.get("source") == "user"
            and descriptor.get("verification") == "mismatched"
            and descriptor.get("api_value") == api_type
            and revision_reviewed
        )
        if not accepted_mismatch:
            errors.append(
                f"control-plane state applications.{slot}.api_app_type differs from "
                "the planned application type; revise and review the plan"
            )

    secret_sink = state.get("secret_sink")
    planned_sinks = [
        reference.get("sink")
        for reference in expected_tokens.values()
        if isinstance(reference, dict) and isinstance(reference.get("sink"), dict)
    ]
    planned_sink = planned_sinks[0] if planned_sinks else None
    if not isinstance(secret_sink, dict):
        errors.append("control-plane state secret_sink must be an object")
    else:
        sink_format = secret_sink.get("format")
        if sink_format not in {"dotenv", "json", "properties", "xcconfig"}:
            errors.append(
                "control-plane state secret_sink.format must be dotenv, json, "
                "properties, or xcconfig"
            )
        elif not isinstance(planned_sink, dict) or sink_format != planned_sink.get(
            "format"
        ):
            errors.append(
                "control-plane state secret_sink.format does not match the plan"
            )
        sink_scope = secret_sink.get("scope")
        if sink_scope not in {"repository", "external"}:
            errors.append(
                "control-plane state secret_sink.scope must be repository or external"
            )
        elif not isinstance(planned_sink, dict) or sink_scope != planned_sink.get(
            "scope"
        ):
            errors.append(
                "control-plane state secret_sink.scope does not match the plan"
            )
        sink_keys = secret_sink.get("keys")
        if not isinstance(sink_keys, dict) or set(sink_keys) != expected_slots:
            errors.append(
                "control-plane state secret_sink.keys must match the plan's Client Token slots"
            )
            sink_keys = {}
        for slot in sorted(expected_slots & set(sink_keys)):
            key = sink_keys.get(slot)
            expected_reference = expected_tokens.get(slot)
            expected_key = _client_token_reference_key(expected_reference)
            planned_slot_sink = (
                expected_reference.get("sink")
                if isinstance(expected_reference, dict)
                else None
            )
            if key != expected_key:
                errors.append(
                    f"control-plane state secret_sink.keys.{slot} does not match "
                    "the plan's Client Token reference"
                )
            if (
                isinstance(planned_slot_sink, dict)
                and key != planned_slot_sink.get("key")
            ):
                errors.append(
                    f"control-plane state secret_sink.keys.{slot} does not match "
                    "the planned sink key"
                )

        sink_path_value = secret_sink.get("path")
        if not is_nonempty_string(sink_path_value):
            errors.append("control-plane state secret_sink.path must be a non-empty string")
        elif (
            isinstance(planned_sink, dict)
            and planned_sink.get("scope") == "external"
            and sink_path_value != planned_sink.get("path")
        ):
            errors.append(
                "control-plane state secret_sink.path does not match the plan"
            )
        elif repository is not None:
            repository_root = repository.resolve()
            sink_path = Path(sink_path_value)
            if not sink_path.is_absolute():
                errors.append("control-plane state secret_sink.path must be absolute")
            elif sink_path.is_symlink() or not sink_path.is_file():
                errors.append(
                    "control-plane state secret_sink.path must be an existing regular non-symlink file"
                )
            else:
                resolved_sink = sink_path.resolve()
                inside_repository = (
                    resolved_sink == repository_root
                    or repository_root in resolved_sink.parents
                )
                actual_scope = "repository" if inside_repository else "external"
                if sink_scope != actual_scope:
                    errors.append(
                        "control-plane state secret_sink.scope does not match its path"
                    )
                planned_path = (
                    planned_sink.get("path")
                    if isinstance(planned_sink, dict)
                    else None
                )
                expected_sink_path = (
                    (repository_root / planned_path).resolve()
                    if sink_scope == "repository"
                    and isinstance(planned_path, str)
                    else Path(planned_path).resolve()
                    if isinstance(planned_path, str)
                    else None
                )
                if expected_sink_path is None or resolved_sink != expected_sink_path:
                    errors.append(
                        "control-plane state secret_sink.path does not match the plan"
                    )
                if stat.S_IMODE(resolved_sink.stat().st_mode) != 0o600:
                    errors.append(
                        "control-plane state secret_sink.path must have mode 0600"
                    )
                if inside_repository:
                    relative = resolved_sink.relative_to(repository_root)
                    try:
                        ignored = subprocess.run(
                            [
                                "git",
                                "-C",
                                str(repository_root),
                                "check-ignore",
                                "-q",
                                "--",
                                str(relative),
                            ],
                            check=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        ).returncode == 0
                    except OSError:
                        ignored = False
                    if not ignored:
                        errors.append(
                            "control-plane state secret_sink.path must be Git-ignored"
                        )
                elif not revision_reviewed and not (plan.get("schema_version") == 3 and scope_authorized(plan, "external_sink")):
                    errors.append(
                        "an external Client Token sink requires revision_review"
                    )
                if state_path is not None:
                    resolved_state = state_path.resolve()
                    if resolved_sink == resolved_state:
                        errors.append(
                            "control-plane state file and Client Token sink must differ"
                        )

    if repository is not None and state_path is not None:
        repository_root = repository.resolve()
        if state_path.is_symlink() or not state_path.is_file():
            errors.append(
                "control-plane execution state must be an existing regular non-symlink file"
            )
        else:
            resolved_state = state_path.resolve()
            if repository_root in resolved_state.parents:
                relative = resolved_state.relative_to(repository_root)
                try:
                    ignored = subprocess.run(
                        [
                            "git",
                            "-C",
                            str(repository_root),
                            "check-ignore",
                            "-q",
                            "--",
                            str(relative),
                        ],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    ).returncode == 0
                except OSError:
                    ignored = False
                if not ignored:
                    errors.append(
                        "control-plane execution state inside the repository must be Git-ignored"
                    )

    validate_sensitive_values(state, "control_plane_state", errors)
    return errors, warnings


def validate_inventory(inventory: Any) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(inventory, dict):
        return ["instrumentation inventory must be a JSON object"], warnings
    if inventory.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    revision = inventory.get("generated_from_plan_revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        errors.append("generated_from_plan_revision must be a positive integer")
    repository = inventory.get("repository")
    if not isinstance(repository, dict):
        errors.append("repository must be an object")
    else:
        for field in ("root", "commit"):
            if not is_nonempty_string(repository.get(field)):
                errors.append(f"repository.{field} must be a non-empty string")

    receiver = inventory.get("receiver")
    receiver_mode: str | None = None
    datakit_readiness_status: str | None = None
    client_tokens: dict[str, Any] = {}
    if not isinstance(receiver, dict):
        errors.append("receiver must be an object")
    else:
        mode = receiver.get("mode")
        if mode not in RECEIVER_MODES:
            errors.append("receiver.mode must be public_dataway or datakit")
        else:
            receiver_mode = mode
        validate_source(receiver.get("endpoint"), "receiver.endpoint", errors, allow_literal=True)
        validate_http_origin(receiver.get("endpoint"), "receiver.endpoint", errors)
        raw_tokens = receiver.get("client_tokens")
        if mode == "public_dataway":
            if not isinstance(raw_tokens, dict):
                errors.append("receiver.client_tokens must be an object")
            else:
                client_tokens = raw_tokens
                for slot, reference in raw_tokens.items():
                    location = f"receiver.client_tokens.{slot}"
                    if not is_nonempty_string(slot):
                        errors.append("receiver.client_tokens keys must be non-empty strings")
                        continue
                    validate_source(reference, location, errors, allow_literal=False)
                    source = reference.get("source") if isinstance(reference, dict) else None
                    if is_nonempty_string(source) and not is_valid_reference(
                        source,
                        client_token=True,
                    ):
                        errors.append(
                            f"{location}.source must be a structured env, existing, or runtime reference"
                        )
                    availability = (
                        reference.get("availability")
                        if isinstance(reference, dict)
                        else None
                    )
                    if availability not in {"existing", "persisted"}:
                        errors.append(
                            f"{location}.availability must be existing or persisted"
                        )
        elif raw_tokens is not None:
            errors.append("receiver.client_tokens is valid only for public_dataway")
        if mode == "datakit" and "readiness" in receiver:
            datakit_readiness_status = validate_datakit_readiness(
                receiver.get("readiness"),
                "receiver.readiness",
                errors,
            )
            if datakit_readiness_status != "verified":
                warnings.append(
                    "receiver.readiness is not verified; remote ingestion must remain unverified"
                )
        elif mode == "datakit":
            datakit_readiness_status = "unknown"
            warnings.append(
                "receiver.readiness is not recorded; remote ingestion must remain unverified"
            )
        elif "readiness" in receiver:
            errors.append("receiver.readiness is valid only for datakit")

    targets = inventory.get("targets")
    if not isinstance(targets, list) or not targets:
        errors.append("targets must be a non-empty array")
        targets = []
    target_ids: set[str] = set()
    active_slots: set[str] = set()
    slot_owners: dict[str, str] = {}
    application_id_owners: dict[tuple[str, str], str] = {}
    for index, target in enumerate(targets):
        location = f"targets[{index}]"
        if not isinstance(target, dict):
            errors.append(f"{location} must be an object")
            continue
        target_id = target.get("id")
        if not is_nonempty_string(target_id):
            errors.append(f"{location}.id must be a non-empty string")
            target_id = location
        elif target_id in target_ids:
            errors.append(f"{location}.id duplicates {target_id}")
        else:
            target_ids.add(target_id)
        for field in ("path", "platform"):
            if not is_nonempty_string(target.get(field)):
                errors.append(f"{location}.{field} must be a non-empty string")
        variants = target.get("variants")
        if not isinstance(variants, list):
            errors.append(f"{location}.variants must be an array")
        evidence = target.get("evidence")
        if not isinstance(evidence, list):
            errors.append(f"{location}.evidence must be an array")
            evidence = []
        elif any(not is_nonempty_string(item) for item in evidence):
            errors.append(f"{location}.evidence must contain only non-empty strings")
        disposition = target.get("disposition")
        if disposition not in FINAL_TARGET_DISPOSITIONS:
            errors.append(f"{location}.disposition is invalid for a final inventory")
        if (
            receiver_mode == "public_dataway"
            and target.get("platform") == "cpp"
            and disposition in {"existing", "instrumented"}
        ):
            errors.append(
                f"{location} cannot use Public DataWay because the current C++ adapter supports only DataKit"
            )
        slots = target.get("application_id_slots", [])
        if not isinstance(slots, list):
            errors.append(f"{location}.application_id_slots must be an array")
            slots = []
        elif len(slots) != len(set(slot for slot in slots if isinstance(slot, str))):
            errors.append(f"{location}.application_id_slots must not contain duplicates")
        application_ids = target.get("application_ids", {})
        if not isinstance(application_ids, dict):
            errors.append(f"{location}.application_ids must be an object")
            application_ids = {}
        for slot in slots:
            if not is_nonempty_string(slot):
                errors.append(f"{location}.application_id_slots must contain non-empty strings")
                continue
            previous_owner = slot_owners.get(slot)
            if previous_owner and previous_owner != target_id:
                errors.append(
                    f"{location}.application_id_slots.{slot} duplicates the repository-wide slot owned by {previous_owner}"
                )
            else:
                slot_owners[slot] = target_id
            if slot in application_ids:
                validate_source(
                    application_ids[slot],
                    f"{location}.application_ids.{slot}",
                    errors,
                    allow_literal=True,
                )
                if disposition in {"existing", "instrumented"}:
                    active_slots.add(slot)
                    identity = reference_identity(application_ids[slot])
                    if identity:
                        owner = application_id_owners.get(identity)
                        current_owner = f"{target_id}:{slot}"
                        if owner:
                            errors.append(
                                f"{location}.application_ids.{slot} reuses the "
                                f"Application ID reference owned by {owner}"
                            )
                        else:
                            application_id_owners[identity] = current_owner
            elif disposition in {"existing", "instrumented"}:
                errors.append(f"{location}.application_ids is missing slot {slot}")
        extra_slots = sorted(set(application_ids) - set(slots))
        if extra_slots:
            errors.append(
                f"{location}.application_ids contains undeclared slots: "
                + ", ".join(extra_slots)
            )
        if disposition in {"existing", "instrumented"}:
            if not evidence:
                errors.append(
                    f"{location}.evidence must not be empty for {disposition} targets"
                )
            validate_application_types(
                target.get("application_types"),
                slots,
                disposition,
                location,
                errors,
                warnings,
                receiver_mode=receiver_mode,
                control_plane_status=(
                    "resolved" if receiver_mode == "public_dataway" else None
                ),
            )
            validate_platform_application_types(
                target,
                disposition,
                location,
                errors,
            )
        elif disposition in {"skipped", "blocked", "failed"}:
            validate_nonempty_string_list(
                target.get("blockers"),
                f"{location}.blockers",
                errors,
            )

    if receiver_mode == "public_dataway":
        missing = sorted(active_slots - set(client_tokens))
        extra = sorted(set(client_tokens) - active_slots)
        if missing:
            errors.append(
                "receiver.client_tokens is missing active Application ID slots: "
                + ", ".join(missing)
            )
        if extra:
            errors.append(
                "receiver.client_tokens contains unknown or inactive slots: "
                + ", ".join(extra)
            )

    validate_nonempty_string_list(inventory.get("validation"), "validation", errors)
    for field in ("artifacts", "handoff"):
        if not isinstance(inventory.get(field), list):
            errors.append(f"{field} must be an array")
    remote = inventory.get("remote_verification")
    if not isinstance(remote, dict):
        errors.append("remote_verification must be an object")
    else:
        if not isinstance(remote.get("verified"), bool):
            errors.append("remote_verification.verified must be a boolean")
        evidence = remote.get("evidence")
        if not isinstance(evidence, list):
            errors.append("remote_verification.evidence must be an array")
        elif any(not is_nonempty_string(item) for item in evidence):
            errors.append(
                "remote_verification.evidence must contain only non-empty strings"
            )
        elif remote.get("verified") is True and not evidence:
            errors.append(
                "remote_verification.evidence must not be empty when verified=true"
            )
        if (
            mode == "datakit"
            and datakit_readiness_status != "verified"
            and remote.get("verified") is True
        ):
            errors.append(
                "remote_verification.verified cannot be true while DataKit readiness "
                "is not verified"
            )

    validate_sensitive_values(inventory, "", errors)
    return errors, warnings


def _git_output(repository: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError:
        raise ValueError("git is required for implementation validation") from None
    if result.returncode != 0:
        raise ValueError("repository Git state could not be verified")
    return result.stdout.rstrip("\r\n")


def _status_path(line: str) -> str:
    value = line[3:] if len(line) > 3 else ""
    if " -> " in value:
        value = value.rsplit(" -> ", 1)[1]
    if value.startswith('"') and value.endswith('"'):
        try:
            decoded = ast.literal_eval(value)
            if isinstance(decoded, str):
                try:
                    return decoded.encode("latin-1").decode("utf-8")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    return decoded
        except (SyntaxError, ValueError):
            pass
    return value.strip('"')


def _git_status_paths(repository: Path) -> set[str]:
    payload = _git_output(
        repository,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    )
    entries = payload.split("\0")
    paths: set[str] = set()
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        if len(entry) < 4:
            raise ValueError("repository Git status returned an invalid entry")
        status = entry[:2]
        path = entry[3:]
        if path:
            paths.add(path)
        if "R" in status or "C" in status:
            index += 1
    return paths


def _hunk_range(start: str, count: str) -> tuple[int, int]:
    """Use zero-based half-open lines, or a point at a zero-length hunk's gap."""
    size = int(count) if count else 1
    begin = int(start) - 1 if size else int(start)
    return begin, begin + size


def _hunks_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    a, b = left
    c, d = right
    if a == b and c == d:
        return a == c
    if a == b:
        return c < a < d
    if c == d:
        return a < c < b
    return a < d and c < b


def nonoverlapping_dirty_edit(plan: dict[str, Any], filename: str, repository: Path) -> bool:
    """Check an exact proposed patch against current bytes and HEAD-to-worktree hunks."""
    changes = [c for c in plan.get("planned_changes", []) if c.get("file") == filename]
    proofs = [c.get("dirty_patch") for c in changes]
    if not proofs or any(not isinstance(p, dict) for p in proofs):
        return False
    try:
        current = (repository / filename).read_bytes()
        digest = "sha256:" + hashlib.sha256(current).hexdigest()
        user_diff = subprocess.run(
            ["git", "-C", str(repository), "diff", "HEAD", "--no-ext-diff", "--unified=0", "--", filename],
            capture_output=True, check=True,
        ).stdout.decode("utf-8")
        tracked = subprocess.run(["git", "-C", str(repository), "cat-file", "-e", f"HEAD:{filename}"], capture_output=True).returncode == 0
        if not tracked or not user_diff or "Binary files" in user_diff or "rename from" in user_diff:
            return False
        pattern = r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"
        user_ranges = [_hunk_range(m[2], m[3]) for m in re.findall(pattern, user_diff, re.M)]
        for proof in proofs:
            patch = proof.get("patch")
            if proof.get("sha256") != digest or not isinstance(patch, str):
                return False
            numstat = subprocess.run(["git", "-C", str(repository), "apply", "--numstat", "-z", "-"], input=patch.encode(), capture_output=True)
            fields = numstat.stdout.rstrip(b"\0").split(b"\t")
            if numstat.returncode or len(fields) != 3 or fields[2].decode() != filename:
                return False
            hunks = re.findall(pattern, patch, re.M)
            planned = [_hunk_range(m[0], m[1]) for m in hunks]
            if not planned or any(_hunks_overlap(p, u) for p in planned for u in user_ranges):
                return False
            # Git may relocate a valid hunk onto user edits outside its declared
            # range. Require exact positions; C locale keeps diagnostics stable.
            check = subprocess.run(
                ["git", "-C", str(repository), "apply", "--check", "--verbose", "--unidiff-zero", "-"],
                input=patch.encode(), capture_output=True, env={**os.environ, "LC_ALL": "C"},
            )
            if check.returncode:
                return False
            # Git reports a +1 offset for a correctly positioned pure deletion
            # because its new-side zero-length header names the preceding gap.
            # Compare actual positions to old-side coordinates plus prior edits.
            positions, delta = [], 0
            for old_start, old_count, _, new_count in hunks:
                positions.append(_hunk_range(old_start, old_count)[0] + 1 + delta)
                delta += int(new_count or 1) - int(old_count or 1)
            for number, position in re.findall(rb"^Hunk #(\d+) succeeded at (\d+) .*\(offset ", check.stderr, re.M):
                if int(number) > len(positions) or int(position) != positions[int(number) - 1]:
                    return False
        return True
    except (OSError, UnicodeError, subprocess.CalledProcessError):
        return False


def file_digest(path: Path) -> str:
    """Fingerprint maintained source without serializing its contents."""
    if not path.exists():
        return "missing"
    if not path.is_file() or path.is_symlink():
        raise ValueError("planned source must be a regular non-symlink file")
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def validate_repository_state(plan: Any, repository: Path) -> list[str]:
    errors: list[str] = []
    resolved_repository = repository.resolve()
    try:
        git_root = Path(
            _git_output(resolved_repository, "rev-parse", "--show-toplevel")
        ).resolve()
    except ValueError as error:
        return [str(error)]
    if git_root != resolved_repository:
        errors.append("--repository must point to the Git worktree root")
        return errors

    repository_contract = plan.get("repository", {}) if isinstance(plan, dict) else {}
    declared_root = repository_contract.get("root")
    if is_nonempty_string(declared_root):
        declared_path = Path(declared_root)
        normalized_root = (
            declared_path.resolve()
            if declared_path.is_absolute()
            else (resolved_repository / declared_path).resolve()
        )
        if normalized_root != resolved_repository:
            errors.append("repository.root does not identify the validated worktree")
    try:
        current_commit = _git_output(resolved_repository, "rev-parse", "HEAD")
    except ValueError as error:
        errors.append(str(error))
        return errors
    if current_commit != repository_contract.get("commit"):
        errors.append("repository.commit no longer matches the validated worktree")

    try:
        dirty_paths = _git_status_paths(resolved_repository)
    except ValueError as error:
        errors.append(str(error))
        return errors
    planned_files = {
        change.get("file")
        for change in plan.get("planned_changes", [])
        if isinstance(change, dict) and is_nonempty_string(change.get("file"))
    }
    for planned_file in sorted(planned_files):
        candidate = resolved_repository / planned_file
        resolved_candidate = candidate.resolve(strict=False)
        traverses_symlink = False
        current = resolved_repository
        for part in PurePosixPath(planned_file).parts:
            current /= part
            if current.is_symlink():
                traverses_symlink = True
                break
        if (
            traverses_symlink
            or resolved_candidate == resolved_repository
            or resolved_repository not in resolved_candidate.parents
        ):
            errors.append(
                f"planned file escapes the repository or traverses a symlink: {planned_file}"
            )
    if errors:
        return errors

    initial_paths = {
        _status_path(line)
        for line in repository_contract.get("initial_status", [])
        if isinstance(line, str) and _status_path(line)
    }
    approval = plan.get("approval", {}) if isinstance(plan, dict) else {}
    if plan.get("schema_version") == 3:
        reviewed_batches = [b for b in plan.get("batches", []) if b.get("approval", {}).get("basis") == "revision_review" and b["approval"].get("status") == "approved"]
        if reviewed_batches:
            approval = {**approval, "basis": "revision_review", "reviewed_overlaps": [o for b in reviewed_batches for o in b["approval"].get("reviewed_overlaps", [])]}
    reviewed_overlaps = {
        overlap.get("file"): overlap.get("sha256")
        for overlap in approval.get("reviewed_overlaps", [])
        if isinstance(overlap, dict)
        and is_nonempty_string(overlap.get("file"))
        and is_nonempty_string(overlap.get("sha256"))
    }
    unreviewed_dirty: list[str] = []
    changed_reviewed: list[str] = []
    changes_by_file = {c["file"]: c for c in plan.get("planned_changes", [])}
    for planned_file in sorted(planned_files):
        change = changes_by_file[planned_file]
        try:
            actual_digest = file_digest(resolved_repository / planned_file)
        except (OSError, ValueError):
            errors.append(f"cannot verify planned source: {planned_file}")
            continue
        before, prepared = change.get("before_sha256"), change.get("prepared_sha256")
        # The expected preparation result is declared BEFORE editing, as part of
        # the authorized plan. Never learn it from whatever happens to be on disk.
        if before is not None and prepared != before and actual_digest == prepared:
            continue
        if before is not None and actual_digest != before:
            errors.append(f"planned file changed after planning or preparation: {planned_file}")
            continue
        if planned_file not in dirty_paths and planned_file not in initial_paths:
            continue
        if planned_file not in initial_paths:
            unreviewed_dirty.append(planned_file)
            continue
        if plan.get("schema_version") == 3 and nonoverlapping_dirty_edit(plan, planned_file, resolved_repository):
            continue
        expected_digest = reviewed_overlaps.get(planned_file)
        if (
            approval.get("basis") != "revision_review"
            or expected_digest is None
        ):
            unreviewed_dirty.append(planned_file)
            continue
        candidate = resolved_repository / planned_file
        if not candidate.is_file() or candidate.is_symlink():
            changed_reviewed.append(planned_file)
            continue
        if actual_digest != expected_digest:
            changed_reviewed.append(planned_file)
    if unreviewed_dirty:
        errors.append(
            "planned files have unreviewed uncommitted changes: "
            + ", ".join(unreviewed_dirty)
        )
    if changed_reviewed:
        errors.append(
            "reviewed planned files changed after approval: "
            + ", ".join(changed_reviewed)
        )

    evidence_paths = {
        evidence
        for target in plan.get("targets", [])
        if isinstance(target, dict)
        for evidence in target.get("evidence", [])
        if is_nonempty_string(evidence)
    }
    changed_evidence = sorted(
        ((dirty_paths - initial_paths) - planned_files) & evidence_paths
    )
    if changed_evidence:
        errors.append(
            "repository evidence changed after planning: " + ", ".join(changed_evidence)
        )
    return errors


def scope_authorized(owner: dict[str, Any], scope: str) -> bool:
    """Receipts record existing user intent; they cannot override failed safety checks."""
    receipts = owner.get("authorizations", {})
    receipt = receipts.get(scope) if isinstance(receipts, dict) else None
    if not isinstance(receipt, dict) or not is_nonempty_string(receipt.get("evidence")):
        return False
    conditions = receipt.get("conditions", {})
    required = {
        "signal:replay": {"consent", "masking", "exclusions", "sampling"},
        "signal:canvas_replay": {"consent", "masking", "exclusions", "sampling"},
        "signal:tracing": {"allowlist", "request_compatibility"},
        "disabled_tls": {"test_only"},
    }.get(scope, set())
    return isinstance(conditions, dict) and all(
        is_nonempty_string(conditions.get(key)) for key in required
    )


def compatible_upgrade(decision: dict[str, Any]) -> bool:
    if decision.get("action") != "upgrade":
        return False
    versions = []
    for key in ("from_version", "version"):
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", str(decision.get(key, "")))
        if not match:
            return False
        versions.append(tuple(map(int, match.groups())))
    before, after = versions
    return (
        decision.get("upgrade_kind") == "compatible_minor"
        and before[0] > 0 and before[0] == after[0] and before < after
        and is_nonempty_string(decision.get("necessity"))
        and is_nonempty_string(decision.get("compatibility"))
    )


def select_plan(plan: dict[str, Any], targets: list[str] | None = None) -> dict[str, Any]:
    """Project an already structurally validated v3 plan onto complete execution batches."""
    if plan.get("schema_version") != 3:
        if targets:
            raise ValueError("--targets requires a schema v3 plan")
        return copy.deepcopy(plan)
    all_targets = {t["id"]: t for t in plan["targets"]}
    unfinished = {
        key for key, target in all_targets.items()
        if target.get("disposition") not in {"existing", "instrumented", "skipped"}
    }
    completed = {
        key for key, target in all_targets.items()
        if target.get("disposition") in {"existing", "instrumented"}
    }
    selected = set(targets) if targets is not None else unfinished
    if (targets is not None and not selected) or selected - set(all_targets):
        raise ValueError("select at least one declared target")
    # Explicit full-batch selections and the default selection must execute the
    # same remaining work, without resolving credentials for completed members.
    selected = selected & unfinished
    batches = {batch["id"]: batch for batch in plan["batches"]}
    selected_batches = [b for b in batches.values() if selected & set(b["target_ids"])]
    for batch in selected_batches:
        if not (set(batch["target_ids"]) & unfinished) <= selected:
            raise ValueError(f"select the complete shared batch {batch['id']}")
        for dependency in batch.get("depends_on", []):
            dependency_ids = set(batches[dependency]["target_ids"])
            if not dependency_ids <= selected | completed:
                raise ValueError(f"batch {batch['id']} requires batch {dependency}")
    ordered = []
    pending_batches = {b["id"]: b for b in selected_batches}
    while pending_batches:
        ready = sorted(key for key, batch in pending_batches.items() if not set(batch.get("depends_on", [])) & set(pending_batches))
        if not ready:
            raise ValueError("batch dependencies contain a cycle")
        for key in ready:
            ordered.append(pending_batches.pop(key))
    selected_batches = ordered
    result = copy.deepcopy(plan)
    result["targets"] = [t for t in result["targets"] if t["id"] in selected]
    result["planned_changes"] = [c for c in result["planned_changes"] if c["target_id"] in selected]
    result["batches"] = copy.deepcopy(selected_batches)
    slots = {slot for t in result["targets"] for slot in t["application_id_slots"]}
    receiver = result["request"]["receiver"]
    if "client_tokens" in receiver:
        receiver["client_tokens"] = {k: v for k, v in receiver["client_tokens"].items() if k in slots}
    # Global input provenance is validated before projection; do not reinterpret a scalar.
    ids = {k: v for t in result["targets"] for k, v in t["application_ids"].items()}
    if ids:
        result["request"]["application_id_input"] = {"kind": "map", "references": ids}
    if len(selected_batches) == 1:
        result["approval"] = copy.deepcopy(selected_batches[0]["approval"])
    else:
        approved = all(b["approval"]["status"] == "approved" for b in selected_batches)
        result["approval"] = {
            "status": "approved" if approved else "pending",
            "basis": "explicit_implementation_request",
            "revision": plan["approval"]["revision"],
            "blockers": [] if approved else ["one or more selected batches need input"],
        }
    return result


def validate_batches(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    batches = plan.get("batches")
    if not isinstance(batches, list) or not batches:
        return ["v3 batches must be a non-empty array"]
    targets = {t.get("id") for t in plan.get("targets", []) if isinstance(t, dict)}
    owners: dict[str, str] = {}
    graph: dict[str, list[str]] = {}
    for batch in batches:
        if not isinstance(batch, dict) or not is_nonempty_string(batch.get("id")):
            errors.append("each batch requires an id")
            continue
        key = batch["id"]
        if key in graph:
            errors.append(f"duplicate batch {key}")
        ids, dependencies = batch.get("target_ids"), batch.get("depends_on", [])
        validate_nonempty_string_list(ids, f"batch {key}.target_ids", errors)
        if not isinstance(dependencies, list) or any(not is_nonempty_string(d) for d in dependencies):
            errors.append(f"batch {key}.depends_on must be an array of batch ids")
            dependencies = []
        graph[key] = dependencies
        for target in ids if isinstance(ids, list) else []:
            if not isinstance(target, str):
                continue
            if target not in targets or target in owners:
                errors.append(f"batch {key} has unknown or repeated target {target}")
            owners[target] = key
        if not isinstance(batch.get("approval"), dict):
            errors.append(f"batch {key} requires approval")
        elif batch["approval"].get("revision") != plan["approval"].get("revision"):
            errors.append(f"batch {key} must use the current plan revision")
    if set(owners) != targets:
        errors.append("batches must cover every target exactly once")
    visiting, visited = set(), set()
    def visit(key: str) -> None:
        if key in visiting:
            errors.append("batch dependencies contain a cycle")
            return
        if key in visited:
            return
        visiting.add(key)
        for dep in graph[key]:
            if dep not in graph:
                errors.append(f"batch {key} has unknown dependency {dep}")
            else:
                visit(dep)
        visiting.remove(key)
        visited.add(key)
    for key in graph:
        visit(key)
    # A shared runtime file is also a shared edit, even if it is Git-ignored.
    sinks: dict[str, tuple[str, str, str]] = {}
    sink_keys: set[tuple[str, str]] = set()
    receiver_tokens = plan.get("request", {}).get("receiver", {}).get("client_tokens", {})
    for target in plan.get("targets", []):
        for slot in target.get("application_id_slots", []):
            sink = receiver_tokens.get(slot, {}).get("sink")
            if not isinstance(sink, dict):
                continue
            filename = sink.get("path")
            if not isinstance(filename, str):
                continue
            filename = str(Path(filename))
            identity = (sink.get("format"), sink.get("scope"), owners.get(target["id"]))
            if filename in sinks and sinks[filename] != identity:
                errors.append(f"shared configuration {filename} requires one batch, format and scope")
            sinks[filename] = identity
            key = (filename, sink.get("key"))
            if key in sink_keys:
                errors.append(f"duplicate runtime key in {filename}")
            sink_keys.add(key)
    file_owners: dict[str, str] = {}
    for change in plan.get("planned_changes", []):
        if not isinstance(change, dict):
            continue
        filename, batch = change.get("file"), owners.get(change.get("target_id"))
        if not isinstance(filename, str):
            continue
        if filename in file_owners and file_owners[filename] != batch:
            errors.append(f"shared file {filename} must belong to one batch")
        file_owners[filename] = batch
    return errors


def validate_resolution_endpoint(plan: dict[str, Any]) -> list[str]:
    """A plan may retain references; executing the control plane needs an origin."""
    receiver = plan.get("request", {}).get("receiver", {})
    if plan.get("targets") and receiver.get("mode") == "public_dataway":
        if not is_nonempty_string(receiver.get("endpoint", {}).get("value")):
            return ["request.receiver.endpoint.value is required before Public DataWay execution; "
                    "resolve the non-secret address from its source and record the concrete origin"]
    return []


def validate_plan(plan: Any, phase: str, targets: list[str] | None = None) -> tuple[list[str], list[str]]:
    if phase == "prepare":
        phase = "implement"
    if not isinstance(plan, dict) or plan.get("schema_version") != 3:
        errors, warnings = _validate_plan_legacy(plan, phase)
        if targets is not None:
            errors.append("--targets requires a schema v3 plan")
        return errors, warnings
    if not isinstance(plan.get("request"), dict) or not isinstance(plan.get("approval"), dict):
        return ["v3 request and summary approval must be objects"], []
    summary = plan["approval"]
    if summary.get("status") not in {"pending", "approved"} or summary.get("basis") not in APPROVAL_BASES or not isinstance(summary.get("blockers"), list):
        return ["v3 summary approval requires status, basis and blockers"], []
    # Validate the full graph before selecting a subset: selection cannot hide bad paths,
    # duplicate IDs, malformed references, or an ambiguous scalar application ID.
    structural = copy.deepcopy(plan)
    structural["schema_version"] = 2
    structural["approval"] = {
        "status": "pending", "basis": "plan_only_request" if plan.get("request", {}).get("intent") in PLAN_ONLY_INTENTS else "explicit_implementation_request",
        "blockers": ["structural validation"], "revision": plan.get("approval", {}).get("revision"),
    }
    errors, warnings = _validate_plan_legacy(structural, "plan", modern=True)
    if errors:
        return errors, warnings
    errors.extend(validate_batches(plan))
    if errors:
        return errors, warnings
    # Validate authorization for every batch, even when another batch is selected.
    for batch in plan["batches"]:
        projected = copy.deepcopy(plan)
        ids = set(batch["target_ids"])
        projected["targets"] = [t for t in projected["targets"] if t["id"] in ids]
        projected["planned_changes"] = [c for c in projected["planned_changes"] if c["target_id"] in ids]
        slots = {s for t in projected["targets"] for s in t["application_id_slots"]}
        receiver = projected["request"]["receiver"]
        if "client_tokens" in receiver:
            receiver["client_tokens"] = {k: v for k, v in receiver["client_tokens"].items() if k in slots}
        application_ids = {k: v for t in projected["targets"] for k, v in t["application_ids"].items()}
        if application_ids:
            projected["request"]["application_id_input"] = {"kind": "map", "references": application_ids}
        projected["approval"] = copy.deepcopy(batch["approval"])
        if projected["approval"].get("basis") == "revision_review":
            # The user reviews the original full plan, never an invisible projection.
            receipt_plan = copy.deepcopy(plan)
            receipt_plan["approval"] = projected["approval"]
            validate_revision_review(receipt_plan, projected["approval"], errors)
        projected["schema_version"] = 2
        if projected["approval"].get("basis") == "revision_review":
            projected["approval"]["reviewed_plan_sha256"] = plan_review_digest(projected)
        batch_errors, _ = _validate_plan_legacy(projected, "plan", modern=True)
        errors.extend(f"batch {batch['id']}: {e}" for e in batch_errors)
    if phase == "implement" or targets is not None:
        try:
            selected = select_plan(plan, targets)
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if phase == "implement":
                errors.extend(validate_resolution_endpoint(selected))
            for batch in selected["batches"]:
                if batch["approval"].get("status") != "approved":
                    errors.append(f"batch {batch['id']} requires resolved input or authorization")
            if any(t.get("disposition") in {"blocked", "failed"} or t.get("blockers") for t in selected["targets"]):
                errors.append("selected targets contain unresolved blockers")
    return errors, warnings


def receiver_origin(value: Any) -> str | None:
    """Match the resolver's origin normalization without accepting paths or credentials."""
    if not isinstance(value, str) or not is_valid_origin(value.strip(), {"http", "https"}):
        return None
    parsed = urlsplit(value.strip())
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def credential_binding(plan: dict[str, Any], slot: str, repository: Path, *, normalize_endpoint: bool = True) -> str:
    receiver = plan["request"]["receiver"]
    target = next(t for t in plan["targets"] if slot in t["application_ids"])
    sink = copy.deepcopy(receiver["client_tokens"][slot]["sink"])
    sink["path"] = str((repository / sink["path"]).resolve())
    endpoint = copy.deepcopy(receiver["endpoint"])
    origin = receiver_origin(endpoint.get("value"))
    if normalize_endpoint and origin is not None:
        endpoint["value"] = origin
    identity = {
        "repository": str(repository.resolve()), "receiver": endpoint,
        "control_plane": {k: receiver["control_plane"].get(k) for k in ("catalog", "site_code", "ai_api_endpoint", "tls_verification")},
        "slot": slot, "app_id": target["application_ids"][slot], "sink": sink,
        "source": receiver["client_tokens"][slot]["source"],
    }
    return "sha256:" + hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def credential_binding_matches(entry: dict[str, Any], plan: dict[str, Any], slot: str, repository: Path) -> bool:
    # Old v2 checkpoints must still match the complete original identity before
    # URL normalization is migrated. Metadata and sink integrity are checked next.
    return entry.get("binding") in (
        credential_binding(plan, slot, repository),
        credential_binding(plan, slot, repository, normalize_endpoint=False),
    )


def validate_control_plane_state(state: Any, plan: dict[str, Any], *, repository: Path | None = None, state_path: Path | None = None) -> tuple[list[str], list[str]]:
    if not isinstance(state, dict) or state.get("schema_version") != 2:
        return _validate_control_plane_state_legacy(state, plan, repository=repository, state_path=state_path)
    if repository is None:
        return ["state v2 validation requires --repository"], []
    errors, warnings = [], []
    if state.get("kind") != "rum_control_plane_state":
        errors.append("invalid control-plane state kind")
    entries = state.get("slots")
    if not isinstance(entries, dict):
        return ["state v2 slots must be an object"], []
    for slot in plan.get("request", {}).get("receiver", {}).get("client_tokens", {}):
        entry = entries.get(slot)
        if not isinstance(entry, dict):
            errors.append(f"missing recoverable state for slot {slot}")
            continue
        if not credential_binding_matches(entry, plan, slot, repository):
            errors.append(f"credential identity changed for slot {slot}; resolve only this slot again")
            continue
        # Reuse the complete v1 validation for site, app metadata, paths and permissions.
        single = copy.deepcopy(plan)
        single["request"]["receiver"]["client_tokens"] = {slot: plan["request"]["receiver"]["client_tokens"][slot]}
        single["targets"] = [t for t in single["targets"] if slot in t["application_ids"]]
        for batch in single.get("batches", []):
            if any(t["id"] in batch["target_ids"] for t in single["targets"]):
                single["approval"] = batch["approval"]
                break
        legacy = copy.deepcopy(entry.get("state", {}))
        if not isinstance(legacy, dict) or not isinstance(legacy.get("site"), dict):
            errors.append(f"malformed checkpoint for slot {slot}")
            continue
        legacy["plan_digest"] = plan_review_digest(single)
        saved_origin = receiver_origin(legacy["site"].get("dataway_url"))
        if saved_origin is None or saved_origin != receiver_origin(plan["request"]["receiver"]["endpoint"].get("value")):
            errors.append(f"receiver metadata changed for slot {slot}")
        ee, ww = _validate_control_plane_state_legacy(legacy, single, repository=repository, state_path=state_path)
        errors.extend(ee)
        warnings.extend(ww)
        try:
            sink_path = Path(legacy["secret_sink"]["path"])
            if not sink_path.is_file() or any(p.is_symlink() for p in (sink_path, *sink_path.parents)):
                raise ValueError()
            digest = "sha256:" + hashlib.sha256(sink_path.read_bytes()).hexdigest()
            if entry.get("sink_sha256") != digest:
                errors.append(f"runtime configuration changed for slot {slot}; verify it before resuming")
        except (OSError, KeyError, TypeError, ValueError):
            errors.append(f"cannot verify runtime configuration integrity for slot {slot}")
    validate_sensitive_values(state, "control_plane_state", errors)
    return errors, warnings


def complete_plan_draft(draft: Any, repository: Path) -> dict[str, Any]:
    """Complete structural defaults only; facts and authorization remain caller input."""
    if not isinstance(draft, dict) or draft.get("schema_version", 3) != 3:
        raise ValueError("draft completion accepts only a v3 plan object")
    root = repository.resolve()
    if Path(_git_output(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise ValueError("--repository must be the Git worktree root")
    plan = copy.deepcopy(draft)
    plan.setdefault("schema_version", 3)
    # Preserve a supplied discovery baseline; never refresh it during a resume.
    if "repository" not in plan:
        plan["repository"] = {"root": ".", "commit": _git_output(root, "rev-parse", "HEAD"),
                              "initial_status": _git_output(root, "status", "--porcelain=v1", "--untracked-files=all").splitlines()}
    request = plan.get("request")
    targets = plan.get("targets")
    if not isinstance(request, dict) or not isinstance(targets, list) or not targets:
        raise ValueError("draft requires request and the complete discovered targets list")
    intent = request.get("intent")
    if intent not in PLAN_ONLY_INTENTS | IMPLEMENTATION_INTENTS:
        raise ValueError("draft requires an explicit request.intent")
    if intent in IMPLEMENTATION_INTENTS and not is_nonempty_string(request.get("authorization_evidence")):
        raise ValueError("implementation draft requires request.authorization_evidence from the actual user request")
    for field in ("validation", "risks", "handoff", "planned_changes"):
        plan.setdefault(field, [])
    for target in targets:
        if not isinstance(target, dict):
            raise ValueError("draft targets must be objects")
        for field in ("receiver_mapping", "privacy", "artifacts"):
            target.setdefault(field, {})
        target.setdefault("blockers", [])
        target.setdefault("disposition", "planned")
        target.setdefault("profile", {"signals": {"rum": True, "logs": "preserve", "tracing": "preserve", "replay": "preserve"}})
        # Identity, type, evidence and existing instrumentation are never guessed.
    if "batches" not in plan:
        if len(targets) != 1:
            raise ValueError("multiple targets require explicit batches and dependencies")
        plan["batches"] = [{"id": "core", "target_ids": [targets[0].get("id")], "depends_on": []}]
    if not isinstance(plan["batches"], list):
        raise ValueError("batches must be an array")
    revision = plan.get("approval", {}).get("revision", 1) if isinstance(plan.get("approval", {}), dict) else 1
    by_id = {t.get("id"): t for t in targets if isinstance(t.get("id"), str)}
    def approval(reasons):
        return {"status": "approved" if intent in IMPLEMENTATION_INTENTS and not reasons else "pending",
                "basis": "explicit_implementation_request" if intent in IMPLEMENTATION_INTENTS else "plan_only_request",
                "blockers": reasons, "revision": revision}
    for batch in plan["batches"]:
        if not isinstance(batch, dict) or not isinstance(batch.get("target_ids"), list):
            raise ValueError("each batch requires target_ids")
        reasons = []
        for tid in batch["target_ids"]:
            if not isinstance(tid, str) or tid not in by_id:
                raise ValueError("batch references an unknown target")
            t = by_id[tid]
            if not isinstance(t["blockers"], list):
                raise ValueError("target blockers must be an array")
            reasons.extend(t["blockers"])
            if t["disposition"] in {"blocked", "failed"} and not t["blockers"]:
                reasons.append(f"target {tid} is {t['disposition']}")
        # An explicit summary decision may encode an unresolved review. Never
        # replace it with a stronger generated batch approval.
        batch.setdefault("approval", copy.deepcopy(plan["approval"]) if "approval" in plan else approval(reasons))
    reasons = [reason for t in targets for reason in t["blockers"]]
    plan.setdefault("approval", approval(reasons))
    if "repository" not in draft:
        # Only a new discovery captures source baselines. Re-completing a plan
        # must never bless user changes by silently refreshing its fingerprints.
        for change in plan["planned_changes"]:
            path_errors: list[str] = []
            validate_planned_file(change.get("file"), "planned file", path_errors)
            if path_errors:
                raise ValueError("; ".join(path_errors))
            path = root / change["file"]
            if any(p.is_symlink() for p in (path, *path.parents)):
                raise ValueError("planned file cannot traverse symlinks")
            change.setdefault("before_sha256", file_digest(path))
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("--complete-draft", type=Path, metavar="NEW_PLAN", help="complete structural defaults, validate, and create a new v3 plan; never overwrite")
    parser.add_argument(
        "--kind",
        choices=("auto", "plan", "instrumentation"),
        default="auto",
    )
    parser.add_argument("--phase", choices=("plan", "prepare", "implement"), default="plan",
                        help="prepare checks authorization/repository before non-secret setup, without credential state")
    parser.add_argument("--repository", type=Path)
    parser.add_argument("--targets", nargs="+", help="complete v3 batch target IDs")
    parser.add_argument(
        "--execution-state",
        type=Path,
        help="non-secret control-plane state produced by resolve_rum_application.py",
    )
    parser.add_argument(
        "--print-review-digest",
        action="store_true",
        help="print the canonical digest to record for revision_review",
    )
    arguments = parser.parse_args()

    try:
        document = json.loads(arguments.document.read_text(encoding="utf-8"))
    except OSError as error:
        parser.error(str(error))
    except json.JSONDecodeError as error:
        print(f"invalid JSON: {error}", file=sys.stderr)
        return 1
    if arguments.complete_draft is not None:
        if (arguments.repository is None or arguments.phase != "plan" or arguments.kind == "instrumentation"
                or arguments.targets or arguments.execution_state or arguments.print_review_digest):
            parser.error("--complete-draft requires --repository and full plan-phase validation only")
        try:
            document = complete_plan_draft(document, arguments.repository)
            errors, warnings = validate_plan(document, "plan")
            if errors:
                for error in errors:
                    print(f"error: {error}", file=sys.stderr)
                return 1
            for warning in warnings:
                print(f"warning: {warning}", file=sys.stderr)
            destination = arguments.complete_draft.absolute()
            if any(p.is_symlink() for p in (destination, *destination.parents)):
                raise ValueError("plan output cannot traverse symlinks")
            if not destination.resolve().is_relative_to(arguments.repository.resolve()):
                raise ValueError("plan output must stay inside --repository")
            # Exclusive creation preserves all existing plans and recovery records.
            fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            print("created validated v3 plan; implementation still requires --phase implement")
            return 0
        except (OSError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
    if arguments.print_review_digest:
        if not isinstance(document, dict) or "generated_from_plan_revision" in document:
            parser.error("--print-review-digest requires a plan document")
        digest_plan = copy.deepcopy(document)
        if arguments.targets:
            if document.get("schema_version") != 3:
                parser.error("--targets requires a schema v3 plan")
            matches = [b for b in document.get("batches", []) if set(b.get("target_ids", [])) == set(arguments.targets)]
            if len(matches) != 1:
                parser.error("review digest selection must identify exactly one complete batch")
            digest_plan["approval"] = matches[0]["approval"]
        print(plan_review_digest(digest_plan))
        return 0

    execution_state = None
    if arguments.execution_state is not None:
        try:
            execution_state = json.loads(
                arguments.execution_state.read_text(encoding="utf-8")
            )
        except OSError as error:
            parser.error(str(error))
        except json.JSONDecodeError as error:
            print(f"invalid execution-state JSON: {error}", file=sys.stderr)
            return 1

    kind = arguments.kind
    if kind == "auto":
        kind = (
            "instrumentation"
            if isinstance(document, dict)
            and "generated_from_plan_revision" in document
            else "plan"
        )
    if kind == "instrumentation":
        if arguments.targets is not None:
            parser.error("--targets requires a plan")
        if arguments.phase != "plan":
            parser.error("--phase is valid only for plan documents")
        if arguments.repository is not None:
            parser.error("--repository is valid only for plan implementation validation")
        if arguments.execution_state is not None:
            parser.error("--execution-state is valid only for plan implementation validation")
        errors, warnings = validate_inventory(document)
    else:
        if arguments.phase != "implement" and arguments.execution_state is not None:
            parser.error("--execution-state requires --phase implement")
        errors, warnings = validate_plan(document, arguments.phase, arguments.targets)
        if document.get("schema_version") == 3 and not errors and arguments.phase in {"prepare", "implement"}:
            document = select_plan(document, arguments.targets)
        if arguments.phase in {"prepare", "implement"}:
            if arguments.repository is None:
                errors.append("implementation validation requires --repository")
            elif not errors:
                errors.extend(
                    validate_repository_state(document, arguments.repository)
                )
            receiver_mode = (
                document.get("request", {}).get("receiver", {}).get("mode")
                if isinstance(document, dict)
                else None
            )
            if arguments.phase == "implement" and receiver_mode == "public_dataway" and document.get("targets"):
                if execution_state is None:
                    errors.append(
                        "Public DataWay implementation requires --execution-state"
                    )
                else:
                    state_errors, state_warnings = validate_control_plane_state(
                        execution_state,
                        document,
                        repository=arguments.repository,
                        state_path=arguments.execution_state,
                    )
                    errors.extend(state_errors)
                    warnings.extend(state_warnings)
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    if kind == "instrumentation":
        print(
            "valid rum instrumentation inventory: revision "
            f"{document['generated_from_plan_revision']}"
        )
    else:
        print(
            f"valid rum plan: revision {document['approval']['revision']} "
            f"({arguments.phase})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
