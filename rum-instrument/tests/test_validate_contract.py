from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_contract.py"
SPEC = importlib.util.spec_from_file_location("validate_contract", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)

RESOLVER_SCRIPT = SCRIPT.with_name("resolve_rum_application.py")
RESOLVER_SPEC = importlib.util.spec_from_file_location(
    "resolve_rum_application_for_smoke",
    RESOLVER_SCRIPT,
)
assert RESOLVER_SPEC and RESOLVER_SPEC.loader
RESOLVER = importlib.util.module_from_spec(RESOLVER_SPEC)
sys.modules[RESOLVER_SPEC.name] = RESOLVER
RESOLVER_SPEC.loader.exec_module(RESOLVER)


def valid_plan():
    return {
        "schema_version": 2,
        "repository": {
            "root": ".",
            "commit": "abc123",
            "initial_status": [],
        },
        "request": {
            "intent": "plan",
            "application_id_input": {
                "kind": "scalar",
                "reference": {"value": "web_demo"},
            },
            "receiver": {
                "mode": "public_dataway",
                "endpoint": {"source": "template:DATAWAY_URL"},
                "client_tokens": {
                    "web": {
                        "source": "runtime:RUM_CLIENT_TOKEN",
                        "availability": "planned",
                        "sink": {
                            "path": ".rum/client-token.env",
                            "format": "dotenv",
                            "scope": "repository",
                            "key": "RUM_CLIENT_TOKEN",
                        },
                    }
                },
                "control_plane": {
                    "status": "catalog_resolved",
                    "catalog": "https://urls.guance.com/",
                    "site_code": "cn3",
                    "ai_api_endpoint": {"value": "https://cn3-ai-api.guance.com"},
                    "exchange_path": "/api/v1/account/accesskey/exchange",
                    "application_lookup_path": "/api/v1/rum/app/get",
                    "api_key_persistence": "memory_only",
                },
            },
        },
        "targets": [
            {
                "id": "web:.",
                "path": ".",
                "platform": "web",
                "variants": ["browser"],
                "evidence": ["package.json"],
                "application_id_slots": ["web"],
                "application_ids": {"web": {"value": "web_demo"}},
                "application_types": {
                    "web": {
                        "value": "web",
                        "source": "repository",
                        "confidence": "high",
                        "verification": "pending",
                        "api_value": None,
                    }
                },
                "existing_instrumentation": {
                    "status": "none",
                    "files": [],
                    "sdk": None,
                    "version": None,
                    "signals": [],
                },
                "profile": {
                    "signals": {
                        "rum": True,
                        "logs": "preserve",
                        "tracing": "preserve",
                        "replay": False,
                    }
                },
                "receiver_mapping": {},
                "privacy": {},
                "artifacts": {},
                "official_sources": ["https://docs.guance.com/real-user-monitoring/web/app-access/"],
                "disposition": "planned",
                "blockers": [],
            }
        ],
        "planned_changes": [
            {
                "target_id": "web:.",
                "file": "src/rum.ts",
                "order": 1,
                "purpose": "Configure Browser RUM once",
                "edits": ["Add the approved Browser RUM initializer"],
                "dependency_decision": {
                    "action": "preserve",
                    "package": "@cloudcare/browser-rum",
                    "owner": "CloudCare",
                    "version": "existing lockfile version",
                    "official_sources": [
                        "https://docs.guance.com/real-user-monitoring/web/app-access/"
                    ],
                    "compatibility": "preserve the repository-resolved version",
                    "verified_at": "2026-08-04",
                },
                "validation": ["npm test"],
                "risk": "The initializer could run too late",
                "rollback": "Revert src/rum.ts",
            }
        ],
        "validation": [],
        "risks": [],
        "handoff": [],
        "approval": {
            "status": "pending",
            "basis": "plan_only_request",
            "blockers": [],
            "revision": 1,
        },
    }


def resolve_public_dataway(plan):
    control_plane = plan["request"]["receiver"]["control_plane"]
    control_plane["status"] = "resolved"
    control_plane["temporary_authorization_code"] = {"source": "prompt:provided"}
    for token in plan["request"]["receiver"].get("client_tokens", {}).values():
        token["availability"] = "persisted"
    for target in plan["targets"]:
        for descriptor in target.get("application_types", {}).values():
            descriptor["api_value"] = descriptor["value"]
            descriptor["verification"] = "matched"


def valid_control_plane_state(plan):
    return {
        "schema_version": 1,
        "kind": "rum_control_plane_state",
        "plan_digest": VALIDATOR.plan_review_digest(plan),
        "site": {
            "brand": "guance",
            "code": plan["request"]["receiver"]["control_plane"]["site_code"],
            "catalog": plan["request"]["receiver"]["control_plane"]["catalog"],
            "dataway_url": "https://cn3-openway.guance.com",
            "ai_api": plan["request"]["receiver"]["control_plane"][
                "ai_api_endpoint"
            ]["value"],
            "tls_verification": "verified",
        },
        "network_preflight": {
            "status": "passed",
            "dataway": {"status": "reachable", "http_status": 404},
            "ai_api": {"status": "reachable", "http_status": 401},
        },
        "credential_resolution": {
            "status": "resolved",
            "exchange_path": "/api/v1/account/accesskey/exchange",
            "application_lookup_path": "/api/v1/rum/app/get",
            "api_key_persistence": "memory_only",
        },
        "applications": {
            "web": {
                "app_id": "web_demo",
                "api_app_type": "web",
                "selected_app_type": "web",
                "selected_app_type_source": "ai_api",
                "type_mismatch": False,
                "token_expired": False,
                "client_token_available": True,
                "network_attempts": 1,
                "observations": {
                    "mapping_status": "pending",
                    "mapping_ready": False,
                },
            }
        },
        "client_tokens": {
            "web": {
                "source": "runtime:RUM_CLIENT_TOKEN",
                "availability": "persisted",
            }
        },
        "secret_sink": {
            "path": "/tmp/rum-client-token.env",
            "format": "dotenv",
            "scope": "repository",
            "keys": {"web": "RUM_CLIENT_TOKEN"},
        },
    }


def verified_datakit_readiness():
    return {
        "status": "verified",
        "checks": {
            "rum_collector": {
                "status": "verified",
                "evidence": ["DataKit /v1/write/rum collector probe passed"],
                "handoff": [],
            },
            "network_reachability": {
                "status": "verified",
                "evidence": ["application runtime can reach the DataKit origin"],
                "handoff": [],
            },
        },
    }


def approve_revision(plan):
    plan["approval"].update(
        {
            "status": "approved",
            "basis": "revision_review",
            "blockers": [],
            "reviewed_overlaps": [],
        }
    )
    plan["approval"]["reviewed_plan_sha256"] = VALIDATOR.plan_review_digest(plan)


