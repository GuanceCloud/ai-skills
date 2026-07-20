from pathlib import Path
import unittest


SKILL_DIR = Path(__file__).resolve().parents[1]


class SkillContractTests(unittest.TestCase):
    def read(self, relative_path):
        return (SKILL_DIR / relative_path).read_text(encoding="utf-8")

    def test_skill_has_no_temporary_credential_exchange_flow(self):
        packaged_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in SKILL_DIR.rglob("*")
            if path.is_file() and path.suffix in {".md", ".yaml", ".yml", ".json"}
        ).lower()

        for obsolete_term in (
            "one-shot",
            "one shot",
            "credential exchange",
            "fetch-credential",
            ".otel/credential.token",
        ):
            self.assertNotIn(obsolete_term, packaged_text)

        self.assertFalse((SKILL_DIR / "references" / "credentials.md").exists())
        self.assertFalse((SKILL_DIR / "scripts" / "fetch-credential.sh").exists())
        self.assertFalse((SKILL_DIR / "scripts" / "fetch-credential.ps1").exists())

    def test_deployment_documents_signal_specific_otlp_http_configuration(self):
        deployment = self.read("references/deployment.md")

        required_settings = (
            "OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf",
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://<otel-host>/v1/traces",
            "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=https://<otel-host>/v1/metrics",
            "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=https://<otel-host>/v1/logs",
            "OTEL_EXPORTER_OTLP_HEADERS='Authorization=Bearer%20<tenant-token>'",
        )
        for setting in required_settings:
            self.assertIn(setting, deployment)

        self.assertIn("Never embed the tenant token", deployment)
        self.assertIn("trusted same-origin backend", deployment)
        self.assertIn("mark authenticated remote export from the client as blocked", deployment)

    def test_inventory_contract_records_signal_endpoints_without_secrets(self):
        contracts = self.read("references/contracts.md")

        self.assertIn('"protocol": "http/protobuf"', contracts)
        self.assertIn('"traces_path": "/v1/traces"', contracts)
        self.assertIn('"metrics_path": "/v1/metrics"', contracts)
        self.assertIn('"logs_path": "/v1/logs"', contracts)
        self.assertIn('"header_name": "Authorization"', contracts)
        self.assertNotIn('"tenant_token"', contracts)

        skill = self.read("SKILL.md")
        self.assertIn("Reuse a host already supplied in the request", skill)
        self.assertIn('"otlp_host": "<approved HTTPS host>"', contracts)

    def test_instrumentation_requires_outbound_url_privacy_proof(self):
        policy = self.read("references/instrumentation.md")
        go = self.read("references/go.md")
        skill = self.read("SKILL.md")

        for required_term in (
            "url.full",
            "query-based authentication",
            "dynamic path",
            "object key",
            "actual exported attributes",
            "negative tests",
        ):
            with self.subTest(required_term=required_term):
                self.assertIn(required_term, policy)

        for required_term in (
            "otelhttp",
            "url.full",
            "sanitized request clone",
            "real outbound request",
            "query token",
        ):
            with self.subTest(go_term=required_term):
                self.assertIn(required_term, go)

        self.assertIn("official instrumentation is not evidence of data safety", skill)

        contracts = self.read("references/contracts.md")
        self.assertIn("version-specific emitted URL attributes", contracts)
        self.assertIn("negative-test canaries", contracts)
        self.assertIn("Never generalize an inbound-only test", contracts)

    def test_skill_supports_every_official_opentelemetry_language(self):
        skill = self.read("SKILL.md")

        language_references = {
            "C++": "cpp.md",
            "C#/.NET": "dotnet.md",
            "Erlang/Elixir": "erlang-elixir.md",
            "Go": "go.md",
            "Java": "java.md",
            "JavaScript/TypeScript": "javascript.md",
            "Kotlin": "kotlin.md",
            "PHP": "php.md",
            "Python": "python.md",
            "Ruby": "ruby.md",
            "Rust": "rust.md",
            "Swift": "swift.md",
        }

        for language, reference in language_references.items():
            with self.subTest(language=language):
                self.assertIn(language, skill)
                self.assertIn(f"references/{reference}", skill)
                self.assertTrue((SKILL_DIR / "references" / reference).is_file())

        rust_reference = self.read("references/rust.md")
        for required_term in (
            "Cargo.toml",
            "Cargo.lock",
            "rust-toolchain",
            "cargo fmt --check",
            "cargo clippy",
            "cargo test",
            "tracing-opentelemetry",
        ):
            self.assertIn(required_term, rust_reference)


if __name__ == "__main__":
    unittest.main()
