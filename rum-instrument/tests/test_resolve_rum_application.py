from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import ssl
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "resolve_rum_application.py"
SPEC = importlib.util.spec_from_file_location("resolve_rum_application", SCRIPT)
assert SPEC and SPEC.loader
RESOLVER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RESOLVER
SPEC.loader.exec_module(RESOLVER)


GUANCE_CATALOG = {
    "urls": {
        "default": {
            "openway": "https://openway.guance.com",
            "ai_api": "https://ai-api.guance.com/",
        },
        "cn3": {
            "openway": "https://cn3-openway.guance.com",
            "ai_api": "https://cn3-ai-api.guance.com/",
        },
    }
}
TRUEWATCH_CATALOG = {
    "urls": {
        "us1": {
            "openway": "https://us1-openway.truewatch.com",
            "ai_api": "https://us1-ai-api.truewatch.com",
        }
    }
}
PLAN_DIGEST = "sha256:" + "a" * 64


def catalog_fetcher(url: str):
    if url == "https://urls.guance.com/":
        return GUANCE_CATALOG
    if url == "https://urls.truewatch.com/":
        return TRUEWATCH_CATALOG
    raise AssertionError(url)


def ready_application(app_id: str, app_type: str, client_token: str) -> dict:
    return {
        "app_id": app_id,
        "app_type": app_type,
        "client_token": client_token,
        "token_expired": False,
        "client_token_sync_status": "accepted",
        "mapping_status": "ready",
        "mapping_ready": True,
    }