class ValidateContractTests(unittest.TestCase):
    def test_status_path_decodes_git_quoted_unicode(self):
        self.assertEqual(
            "src/监控 rum.ts",
            VALIDATOR._status_path(
                r' M "src/\347\233\221\346\216\247 rum.ts"'
            ),
        )

    def test_accepts_minimal_public_dataway_plan(self):
        errors, warnings = VALIDATOR.validate_plan(valid_plan(), "plan")

        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_rejects_malformed_receiver_origin(self):
        plan = valid_plan()
        plan["request"]["receiver"]["endpoint"] = {
            "value": "https://open way.guance.com"
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("must be an HTTP(S) origin" in error for error in errors))

    def test_ai_api_endpoint_must_be_catalog_matched_literal(self):
        plan = valid_plan()
        plan["request"]["receiver"]["control_plane"]["ai_api_endpoint"] = {
            "source": "runtime:AI_API_ENDPOINT"
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(
            any("literal catalog-matched value" in error for error in errors)
        )

    def test_rejects_legacy_plan_schema(self):
        plan = valid_plan()
        plan["schema_version"] = 1

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertIn("schema_version must be 2", errors)

    def test_resolved_control_plane_allows_discarded_code_and_requires_routed_token(self):
        plan = valid_plan()
        control_plane = plan["request"]["receiver"]["control_plane"]
        control_plane["status"] = "resolved"
        plan["request"]["receiver"]["client_tokens"]["web"][
            "availability"
        ] = "persisted"
        descriptor = plan["targets"][0]["application_types"]["web"]
        descriptor.update({"verification": "matched", "api_value": "web"})

        errors, _ = VALIDATOR.validate_plan(plan, "plan")
        self.assertEqual([], errors)

        control_plane["temporary_authorization_code"] = {
            "source": "prompt:provided"
        }
        errors, _ = VALIDATOR.validate_plan(plan, "plan")
        self.assertEqual([], errors)

    def test_catalog_status_rejects_persisted_token_availability(self):
        plan = valid_plan()
        plan["request"]["receiver"]["client_tokens"]["web"][
            "availability"
        ] = "persisted"

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(
            any(
                "availability must be planned or existing when control_plane.status=catalog_resolved"
                in error
                for error in errors
            )
        )

    def test_accepts_built_in_testing_site_and_tls_exception(self):
        plan = valid_plan()
        control_plane = plan["request"]["receiver"]["control_plane"]
        control_plane.update(
            {
                "catalog": "builtin_testing",
                "site_code": "testing",
                "ai_api_endpoint": {
                    "value": "https://testing-ft2x-ai-api.dataflux.cn"
                },
                "test_only": True,
                "tls_verification": "disabled_for_testing",
            }
        )

        errors, warnings = VALIDATOR.validate_plan(plan, "plan")

        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_rejects_tls_exception_for_an_official_catalog(self):
        plan = valid_plan()
        plan["request"]["receiver"]["control_plane"][
            "tls_verification"
        ] = "disabled_for_testing"

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(
            any("must remain verified for official catalogs" in error for error in errors)
        )

    def test_built_in_testing_site_requires_test_only(self):
        plan = valid_plan()
        control_plane = plan["request"]["receiver"]["control_plane"]
        control_plane.update(
            {
                "catalog": "builtin_testing",
                "site_code": "testing",
                "ai_api_endpoint": {
                    "value": "https://testing-ft2x-ai-api.dataflux.cn"
                },
            }
        )

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any(".test_only must be true" in error for error in errors))

    def test_rejects_any_other_testing_ai_api(self):
        plan = valid_plan()
        control_plane = plan["request"]["receiver"]["control_plane"]
        control_plane.update(
            {
                "catalog": "builtin_testing",
                "site_code": "testing",
                "test_only": True,
                "tls_verification": "disabled_for_testing",
                "ai_api_endpoint": {
                    "value": "https://testing-ai-api.dataflux.cn"
                },
            }
        )

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(
            any("must be https://testing-ft2x-ai-api.dataflux.cn" in error for error in errors)
        )

    def test_plan_only_request_requires_revision_review_for_implementation(self):
        errors, _ = VALIDATOR.validate_plan(valid_plan(), "implement")

        self.assertIn("implementation requires approval.status=approved", errors)

        plan = valid_plan()
        resolve_public_dataway(plan)
        approve_revision(plan)
        errors, _ = VALIDATOR.validate_plan(plan, "implement")
        self.assertEqual([], errors)

    def test_explicit_implementation_request_is_pre_authorized(self):
        plan = valid_plan()
        plan["request"]["intent"] = "implement"
        plan["approval"].update(
            {
                "status": "approved",
                "basis": "explicit_implementation_request",
            }
        )
        resolve_public_dataway(plan)

        errors, _ = VALIDATOR.validate_plan(plan, "implement")

        self.assertEqual([], errors)

    def test_control_plane_state_keeps_mapping_observations_out_of_the_gate(self):
        plan = valid_plan()
        state = valid_control_plane_state(plan)
        state["applications"]["web"]["observations"] = {
            "client_token_sync_status": "failed",
            "mapping_status": "failed",
            "mapping_ready": False,
        }

        errors, warnings = VALIDATOR.validate_control_plane_state(state, plan)

        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_control_plane_state_requires_only_a_current_persisted_token(self):
        plan = valid_plan()
        state = valid_control_plane_state(plan)

        state["applications"]["web"]["token_expired"] = True
        errors, _ = VALIDATOR.validate_control_plane_state(state, plan)
        self.assertTrue(any("token_expired must be false" in error for error in errors))

        state = valid_control_plane_state(plan)
        state["applications"]["web"]["client_token_available"] = False
        errors, _ = VALIDATOR.validate_control_plane_state(state, plan)
        self.assertTrue(
            any("client_token_available must be true" in error for error in errors)
        )

    def test_control_plane_state_is_bound_to_the_stable_plan_digest(self):
        plan = valid_plan()
        state = valid_control_plane_state(plan)
        plan["planned_changes"][0]["file"] = "src/monitoring/rum.ts"

        errors, _ = VALIDATOR.validate_control_plane_state(state, plan)

        self.assertIn(
            "control-plane state plan_digest does not match this plan",
            errors,
        )

    def test_control_plane_state_is_bound_to_application_id_and_sink(self):
        plan = valid_plan()
        state = valid_control_plane_state(plan)
        state["applications"]["web"]["app_id"] = "different_application"
        state["secret_sink"]["keys"]["web"] = "OTHER_CLIENT_TOKEN"
        state["secret_sink"]["format"] = "json"

        errors, _ = VALIDATOR.validate_control_plane_state(state, plan)

        self.assertTrue(any(".app_id does not match" in error for error in errors))
        self.assertTrue(any("secret_sink.keys.web" in error for error in errors))
        self.assertTrue(any("secret_sink.format does not match" in error for error in errors))

        state = valid_control_plane_state(plan)
        state.pop("secret_sink")
        errors, _ = VALIDATOR.validate_control_plane_state(state, plan)
        self.assertIn("control-plane state secret_sink must be an object", errors)

    def test_control_plane_state_requires_concrete_application_id(self):
        plan = valid_plan()
        plan["request"]["application_id_input"]["reference"] = {
            "source": "template:APP_ID"
        }
        plan["targets"][0]["application_ids"]["web"] = {
            "source": "template:APP_ID"
        }
        state = valid_control_plane_state(plan)

        errors, _ = VALIDATOR.validate_control_plane_state(state, plan)

        self.assertTrue(
            any("requires a concrete Application ID" in error for error in errors)
        )

    def test_external_client_token_sink_requires_revision_review(self):
        plan = valid_plan()
        plan["request"]["intent"] = "implement"
        plan["request"]["receiver"]["client_tokens"]["web"]["sink"].update(
            {
                "path": "/tmp/rum-client-token.env",
                "scope": "external",
            }
        )
        plan["approval"].update(
            {
                "status": "approved",
                "basis": "explicit_implementation_request",
            }
        )

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("external Client Token sink" in error for error in errors))

    def test_control_plane_state_validates_real_ignored_sink(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            (repository / ".gitignore").write_text(".rum/\n", encoding="utf-8")
            (repository / "package.json").write_text("{}\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.com",
                    "commit",
                    "-qm",
                    "baseline",
                ],
                check=True,
            )
            sink = repository / ".rum" / "runtime.json"
            sink.parent.mkdir()
            sink.write_text(
                '{"RUM_CLIENT_TOKEN":"redacted-test-value"}\n',
                encoding="utf-8",
            )
            os.chmod(sink, 0o600)
            state_path = repository / ".rum" / "control-plane-state.json"
            state_path.write_text("{}\n", encoding="utf-8")
            os.chmod(state_path, 0o600)

            plan = valid_plan()
            plan["request"]["receiver"]["client_tokens"]["web"]["sink"].update(
                {
                    "path": ".rum/runtime.json",
                    "format": "json",
                }
            )
            state = valid_control_plane_state(plan)
            state["secret_sink"] = {
                "path": str(sink.resolve()),
                "format": "json",
                "scope": "repository",
                "keys": {"web": "RUM_CLIENT_TOKEN"},
            }

            errors, _ = VALIDATOR.validate_control_plane_state(
                state,
                plan,
                repository=repository,
                state_path=state_path,
            )

            self.assertEqual([], errors)

    def test_public_dataway_resolution_to_implementation_smoke(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            (repository / ".gitignore").write_text(".rum/\n", encoding="utf-8")
            (repository / "package.json").write_text("{}\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.com",
                    "commit",
                    "-qm",
                    "baseline",
                ],
                check=True,
            )
            commit = subprocess.run(
                ["git", "-C", str(repository), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            plan = valid_plan()
            plan["repository"]["commit"] = commit
            plan["request"]["intent"] = "implement"
            plan["request"]["receiver"]["client_tokens"]["web"]["sink"].update(
                {
                    "path": ".rum/runtime.json",
                    "format": "json",
                }
            )
            plan["approval"].update(
                {
                    "status": "approved",
                    "basis": "explicit_implementation_request",
                }
            )

            site = RESOLVER.Site(
                brand="catalog_a",
                code="cn3",
                catalog_url="https://urls.guance.com/",
                dataway_url="https://cn3-openway.guance.com",
                ai_api_url="https://cn3-ai-api.guance.com",
            )

            def poster(url, body, headers, operation):
                if url.endswith(RESOLVER.EXCHANGE_PATH):
                    return {"success": True, "data": {"item": {"sk": "api-key"}}}
                return {
                    "success": True,
                    "data": {
                        "item": {
                            "app_id": body["app_id"],
                            "app_type": "web",
                            "token_expired": False,
                            "client_token": "token with spaces",
                            "mapping_ready": False,
                        }
                    },
                }

            metadata, client_tokens = RESOLVER.resolve_applications(
                site,
                {"web": "web_demo"},
                "one-time-code",
                json_poster=poster,
            )
            metadata["network_preflight"] = {
                "status": "passed",
                "dataway": {"status": "reachable", "http_status": 404},
                "ai_api": {"status": "reachable", "http_status": 401},
            }
            sink = repository / ".rum" / "runtime.json"
            state_path = repository / ".rum" / "control-plane-state.json"
            snapshot = RESOLVER.inspect_secret_sink(
                sink,
                sink_format="json",
                keys={"web": "RUM_CLIENT_TOKEN"},
                repository=repository,
                allow_external=False,
            )
            state = RESOLVER.build_safe_result(
                metadata,
                plan_digest=VALIDATOR.plan_review_digest(plan),
                client_token_keys={"web": "RUM_CLIENT_TOKEN"},
                secret_file=snapshot.path,
                sink_format=snapshot.sink_format,
                sink_scope=snapshot.scope,
            )
            RESOLVER.write_client_tokens_sink(
                snapshot,
                {"web": "RUM_CLIENT_TOKEN"},
                client_tokens,
            )
            RESOLVER.write_state_file(
                state_path,
                json.dumps(state, ensure_ascii=False, sort_keys=True),
            )

            plan_errors, _ = VALIDATOR.validate_plan(plan, "implement")
            repository_errors = VALIDATOR.validate_repository_state(
                plan,
                repository,
            )
            state_errors, _ = VALIDATOR.validate_control_plane_state(
                state,
                plan,
                repository=repository,
                state_path=state_path,
            )

            self.assertEqual([], plan_errors)
            self.assertEqual([], repository_errors)
            self.assertEqual([], state_errors)

    def test_rejects_inconsistent_approval_status_and_basis(self):
        plan = valid_plan()
        plan["approval"]["basis"] = "revision_review"

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertIn(
            "approval.basis=revision_review requires approval.status=approved",
            errors,
        )

        plan["approval"].update(
            {
                "status": "approved",
                "basis": "plan_only_request",
            }
        )
        errors, _ = VALIDATOR.validate_plan(plan, "plan")
        self.assertIn(
            "approval.basis=plan_only_request requires approval.status=pending",
            errors,
        )

    def test_explicit_implementation_request_pauses_when_blocked(self):
        plan = valid_plan()
        plan["request"]["intent"] = "implement"
        plan["targets"][0]["disposition"] = "blocked"
        plan["targets"][0]["blockers"] = ["Application type mismatch requires review"]
        plan["request"]["receiver"]["client_tokens"] = {}
        plan["planned_changes"] = []
        plan["approval"].update(
            {
                "status": "pending",
                "basis": "explicit_implementation_request",
                "blockers": ["Application type mismatch requires review"],
            }
        )

        plan_errors, _ = VALIDATOR.validate_plan(plan, "plan")
        implementation_errors, _ = VALIDATOR.validate_plan(plan, "implement")

        self.assertEqual([], plan_errors)
        self.assertIn(
            "implementation requires approval.status=approved",
            implementation_errors,
        )
        self.assertTrue(
            any(
                "implementation cannot start while blockers remain" in error
                for error in implementation_errors
            )
        )

    def test_material_risk_requires_revision_review(self):
        plan = valid_plan()
        plan["request"]["intent"] = "implement"
        plan["approval"].update(
            {
                "status": "approved",
                "basis": "explicit_implementation_request",
            }
        )
        plan["planned_changes"][0]["dependency_decision"]["action"] = "upgrade"

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(
            any(
                "explicit implementation authorization cannot cover material-risk changes"
                in error
                for error in errors
            )
        )

        resolve_public_dataway(plan)
        approve_revision(plan)
        errors, _ = VALIDATOR.validate_plan(plan, "implement")
        self.assertEqual([], errors)

    def test_new_optional_signal_requires_revision_review(self):
        plan = valid_plan()
        plan["request"]["intent"] = "implement"
        plan["approval"].update(
            {
                "status": "approved",
                "basis": "explicit_implementation_request",
            }
        )
        plan["targets"][0]["profile"]["signals"]["replay"] = True

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(
            any(
                "new optional signal replay" in error
                for error in errors
            )
        )

        plan["approval"].update(
            {
                "status": "pending",
                "basis": "explicit_implementation_request",
                "blockers": ["New Session Replay scope requires review"],
            }
        )
        errors, _ = VALIDATOR.validate_plan(plan, "plan")
        self.assertEqual([], errors)

        resolve_public_dataway(plan)
        approve_revision(plan)
        errors, _ = VALIDATOR.validate_plan(plan, "implement")
        self.assertEqual([], errors)

    def test_native_crash_signal_requires_revision_review(self):
        plan = valid_plan()
        plan["request"]["intent"] = "implement"
        plan["approval"].update(
            {
                "status": "approved",
                "basis": "explicit_implementation_request",
            }
        )
        plan["targets"][0]["profile"]["signals"]["native_crash"] = True

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(
            any("new optional signal native_crash" in error for error in errors)
        )

    def test_rejects_unknown_signal_and_recursive_decision_object(self):
        plan = valid_plan()
        plan["targets"][0]["profile"]["signals"]["performance_magic"] = {
            "nested": {"enabled": True}
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("is not a supported signal" in error for error in errors))

        plan = valid_plan()
        plan["targets"][0]["existing_instrumentation"]["signals"] = [
            "performance_magic"
        ]
        errors, _ = VALIDATOR.validate_plan(plan, "plan")
        self.assertTrue(any("contains unsupported signal" in error for error in errors))

    def test_planned_target_requires_core_rum(self):
        plan = valid_plan()
        plan["targets"][0]["profile"]["signals"]["rum"] = False

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(
            any("profile.signals.rum must be enabled" in error for error in errors)
        )

    def test_rejects_contradictory_artifact_controls(self):
        plan = valid_plan()
        plan["targets"][0]["artifacts"]["sourcemaps"] = {
            "status": "existing",
            "upload": True,
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(
            any("exactly one status or action control field" in error for error in errors)
        )

        plan = valid_plan()
        plan["targets"][0]["profile"]["signals"]["replay"] = {"status": True}
        plan["targets"][0]["artifacts"]["sourcemaps"] = {"action": True}
        errors, _ = VALIDATOR.validate_plan(plan, "plan")
        self.assertGreaterEqual(
            sum("status must be a non-empty string" in error for error in errors),
            2,
        )

    def test_application_type_mismatch_requires_revision_review(self):
        plan = valid_plan()
        plan["request"]["intent"] = "implement"
        plan["approval"].update(
            {
                "status": "approved",
                "basis": "explicit_implementation_request",
            }
        )
        descriptor = plan["targets"][0]["application_types"]["web"]
        descriptor.update(
            {
                "value": "web",
                "source": "user",
                "verification": "mismatched",
                "api_value": "custom",
            }
        )

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(
            any("user application type differs from AI API" in error for error in errors)
        )

    def test_revision_review_digest_binds_exact_plan(self):
        plan = valid_plan()
        resolve_public_dataway(plan)
        approve_revision(plan)

        errors, _ = VALIDATOR.validate_plan(plan, "plan")
        self.assertEqual([], errors)

        plan["planned_changes"][0]["purpose"] = "A different change after review"
        errors, _ = VALIDATOR.validate_plan(plan, "plan")
        self.assertTrue(
            any("reviewed_plan_sha256 does not match" in error for error in errors)
        )

    def test_existing_optional_signal_does_not_require_revision_review(self):
        plan = valid_plan()
        plan["request"]["intent"] = "implement"
        plan["approval"].update(
            {
                "status": "approved",
                "basis": "explicit_implementation_request",
            }
        )
        plan["targets"][0]["existing_instrumentation"]["signals"] = ["replay"]
        plan["targets"][0]["profile"]["signals"]["replay"] = True
        resolve_public_dataway(plan)

        errors, _ = VALIDATOR.validate_plan(plan, "implement")

        self.assertEqual([], errors)

    def test_new_release_artifact_requires_revision_review(self):
        plan = valid_plan()
        plan["request"]["intent"] = "implement"
        plan["approval"].update(
            {
                "status": "approved",
                "basis": "explicit_implementation_request",
            }
        )
        plan["targets"][0]["artifacts"] = {
            "sourcemaps": {"action": "generate"}
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(
            any(
                "new release artifact scope sourcemaps" in error
                for error in errors
            )
        )

    def test_existing_release_artifact_does_not_require_revision_review(self):
        plan = valid_plan()
        plan["request"]["intent"] = "implement"
        plan["approval"].update(
            {
                "status": "approved",
                "basis": "explicit_implementation_request",
            }
        )
        plan["targets"][0]["artifacts"] = {
            "sourcemaps": {
                "status": "existing",
                "path": "dist/assets/*.map",
            }
        }
        resolve_public_dataway(plan)

        errors, _ = VALIDATOR.validate_plan(plan, "implement")

        self.assertEqual([], errors)

    def test_built_in_testing_site_requires_revision_review(self):
        plan = valid_plan()
        plan["request"]["intent"] = "implement"
        plan["approval"].update(
            {
                "status": "approved",
                "basis": "explicit_implementation_request",
            }
        )
        control_plane = plan["request"]["receiver"]["control_plane"]
        control_plane.update(
            {
                "catalog": "builtin_testing",
                "site_code": "testing",
                "ai_api_endpoint": {
                    "value": "https://testing-ft2x-ai-api.dataflux.cn"
                },
                "test_only": True,
                "tls_verification": "disabled_for_testing",
            }
        )

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(
            any("testing control-plane override" in error for error in errors)
        )

    def test_rejects_empty_changes_for_a_planned_target(self):
        plan = valid_plan()
        plan["planned_changes"] = []

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("planned_changes must not be empty" in error for error in errors))

    def test_rejects_incomplete_or_unmatched_planned_changes(self):
        plan = valid_plan()
        plan["planned_changes"] = [
            {
                "target_id": "web:missing",
                "file": "dist/rum.js",
                "order": 0,
                "purpose": "",
                "edits": [],
                "dependency_decision": {},
                "validation": [],
                "risk": "",
                "rollback": "",
            }
        ]

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("unknown target_id" in error for error in errors))
        self.assertTrue(any("generated or dependency directory" in error for error in errors))
        self.assertTrue(any(".order must be a positive integer" in error for error in errors))
        self.assertTrue(any(".edits must be a non-empty array" in error for error in errors))
        self.assertTrue(any(".dependency_decision.action" in error for error in errors))
        self.assertTrue(any("has no planned change" in error for error in errors))

    def test_rejects_repository_control_paths(self):
        plan = valid_plan()
        plan["planned_changes"][0]["file"] = ".git/hooks/post-checkout"

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(
            any("repository control directory" in error for error in errors)
        )

        plan["planned_changes"][0]["file"] = ".github/skills/rum/SKILL.md"
        errors, _ = VALIDATOR.validate_plan(plan, "plan")
        self.assertTrue(
            any("Agent Skill control directory" in error for error in errors)
        )

    def test_dependency_add_requires_complete_provenance(self):
        plan = valid_plan()
        plan["planned_changes"][0]["dependency_decision"] = {"action": "add"}

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        for field in (
            "package",
            "owner",
            "version",
            "official_sources",
            "compatibility",
            "verified_at",
        ):
            self.assertTrue(
                any(f"dependency_decision.{field}" in error for error in errors),
                field,
            )

    def test_rejects_client_token_value(self):
        plan = valid_plan()
        plan["request"]["receiver"]["client_tokens"]["web"] = {
            "value": "must-not-be-persisted"
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("client_token" in error for error in errors))
        self.assertTrue(any("never contain a value" in error for error in errors))

    def test_rejects_client_token_literal_disguised_as_runtime_reference(self):
        plan = valid_plan()
        plan["request"]["receiver"]["client_tokens"]["web"]["source"] = (
            "runtime:synthetic-client-token-literal"
        )

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(
            any(
                "structured env, existing, or runtime reference" in error
                for error in errors
            )
        )

    def test_rejects_user_supplied_client_token_template(self):
        plan = valid_plan()
        plan["request"]["receiver"]["client_tokens"]["web"] = {
            "source": "template:CLIENT_TOKEN"
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("env, existing, or runtime" in error for error in errors))

    def test_rejects_prompt_provided_client_token(self):
        plan = valid_plan()
        plan["request"]["receiver"]["client_tokens"]["web"] = {
            "source": "prompt:provided"
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("env, existing, or runtime" in error for error in errors))

    def test_rejects_prompt_provided_marker_for_nested_client_token(self):
        plan = valid_plan()
        plan["targets"][0]["receiver_mapping"] = {
            "clientToken": {"source": "prompt:provided"}
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(
            any(
                "receiver_mapping.clientToken must contain only a non-secret source reference"
                in error
                for error in errors
            )
        )

    def test_rejects_authorization_code_embedded_in_prompt_reference(self):
        plan = valid_plan()
        plan["request"]["receiver"]["control_plane"]["temporary_authorization_code"] = {
            "source": "prompt:synthetic-temporary-code"
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("prompt:provided" in error for error in errors))

    def test_rejects_temporary_authorization_code_value_without_echoing_it(self):
        plan = valid_plan()
        secret = "synthetic-temporary-code"
        plan["request"]["receiver"]["control_plane"]["temporary_authorization_code"] = {
            "value": secret
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")
        rendered = "\n".join(errors)

        self.assertIn("temporary_authorization_code", rendered)
        self.assertNotIn(secret, rendered)

    def test_requires_resolved_public_dataway_control_plane_contract(self):
        plan = valid_plan()
        del plan["request"]["receiver"]["control_plane"]

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("control_plane must be an object" in error for error in errors))

    def test_rejects_nested_sensitive_values_without_echoing_them(self):
        plan = valid_plan()
        secret = "synthetic-secret-for-validator-test"
        plan["targets"][0]["receiver_mapping"] = {
            "clientToken": {"value": secret},
            "headers": {"Authorization": f"Bearer {secret}"},
        }
        plan["handoff"] = [{"cookie": secret}]

        errors, _ = VALIDATOR.validate_plan(plan, "plan")
        rendered = "\n".join(errors)

        self.assertIn("targets[0].receiver_mapping.clientToken", rendered)
        self.assertIn("targets[0].receiver_mapping.headers.Authorization", rendered)
        self.assertIn("handoff[0].cookie", rendered)
        self.assertNotIn(secret, rendered)

    def test_accepts_nested_sensitive_source_references(self):
        plan = valid_plan()
        plan["targets"][0]["receiver_mapping"] = {
            "clientToken": {
                "input": "runtime:GUANCE_RUM_CLIENT_TOKEN",
                "runtime": "runtime:DEPLOYCONFIG.rumClientToken",
                "persistence": "deployment only",
            },
            "headers": {"Authorization": "runtime:RUM_AUTHORIZATION"},
        }
        plan["targets"][0]["privacy"] = {
            "cookies": "disabled",
            "requestBody": "not_collected",
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertEqual([], errors)

    def test_rejects_persisted_request_or_response_bodies(self):
        plan = valid_plan()
        plan["handoff"] = [{"requestBody": {"source": "runtime:PAYLOAD"}}]

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("handoff[0].requestBody must not be persisted" in error for error in errors))

    def test_rejects_conflicting_raw_prompt_fields(self):
        plan = valid_plan()
        plan["request"]["receiver"]["datakitUrl"] = {"source": "template:DATAKIT_URL"}

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("raw prompt fields" in error for error in errors))

    def test_missing_platform_id_is_allowed_only_when_blocked(self):
        plan = valid_plan()
        plan["request"]["application_id_input"] = {
            "kind": "map",
            "references": {
                "android": {"source": "template:ANDROID_APP_ID"},
                "ios": {"source": "template:IOS_APP_ID"},
            },
        }
        target = plan["targets"][0]
        target["platform"] = "flutter"
        target["application_id_slots"] = ["android", "ios"]
        target["application_ids"] = {"android": {"source": "template:ANDROID_APP_ID"}}
        target["application_types"] = {
            "android": {
                "value": "android",
                "source": "ai_api",
                "confidence": "high",
                "verification": "pending",
                "api_value": None,
            },
            "ios": {
                "value": "ios",
                "source": "ai_api",
                "confidence": "high",
                "verification": "pending",
                "api_value": None,
            },
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")
        self.assertTrue(any("missing slot ios" in error for error in errors))

        target["disposition"] = "blocked"
        target["blockers"] = ["Missing Application ID slot: ios"]
        plan["planned_changes"] = []
        plan["request"]["receiver"]["client_tokens"] = {}
        errors, warnings = VALIDATOR.validate_plan(plan, "plan")
        self.assertEqual([], errors)
        self.assertTrue(any("slot ios" in warning for warning in warnings))

    def test_datakit_omits_client_token(self):
        plan = valid_plan()
        plan["request"]["receiver"] = {
            "mode": "datakit",
            "endpoint": {"source": "template:DATAKIT_URL"},
            "readiness": verified_datakit_readiness(),
        }
        plan["targets"][0]["application_types"]["web"].update(
            {
                "source": "repository",
                "verification": "not_applicable",
                "api_value": None,
            }
        )

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertEqual([], errors)

    def test_datakit_unknown_readiness_warns_but_allows_implementation(self):
        plan = valid_plan()
        plan["request"]["intent"] = "implement"
        plan["request"]["receiver"] = {
            "mode": "datakit",
            "endpoint": {"source": "template:DATAKIT_URL"},
            "readiness": {
                "status": "unknown",
                "checks": {
                    check: {
                        "status": "unknown",
                        "evidence": [],
                        "handoff": [f"Verify {check} before implementation"],
                    }
                    for check in ("rum_collector", "network_reachability")
                },
            },
        }
        plan["targets"][0]["application_types"]["web"].update(
            {
                "verification": "not_applicable",
                "api_value": None,
            }
        )
        plan["approval"].update(
            {
                "status": "approved",
                "basis": "explicit_implementation_request",
                "blockers": [],
            }
        )

        plan_errors, plan_warnings = VALIDATOR.validate_plan(plan, "plan")
        implementation_errors, implementation_warnings = VALIDATOR.validate_plan(
            plan, "implement"
        )

        self.assertEqual([], plan_errors)
        self.assertEqual([], implementation_errors)
        self.assertTrue(
            any("readiness is not verified" in warning for warning in implementation_warnings)
        )
        self.assertEqual([], plan_warnings)

    def test_datakit_readiness_is_optional(self):
        plan = valid_plan()
        plan["request"]["intent"] = "implement"
        plan["request"]["receiver"] = {
            "mode": "datakit",
            "endpoint": {"source": "template:DATAKIT_URL"},
        }
        plan["targets"][0]["application_types"]["web"].update(
            {
                "verification": "not_applicable",
                "api_value": None,
            }
        )
        plan["approval"].update(
            {
                "status": "approved",
                "basis": "explicit_implementation_request",
            }
        )

        errors, warnings = VALIDATOR.validate_plan(plan, "implement")

        self.assertEqual([], errors)
        self.assertTrue(any("readiness is not recorded" in warning for warning in warnings))

    def test_datakit_rejects_public_control_plane_fields(self):
        plan = valid_plan()
        plan["request"]["receiver"]["mode"] = "datakit"
        plan["request"]["receiver"].pop("client_tokens")

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("control_plane is valid only" in error for error in errors))

    def test_requires_application_type_value_and_source(self):
        plan = valid_plan()
        plan["targets"][0]["application_types"]["web"] = {
            "value": "flutter",
            "source": "guess",
            "confidence": "certain",
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("supported RUM application type" in error for error in errors))
        self.assertTrue(any("source must be user, ai_api, or repository" in error for error in errors))
        self.assertTrue(any("confidence must be high, medium, or low" in error for error in errors))

    def test_rejects_reused_application_id_reference(self):
        plan = valid_plan()
        plan["request"]["application_id_input"] = {
            "kind": "map",
            "references": {
                "android": {"source": "template:APP_ID"},
                "ios": {"source": "template:IOS_APP_ID"},
            },
        }
        target = plan["targets"][0]
        target["platform"] = "flutter"
        target["application_id_slots"] = ["android", "ios"]
        target["application_ids"] = {
            "android": {"source": "template:APP_ID"},
            "ios": {"source": "template:APP_ID"},
        }
        target["application_types"] = {
            "android": {
                "value": "android",
                "source": "ai_api",
                "confidence": "high",
                "verification": "pending",
                "api_value": None,
            },
            "ios": {
                "value": "ios",
                "source": "ai_api",
                "confidence": "high",
                "verification": "pending",
                "api_value": None,
            },
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("reuses the Application ID reference" in error for error in errors))

    def test_rejects_assigning_a_scalar_id_when_multiple_slots_are_unresolved(self):
        plan = valid_plan()
        first = plan["targets"][0]
        first["id"] = "web:apps/admin"
        first["path"] = "apps/admin"
        plan["planned_changes"][0]["target_id"] = first["id"]
        plan["planned_changes"][0]["file"] = "apps/admin/src/main.jsx"

        second = copy.deepcopy(first)
        second["id"] = "web:apps/portal"
        second["path"] = "apps/portal"
        second["application_ids"] = {}
        second["disposition"] = "blocked"
        second["blockers"] = ["Missing Application ID slot: web"]
        plan["targets"].append(second)
        plan["request"]["receiver"]["client_tokens"] = {
            "web": {
                "source": "runtime:GUANCE_RUM_CLIENT_TOKEN",
                "availability": "planned",
            }
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("scalar is ambiguous" in error for error in errors))

    def test_accepts_unassigned_scalar_when_all_ambiguous_slots_are_blocked(self):
        plan = valid_plan()
        first = plan["targets"][0]
        first["id"] = "web:apps/admin"
        first["path"] = "apps/admin"
        first["application_ids"] = {}
        first["disposition"] = "blocked"
        first["blockers"] = ["Missing Application ID slot: web; scalar input is ambiguous"]

        second = copy.deepcopy(first)
        second["id"] = "web:apps/portal"
        second["path"] = "apps/portal"
        plan["targets"].append(second)
        plan["planned_changes"] = []
        plan["request"]["receiver"]["client_tokens"] = {}

        errors, warnings = VALIDATOR.validate_plan(plan, "plan")

        self.assertEqual([], errors)
        self.assertTrue(any("scalar Application ID input remains unassigned" in warning for warning in warnings))

    def test_rejects_client_token_slot_that_does_not_match_active_target(self):
        plan = valid_plan()
        plan["request"]["receiver"]["client_tokens"] = {
            "wrong": {
                "source": "runtime:GUANCE_RUM_CLIENT_TOKEN_WRONG",
                "availability": "planned",
            }
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("missing active Application ID slots: web" in error for error in errors))
        self.assertTrue(any("unknown or blocked slots: wrong" in error for error in errors))

    def test_blocked_control_plane_allows_no_client_tokens(self):
        plan = valid_plan()
        plan["request"]["receiver"].pop("client_tokens")
        plan["request"]["receiver"]["control_plane"] = {
            "status": "blocked",
            "api_key_persistence": "memory_only",
            "blockers": ["Public DataWay site is not in an approved catalog"],
        }
        plan["targets"][0]["disposition"] = "blocked"
        plan["targets"][0]["blockers"] = ["Receiver resolution is blocked"]
        plan["planned_changes"] = []

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertEqual([], errors)

    def test_rejects_duplicate_active_slot_names_across_targets(self):
        plan = valid_plan()
        second = copy.deepcopy(plan["targets"][0])
        second["id"] = "web:apps/portal"
        second["path"] = "apps/portal"
        second["application_ids"]["web"] = {"source": "template:PORTAL_APP_ID"}
        plan["targets"].append(second)
        second_change = copy.deepcopy(plan["planned_changes"][0])
        second_change["target_id"] = second["id"]
        second_change["file"] = "apps/portal/src/rum.ts"
        second_change["order"] = 2
        plan["planned_changes"].append(second_change)

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(any("target-specific slot names" in error for error in errors))

    def test_public_dataway_cpp_target_must_be_blocked(self):
        plan = valid_plan()
        target = plan["targets"][0]
        target.update(
            {
                "id": "cpp:apps/desktop",
                "path": "apps/desktop",
                "platform": "cpp",
                "variants": ["windows-linux"],
                "application_id_slots": ["cpp"],
                "application_ids": {
                    "cpp": {"source": "template:APP_ID"}
                },
                "application_types": {
                    "cpp": {
                        "value": "custom",
                        "source": "repository",
                        "confidence": "high",
                        "verification": "pending",
                        "api_value": None,
                    }
                },
            }
        )
        plan["planned_changes"][0]["target_id"] = target["id"]
        plan["planned_changes"][0]["file"] = "apps/desktop/src/rum.cpp"
        plan["request"]["receiver"]["client_tokens"] = {
            "cpp": {
                "source": "runtime:GUANCE_RUM_CLIENT_TOKEN_CPP",
                "availability": "planned",
            }
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertTrue(
            any("current C++ adapter supports only DataKit" in error for error in errors)
        )

        target["disposition"] = "blocked"
        target["blockers"] = ["C++ Public DataWay is unsupported; provide datakitUrl"]
        plan["planned_changes"] = []
        plan["request"]["receiver"]["client_tokens"] = {}
        errors, _ = VALIDATOR.validate_plan(plan, "plan")
        self.assertEqual([], errors)

    def test_datakit_cpp_target_is_supported(self):
        plan = valid_plan()
        receiver = plan["request"]["receiver"]
        receiver["mode"] = "datakit"
        receiver.pop("client_tokens")
        receiver.pop("control_plane")
        receiver["readiness"] = verified_datakit_readiness()
        target = plan["targets"][0]
        target.update(
            {
                "id": "cpp:.",
                "platform": "cpp",
                "variants": ["windows-linux"],
                "application_id_slots": ["cpp"],
                "application_ids": {
                    "cpp": {"source": "template:APP_ID"}
                },
                "application_types": {
                    "cpp": {
                        "value": "custom",
                        "source": "repository",
                        "confidence": "high",
                        "verification": "not_applicable",
                        "api_value": None,
                    }
                },
            }
        )
        plan["planned_changes"][0]["target_id"] = "cpp:."
        plan["planned_changes"][0]["file"] = "src/rum.cpp"

        errors, _ = VALIDATOR.validate_plan(plan, "plan")

        self.assertEqual([], errors)

    def test_macos_application_type_is_custom(self):
        plan = valid_plan()
        target = plan["targets"][0]
        target.update(
            {
                "id": "apple:.",
                "platform": "apple",
                "variants": ["macos"],
                "application_id_slots": ["macos"],
                "application_ids": {
                    "macos": {"source": "template:APP_ID"}
                },
                "application_types": {
                    "macos": {
                        "value": "ios",
                        "source": "repository",
                        "confidence": "high",
                        "verification": "pending",
                        "api_value": None,
                    }
                },
            }
        )
        plan["planned_changes"][0]["target_id"] = "apple:."
        plan["planned_changes"][0]["file"] = "Sources/main.swift"
        plan["request"]["receiver"]["client_tokens"] = {
            "macos": {
                "source": "runtime:GUANCE_RUM_CLIENT_TOKEN_MACOS",
                "availability": "planned",
                "sink": {
                    "path": ".rum/client-token.env",
                    "format": "dotenv",
                    "scope": "repository",
                    "key": "GUANCE_RUM_CLIENT_TOKEN_MACOS",
                },
            }
        }

        errors, _ = VALIDATOR.validate_plan(plan, "plan")
        self.assertTrue(
            any("must be custom for the declared Apple variant" in error for error in errors)
        )

        target["application_types"]["macos"]["value"] = "custom"
        errors, _ = VALIDATOR.validate_plan(plan, "plan")
        self.assertEqual([], errors)

    def test_validates_final_inventory_and_rejects_planned_token(self):
        inventory = {
            "schema_version": 1,
            "generated_from_plan_revision": 2,
            "repository": {"root": ".", "commit": "abc123"},
            "receiver": {
                "mode": "public_dataway",
                "endpoint": {"source": "env:DATAWAY_URL"},
                "client_tokens": {
                    "web": {
                        "source": "runtime:GUANCE_RUM_CLIENT_TOKEN",
                        "availability": "persisted",
                    }
                },
            },
            "targets": [
                {
                    "id": "web:.",
                    "path": ".",
                    "platform": "web",
                    "variants": ["browser"],
                    "evidence": ["src/rum.ts"],
                    "disposition": "instrumented",
                    "application_id_slots": ["web"],
                    "application_ids": {
                        "web": {"source": "env:RUM_APPLICATION_ID"}
                    },
                    "application_types": {
                        "web": {
                            "value": "web",
                            "source": "repository",
                            "confidence": "high",
                            "verification": "matched",
                            "api_value": "web",
                        }
                    },
                }
            ],
            "validation": ["npm test: passed"],
            "artifacts": [],
            "remote_verification": {"verified": False, "evidence": []},
            "handoff": [],
        }

        errors, _ = VALIDATOR.validate_inventory(inventory)
        self.assertEqual([], errors)

        inventory["receiver"]["client_tokens"]["web"]["availability"] = "planned"
        errors, _ = VALIDATOR.validate_inventory(inventory)
        self.assertTrue(any("existing or persisted" in error for error in errors))

        inventory["receiver"]["client_tokens"]["web"]["availability"] = "persisted"
        duplicate = copy.deepcopy(inventory["targets"][0])
        duplicate["id"] = "web:apps/portal"
        duplicate["path"] = "apps/portal"
        duplicate["application_id_slots"] = ["portal_web"]
        duplicate["application_ids"] = {
            "portal_web": {"source": "env:RUM_APPLICATION_ID"}
        }
        duplicate["application_types"] = {
            "portal_web": {
                "value": "web",
                "source": "repository",
                "confidence": "high",
                "verification": "matched",
                "api_value": "web",
            }
        }
        inventory["targets"].append(duplicate)
        inventory["receiver"]["client_tokens"]["portal_web"] = {
            "source": "runtime:GUANCE_RUM_CLIENT_TOKEN_PORTAL",
            "availability": "persisted",
        }
        errors, _ = VALIDATOR.validate_inventory(inventory)
        self.assertTrue(
            any("reuses the Application ID reference" in error for error in errors)
        )

    def test_inventory_requires_target_evidence_types_and_validation(self):
        inventory = {
            "schema_version": 1,
            "generated_from_plan_revision": 1,
            "repository": {"root": ".", "commit": "abc123"},
            "receiver": {
                "mode": "datakit",
                "endpoint": {"source": "env:DATAKIT_URL"},
                "readiness": verified_datakit_readiness(),
            },
            "targets": [
                {
                    "id": "web:.",
                    "path": ".",
                    "platform": "web",
                    "variants": ["browser"],
                    "evidence": [],
                    "disposition": "instrumented",
                    "application_id_slots": ["web"],
                    "application_ids": {
                        "web": {"source": "env:RUM_APPLICATION_ID"}
                    },
                }
            ],
            "validation": [],
            "artifacts": [],
            "remote_verification": {"verified": False, "evidence": []},
            "handoff": [],
        }

        errors, _ = VALIDATOR.validate_inventory(inventory)

        self.assertTrue(any("evidence must not be empty" in error for error in errors))
        self.assertTrue(any("application_types must be an object" in error for error in errors))
        self.assertTrue(any("validation must be a non-empty array" in error for error in errors))

    def test_repository_state_rejects_unreceipted_changes_after_planning(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "config", "user.name", "Test"],
                check=True,
            )
            (repository / "src").mkdir()
            (repository / "src" / "rum.ts").write_text("export {}\n", encoding="utf-8")
            (repository / "package.json").write_text("{}\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "commit", "-qm", "baseline"],
                check=True,
            )
            commit = subprocess.run(
                ["git", "-C", str(repository), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            plan = valid_plan()
            plan["repository"]["commit"] = commit

            self.assertEqual(
                [],
                VALIDATOR.validate_repository_state(plan, repository),
            )

            (repository / "src" / "rum.ts").write_text(
                "export const changed = true\n",
                encoding="utf-8",
            )
            errors = VALIDATOR.validate_repository_state(plan, repository)
            self.assertTrue(any("unreviewed uncommitted changes" in error for error in errors))

    def test_repository_state_handles_unicode_and_space_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "config", "user.name", "Test"],
                check=True,
            )
            planned_path = "src/监控 rum.ts"
            source = repository / planned_path
            source.parent.mkdir()
            source.write_text("export {}\n", encoding="utf-8")
            (repository / "package.json").write_text("{}\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "commit", "-qm", "baseline"],
                check=True,
            )
            commit = subprocess.run(
                ["git", "-C", str(repository), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            plan = valid_plan()
            plan["repository"]["commit"] = commit
            plan["planned_changes"][0]["file"] = planned_path
            plan["planned_changes"][0]["before_sha256"] = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
            plan["planned_changes"][0]["prepared_sha256"] = "sha256:" + hashlib.sha256(b"export const changed = true\n").hexdigest()
            source.write_text("export const changed = true\n", encoding="utf-8")

            errors = VALIDATOR.validate_repository_state(plan, repository)

            self.assertEqual([], errors)

    def test_revision_review_can_bind_a_preexisting_dirty_planned_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "config", "user.name", "Test"],
                check=True,
            )
            source = repository / "src" / "rum.ts"
            source.parent.mkdir()
            source.write_text("export {}\n", encoding="utf-8")
            (repository / "package.json").write_text("{}\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "commit", "-qm", "baseline"],
                check=True,
            )
            commit = subprocess.run(
                ["git", "-C", str(repository), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            source.write_text("export const userChange = true\n", encoding="utf-8")
            digest = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
            plan = valid_plan()
            plan["repository"].update(
                {
                    "commit": commit,
                    "initial_status": [" M src/rum.ts"],
                }
            )
            plan["approval"].update(
                {
                    "basis": "revision_review",
                    "reviewed_overlaps": [
                        {"file": "src/rum.ts", "sha256": digest}
                    ],
                }
            )

            self.assertEqual(
                [],
                VALIDATOR.validate_repository_state(plan, repository),
            )

            source.write_text("export const changedAfterReview = true\n", encoding="utf-8")
            errors = VALIDATOR.validate_repository_state(plan, repository)
            self.assertTrue(
                any("changed after approval" in error for error in errors)
            )

    def test_repository_state_rejects_symlinked_planned_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            outside = Path(temporary) / "outside.ts"
            repository.mkdir()
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "config", "user.name", "Test"],
                check=True,
            )
            outside.write_text("export {}\n", encoding="utf-8")
            (repository / "src").mkdir()
            (repository / "src" / "rum.ts").symlink_to(outside)
            (repository / "package.json").write_text("{}\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "commit", "-qm", "baseline"],
                check=True,
            )
            commit = subprocess.run(
                ["git", "-C", str(repository), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            plan = valid_plan()
            plan["repository"]["commit"] = commit

            errors = VALIDATOR.validate_repository_state(plan, repository)

            self.assertTrue(
                any("traverses a symlink" in error for error in errors)
            )


if __name__ == "__main__":
    unittest.main()
