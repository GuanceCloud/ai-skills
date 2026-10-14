from __future__ import annotations

from pathlib import Path
import unittest


SKILL_DIR = Path(__file__).resolve().parents[1]


class SkillContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (SKILL_DIR / relative).read_text(encoding="utf-8")

    def test_skill_uses_minimal_connection_input(self):
        skill = self.read("SKILL.md")

        for field in (
            "datawayUrl",
            "temporaryAuthCode",
            "datakitUrl",
            "appId",
        ):
            with self.subTest(field=field):
                self.assertIn(field, skill)

        minimal_prompt = skill.split("## Minimal prompt", 1)[1].split("## Workflow", 1)[0]
        self.assertNotIn("clientToken:", minimal_prompt)
        self.assertNotIn("aiApiEndpoint:", minimal_prompt)
        self.assertIn("prompt:provided", skill)
        self.assertIn(
            "Pass it through process stdin after preflight",
            skill,
        )
        self.assertIn(
            '{"source":"prompt:provided"}',
            self.read("references/contracts.md"),
        )


    def test_all_official_rum_application_families_have_adapters(self):
        skill = self.read("SKILL.md")
        adapters = {
            "Web": "web.md",
            "MiniApp": "miniapp.md",
            "Android": "android.md",
            "iOS": "apple.md",
            "macOS": "macos.md",
            "HarmonyOS": "harmonyos.md",
            "React Native": "react-native.md",
            "Flutter": "flutter.md",
            "UniApp": "uniapp.md",
            "C++": "cpp.md",
            "Unity": "unity.md",
        }

        for family, filename in adapters.items():
            with self.subTest(family=family):
                self.assertIn(family, skill)
                self.assertIn(f"references/{filename}", skill)
                self.assertTrue((SKILL_DIR / "references" / filename).is_file())

    def test_skill_keeps_token_values_and_remote_actions_out_of_plan(self):
        skill = self.read("SKILL.md")
        privacy = self.read("references/privacy-security.md")
        contracts = self.read("references/contracts.md")

        self.assertIn("Keep authorization codes, API Keys, and Client Token values out", skill)
        self.assertIn("uploaded only after explicit authorization", privacy)
        self.assertNotIn('"client_token": "<', contracts)
        self.assertIn("remote_verification.verified: false", contracts)

    def test_public_dataway_uses_catalog_and_ai_api_helper(self):
        skill = self.read("SKILL.md")
        control_plane = self.read("references/control-plane.md")
        helper = self.read("scripts/resolve_rum_application.py")

        for value in (
            "https://urls.guance.com/",
            "https://urls.truewatch.com/",
            "/api/v1/account/accesskey/exchange",
            "/api/v1/rum/app/get",
        ):
            with self.subTest(value=value):
                self.assertIn(value, control_plane + helper)

        self.assertIn("api_key_persistence", helper)
        self.assertIn("memory_only", helper)
        self.assertIn("temporary-auth-code-env", helper)
        self.assertIn("temporary-auth-code-stdin", helper)
        self.assertIn("getpass.getpass", helper)
        self.assertIn("--site-only", skill)
        self.assertIn("application lookup requires --client-token-sink", helper)
        self.assertIn("application lookup requires --state-file", helper)
        self.assertIn("application lookup requires --plan-digest", helper)
        self.assertIn("--allow-external-secret-sink", helper)
        for sink_format in ("dotenv", "json", "properties", "xcconfig"):
            self.assertIn(sink_format, helper)
        self.assertIn("restores the previous sink", skill)
        self.assertIn("credential-free network preflight", skill)
        self.assertIn("never polls mapping state", skill)
        self.assertNotIn("OWL_REGISTRY_ENDPOINT", helper)
        self.assertIn("use `OWL_REGISTRY_ENDPOINT`", control_plane)

    def test_testing_site_is_built_in_and_not_a_standard_prompt_field(self):
        skill = self.read("SKILL.md")
        control_plane = self.read("references/control-plane.md")
        validator = self.read("scripts/validate_contract.py")
        testing_site = self.read("references/testing-site.md")

        for value in (
            "--insecure-test-tls",
            "builtin_testing",
            "https://testing-ft2x-ai-api.dataflux.cn",
            "test_only",
        ):
            with self.subTest(value=value):
                self.assertIn(value, skill + control_plane + testing_site + validator)
        for removed in ("--test-site-catalog-file", "testing_override"):
            with self.subTest(removed=removed):
                self.assertNotIn(removed, skill + control_plane + validator)

        minimal_contract = skill.split("## Minimal prompt", 1)[1].split(
            "## Workflow",
            1,
        )[0]
        self.assertNotIn("aiApiEndpoint:", minimal_contract)
        self.assertNotIn("clientToken:", minimal_contract)
        self.assertNotIn("evals/files", skill + control_plane)

    def test_headless_receiver_mode_is_absent(self):
        paths = [
            "SKILL.md",
            "references/common.md",
            "references/contracts.md",
            "references/web.md",
            "references/miniapp.md",
            "evals/evals.json",
        ]

        for relative in paths:
            with self.subTest(relative=relative):
                self.assertNotIn("headless", self.read(relative).lower())

    def test_progressive_disclosure_and_metadata(self):
        skill_lines = self.read("SKILL.md").splitlines()
        agent = self.read("agents/openai.yaml")

        self.assertLess(len(skill_lines), 500)
        self.assertIn('display_name: "RUM Instrumentation"', agent)
        self.assertIn("$rum-instrument", agent)
        self.assertIn("Load references progressively", self.read("SKILL.md"))

    def test_optional_capabilities_are_repository_or_user_driven(self):
        skill = self.read("SKILL.md")
        common = self.read("references/common.md")

        self.assertIn(
            "do not enable absent Logs, Trace, Replay",
            skill,
        )
        self.assertIn("Core RUM is the default planning scope", common)
        self.assertIn("omit irrelevant sections", common)

    def test_macos_and_cpp_receiver_boundaries_are_explicit(self):
        macos = self.read("references/macos.md")
        cpp = self.read("references/cpp.md")
        validator = self.read("scripts/validate_contract.py")
        common = self.read("references/common.md")

        for value in ("datakit-macos", "FTMacOSSDK", "main.swift", "custom"):
            with self.subTest(value=value):
                self.assertIn(value, macos)
        for value in ("setServerUrl", "setRumAppId", "only DataKit"):
            with self.subTest(value=value):
                self.assertIn(value, cpp + validator)
        self.assertIn("block Public DataWay plans", common)

    def test_evals_have_repository_fixtures_and_platform_edge_cases(self):
        import json

        evals = json.loads(self.read("evals/evals.json"))["evals"]
        self.assertTrue(all(case["files"] for case in evals))
        for case in evals:
            for relative in case["files"]:
                with self.subTest(case=case["id"], relative=relative):
                    self.assertTrue((SKILL_DIR / relative).is_file())
        prompts = "\n".join(case["prompt"] for case in evals)
        for family in (
            "Android",
            "iOS",
            "tvOS",
            "macOS",
            "HarmonyOS",
            "React Native",
            "Flutter",
            "UniApp",
            "C++",
            "Unity",
            "小程序",
        ):
            with self.subTest(family=family):
                self.assertIn(family, prompts)
        self.assertIn("规划并实施", prompts)
        self.assertTrue(
            any(
                "explicit_implementation_request" in expectation
                for case in evals
                for expectation in case["expectations"]
            )
        )

    def test_contract_covers_datakit_readiness_and_type_verification(self):
        contracts = self.read("references/contracts.md")
        validator = self.read("scripts/validate_contract.py")

        for value in (
            "rum_collector",
            "network_reachability",
            "verification",
            "api_value",
            "not_applicable",
        ):
            with self.subTest(value=value):
                self.assertIn(value, contracts + validator)

    def test_markdown_is_brand_neutral(self):
        forbidden = ("guance", "观测云", "观测")
        markdown_files = [SKILL_DIR / "SKILL.md", *SKILL_DIR.glob("references/*.md")]

        for path in markdown_files:
            content = path.read_text(encoding="utf-8").lower()
            for term in forbidden:
                with self.subTest(path=path.name, term=term):
                    self.assertNotIn(term, content)

    def test_primary_source_registry_covers_every_adapter(self):
        import json

        registry = json.loads(self.read("references/official-sources.json"))
        self.assertEqual(
            {
                "android",
                "apple",
                "cpp",
                "flutter",
                "harmonyos",
                "macos",
                "miniapp",
                "react_native",
                "uniapp",
                "unity",
                "web",
            },
            set(registry),
        )

if __name__ == "__main__":
    unittest.main()