class ResolveRumApplicationTests(unittest.TestCase):
    def init_git(self, repository: Path) -> None:
        subprocess.run(["git", "init", "-q", str(repository)], check=True)

    def test_resolves_guance_and_truewatch_from_official_catalog_entries(self):
        guance = RESOLVER.resolve_site(
            "https://cn3-openway.guance.com/",
            catalog_fetcher=catalog_fetcher,
        )
        truewatch = RESOLVER.resolve_site(
            "https://us1-openway.truewatch.com",
            catalog_fetcher=catalog_fetcher,
        )

        self.assertEqual(("guance", "cn3"), (guance.brand, guance.code))
        self.assertEqual("https://cn3-ai-api.guance.com", guance.ai_api_url)
        self.assertEqual("official", guance.catalog_kind)
        self.assertEqual("verified", guance.tls_verification)
        self.assertEqual(("truewatch", "us1"), (truewatch.brand, truewatch.code))
        self.assertEqual("https://us1-ai-api.truewatch.com", truewatch.ai_api_url)

    def test_resolves_only_the_built_in_testing_site(self):
        site = RESOLVER.resolve_site(
            "http://testing-openway.dataflux.cn",
            catalog_fetcher=mock.Mock(side_effect=AssertionError("catalog must not load")),
        )

        self.assertEqual(("guance", "testing"), (site.brand, site.code))
        self.assertEqual("testing", site.catalog_kind)
        self.assertEqual("builtin_testing", site.catalog_url)
        self.assertEqual(
            "https://testing-ft2x-ai-api.dataflux.cn",
            site.ai_api_url,
        )

    def test_insecure_tls_is_scoped_to_the_built_in_testing_site(self):
        self.assertIsNone(
            RESOLVER.build_ai_api_tls_context(
                insecure_test_tls=False,
                testing_site=False,
            )
        )
        with self.assertRaisesRegex(
            RESOLVER.ResolutionError,
            "built-in testing site",
        ):
            RESOLVER.build_ai_api_tls_context(
                insecure_test_tls=True,
                testing_site=False,
            )

        context = RESOLVER.build_ai_api_tls_context(
            insecure_test_tls=True,
            testing_site=True,
        )
        self.assertIsNotNone(context)
        self.assertEqual(ssl.CERT_NONE, context.verify_mode)

    def test_resolves_documented_default_rum_openway_alias(self):
        site = RESOLVER.resolve_site(
            "https://rum-openway.guance.com",
            catalog_fetcher=catalog_fetcher,
        )

        self.assertEqual("default", site.code)
        self.assertEqual("https://ai-api.guance.com", site.ai_api_url)

    def test_rejects_unknown_dataway_without_guessing_an_ai_api_endpoint(self):
        with self.assertRaisesRegex(
            RESOLVER.ResolutionError,
            "catalogs checked: https://urls.guance.com/, https://urls.truewatch.com/",
        ):
            RESOLVER.resolve_site(
                "https://private-openway.example.com",
                catalog_fetcher=catalog_fetcher,
            )

    def test_rejects_malformed_origin_host_and_port(self):
        for origin in ("https://open way.guance.com", "https://openway.guance.com:bad"):
            with self.subTest(origin=origin):
                with self.assertRaises(RESOLVER.ResolutionError):
                    RESOLVER.normalize_origin(origin, "datawayUrl")

    def test_rejects_slot_names_that_could_inject_output(self):
        with self.assertRaisesRegex(RESOLVER.ResolutionError, "assignments"):
            RESOLVER.parse_slot_assignments(
                ["web\nforged=app"],
                "appId",
            )

    def test_exchange_and_lookup_keep_api_key_and_client_token_out_of_metadata(self):
        site = RESOLVER.Site(
            brand="guance",
            code="cn3",
            catalog_url="https://urls.guance.com/",
            dataway_url="https://cn3-openway.guance.com",
            ai_api_url="https://cn3-ai-api.guance.com",
        )
        calls = []

        def poster(url, body, headers, operation):
            calls.append((url, body, headers, operation))
            if url.endswith(RESOLVER.EXCHANGE_PATH):
                return {
                    "success": True,
                    "data": {"item": {"sk": "synthetic-api-key"}},
                }
            return {
                "success": True,
                "data": {
                    "item": ready_application(
                        "web_demo",
                        "web",
                        "synthetic-client-token",
                    )
                },
            }

        metadata, client_token = RESOLVER.resolve_application(
            site,
            "web_demo",
            "synthetic-temporary-code",
            json_poster=poster,
        )
        rendered = str(metadata)

        self.assertEqual("synthetic-client-token", client_token)
        self.assertNotIn("synthetic-api-key", rendered)
        self.assertNotIn("synthetic-client-token", rendered)
        self.assertNotIn("synthetic-temporary-code", rendered)
        self.assertEqual(
            {"DF-API-KEY": "synthetic-api-key"},
            calls[1][2],
        )
        self.assertEqual("ai_api", metadata["application"]["selected_app_type_source"])

    def test_user_application_type_wins_and_mismatch_is_reported(self):
        site = RESOLVER.Site(
            brand="guance",
            code="default",
            catalog_url="https://urls.guance.com/",
            dataway_url="https://rum-openway.guance.com",
            ai_api_url="https://ai-api.guance.com",
        )

        def poster(url, body, headers, operation):
            if url.endswith(RESOLVER.EXCHANGE_PATH):
                return {"success": True, "data": {"item": {"sk": "api-key"}}}
            return {
                "success": True,
                "data": {
                    "item": ready_application("app", "web", "client-token")
                },
            }

        metadata, _ = RESOLVER.resolve_application(
            site,
            "app",
            "temp-code",
            user_application_type="custom",
            json_poster=poster,
        )

        self.assertEqual("custom", metadata["application"]["selected_app_type"])
        self.assertEqual("user", metadata["application"]["selected_app_type_source"])
        self.assertTrue(metadata["application"]["type_mismatch"])

    def test_secret_env_file_is_mode_600_and_safe_result_contains_only_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "rum-client-token.env"
            written = RESOLVER.write_client_token_env(
                output,
                "GUANCE_RUM_CLIENT_TOKEN",
                "synthetic-client-token",
            )
            result = RESOLVER.build_safe_result(
                {"application": {"app_id": "demo"}},
                plan_digest=PLAN_DIGEST,
                client_token_keys={
                    "default": "GUANCE_RUM_CLIENT_TOKEN"
                },
                secret_file=written,
            )

            self.assertEqual(
                'GUANCE_RUM_CLIENT_TOKEN="synthetic-client-token"\n',
                output.read_text(encoding="utf-8"),
            )
            self.assertEqual(0o600, stat.S_IMODE(output.stat().st_mode))
            self.assertNotIn("synthetic-client-token", str(result))
            self.assertEqual(
                "runtime:GUANCE_RUM_CLIENT_TOKEN",
                result["client_tokens"]["default"]["source"],
            )

    def test_supported_sink_formats_escape_arbitrary_nonempty_tokens(self):
        token = 'token with spaces="quotes"\\and\nnewlines'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = {
                "dotenv": (root / ".env.local", "RUM_CLIENT_TOKEN"),
                "json": (root / "rum.local.json", "rumClientToken"),
                "properties": (root / "local.properties", "rum.client.token"),
                "xcconfig": (root / "Secrets.xcconfig", "RUM_CLIENT_TOKEN"),
            }
            for sink_format, (path, key) in cases.items():
                with self.subTest(sink_format=sink_format):
                    snapshot = RESOLVER.SecretSinkSnapshot(
                        path=path,
                        existed_before=False,
                        previous_bytes=None,
                        previous_mode=None,
                        sink_format=sink_format,
                        scope="external",
                    )
                    RESOLVER.write_client_tokens_sink(
                        snapshot,
                        {"default": key},
                        {"default": token},
                    )
                    self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
                    if sink_format == "json":
                        self.assertEqual(
                            token,
                            json.loads(path.read_text(encoding="utf-8"))[key],
                        )
                    else:
                        rendered = path.read_text(encoding="utf-8")
                        self.assertIn(key, rendered)
                        self.assertNotIn("\nand\n", rendered)

    def test_multiple_applications_share_one_api_key_exchange(self):
        site = RESOLVER.Site(
            brand="guance",
            code="cn3",
            catalog_url="https://urls.guance.com/",
            dataway_url="https://cn3-openway.guance.com",
            ai_api_url="https://cn3-ai-api.guance.com",
        )
        calls = []

        def poster(url, body, headers, operation):
            calls.append((url, body, headers, operation))
            if url.endswith(RESOLVER.EXCHANGE_PATH):
                return {"success": True, "data": {"item": {"sk": "api-key"}}}
            app_type = "android" if body["app_id"] == "android_app" else "ios"
            return {
                "success": True,
                "data": {
                    "item": ready_application(
                        body["app_id"],
                        app_type,
                        f"{app_type}-client-token",
                    )
                },
            }

        metadata, tokens = RESOLVER.resolve_applications(
            site,
            {"android": "android_app", "ios": "ios_app"},
            "temporary-code",
            json_poster=poster,
        )

        self.assertEqual(3, len(calls))
        self.assertEqual(1, sum(url.endswith(RESOLVER.EXCHANGE_PATH) for url, *_ in calls))
        self.assertEqual(
            {"android": "android-client-token", "ios": "ios-client-token"},
            tokens,
        )
        self.assertNotIn("client-token", str(metadata))

    def test_accepts_a_valid_token_without_waiting_for_mapping(self):
        site = RESOLVER.Site(
            brand="guance",
            code="default",
            catalog_url="https://urls.guance.com/",
            dataway_url="https://openway.guance.com",
            ai_api_url="https://ai-api.guance.com",
        )
        lookups = 0

        def poster(url, body, headers, operation):
            nonlocal lookups
            if url.endswith(RESOLVER.EXCHANGE_PATH):
                return {"success": True, "data": {"item": {"sk": "api-key"}}}
            lookups += 1
            item = ready_application("web_app", "web", "client-token")
            if lookups == 1:
                item.update(
                    {
                        "client_token_sync_status": "queued",
                        "mapping_status": "pending",
                        "mapping_ready": False,
                    }
                )
            return {"success": True, "data": {"item": item}}

        sleeper = mock.Mock()
        metadata, tokens = RESOLVER.resolve_applications(
            site,
            {"web": "web_app"},
            "temporary-code",
            json_poster=poster,
            retry_delay=0,
            sleeper=sleeper,
        )

        self.assertEqual(1, lookups)
        sleeper.assert_not_called()
        self.assertEqual({"web": "client-token"}, tokens)
        application = metadata["applications"]["web"]
        self.assertTrue(application["client_token_available"])
        self.assertEqual("pending", application["observations"]["mapping_status"])
        self.assertFalse(application["observations"]["mapping_ready"])

    def test_retries_only_transient_application_lookup_failures(self):
        site = RESOLVER.Site(
            brand="guance",
            code="default",
            catalog_url="https://urls.guance.com/",
            dataway_url="https://openway.guance.com",
            ai_api_url="https://ai-api.guance.com",
        )
        lookups = 0

        def poster(url, body, headers, operation):
            nonlocal lookups
            if url.endswith(RESOLVER.EXCHANGE_PATH):
                return {"success": True, "data": {"item": {"sk": "api-key"}}}
            lookups += 1
            if lookups == 1:
                raise RESOLVER.TransientResolutionError("temporary network failure")
            return {
                "success": True,
                "data": {
                    "item": ready_application("web_app", "web", "client-token")
                },
            }

        sleeper = mock.Mock()
        metadata, tokens = RESOLVER.resolve_applications(
            site,
            {"web": "web_app"},
            "temporary-code",
            json_poster=poster,
            retry_delay=0,
            sleeper=sleeper,
        )

        self.assertEqual(2, lookups)
        sleeper.assert_called_once_with(0)
        self.assertEqual({"web": "client-token"}, tokens)
        self.assertEqual(2, metadata["applications"]["web"]["network_attempts"])

    def test_sync_and_mapping_failures_do_not_invalidate_a_current_token(self):
        site = RESOLVER.Site(
            brand="guance",
            code="default",
            catalog_url="https://urls.guance.com/",
            dataway_url="https://openway.guance.com",
            ai_api_url="https://ai-api.guance.com",
        )

        def poster(url, body, headers, operation):
            if url.endswith(RESOLVER.EXCHANGE_PATH):
                return {"success": True, "data": {"item": {"sk": "api-key"}}}
            item = ready_application("web_app", "web", "client-token")
            item.update(
                {
                    "client_token_sync_status": "failed",
                    "mapping_status": "failed",
                    "mapping_ready": False,
                }
            )
            return {"success": True, "data": {"item": item}}

        metadata, tokens = RESOLVER.resolve_applications(
            site,
            {"web": "web_app"},
            "temporary-code",
            json_poster=poster,
        )

        self.assertEqual({"web": "client-token"}, tokens)
        self.assertTrue(metadata["applications"]["web"]["client_token_available"])

    def test_rejects_expired_or_failed_client_token_state(self):
        site = RESOLVER.Site(
            brand="guance",
            code="default",
            catalog_url="https://urls.guance.com/",
            dataway_url="https://openway.guance.com",
            ai_api_url="https://ai-api.guance.com",
        )

        def expired_poster(url, body, headers, operation):
            if url.endswith(RESOLVER.EXCHANGE_PATH):
                return {"success": True, "data": {"item": {"sk": "api-key"}}}
            item = ready_application("web_app", "web", "client-token")
            item["token_expired"] = True
            return {"success": True, "data": {"item": item}}

        with self.assertRaisesRegex(RESOLVER.ResolutionError, "expired"):
            RESOLVER.resolve_applications(
                site,
                {"web": "web_app"},
                "temporary-code",
                json_poster=expired_poster,
                sleeper=lambda _: None,
            )

    def test_refuses_unignored_in_repository_secret_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            self.init_git(repository)
            output = repository / ".rum" / "runtime-secrets.env"

            with self.assertRaisesRegex(RESOLVER.ResolutionError, "not git-ignored"):
                RESOLVER.write_client_token_env(
                    output,
                    "GUANCE_RUM_CLIENT_TOKEN",
                    "synthetic-client-token",
                    repository=repository,
                )

    def test_allows_ignored_in_repository_secret_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            self.init_git(repository)
            (repository / ".gitignore").write_text(".rum/\n", encoding="utf-8")
            output = repository / ".rum" / "runtime-secrets.env"

            written = RESOLVER.write_client_token_env(
                output,
                "GUANCE_RUM_CLIENT_TOKEN",
                "synthetic-client-token",
                repository=repository,
            )

            self.assertEqual(output.resolve(), written)
            self.assertEqual(0o600, stat.S_IMODE(output.stat().st_mode))

    def test_cli_output_never_contains_credentials(self):
        site = RESOLVER.Site(
            brand="guance",
            code="default",
            catalog_url="https://urls.guance.com/",
            dataway_url="https://openway.guance.com",
            ai_api_url="https://ai-api.guance.com",
        )
        metadata = {
            "site": {
                "brand": "guance",
                "code": "default",
                "catalog": "https://urls.guance.com/",
                "catalog_kind": "official",
                "dataway_url": "https://openway.guance.com",
                "ai_api": "https://ai-api.guance.com",
                "tls_verification": "verified",
            },
            "applications": {
                "default": {
                    "app_id": "web_demo",
                    "api_app_type": "web",
                    "selected_app_type": "web",
                    "selected_app_type_source": "ai_api",
                    "type_mismatch": False,
                }
            },
            "credential_resolution": {
                "exchange_path": RESOLVER.EXCHANGE_PATH,
                "application_lookup_path": RESOLVER.RUM_APP_GET_PATH,
                "api_key_persistence": "memory_only",
            },
        }
        stdout = io.StringIO()
        stderr = io.StringIO()
        temporary_code = "synthetic-temporary-code"
        client_token = "synthetic-client-token"
        with tempfile.TemporaryDirectory() as temporary:
            temporary = str(Path(temporary).resolve())
            repository = Path(temporary) / "repository"
            repository.mkdir()
            self.init_git(repository)
            secret_file = Path(temporary) / "client-token.env"
            state_file = Path(temporary) / "control-plane-state.json"
            with (
                mock.patch.object(RESOLVER, "resolve_site", return_value=site),
                mock.patch.object(
                    RESOLVER,
                    "preflight_site",
                    return_value={"status": "passed"},
                ),
                mock.patch.object(
                    RESOLVER,
                    "resolve_applications",
                    return_value=(metadata, {"default": client_token}),
                ) as resolve_applications,
                mock.patch.object(sys, "stdin", io.StringIO(f"{temporary_code}\n")),
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        str(SCRIPT),
                        "--dataway-url",
                        "https://openway.guance.com",
                        "--app-id",
                        "web_demo",
                        "--temporary-auth-code-stdin",
                        "--client-token-env-file",
                        str(secret_file),
                        "--state-file",
                        str(state_file),
                        "--plan-digest",
                        PLAN_DIGEST,
                        "--allow-external-secret-sink",
                        "--repository",
                        str(repository),
                    ],
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                result = RESOLVER.main()

        rendered = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(0, result)
        self.assertNotIn(temporary_code, rendered)
        self.assertNotIn(client_token, rendered)
        self.assertIn("runtime:RUM_CLIENT_TOKEN", rendered)
        self.assertEqual(temporary_code, resolve_applications.call_args.args[2])

    def test_cli_requires_secret_sink_before_catalog_or_code_access(self):
        stderr = io.StringIO()
        with (
            mock.patch.object(RESOLVER, "resolve_site") as resolve_site,
            mock.patch.object(
                RESOLVER,
                "read_temporary_authorization_code",
            ) as read_code,
            mock.patch.object(
                sys,
                "argv",
                [
                    str(SCRIPT),
                    "--dataway-url",
                    "https://openway.guance.com",
                    "--app-id",
                    "web_demo",
                    "--temporary-auth-code-stdin",
                ],
            ),
            redirect_stderr(stderr),
        ):
            result = RESOLVER.main()

        self.assertEqual(1, result)
        resolve_site.assert_not_called()
        read_code.assert_not_called()
        self.assertIn("Client Token is not discarded", stderr.getvalue())

    def test_cli_requires_state_sink_before_catalog_or_code_access(self):
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            secret_file = repository / ".rum" / "client-token.env"
            with (
                mock.patch.object(RESOLVER, "resolve_site") as resolve_site,
                mock.patch.object(
                    RESOLVER,
                    "read_temporary_authorization_code",
                ) as read_code,
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        str(SCRIPT),
                        "--dataway-url",
                        "https://openway.guance.com",
                        "--app-id",
                        "web_demo",
                        "--client-token-env-file",
                        str(secret_file),
                        "--repository",
                        str(repository),
                    ],
                ),
                redirect_stderr(stderr),
            ):
                result = RESOLVER.main()

        self.assertEqual(1, result)
        resolve_site.assert_not_called()
        read_code.assert_not_called()
        self.assertIn("requires --state-file", stderr.getvalue())

    def test_state_failure_rolls_back_new_secret_sink(self):
        site = RESOLVER.Site(
            brand="guance",
            code="default",
            catalog_url="https://urls.guance.com/",
            dataway_url="https://openway.guance.com",
            ai_api_url="https://ai-api.guance.com",
        )
        metadata = {
            "site": {"code": "default"},
            "applications": {
                "default": {
                    "app_id": "web_demo",
                    "api_app_type": "web",
                    "selected_app_type": "web",
                    "selected_app_type_source": "ai_api",
                    "type_mismatch": False,
                }
            },
            "credential_resolution": {
                "exchange_path": RESOLVER.EXCHANGE_PATH,
                "application_lookup_path": RESOLVER.RUM_APP_GET_PATH,
                "api_key_persistence": "memory_only",
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary).resolve()
            self.init_git(repository)
            (repository / ".gitignore").write_text(".rum/\n", encoding="utf-8")
            secret_file = repository / ".rum" / "client-token.env"
            state_file = repository / ".rum" / "control-plane-state.json"
            stderr = io.StringIO()
            with (
                mock.patch.object(RESOLVER, "resolve_site", return_value=site),
                mock.patch.object(
                    RESOLVER,
                    "preflight_site",
                    return_value={"status": "passed"},
                ),
                mock.patch.object(
                    RESOLVER,
                    "resolve_applications",
                    return_value=(metadata, {"default": "synthetic-client-token"}),
                ),
                mock.patch.object(
                    RESOLVER,
                    "write_state_file",
                    side_effect=RESOLVER.ResolutionError(
                        "control-plane state file could not be created safely"
                    ),
                ),
                mock.patch.object(sys, "stdin", io.StringIO("synthetic-code\n")),
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        str(SCRIPT),
                        "--dataway-url",
                        "https://openway.guance.com",
                        "--app-id",
                        "web_demo",
                        "--temporary-auth-code-stdin",
                        "--client-token-env-file",
                        str(secret_file),
                        "--state-file",
                        str(state_file),
                        "--plan-digest",
                        PLAN_DIGEST,
                        "--repository",
                        str(repository),
                    ],
                ),
                redirect_stderr(stderr),
            ):
                result = RESOLVER.main()

            self.assertEqual(1, result)
            self.assertFalse(secret_file.exists())
            self.assertIn("control-plane state file could not be created", stderr.getvalue())

    def test_network_preflight_runs_before_authorization_code_is_read(self):
        site = RESOLVER.Site(
            brand="guance",
            code="default",
            catalog_url="https://urls.guance.com/",
            dataway_url="https://openway.guance.com",
            ai_api_url="https://ai-api.guance.com",
        )
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary).resolve()
            self.init_git(repository)
            (repository / ".gitignore").write_text(".rum/\n", encoding="utf-8")
            stderr = io.StringIO()
            with (
                mock.patch.object(RESOLVER, "resolve_site", return_value=site),
                mock.patch.object(
                    RESOLVER,
                    "preflight_site",
                    side_effect=RESOLVER.ResolutionError("network preflight failed"),
                ) as preflight,
                mock.patch.object(
                    RESOLVER,
                    "read_temporary_authorization_code",
                ) as read_code,
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        str(SCRIPT),
                        "--dataway-url",
                        "https://openway.guance.com",
                        "--app-id",
                        "web_demo",
                        "--temporary-auth-code-stdin",
                        "--client-token-env-file",
                        str(repository / ".rum" / "client-token.env"),
                        "--state-file",
                        str(repository / ".rum" / "control-plane-state.json"),
                        "--plan-digest",
                        PLAN_DIGEST,
                        "--repository",
                        str(repository),
                    ],
                ),
                redirect_stderr(stderr),
            ):
                result = RESOLVER.main()

        self.assertEqual(1, result)
        preflight.assert_called_once()
        read_code.assert_not_called()
        self.assertIn("network preflight failed", stderr.getvalue())

    def test_environment_source_remains_supported_for_automation(self):
        temporary_code = "  synthetic-environment-code  "

        with mock.patch.dict(
            os.environ,
            {"CUSTOM_RUM_AUTH_CODE": temporary_code},
            clear=False,
        ):
            resolved = RESOLVER.read_temporary_authorization_code(
                environment_name="CUSTOM_RUM_AUTH_CODE",
                from_stdin=False,
            )

        self.assertEqual("synthetic-environment-code", resolved)

    def test_stdin_source_rejects_empty_input_without_echoing_it(self):
        with (
            mock.patch.object(sys, "stdin", io.StringIO("\n")),
            self.assertRaisesRegex(RESOLVER.ResolutionError, "input is empty"),
        ):
            RESOLVER.read_temporary_authorization_code(
                environment_name=None,
                from_stdin=True,
            )

    def test_tty_source_uses_hidden_input(self):
        terminal = mock.Mock()
        terminal.isatty.return_value = True
        temporary_code = "synthetic-hidden-code"

        with (
            mock.patch.object(sys, "stdin", terminal),
            mock.patch.object(
                RESOLVER.getpass,
                "getpass",
                return_value=temporary_code,
            ) as hidden_input,
        ):
            resolved = RESOLVER.read_temporary_authorization_code(
                environment_name=None,
                from_stdin=True,
            )

        self.assertEqual(temporary_code, resolved)
        hidden_input.assert_called_once_with("Temporary authorization code: ")
        terminal.readline.assert_not_called()

    def test_site_only_resolution_does_not_read_authorization_code(self):
        site = RESOLVER.Site(
            brand="guance",
            code="default",
            catalog_url="https://urls.guance.com/",
            dataway_url="https://openway.guance.com",
            ai_api_url="https://ai-api.guance.com",
        )
        stdout = io.StringIO()
        with (
            mock.patch.object(RESOLVER, "resolve_site", return_value=site),
            mock.patch.object(
                RESOLVER,
                "read_temporary_authorization_code",
            ) as read_code,
            mock.patch.object(
                sys,
                "argv",
                [
                    str(SCRIPT),
                    "--dataway-url",
                    "https://openway.guance.com",
                    "--site-only",
                ],
            ),
            redirect_stdout(stdout),
        ):
            result = RESOLVER.main()

        self.assertEqual(0, result)
        read_code.assert_not_called()
        self.assertIn("catalog_resolved", stdout.getvalue())

    def test_cli_requires_repository_for_client_token_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "token.env"
            state = Path(temporary) / "control-plane-state.json"
            stderr = io.StringIO()
            with (
                mock.patch.object(RESOLVER, "resolve_site") as resolve_site,
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        str(SCRIPT),
                        "--dataway-url",
                        "https://openway.guance.com",
                        "--app-id",
                        "web_demo",
                        "--client-token-env-file",
                        str(output),
                        "--state-file",
                        str(state),
                        "--plan-digest",
                        PLAN_DIGEST,
                    ],
                ),
                redirect_stderr(stderr),
            ):
                result = RESOLVER.main()

        self.assertEqual(1, result)
        resolve_site.assert_not_called()
        self.assertIn("requires --repository", stderr.getvalue())

    def test_cli_rejects_state_and_secret_path_collision(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            repository.mkdir()
            shared = Path(temporary) / "shared-output"
            stderr = io.StringIO()
            with (
                mock.patch.object(RESOLVER, "resolve_site") as resolve_site,
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        str(SCRIPT),
                        "--dataway-url",
                        "https://openway.guance.com",
                        "--app-id",
                        "web_demo",
                        "--client-token-env-file",
                        str(shared),
                        "--repository",
                        str(repository),
                        "--state-file",
                        str(shared),
                        "--plan-digest",
                        PLAN_DIGEST,
                    ],
                ),
                redirect_stderr(stderr),
            ):
                result = RESOLVER.main()

        self.assertEqual(1, result)
        resolve_site.assert_not_called()
        self.assertIn("different paths", stderr.getvalue())

    def test_repository_subdirectory_cannot_bypass_ignore_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            repository.mkdir()
            self.init_git(repository)
            subdirectory = repository / "app"
            subdirectory.mkdir()
            output = repository / ".rum" / "client-token.env"

            with self.assertRaisesRegex(
                RESOLVER.ResolutionError,
                "Git worktree root",
            ):
                RESOLVER.write_client_token_env(
                    output,
                    "GUANCE_RUM_CLIENT_TOKEN",
                    "synthetic-client-token",
                    repository=subdirectory,
                )

    def test_existing_secret_sink_is_atomically_upserted(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            self.init_git(repository)
            (repository / ".gitignore").write_text(".env.local\n", encoding="utf-8")
            output = repository / ".env.local"
            output.write_text(
                "UNCHANGED=value\nRUM_CLIENT_TOKEN=old\n",
                encoding="utf-8",
            )
            snapshot = RESOLVER.inspect_secret_sink(
                output,
                sink_format="dotenv",
                keys={"default": "RUM_CLIENT_TOKEN"},
                repository=repository,
                allow_external=False,
            )
            RESOLVER.write_client_tokens_sink(
                snapshot,
                {"default": "RUM_CLIENT_TOKEN"},
                {"default": "new token\nwith newline"},
            )

            self.assertEqual(
                'UNCHANGED=value\nRUM_CLIENT_TOKEN="new token\\nwith newline"\n',
                output.read_text(encoding="utf-8"),
            )
            self.assertEqual(0o600, stat.S_IMODE(output.stat().st_mode))
            RESOLVER.restore_secret_sink(snapshot)
            self.assertEqual(
                "UNCHANGED=value\nRUM_CLIENT_TOKEN=old\n",
                output.read_text(encoding="utf-8"),
            )
            self.assertEqual(
                snapshot.previous_mode,
                stat.S_IMODE(output.stat().st_mode),
            )


if __name__ == "__main__":
    unittest.main()
