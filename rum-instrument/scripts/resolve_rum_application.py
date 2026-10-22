#!/usr/bin/env python3
"""Resolve a public RUM application without exposing its credentials to the agent."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import copy
import hashlib
import getpass
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


CATALOGS = (
    ("guance", "https://urls.guance.com/"),
    ("truewatch", "https://urls.truewatch.com/"),
)
TESTING_DATAWAY_URL = "http://testing-openway.dataflux.cn"
TESTING_AI_API_URL = "https://testing-ft2x-ai-api.dataflux.cn"
TESTING_CATALOG = "builtin_testing"
APPLICATION_TYPES = {
    "web",
    "miniapp",
    "android",
    "ios",
    "custom",
    "reactnative",
    "harmonyos",
}
ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PROPERTY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
SLOT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
SINK_FORMATS = {"dotenv", "json", "properties", "xcconfig"}
EXCHANGE_PATH = "/api/v1/account/accesskey/exchange"
RUM_APP_GET_PATH = "/api/v1/rum/app/get"
DEFAULT_TEMP_CODE_ENV = "RUM_TEMP_AUTH_CODE"
DEFAULT_CLIENT_TOKEN_KEY = "RUM_CLIENT_TOKEN"


class ResolutionError(RuntimeError):
    """A safe-to-display resolution error that never contains response bodies."""


class TransientResolutionError(ResolutionError):
    """A retryable transport failure for an idempotent application lookup."""


@dataclass(frozen=True)
class Site:
    brand: str
    code: str
    catalog_url: str
    dataway_url: str
    ai_api_url: str
    catalog_kind: str = "official"
    tls_verification: str = "verified"
    endpoint_resolution: dict[str, Any] | None = None


@dataclass(frozen=True)
class SecretSinkSnapshot:
    path: Path
    existed_before: bool
    previous_bytes: bytes | None
    previous_mode: int | None
    sink_format: str
    scope: str


JsonFetcher = Callable[[str], dict[str, Any]]
JsonPoster = Callable[[str, dict[str, str], dict[str, str], str], dict[str, Any]]
Sleeper = Callable[[float], None]


def normalize_origin(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResolutionError(f"{field} must be a non-empty absolute URL")
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        raise ResolutionError(f"{field} contains an invalid host") from None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ResolutionError(f"{field} must be an absolute http(s) URL")
    try:
        parsed.port
    except ValueError:
        raise ResolutionError(f"{field} contains an invalid port") from None
    if parsed.hostname is None or any(
        character.isspace() or ord(character) < 32
        for character in parsed.netloc
    ):
        raise ResolutionError(f"{field} contains an invalid host")
    if parsed.username or parsed.password:
        raise ResolutionError(f"{field} must not contain URL credentials")
    if parsed.query or parsed.fragment:
        raise ResolutionError(f"{field} must not contain a query or fragment")
    if parsed.path not in {"", "/"}:
        raise ResolutionError(f"{field} must be an origin without a path")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _origin_key(origin: str) -> tuple[str, str | None, int]:
    parsed = urlsplit(origin)
    port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
    return parsed.scheme, parsed.hostname, port


def _read_json_response(
    request: Request,
    timeout: float,
    operation: str,
    *,
    tls_context: ssl.SSLContext | None = None,
) -> dict[str, Any]:
    try:
        with urlopen(request, timeout=timeout, context=tls_context) as response:
            payload = json.load(response)
    except HTTPError as error:
        error_type = (
            TransientResolutionError
            if error.code in {408, 429, 500, 502, 503, 504}
            else ResolutionError
        )
        raise error_type(f"{operation} failed with HTTP {error.code}") from None
    except (URLError, TimeoutError, OSError, UnicodeError, json.JSONDecodeError):
        raise TransientResolutionError(
            f"{operation} failed before a valid JSON response was received"
        ) from None
    if not isinstance(payload, dict):
        raise ResolutionError(f"{operation} returned an invalid JSON object")
    return payload


def fetch_json(url: str, timeout: float = 15.0) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "rum-instrument/1",
        },
    )
    return _read_json_response(request, timeout, "site catalog lookup")


def post_json(
    url: str,
    body: dict[str, str],
    headers: dict[str, str],
    operation: str,
    timeout: float = 15.0,
    *,
    tls_context: ssl.SSLContext | None = None,
) -> dict[str, Any]:
    request_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "rum-instrument/1",
        **headers,
    }
    request = Request(
        url,
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    return _read_json_response(
        request,
        timeout,
        operation,
        tls_context=tls_context,
    )


def _catalog_entries(payload: dict[str, Any], catalog_url: str) -> dict[str, Any]:
    entries = payload.get("urls")
    if not isinstance(entries, dict) or not entries:
        raise ResolutionError(f"site catalog {catalog_url} does not contain a non-empty urls object")
    return entries


def resolve_site(
    dataway_url: str,
    *,
    catalog_fetcher: JsonFetcher = fetch_json,
    catalogs: tuple[tuple[str, str], ...] = CATALOGS,
    catalog_kind: str = "official",
    tls_verification: str = "verified",
    endpoint_resolution: dict[str, Any] | None = None,
) -> Site:
    requested_origin = normalize_origin(dataway_url, "datawayUrl")
    testing_site = _origin_key(requested_origin) == _origin_key(TESTING_DATAWAY_URL)
    deployment_api = None
    if endpoint_resolution is not None:
        try:
            deployment_api = load_validator().deployment_endpoint(endpoint_resolution)
        except ValueError as exc:
            raise ResolutionError(str(exc)) from None
        if normalize_origin(endpoint_resolution["dataway_url"], "deployment datawayUrl") != requested_origin:
            raise ResolutionError("deployment evidence does not match the receiver")
        if testing_site:
            raise ResolutionError("built-in testing site cannot use deployment overrides")
        if endpoint_resolution["method"] == "configured":
            return Site("deployment", "deployment", "deployment_config", requested_origin, deployment_api,
                        catalog_kind="configured", endpoint_resolution=copy.deepcopy(endpoint_resolution))
    if testing_site:
        return Site(
            brand="guance",
            code="testing",
            catalog_url=TESTING_CATALOG,
            dataway_url=requested_origin,
            ai_api_url=TESTING_AI_API_URL,
            catalog_kind="testing",
            tls_verification=tls_verification,
        )
    # Catalogs contain only ordinary OpenWay. Normalize the service label for
    # comparison, never the receiver stored in SDK configuration or state.
    ordinary = load_validator().service_origin(requested_origin, "openway")
    candidates = {_origin_key(origin) for origin in (requested_origin, ordinary) if origin is not None}
    matches: list[Site] = []
    unavailable_catalogs: list[str] = []
    for brand, catalog_url in catalogs:
        try:
            entries = _catalog_entries(catalog_fetcher(catalog_url), catalog_url)
        except ResolutionError:
            unavailable_catalogs.append(catalog_url)
            continue
        for code, entry in entries.items():
            if not isinstance(code, str) or not isinstance(entry, dict):
                continue
            if not isinstance(entry.get("openway"), str) or not isinstance(entry.get("ai_api"), str):
                continue
            try:
                openway = normalize_origin(entry["openway"], "catalog openway")
            except ResolutionError:
                continue
            if _origin_key(openway) in candidates:
                matches.append(_site_from_entry(brand, code, catalog_url, requested_origin, entry,
                    catalog_kind=catalog_kind, tls_verification=tls_verification))
    if len(matches) > 1:
        raise ResolutionError("ambiguous site metadata; conflicting catalog entries must be resolved before supplying a code")
    if matches:
        return matches[0]
    if deployment_api is not None:
        return Site("deployment", "deployment", "deployment_config", requested_origin, deployment_api,
                    catalog_kind="service_name", endpoint_resolution=copy.deepcopy(endpoint_resolution))

    checked = ", ".join(catalog_url for _, catalog_url in catalogs)
    unavailable = (
        f"; unavailable catalogs: {', '.join(unavailable_catalogs)}"
        if unavailable_catalogs
        else ""
    )
    raise ResolutionError(
        f"cannot determine AI API for datawayUrl origin {requested_origin}; "
        f"catalogs checked: {checked}{unavailable}"
    )


def _site_from_entry(
    brand: str,
    code: str,
    catalog_url: str,
    dataway_url: str,
    entry: dict[str, Any],
    *,
    catalog_kind: str,
    tls_verification: str,
) -> Site:
    ai_api_url = normalize_origin(str(entry.get("ai_api", "")), f"{catalog_url}:{code}.ai_api")
    if not ai_api_url.startswith("https://"):
        raise ResolutionError("the matched site catalog ai_api endpoint must use https")
    return Site(
        brand=brand,
        code=code,
        catalog_url=catalog_url,
        dataway_url=dataway_url,
        ai_api_url=ai_api_url,
        catalog_kind=catalog_kind,
        tls_verification=tls_verification,
    )


def build_ai_api_tls_context(
    *,
    insecure_test_tls: bool,
    testing_site: bool,
) -> ssl.SSLContext | None:
    if insecure_test_tls and not testing_site:
        raise ResolutionError(
            "--insecure-test-tls is allowed only for the built-in testing site"
        )
    if insecure_test_tls:
        return ssl._create_unverified_context()
    return None


def probe_http_origin(
    origin: str,
    *,
    timeout: float = 10.0,
    tls_context: ssl.SSLContext | None = None,
) -> dict[str, Any]:
    request = Request(
        f"{origin}/",
        headers={"User-Agent": "rum-instrument/1"},
        method="HEAD",
    )
    try:
        with urlopen(request, timeout=timeout, context=tls_context) as response:
            status = response.status
    except HTTPError as error:
        status = error.code
    except (URLError, TimeoutError, OSError):
        raise ResolutionError(
            f"credential-free network preflight failed for {origin}"
        ) from None
    return {"status": "reachable", "http_status": status}


def preflight_site(
    site: Site,
    *,
    ai_api_tls_context: ssl.SSLContext | None = None,
) -> dict[str, Any]:
    ai_api = probe_http_origin(site.ai_api_url, tls_context=ai_api_tls_context)
    try:
        dataway = probe_http_origin(site.dataway_url)
    except ResolutionError:
        dataway = {"status": "unverified", "reason": "receiver probe failed; verify reporting from the application environment"}
    return {"status": "passed", "dataway": dataway, "ai_api": ai_api}


def _response_item(payload: dict[str, Any], operation: str) -> dict[str, Any]:
    if payload.get("success") is not True:
        raise ResolutionError(f"{operation} was rejected")
    data = payload.get("data")
    item = data.get("item") if isinstance(data, dict) else None
    if not isinstance(item, dict):
        raise ResolutionError(f"{operation} response did not contain data.item")
    return item


def resolve_application(
    site: Site,
    app_id: str,
    temporary_authorization_code: str,
    *,
    user_application_type: str | None = None,
    json_poster: JsonPoster = post_json,
) -> tuple[dict[str, Any], str]:
    metadata, client_tokens = resolve_applications(
        site,
        {"default": app_id},
        temporary_authorization_code,
        user_application_types=(
            {"default": user_application_type}
            if user_application_type is not None
            else {}
        ),
        json_poster=json_poster,
    )
    return {
        **metadata,
        "application": metadata["applications"]["default"],
    }, client_tokens["default"]


def resolve_applications(
    site: Site,
    application_ids: dict[str, str],
    temporary_authorization_code: str,
    *,
    user_application_types: dict[str, str] | None = None,
    json_poster: JsonPoster = post_json,
    network_attempts: int = 3,
    retry_delay: float = 1.0,
    sleeper: Sleeper = time.sleep,
    on_application: Callable[[str, dict[str, Any], str], None] | None = None,
    on_error: Callable[[str, ResolutionError], None] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    if not isinstance(application_ids, dict) or not application_ids:
        raise ResolutionError("at least one appId is required")
    for slot, app_id in application_ids.items():
        if (
            not isinstance(slot, str)
            or not SLOT_PATTERN.fullmatch(slot)
            or not isinstance(app_id, str)
            or not app_id.strip()
        ):
            raise ResolutionError("every appId slot and value must be a non-empty string")
    if not isinstance(temporary_authorization_code, str) or not temporary_authorization_code.strip():
        raise ResolutionError("the temporary authorization code input is empty")
    temporary_authorization_code = temporary_authorization_code.strip()
    if network_attempts < 1:
        raise ResolutionError("network_attempts must be at least 1")
    selected_user_types = user_application_types or {}
    if set(selected_user_types) - set(application_ids):
        raise ResolutionError("applicationType contains a slot that has no matching appId")
    if any(value not in APPLICATION_TYPES for value in selected_user_types.values()):
        raise ResolutionError(
            "applicationType must be web, miniapp, android, ios, custom, reactnative, or harmonyos"
        )

    exchange_url = f"{site.ai_api_url}{EXCHANGE_PATH}"
    exchange_payload = json_poster(
        exchange_url,
        {"code": temporary_authorization_code},
        {},
        "temporary authorization code exchange",
    )
    api_key = _response_item(exchange_payload, "temporary authorization code exchange").get("sk")
    if not isinstance(api_key, str) or not api_key:
        raise ResolutionError("temporary authorization code exchange did not return data.item.sk")

    applications: dict[str, dict[str, Any]] = {}
    client_tokens: dict[str, str] = {}
    for slot, app_id in application_ids.items():
        try:
            app_url = f"{site.ai_api_url}{RUM_APP_GET_PATH}"
            operation = f"RUM application lookup for slot {slot}"
            app_item: dict[str, Any] | None = None
            attempts_used = 0
            for attempt in range(network_attempts):
                attempts_used = attempt + 1
                try:
                    app_payload = json_poster(
                        app_url,
                        {"app_id": app_id.strip()},
                        {"DF-API-KEY": api_key},
                        operation,
                    )
                except TransientResolutionError:
                    if attempt + 1 >= network_attempts:
                        raise ResolutionError(
                            f"{operation} failed after {network_attempts} network attempts"
                        ) from None
                    sleeper(retry_delay)
                    continue
                candidate = _response_item(app_payload, operation)
                returned_app_id = candidate.get("app_id")
                if returned_app_id is not None and returned_app_id != app_id.strip():
                    raise ResolutionError(f"{operation} returned a different app_id")

                token_expired = candidate.get("token_expired")
                if token_expired is not False:
                    raise ResolutionError(f"{operation} returned an expired or unverifiable Client Token")
                app_item = candidate
                break

            if app_item is None:
                raise ResolutionError(f"{operation} did not return an application")
            client_token = app_item.get("client_token")
            api_application_type = app_item.get("app_type")
            if not isinstance(client_token, str) or not client_token:
                raise ResolutionError(
                    f"{operation} did not return data.item.client_token"
                )
            if api_application_type not in APPLICATION_TYPES:
                raise ResolutionError(
                    f"RUM application lookup for slot {slot} returned an unsupported app_type"
                )

            user_type = selected_user_types.get(slot)
            applications[slot] = {
                "app_id": app_id.strip(),
                "api_app_type": api_application_type,
                "selected_app_type": user_type or api_application_type,
                "selected_app_type_source": "user" if user_type else "ai_api",
                "type_mismatch": bool(user_type and user_type != api_application_type),
                "token_expired": False,
                "client_token_available": True,
                "network_attempts": attempts_used,
                "observations": {
                    field: app_item[field]
                    for field in (
                        "client_token_sync_status",
                        "mapping_status",
                        "mapping_ready",
                    )
                    if field in app_item
                },
            }
            client_tokens[slot] = client_token
        except ResolutionError as error:
            if on_error is None:
                raise
            on_error(slot, error)
            continue
        if on_application is not None:
            on_application(slot, applications[slot], client_token)

    metadata = {
        "site": {
            "brand": site.brand,
            "code": site.code,
            "catalog": site.catalog_url,
            "catalog_kind": site.catalog_kind,
            "dataway_url": site.dataway_url,
            "ai_api": site.ai_api_url,
            "tls_verification": site.tls_verification,
            **({"endpoint_resolution": copy.deepcopy(site.endpoint_resolution)} if site.endpoint_resolution is not None else {}),
        },
        "applications": applications,
        "credential_resolution": {
            "status": "resolved",
            "exchange_path": EXCHANGE_PATH,
            "application_lookup_path": RUM_APP_GET_PATH,
            "api_key_persistence": "memory_only",
        },
    }
    return metadata, client_tokens


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _require_git_ignored(path: Path, repository: Path) -> None:
    repository = repository.resolve()
    path = path.resolve()
    try:
        root_result = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "--show-toplevel"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if (
            root_result.returncode != 0
            or Path(root_result.stdout.strip()).resolve() != repository
        ):
            raise ResolutionError("--repository must point to the Git worktree root")
        if not _is_within(path, repository):
            return
        relative = path.relative_to(repository)
        result = subprocess.run(
            ["git", "-C", str(repository), "check-ignore", "-q", "--", str(relative)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        raise ResolutionError("git is required to verify an in-repository secret file") from None
    if result.returncode != 0:
        raise ResolutionError(
            "the requested client-token sink is inside the repository but is not git-ignored"
        )


def infer_sink_format(path: Path, requested: str | None = None) -> str:
    if requested is not None:
        if requested not in SINK_FORMATS:
            raise ResolutionError(
                "client-token sink format must be dotenv, json, properties, or xcconfig"
            )
        return requested
    name = path.name.lower()
    if name.endswith(".json"):
        return "json"
    if name.endswith(".properties"):
        return "properties"
    if name.endswith(".xcconfig"):
        return "xcconfig"
    return "dotenv"


def validate_sink_keys(keys: dict[str, str], sink_format: str) -> None:
    if not keys or len(set(keys.values())) != len(keys):
        raise ResolutionError("every Client Token must have one unique sink key")
    for key in keys.values():
        valid = (
            bool(ENV_NAME_PATTERN.fullmatch(key))
            if sink_format in {"dotenv", "xcconfig"}
            else (
                bool(PROPERTY_KEY_PATTERN.fullmatch(key))
                if sink_format == "properties"
                else isinstance(key, str)
                and bool(key.strip())
                and not any(ord(character) < 32 for character in key)
            )
        )
        if not valid:
            raise ResolutionError(
                f"client-token sink key is invalid for {sink_format}"
            )
    if sink_format == "json":
        paths = [key.split('.') for key in keys.values()]
        if any(not all(path) for path in paths):
            raise ResolutionError("JSON sink paths must have non-empty dot-separated components")
        if any(left != right and right[:len(left)] == left for left in paths for right in paths):
            raise ResolutionError("JSON sink paths cannot overlap as parent and child")


def inspect_secret_sink(
    path: Path,
    *,
    sink_format: str,
    keys: dict[str, str],
    repository: Path,
    allow_external: bool,
) -> SecretSinkSnapshot:
    validate_sink_keys(keys, sink_format)
    candidate = path.expanduser()
    if candidate.is_symlink():
        raise ResolutionError("client-token sink must not be a symlink")
    output = candidate.resolve(strict=False)
    repository_root = repository.expanduser().resolve()
    _require_git_ignored(output, repository_root)
    inside_repository = _is_within(output, repository_root)
    if not inside_repository and not allow_external:
        raise ResolutionError(
            "an external client-token sink requires --allow-external-secret-sink"
        )
    if output.exists() and not output.is_file():
        raise ResolutionError("client-token sink must be a regular file")
    try:
        previous_bytes = output.read_bytes() if output.exists() else None
        previous_mode = (
            output.stat().st_mode & 0o777 if output.exists() else None
        )
    except OSError:
        raise ResolutionError("client-token sink could not be read safely") from None
    # Both CLI modes check parsing and destination shape before reading a code.
    # Only synthetic values are rendered here; existing configuration is untouched.
    _render_secret_sink(previous_bytes, keys, {slot: "preflight" for slot in keys}, sink_format)
    return SecretSinkSnapshot(
        path=output,
        existed_before=output.exists(),
        previous_bytes=previous_bytes,
        previous_mode=previous_mode,
        sink_format=sink_format,
        scope="repository" if inside_repository else "external",
    )


def require_secure_storage() -> None:
    """Fail before credentials on hosts without the required POSIX permissions."""
    if sys.platform == "win32" or not callable(getattr(os, "fchmod", None)):
        raise ResolutionError(
            "Public DataWay credential storage requires macOS/Linux POSIX permissions; "
            "on Windows use WSL with a Linux filesystem, or resolve configuration on a supported host"
        )


def preflight_destinations(paths: list[Path]) -> None:
    """Probe secure creation/replacement without touching any existing value file."""
    require_secure_storage()
    candidates = {_checked_path(path) for path in paths}
    if any(left != right and left in right.parents for left in candidates for right in candidates):
        raise ResolutionError("runtime/state destinations cannot be parent directories of one another")
    checked_parents: set[Path] = set()
    for candidate in sorted(candidates):
        try:
            if candidate.exists() and not candidate.is_file():
                raise ResolutionError("runtime/state destination must be a regular file")
            candidate.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if candidate.parent in checked_parents:
                continue
            with tempfile.TemporaryDirectory(prefix=".rum-preflight-", dir=candidate.parent) as temporary:
                probe = Path(temporary) / "write-probe"
                _atomic_write(probe, b"preflight\n")
                _atomic_write(probe, b"replace-probe\n")
                if probe.stat().st_mode & 0o777 != 0o600:
                    raise ResolutionError("runtime/state filesystem must enforce mode 0600")
            checked_parents.add(candidate.parent)
        except OSError:
            raise ResolutionError("runtime/state destination is not writable; repair its parent directory before supplying a code") from None


def _encode_assignment_value(value: str, sink_format: str) -> str:
    if sink_format in {"dotenv", "xcconfig"}:
        return json.dumps(value, ensure_ascii=False)
    if sink_format == "properties":
        rendered: list[str] = []
        for character in value:
            if character == "\\":
                rendered.append("\\\\")
            elif character == "\n":
                rendered.append("\\n")
            elif character == "\r":
                rendered.append("\\r")
            elif character == "\t":
                rendered.append("\\t")
            elif ord(character) < 32:
                rendered.append(f"\\u{ord(character):04x}")
            else:
                rendered.append(character)
        return "".join(rendered)
    raise ResolutionError(f"unsupported client-token sink format: {sink_format}")


def _render_assignment_sink(
    existing: str,
    keys: dict[str, str],
    client_tokens: dict[str, str],
    sink_format: str,
) -> str:
    separator = " = " if sink_format == "xcconfig" else "="
    patterns = {
        slot: re.compile(
            (
                rf"^\s*(?:export\s+)?{re.escape(key)}\s*="
                if sink_format == "dotenv"
                else rf"^\s*{re.escape(key)}\s*[:=]"
            )
        )
        for slot, key in keys.items()
    }
    rendered_lines: list[str] = []
    replaced: set[str] = set()
    for line in existing.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        ending = line[len(content):]
        matching = [slot for slot, pattern in patterns.items() if pattern.match(content)]
        if not matching:
            rendered_lines.append(line)
            continue
        slot = matching[0]
        if slot in replaced:
            continue
        rendered_lines.append(
            f"{keys[slot]}{separator}"
            f"{_encode_assignment_value(client_tokens[slot], sink_format)}"
            f"{ending}"
        )
        replaced.add(slot)
    if existing and not existing.endswith(("\n", "\r")):
        rendered_lines.append(os.linesep)
    for slot in sorted(set(keys) - replaced):
        rendered_lines.append(
            f"{keys[slot]}{separator}"
            f"{_encode_assignment_value(client_tokens[slot], sink_format)}"
            f"{os.linesep}"
        )
    return "".join(rendered_lines)


def _render_secret_sink(
    existing: bytes | None,
    keys: dict[str, str],
    client_tokens: dict[str, str],
    sink_format: str,
) -> bytes:
    try:
        current_text = existing.decode("utf-8") if existing is not None else ""
    except UnicodeDecodeError:
        raise ResolutionError("existing client-token sink must be UTF-8") from None
    if sink_format == "json":
        if current_text.strip():
            try:
                payload = json.loads(current_text)
            except json.JSONDecodeError:
                raise ResolutionError(
                    "existing JSON client-token sink is invalid"
                ) from None
            if not isinstance(payload, dict):
                raise ResolutionError(
                    "existing JSON client-token sink must contain an object"
                )
        else:
            payload = {}
        for slot, key in keys.items():
            parts = key.split('.')
            node = payload
            for index, part in enumerate(parts):
                # Do not silently reinterpret a previously literal dotted key.
                if index < len(parts) - 1 and '.'.join(parts[index:]) in node:
                    raise ResolutionError("JSON sink path conflicts with a literal dotted key; repair configuration before resolution")
                if index == len(parts) - 1:
                    if isinstance(node.get(part), (dict, list)):
                        raise ResolutionError("JSON sink token destination must not replace an object or array")
                    node[part] = client_tokens[slot]
                else:
                    if part not in node:
                        node[part] = {}
                    if not isinstance(node[part], dict):
                        raise ResolutionError("JSON sink path traverses a non-object; preserve existing configuration")
                    node = node[part]
        return (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
    return _render_assignment_sink(
        current_text,
        keys,
        client_tokens,
        sink_format,
    ).encode("utf-8")


def _atomic_write(path: Path, payload: bytes, mode: int = 0o600) -> None:
    require_secure_storage()
    descriptor = None
    temporary_path = None
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary_path = Path(temporary_name)
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except OSError:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise ResolutionError("client-token sink could not be written safely") from None


def write_client_tokens_sink(
    snapshot: SecretSinkSnapshot,
    keys: dict[str, str],
    client_tokens: dict[str, str],
) -> Path:
    if set(keys) != set(client_tokens):
        raise ResolutionError("every Client Token must have exactly one sink key")
    validate_sink_keys(keys, snapshot.sink_format)
    payload = _render_secret_sink(
        snapshot.previous_bytes,
        keys,
        client_tokens,
        snapshot.sink_format,
    )
    _atomic_write(snapshot.path, payload)
    return snapshot.path


def restore_secret_sink(snapshot: SecretSinkSnapshot) -> None:
    if snapshot.existed_before:
        assert snapshot.previous_bytes is not None
        _atomic_write(
            snapshot.path,
            snapshot.previous_bytes,
            snapshot.previous_mode
            if snapshot.previous_mode is not None
            else 0o600,
        )
    else:
        snapshot.path.unlink(missing_ok=True)


def write_client_token_env(
    path: Path,
    environment_name: str,
    client_token: str,
    *,
    repository: Path | None = None,
) -> Path:
    return write_client_tokens_env(
        path,
        {"default": environment_name},
        {"default": client_token},
        repository=repository,
    )


def write_client_tokens_env(
    path: Path,
    environment_names: dict[str, str],
    client_tokens: dict[str, str],
    *,
    repository: Path | None = None,
) -> Path:
    if set(environment_names) != set(client_tokens) or not environment_names:
        raise ResolutionError("every Client Token must have exactly one runtime environment name")
    if repository is None:
        candidate = path.expanduser()
        if candidate.is_symlink():
            raise ResolutionError("client-token sink must not be a symlink")
        output = candidate.resolve(strict=False)
        snapshot = SecretSinkSnapshot(
            path=output,
            existed_before=output.exists(),
            previous_bytes=output.read_bytes() if output.exists() else None,
            previous_mode=(output.stat().st_mode & 0o777) if output.exists() else None,
            sink_format="dotenv",
            scope="external",
        )
    else:
        snapshot = inspect_secret_sink(
            path,
            sink_format="dotenv",
            keys=environment_names,
            repository=repository,
            allow_external=True,
        )
    return write_client_tokens_sink(snapshot, environment_names, client_tokens)


def build_safe_result(
    metadata: dict[str, Any],
    *,
    plan_digest: str,
    client_token_keys: dict[str, str],
    secret_file: Path | None,
    sink_format: str = "dotenv",
    sink_scope: str = "repository",
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "rum_control_plane_state",
        "plan_digest": plan_digest,
        **metadata,
        "client_tokens": {
            slot: {
                "source": f"runtime:{key}",
                "availability": "persisted" if secret_file is not None else "planned",
            }
            for slot, key in sorted(client_token_keys.items())
        },
        "secret_sink": (
            {
                "path": str(secret_file),
                "format": sink_format,
                "scope": sink_scope,
                "keys": {
                    slot: key
                    for slot, key in sorted(client_token_keys.items())
                },
            }
            if secret_file is not None
            else None
        ),
    }


def parse_slot_assignments(values: list[str] | None, field: str) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for raw in values or []:
        if "=" in raw:
            slot, value = raw.split("=", 1)
        else:
            slot, value = "default", raw
        slot = slot.strip()
        value = value.strip()
        if not SLOT_PATTERN.fullmatch(slot) or not value:
            raise ResolutionError(f"{field} assignments must use [slot=]value")
        if slot in assignments:
            raise ResolutionError(f"{field} contains duplicate slot {slot}")
        assignments[slot] = value
    return assignments


def default_client_token_keys(application_ids: dict[str, str]) -> dict[str, str]:
    if set(application_ids) == {"default"}:
        return {"default": DEFAULT_CLIENT_TOKEN_KEY}
    keys: dict[str, str] = {}
    for slot in application_ids:
        normalized_slot = re.sub(r"[^A-Za-z0-9]+", "_", slot).strip("_").upper()
        if not normalized_slot:
            raise ResolutionError(f"cannot derive a runtime key for appId slot {slot}")
        keys[slot] = f"{DEFAULT_CLIENT_TOKEN_KEY}_{normalized_slot}"
    if len(set(keys.values())) != len(keys):
        raise ResolutionError("appId slots produce duplicate runtime keys")
    return keys


def read_temporary_authorization_code(
    *,
    environment_name: str | None,
    from_stdin: bool,
) -> str:
    if from_stdin:
        if sys.stdin.isatty():
            temporary_code = getpass.getpass("Temporary authorization code: ")
        else:
            temporary_code = sys.stdin.readline().rstrip("\r\n")
    else:
        selected_environment = environment_name or DEFAULT_TEMP_CODE_ENV
        if not ENV_NAME_PATTERN.fullmatch(selected_environment):
            raise ResolutionError("temporary authorization code environment name is invalid")
        temporary_code = os.environ.get(selected_environment, "")
    if not temporary_code.strip():
        raise ResolutionError("the temporary authorization code input is empty")
    return temporary_code.strip()


def site_metadata(site: Site) -> dict[str, Any]:
    return {
        "site": {
            "brand": site.brand,
            "code": site.code,
            "catalog": site.catalog_url,
            "catalog_kind": site.catalog_kind,
            "dataway_url": site.dataway_url,
            "ai_api": site.ai_api_url,
            "tls_verification": site.tls_verification,
            **({"endpoint_resolution": copy.deepcopy(site.endpoint_resolution)} if site.endpoint_resolution is not None else {}),
        },
        "credential_resolution": {
            "status": "catalog_resolved",
            "exchange_path": EXCHANGE_PATH,
            "application_lookup_path": RUM_APP_GET_PATH,
            "api_key_persistence": "memory_only",
        },
    }


def write_state_file(path: Path, rendered: str) -> Path:
    candidate = path.expanduser()
    if candidate.exists() or candidate.is_symlink():
        raise ResolutionError(
            "control-plane state file already exists; refusing to overwrite it"
        )
    output = candidate.resolve()
    created = False
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(f"{rendered}\n")
    except OSError:
        if created:
            output.unlink(missing_ok=True)
        raise ResolutionError("control-plane state file could not be created safely") from None
    return output


def load_validator():
    import importlib.util
    spec = importlib.util.spec_from_file_location("rum_contract", Path(__file__).with_name("validate_contract.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _checked_path(path: Path) -> Path:
    candidate = path.expanduser().absolute()
    if any(part.is_symlink() for part in (candidate, *candidate.parents)):
        raise ResolutionError("runtime/state paths must not traverse symlinks")
    return candidate


def _sink_digest(path: Path) -> str:
    try:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        raise ResolutionError("runtime configuration integrity could not be checked") from None


def _single_slot_plan(plan: dict[str, Any], slot: str) -> dict[str, Any]:
    result = copy.deepcopy(plan)
    result["request"]["receiver"]["client_tokens"] = {slot: result["request"]["receiver"]["client_tokens"][slot]}
    result["targets"] = [t for t in result["targets"] if slot in t["application_ids"]]
    for batch in result.get("batches", []):
        if any(t["id"] in batch["target_ids"] for t in result["targets"]):
            result["approval"] = batch["approval"]
            break
    return result


def _reconcile_application_type(entry: dict[str, Any], slot: str, descriptor: dict[str, Any]) -> None:
    """Update only derived type selection, retaining the saved API facts."""
    try:
        application = entry["state"]["applications"][slot]
        api_type = application["api_app_type"]
        previous_type = application["selected_app_type"]
        previous_source = application["selected_app_type_source"]
        previous_mismatch = application["type_mismatch"]
    except (KeyError, TypeError):
        raise ResolutionError("saved application type metadata is malformed") from None
    if (not isinstance(api_type, str) or api_type not in APPLICATION_TYPES
            or not isinstance(previous_type, str) or previous_type not in APPLICATION_TYPES
            or not isinstance(previous_source, str) or previous_source not in {"user", "ai_api"}
            or (previous_source == "ai_api" and previous_type != api_type)
            or previous_mismatch is not bool(previous_source == "user" and previous_type != api_type)):
        raise ResolutionError("saved application type metadata is inconsistent")
    user_selected = descriptor["source"] == "user"
    selected_type = descriptor["value"] if user_selected else api_type
    application.update(
        selected_app_type=selected_type,
        selected_app_type_source="user" if user_selected else "ai_api",
        type_mismatch=bool(user_selected and selected_type != api_type),
    )


def resolve_plan(
    plan: dict[str, Any], repository: Path, state_path: Path, *,
    targets: list[str] | None = None, resume: bool = False,
    code_reader: Callable[[], str], json_poster: JsonPoster | None = None,
) -> dict[str, Any]:
    """Resolve only missing slots, checkpoint each success, never serialize server credentials."""
    validator = load_validator()
    errors, _ = validator.validate_plan(plan, "implement", targets)
    if errors:
        raise ResolutionError("plan validation failed: " + "; ".join(errors))
    selected = validator.select_plan(plan, targets)
    errors = validator.validate_repository_state(selected, repository)
    if errors:
        raise ResolutionError("repository validation failed: " + "; ".join(errors))
    receiver = selected["request"]["receiver"]
    if not selected["targets"]:
        return {"status": "complete", "resolved_slots": []}
    if receiver["mode"] != "public_dataway":
        raise ResolutionError("DataKit does not use credential resolution")
    require_secure_storage()
    errors = validator.validate_resolution_endpoint(selected)
    if errors:
        raise ResolutionError("plan validation failed: " + "; ".join(errors))
    state_path = _checked_path(state_path)
    _require_git_ignored(state_path, repository)
    if state_path.exists() and (not resume or not state_path.is_file()):
        raise ResolutionError("state already exists; use --resume with the same reviewed configuration")
    state = {"schema_version": 2, "kind": "rum_control_plane_state", "slots": {}}
    migration = False
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ResolutionError("saved state cannot be read; do not exchange a new code") from None
        if not isinstance(state, dict):
            raise ResolutionError("saved state must be an object")
        if state.get("schema_version") == 1:
            # Validate the ORIGINAL plan/digest first. A changed plan cannot bless old state.
            errors, _ = validator.validate_control_plane_state(state, plan, repository=repository, state_path=state_path)
            if errors:
                raise ResolutionError("legacy state requires its original valid plan: " + "; ".join(errors))
            previous = state
            state = {"schema_version": 2, "kind": "rum_control_plane_state", "slots": {}}
            for slot in previous["applications"]:
                single = copy.deepcopy(previous)
                single["applications"] = {slot: previous["applications"][slot]}
                single["client_tokens"] = {slot: previous["client_tokens"][slot]}
                single["secret_sink"]["keys"] = {slot: previous["secret_sink"]["keys"][slot]}
                state["slots"][slot] = {
                    "binding": validator.credential_binding(plan, slot, repository),
                    "state": single,
                    "sink_sha256": _sink_digest(Path(single["secret_sink"]["path"])),
                }
            migration = True
        if state.get("schema_version") != 2 or state.get("kind") != "rum_control_plane_state" or not isinstance(state.get("slots"), dict):
            raise ResolutionError("unsupported control-plane state")
    snapshots = {}
    pending = {}
    expected_state_bytes = state_path.read_bytes() if state_path.exists() else None
    for slot, reference in receiver["client_tokens"].items():
        sink = reference["sink"]
        path = _checked_path(repository / sink["path"])
        if path.resolve() == state_path.resolve():
            raise ResolutionError("control-plane state and runtime configuration must differ")
        single = _single_slot_plan(selected, slot)
        # Validate all keys in a shared file together so parent/child paths fail
        # before the first slot can consume a code or create a checkpoint.
        shared_keys = {
            other_slot: other["sink"]["key"]
            for other_slot, other in receiver["client_tokens"].items()
            if (repository / other["sink"]["path"]).resolve() == path.resolve()
        }
        snapshot = inspect_secret_sink(
            path, sink_format=sink["format"], keys=shared_keys, repository=repository,
            allow_external=single["approval"].get("basis") == "revision_review" or validator.scope_authorized(single, "external_sink"),
        )
        if snapshot.scope != sink["scope"]:
            raise ResolutionError(f"slot {slot} sink.scope does not match its path; "
                                  "use a repository-relative path and scope=repository for in-repository configuration")
        snapshots[slot] = snapshot
        entry = state["slots"].get(slot)
        if isinstance(entry, dict) and validator.credential_binding_matches(entry, selected, slot, repository):
            # A revised plan can accept the saved API type or change its user
            # override without changing credentials. Validate the reconciled
            # candidate fully before replacing any checkpoint metadata.
            candidate = copy.deepcopy(state)
            target = next(t for t in selected["targets"] if slot in t["application_ids"])
            _reconcile_application_type(candidate["slots"][slot], slot, target["application_types"][slot])
            errors, _ = validator.validate_control_plane_state(candidate, single, repository=repository, state_path=state_path)
            if errors:
                raise ResolutionError("saved configuration needs repair before resuming: " + "; ".join(errors))
            if candidate != state:
                state = candidate
                entry = state["slots"][slot]
                migration = True
            canonical_binding = validator.credential_binding(selected, slot, repository)
            if entry["binding"] != canonical_binding:
                entry["binding"] = canonical_binding
                migration = True
            continue
        target = next(t for t in selected["targets"] if slot in t["application_ids"])
        app_id = target["application_ids"][slot].get("value")
        if not isinstance(app_id, str) or not app_id:
            raise ResolutionError(f"slot {slot} requires a concrete Application ID before exchange")
        pending[slot] = app_id
    expected_sink_bytes = {snapshot.path: snapshot.previous_bytes for snapshot in snapshots.values()}
    # Validate *all* checkpointed keys in sinks we may update, including unselected slots.
    for entry in state["slots"].values():
        try:
            path = Path(entry["state"]["secret_sink"]["path"])
            if path in {snapshot.path for snapshot in snapshots.values()} and entry["sink_sha256"] != _sink_digest(path):
                raise ResolutionError("a shared runtime configuration changed; repair it before resuming")
        except (KeyError, TypeError):
            raise ResolutionError("saved slot checkpoint is malformed") from None
    if not pending:
        if migration:
            _atomic_write(state_path, (json.dumps(state, sort_keys=True, indent=2) + "\n").encode())
        return {"status": "reused", "resolved_slots": sorted(receiver["client_tokens"]), "state_file": str(state_path)}
    preflight_destinations([state_path, *(snapshot.path for snapshot in snapshots.values())])
    # Refresh destination snapshots at checkpoint time; all preflight checks precede input.
    control = receiver["control_plane"]
    site = resolve_site(receiver["endpoint"]["value"], endpoint_resolution=control.get("endpoint_resolution"))
    if (site.catalog_url != control["catalog"] or site.code != control["site_code"] or site.ai_api_url != control["ai_api_endpoint"]["value"]):
        raise ResolutionError("official site metadata changed; revise the plan before supplying a code")
    insecure = control.get("tls_verification") == "disabled_for_testing"
    tls_context = build_ai_api_tls_context(insecure_test_tls=insecure, testing_site=site.catalog_url == TESTING_CATALOG)
    if insecure:
        site = Site(**{**site.__dict__, "tls_verification": "disabled_for_testing"})
    preflight = preflight_site(site, ai_api_tls_context=tls_context)
    code = code_reader()
    consumed = False
    def poster(url, body, headers, operation):
        nonlocal consumed
        if url.endswith(EXCHANGE_PATH):
            consumed = True
        if json_poster is not None:
            return json_poster(url, body, headers, operation)
        return post_json(url, body, headers, operation, tls_context=tls_context)
    def checkpoint(slot, application, token):
        nonlocal expected_state_bytes
        sink = receiver["client_tokens"][slot]["sink"]
        snapshot = inspect_secret_sink(
            _checked_path(snapshots[slot].path), sink_format=sink["format"], keys={slot: sink["key"]},
            repository=repository, allow_external=sink["scope"] == "external",
        )
        current_state_bytes = state_path.read_bytes() if state_path.exists() else None
        if current_state_bytes != expected_state_bytes or snapshot.previous_bytes != expected_sink_bytes[snapshot.path]:
            raise ResolutionError("runtime configuration or checkpoint changed during resolution; preserve it and retry after verification")
        metadata = site_metadata(site)
        metadata["credential_resolution"]["status"] = "resolved"
        metadata["applications"] = {slot: application}
        metadata["network_preflight"] = preflight
        safe = build_safe_result(metadata, plan_digest=validator.plan_review_digest(selected), client_token_keys={slot: sink["key"]}, secret_file=snapshot.path, sink_format=sink["format"], sink_scope=sink["scope"])
        safe["client_tokens"][slot]["source"] = receiver["client_tokens"][slot]["source"]
        candidate = copy.deepcopy(state)
        try:
            write_client_tokens_sink(snapshot, {slot: sink["key"]}, {slot: token})
            digest = _sink_digest(snapshot.path)
            candidate["slots"][slot] = {"binding": validator.credential_binding(selected, slot, repository), "state": safe, "sink_sha256": digest}
            for existing in candidate["slots"].values():
                if existing["state"]["secret_sink"]["path"] == str(snapshot.path):
                    existing["sink_sha256"] = digest
            _atomic_write(state_path, (json.dumps(candidate, sort_keys=True, indent=2) + "\n").encode())
        except (ResolutionError, OSError):
            try:
                restore_secret_sink(snapshot)
            except (ResolutionError, OSError):
                raise ResolutionError("checkpoint failed and runtime configuration needs repair") from None
            raise ResolutionError("checkpoint failed; earlier saved applications are preserved") from None
        expected_state_bytes = state_path.read_bytes()
        expected_sink_bytes[snapshot.path] = snapshot.path.read_bytes()
        state.clear()
        state.update(candidate)
    user_types = {
        slot: descriptor["value"] for target in selected["targets"]
        for slot, descriptor in target["application_types"].items()
        if slot in pending and descriptor["source"] == "user"
    }
    failed_slots: dict[str, str] = {}
    try:
        resolve_applications(site, pending, code, user_application_types=user_types, json_poster=poster, on_application=checkpoint, on_error=lambda slot, error: failed_slots.update({slot: str(error)}))
        if failed_slots:
            raise ResolutionError("; ".join(failed_slots.values()))
    except ResolutionError as exc:
        remaining = sorted(set(pending) - {s for s in pending if s in state["slots"] and state["slots"][s].get("binding") == validator.credential_binding(selected, s, repository)})
        recovery = "; a fresh authorization code may be required for unresolved slots" if consumed else ""
        raise ResolutionError(f"{exc}; saved checkpoints preserved; unresolved slots: {', '.join(remaining)}{recovery}") from None
    errors, _ = validator.validate_control_plane_state(state, selected, repository=repository, state_path=state_path)
    if errors:
        raise ResolutionError("configuration saved; revise application metadata and resume without another code: " + "; ".join(errors))
    return {"status": "resolved", "resolved_slots": sorted(receiver["client_tokens"]), "state_file": str(state_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataway-url")
    parser.add_argument("--site-config", type=Path, help="non-secret same-deployment endpoint resolution JSON prepared from verified project/task evidence")
    parser.add_argument(
        "--app-id",
        action="append",
        help="repeat [slot=]APP_ID for independently deployed applications",
    )
    parser.add_argument(
        "--site-only",
        action="store_true",
        help="resolve only the control-plane endpoint; do not exchange credentials or look up applications",
    )
    parser.add_argument(
        "--application-type",
        action="append",
        help="repeat [slot=]TYPE; user values take precedence over AI API metadata",
    )
    temporary_code_source = parser.add_mutually_exclusive_group()
    temporary_code_source.add_argument(
        "--temporary-auth-code-env",
        help=f"read the code from this environment variable; defaults to {DEFAULT_TEMP_CODE_ENV}",
    )
    temporary_code_source.add_argument(
        "--temporary-auth-code-stdin",
        action="store_true",
        help="read one code line from stdin; terminal input is hidden",
    )
    parser.add_argument(
        "--client-token-key",
        "--client-token-env",
        dest="client_token_key",
        action="append",
        help="repeat [slot=]KEY; defaults are derived from appId slots",
    )
    parser.add_argument(
        "--client-token-sink",
        "--client-token-env-file",
        dest="client_token_sink",
        type=Path,
        help="Git-ignored local runtime/build configuration file",
    )
    parser.add_argument(
        "--sink-format",
        choices=sorted(SINK_FORMATS),
        help="sink format; inferred from .json, .properties, or .xcconfig, otherwise dotenv",
    )
    parser.add_argument("--plan", type=Path, help="validated v2/v3 plan; resolves slot-specific runtime configuration")
    parser.add_argument("--targets", nargs="+", help="complete v3 batch target IDs")
    parser.add_argument("--resume", action="store_true", help="reuse verified checkpoints and resolve only missing slots")
    parser.add_argument("--repository", type=Path)
    parser.add_argument(
        "--state-file",
        "--metadata-file",
        dest="state_file",
        type=Path,
        help="write non-secret control-plane execution state",
    )
    parser.add_argument(
        "--plan-digest",
        help="canonical plan digest emitted by validate_contract.py --print-review-digest",
    )
    parser.add_argument(
        "--allow-external-secret-sink",
        action="store_true",
        help="allow an explicitly reviewed secret sink outside the repository",
    )
    parser.add_argument(
        "--insecure-test-tls",
        action="store_true",
        help="test only: disable AI API certificate verification for the built-in testing site",
    )
    arguments = parser.parse_args()

    try:
        if arguments.plan is None and not arguments.site_only:
            require_secure_storage()
        if arguments.plan is not None:
            if any((arguments.site_config, arguments.dataway_url, arguments.app_id, arguments.application_type, arguments.client_token_key, arguments.client_token_sink, arguments.sink_format, arguments.plan_digest, arguments.site_only, arguments.allow_external_secret_sink, arguments.insecure_test_tls)):
                raise ResolutionError("--plan cannot be mixed with legacy receiver/sink/review options")
            if arguments.repository is None:
                raise ResolutionError("--plan requires --repository")
            try:
                plan = json.loads(arguments.plan.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raise ResolutionError("plan could not be read") from None
            result = resolve_plan(
                plan, arguments.repository.resolve(),
                arguments.state_file or arguments.repository / ".rum/control-plane-state.json",
                targets=arguments.targets, resume=arguments.resume,
                code_reader=lambda: read_temporary_authorization_code(environment_name=arguments.temporary_auth_code_env, from_stdin=arguments.temporary_auth_code_stdin),
            )
            print(json.dumps(result, sort_keys=True))
            return 0
        if arguments.targets is not None or arguments.resume:
            raise ResolutionError("--targets and --resume require --plan")
        if not arguments.dataway_url:
            raise ResolutionError("--dataway-url is required without --plan")
        application_ids = parse_slot_assignments(arguments.app_id, "appId")
        application_types = parse_slot_assignments(
            arguments.application_type,
            "applicationType",
        )
        if arguments.site_only:
            incompatible = (
                application_ids
                or application_types
                or arguments.temporary_auth_code_env
                or arguments.temporary_auth_code_stdin
                or arguments.client_token_key
                or arguments.client_token_sink
                or arguments.sink_format
                or arguments.repository
                or arguments.state_file
                or arguments.plan_digest
                or arguments.allow_external_secret_sink
            )
            if incompatible:
                raise ResolutionError(
                    "--site-only accepts only site resolution"
                )
        elif not application_ids:
            raise ResolutionError("at least one --app-id is required unless --site-only is used")
        elif arguments.client_token_sink is None:
            raise ResolutionError(
                "application lookup requires --client-token-sink so the Client Token is not discarded"
            )
        elif arguments.state_file is None:
            raise ResolutionError(
                "application lookup requires --state-file for recoverable non-secret results"
            )
        elif not isinstance(arguments.plan_digest, str) or not SHA256_PATTERN.fullmatch(
            arguments.plan_digest
        ):
            raise ResolutionError(
                "application lookup requires --plan-digest as sha256:<64 lowercase hex>"
            )
        client_token_keys = (
            parse_slot_assignments(arguments.client_token_key, "client-token sink key")
            if arguments.client_token_key
            else default_client_token_keys(application_ids)
        )
        if set(application_types) - set(application_ids):
            raise ResolutionError("applicationType contains a slot that has no matching appId")
        if set(client_token_keys) != set(application_ids):
            raise ResolutionError(
                "client-token sink key slots must exactly match appId slots"
            )
        if arguments.client_token_sink is not None:
            if arguments.repository is None:
                raise ResolutionError(
                    "--client-token-sink requires --repository for Git ignore verification"
                )
        if arguments.state_file is not None:
            state_candidate = arguments.state_file.expanduser()
            if state_candidate.exists() or state_candidate.is_symlink():
                raise ResolutionError(
                    "control-plane state file already exists; refusing to overwrite it"
                )
            if (
                arguments.client_token_sink is not None
                and state_candidate.resolve()
                == arguments.client_token_sink.expanduser().resolve()
            ):
                raise ResolutionError(
                    "control-plane state and client-token sink must use different paths"
                )
        sink_snapshot: SecretSinkSnapshot | None = None
        if arguments.client_token_sink is not None:
            sink_format = infer_sink_format(
                arguments.client_token_sink,
                arguments.sink_format,
            )
            sink_snapshot = inspect_secret_sink(
                arguments.client_token_sink,
                sink_format=sink_format,
                keys=client_token_keys,
                repository=arguments.repository,
                allow_external=arguments.allow_external_secret_sink,
            )
        if arguments.state_file is not None:
            _require_git_ignored(
                arguments.state_file.expanduser().resolve(),
                arguments.repository,
            )
        if not arguments.site_only:
            preflight_destinations([arguments.state_file, sink_snapshot.path])
        endpoint_resolution = None
        if arguments.site_config is not None:
            try:
                endpoint_resolution = json.loads(arguments.site_config.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raise ResolutionError("site configuration could not be read") from None
            if not isinstance(endpoint_resolution, dict):
                raise ResolutionError("site configuration must be an object")
        site = resolve_site(arguments.dataway_url, endpoint_resolution=endpoint_resolution)
        testing_site = site.catalog_url == TESTING_CATALOG
        tls_context = build_ai_api_tls_context(
            insecure_test_tls=arguments.insecure_test_tls,
            testing_site=testing_site,
        )
        if arguments.insecure_test_tls:
            site = Site(
                **{
                    **site.__dict__,
                    "tls_verification": "disabled_for_testing",
                }
            )
        if arguments.site_only:
            rendered = json.dumps(
                site_metadata(site),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            print(rendered)
            return 0
        network_preflight = preflight_site(
            site,
            ai_api_tls_context=tls_context,
        )
        temporary_code = read_temporary_authorization_code(
            environment_name=arguments.temporary_auth_code_env,
            from_stdin=arguments.temporary_auth_code_stdin,
        )

        def selected_json_poster(
            url: str,
            body: dict[str, str],
            headers: dict[str, str],
            operation: str,
        ) -> dict[str, Any]:
            return post_json(
                url,
                body,
                headers,
                operation,
                tls_context=tls_context,
            )

        metadata, client_tokens = resolve_applications(
            site,
            application_ids,
            temporary_code,
            user_application_types=application_types,
            json_poster=selected_json_poster,
        )
        metadata["network_preflight"] = network_preflight
        assert sink_snapshot is not None
        result = build_safe_result(
            metadata,
            plan_digest=arguments.plan_digest,
            client_token_keys=client_token_keys,
            secret_file=sink_snapshot.path,
            sink_format=sink_snapshot.sink_format,
            sink_scope=sink_snapshot.scope,
        )
        rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
        write_client_tokens_sink(
            sink_snapshot,
            client_token_keys,
            client_tokens,
        )
        try:
            write_state_file(arguments.state_file, rendered)
        except ResolutionError as state_error:
            try:
                restore_secret_sink(sink_snapshot)
            except (OSError, ResolutionError):
                raise ResolutionError(
                    "control-plane state persistence failed and the client-token sink "
                    "could not be restored; repair that sink before retrying"
                ) from None
            raise state_error
        print(rendered)
        return 0
    except ResolutionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
