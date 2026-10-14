from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "detect_rum_targets.py"
EVAL_FILES = Path(__file__).resolve().parents[1] / "evals" / "files"
SPEC = importlib.util.spec_from_file_location("detect_rum_targets", SCRIPT)
assert SPEC and SPEC.loader
DETECTOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DETECTOR
SPEC.loader.exec_module(DETECTOR)


class DetectRumTargetsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, relative: str, content: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def targets(self):
        return DETECTOR.detect(self.root)["targets"]

    def test_detects_existing_web_rum_without_emitting_source_values(self):
        self.write(
            "package.json",
            json.dumps({"dependencies": {"vue": "3.5.0", "@cloudcare/browser-rum": "3.0.0"}}),
        )
        self.write(
            "public/index.html",
            "<script>DATAFLUX_RUM.init({clientToken: 'do-not-emit-this-value'})</script>",
        )

        targets = self.targets()

        self.assertEqual(1, len(targets))
        self.assertEqual("web", targets[0]["platform"])
        self.assertEqual(["web"], targets[0]["application_id_slots"])
        self.assertIn("browser-rum-global", targets[0]["existing_rum_markers"])
        self.assertNotIn("do-not-emit-this-value", json.dumps(targets))

    def test_adding_miniapp_sdk_does_not_invent_a_framework(self):
        self.write('app.js', 'App({})')
        self.write('app.json', '{"pages": []}')
        self.write('project.config.json', '{"compileType": "miniprogram"}')
        before = self.targets()[0]
        self.write('package.json', json.dumps({'dependencies': {'@cloudcare/rum-miniapp': '2.2.20'}}))
        after = self.targets()[0]
        for key in ('id', 'platform', 'variants', 'confidence', 'application_id_slots'):
            self.assertEqual(before[key], after[key], key)
        self.assertIn('miniapp-rum-package', after['existing_rum_markers'])

    def test_actual_miniapp_framework_dependency_keeps_framework_variant(self):
        self.write('package.json', json.dumps({'dependencies': {'@tarojs/taro': '4.0.0', '@cloudcare/rum-miniapp': '2.2.20'}}))
        self.write('src/app.ts', 'export default {}')
        self.assertEqual(['framework'], self.targets()[0]['variants'])

    def test_detects_vanilla_web_without_package_manifest(self):
        self.write(
            "index.html",
            "<html><script>window.DATAFLUX_RUM.init({})</script></html>\n",
        )

        targets = self.targets()

        self.assertEqual(1, len(targets))
        self.assertEqual("web", targets[0]["platform"])
        self.assertEqual(["index.html"], targets[0]["evidence"])

    def test_excludes_agent_skills_and_generated_plan_from_markers(self):
        self.write("package.json", json.dumps({"dependencies": {"vue": "3.5.0"}}))
        self.write("public/index.html", "<script>window.DATAFLUX_RUM.init({})</script>\n")
        for relative in (
            ".agents/skills/rum-instrument/references/web.md",
            ".claude/skills/rum-instrument/SKILL.md",
            ".codex/skills/rum-instrument/SKILL.md",
            ".cursor/skills/rum-instrument/SKILL.md",
            "evals/files/sample/package.json",
            ".github/skills/rum-instrument/SKILL.md",
            ".rum/plan.json",
        ):
            self.write(relative, "DATAFLUX_RUM datafluxRum @cloudcare/browser-rum\n")

        targets = self.targets()

        self.assertEqual(
            {"browser-rum-global": ["public/index.html"]},
            targets[0]["existing_rum_markers"],
        )

    def test_detector_result_is_stable_after_plan_generation(self):
        self.write("package.json", json.dumps({"dependencies": {"vue": "3.5.0"}}))
        self.write("public/index.html", "<script>window.DATAFLUX_RUM.init({})</script>\n")
        before = self.targets()
        self.write(
            ".rum/plan.json",
            json.dumps({"sdk": "@cloudcare/browser-rum", "initializer": "DATAFLUX_RUM.init({})"}),
        )

        self.assertEqual(before, self.targets())

    def test_package_marker_requires_manifest_dependency(self):
        self.write("package.json", json.dumps({"dependencies": {"vue": "3.5.0"}}))
        self.write("src/main.ts", "export {}\n")
        self.write(
            "src/IntegrationExample.vue",
            """<script lang="ts">
            const sample = `npm install @cloudcare/browser-rum
            datafluxRum.init({ applicationId: "example" })`;
            </script>
            """,
        )

        target = self.targets()[0]

        self.assertNotIn("browser-rum-package", target["existing_rum_markers"])
        self.assertNotIn("javascript-rum-api", target["existing_rum_markers"])

        self.write(
            "package.json",
            json.dumps({"dependencies": {"vue": "3.5.0", "@cloudcare/browser-rum": "3.3.5"}}),
        )
        target = self.targets()[0]
        self.assertEqual(["package.json"], target["existing_rum_markers"]["browser-rum-package"])

    def test_runtime_marker_ignores_comments_and_string_examples(self):
        self.write("package.json", json.dumps({"dependencies": {"vue": "3.5.0"}}))
        self.write("src/main.ts", "export {}\n")
        self.write("src/rum.d.ts", "declare const DATAFLUX_RUM: unknown;\n")
        self.write(
            "src/rum.ts",
            """
            // DATAFLUX_RUM.init({})
            const example = `datafluxRum.init({
              ${receiver === 'public' ? `site: '${site}'` : `datakitOrigin: '${origin}'`}
            })`;
            window.DATAFLUX_RUM.onReady(() => window.DATAFLUX_RUM.init({}));
            """,
        )

        target = self.targets()[0]

        self.assertEqual(["src/rum.ts"], target["existing_rum_markers"]["browser-rum-global"])
        self.assertNotIn("javascript-rum-api", target["existing_rum_markers"])

    def test_detects_runtime_markers_in_modern_web_source_extensions(self):
        self.write("package.json", json.dumps({"dependencies": {"react": "19.0.0"}}))
        self.write("src/main.jsx", "window.DATAFLUX_RUM.init({})\n")
        self.write("src/bootstrap.mjs", "datafluxRum.init({})\n")
        self.write(
            "src/App.svelte",
            """
            <p>DATAFLUX_RUM.init({}) is documentation, not executable code.</p>
            <script>
              window.DATAFLUX_RUM.init({})
            </script>
            """,
        )

        target = self.targets()[0]

        self.assertEqual(
            ["src/App.svelte", "src/main.jsx"],
            target["existing_rum_markers"]["browser-rum-global"],
        )
        self.assertEqual(
            ["src/bootstrap.mjs"],
            target["existing_rum_markers"]["javascript-rum-api"],
        )

    def test_svelte_markup_example_is_not_a_runtime_marker(self):
        self.write("package.json", json.dumps({"dependencies": {"svelte": "5.0.0"}}))
        self.write("svelte.config.js", "export default {}\n")
        self.write("src/App.svelte", "<p>Example: DATAFLUX_RUM.init({})</p>\n")

        target = self.targets()[0]

        self.assertEqual({}, target["existing_rum_markers"])

    def test_flutter_owns_native_subprojects_and_keeps_web_as_variant(self):
        self.write("pubspec.yaml", "name: mobile\n\ndependencies:\n  flutter:\n    sdk: flutter\n")
        self.write("lib/main.dart", "void main() {}\n")
        self.write("web/index.html", "<html></html>\n")
        self.write("android/app/build.gradle", "plugins { id 'com.android.application' }\n")
        self.write("android/app/src/main/AndroidManifest.xml", "<manifest />\n")
        self.write("ios/Runner.xcodeproj/project.pbxproj", "// project\n")

        targets = self.targets()

        self.assertEqual(1, len(targets))
        self.assertEqual("flutter", targets[0]["platform"])
        self.assertEqual(["android", "ios", "web"], targets[0]["variants"])
        self.assertEqual(["android", "ios", "web"], targets[0]["application_id_slots"])

    def test_excludes_generated_and_example_projects(self):
        self.write("build/web/package.json", json.dumps({"dependencies": {"vue": "3.5.0"}}))
        self.write("examples/demo/package.json", json.dumps({"dependencies": {"react": "19.0.0"}}))

        result = DETECTOR.detect(self.root)

        self.assertEqual([], result["targets"])
        self.assertTrue(any("No supported" in warning for warning in result["warnings"]))

    def test_detects_react_native_as_one_target_with_two_slots(self):
        self.write("apps/mobile/package.json", json.dumps({"dependencies": {"react-native": "0.80.0"}}))
        self.write("apps/mobile/index.js", "export {}\n")
        self.write("apps/mobile/android/app/build.gradle", "plugins { id 'com.android.application' }\n")
        self.write("apps/mobile/android/app/src/main/AndroidManifest.xml", "<manifest />\n")
        self.write("apps/mobile/ios/App.xcodeproj/project.pbxproj", "// project\n")

        targets = self.targets()

        self.assertEqual(1, len(targets))
        self.assertEqual("react-native", targets[0]["platform"])
        self.assertEqual(["android", "ios"], targets[0]["application_id_slots"])

    def test_detects_hbuilder_uniapp_without_package_json(self):
        self.write("apps/uni/manifest.json", '{"app-plus": {}, "h5": {}}\n')
        self.write("apps/uni/pages.json", '{"pages": []}\n')

        targets = self.targets()

        self.assertEqual(1, len(targets))
        self.assertEqual("uniapp", targets[0]["platform"])
        self.assertEqual(["android", "ios", "web"], targets[0]["application_id_slots"])

    def test_uniapp_root_html_belongs_to_the_wrapper(self):
        self.write('manifest.json', '{"h5":{}}')
        self.write('pages.json', '{"pages":[]}')
        self.write('index.html', '<html><div id="app"></div></html>')
        for with_package in (False, True):
            if with_package:
                self.write('package.json', json.dumps({'dependencies': {'@dcloudio/uni-app': '3.0.0', 'vue': '3.5.0'}}))
            with self.subTest(with_package=with_package):
                targets = self.targets()
                self.assertEqual(['uniapp'], [t['platform'] for t in targets])
                self.assertEqual(['web'], targets[0]['application_id_slots'])

    def test_uniapp_ownership_preserves_a_sibling_web_application(self):
        self.write('mobile/manifest.json', '{"h5":{}}')
        self.write('mobile/pages.json', '{"pages":[]}')
        self.write('mobile/index.html', '<html></html>')
        self.write('admin/index.html', '<html></html>')
        self.assertEqual(['web:admin', 'uniapp:mobile'], [t['id'] for t in self.targets()])

    def test_detects_native_desktop_and_miniapp_families(self):
        self.write("apps/mini/project.config.json", "{}\n")
        self.write("apps/mini/app.json", "{}\n")
        self.write("apps/android/app/build.gradle.kts", "plugins { id(\"com.android.application\") }\n")
        self.write("apps/android/app/src/main/AndroidManifest.xml", "<manifest />\n")
        self.write(
            "apps/apple/App.xcodeproj/project.pbxproj",
            "IPHONEOS_DEPLOYMENT_TARGET = 17.0;\nSDKROOT = iphoneos;\n",
        )
        self.write("apps/harmony/build-profile.json5", "{}\n")
        self.write("apps/harmony/oh-package.json5", "{}\n")
        self.write(
            "apps/harmony/entry/src/main/ets/entryability/EntryAbility.ets",
            "export default class EntryAbility {}\n",
        )
        self.write("apps/cpp/CMakeLists.txt", "project (Desktop LANGUAGES CXX)\nadd_executable (desktop main.cpp)\n")
        self.write("apps/unity/ProjectSettings/ProjectVersion.txt", "m_EditorVersion: 6000.0\n")

        targets = self.targets()
        platforms = {target["platform"] for target in targets}

        self.assertEqual(
            {"miniapp", "android", "apple", "harmonyos", "cpp", "unity"},
            platforms,
        )
        apple = next(target for target in targets if target["platform"] == "apple")
        self.assertEqual(["ios"], apple["application_id_slots"])

    def test_scope_limits_detection_but_keeps_repository_relative_paths(self):
        self.write(
            "apps/admin/package.json",
            json.dumps({"dependencies": {"vue": "3.5.0"}}),
        )
        self.write("apps/admin/src/main.ts", "export {}\n")
        self.write(
            "apps/storefront/package.json",
            json.dumps({"dependencies": {"react": "19.0.0"}}),
        )
        self.write("apps/storefront/src/main.tsx", "export {}\n")

        result = DETECTOR.detect(self.root, Path("apps/admin"))

        self.assertEqual("apps/admin", result["repository"]["scan_scope"])
        self.assertEqual(["web:apps/admin"], [target["id"] for target in result["targets"]])
        self.assertEqual(
            ["apps/admin/package.json", "apps/admin/src/main.ts"],
            result["targets"][0]["evidence"],
        )

    def test_git_discovery_excludes_ignored_targets(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.write(".gitignore", "ignored/\n")
        self.write(
            "package.json",
            json.dumps({"dependencies": {"vue": "3.5.0"}}),
        )
        self.write("src/main.ts", "export {}\n")
        self.write(
            "ignored/package.json",
            json.dumps(
                {
                    "dependencies": {
                        "react": "19.0.0",
                        "@cloudcare/browser-rum": "3.0.0",
                    }
                }
            ),
        )

        result = DETECTOR.detect(self.root)

        self.assertEqual(["web:."], [target["id"] for target in result["targets"]])
        self.assertNotIn("ignored", json.dumps(result))

    def test_rejects_scope_outside_repository(self):
        with self.assertRaisesRegex(ValueError, "inside the repository"):
            DETECTOR.detect(self.root, self.root.parent)

    def test_ignores_react_component_library_without_web_entry(self):
        self.write(
            "package.json",
            json.dumps(
                {
                    "name": "component-library",
                    "peerDependencies": {"react": "19.0.0"},
                }
            ),
        )
        self.write("src/Button.tsx", "export const Button = () => null\n")

        result = DETECTOR.detect(self.root)

        self.assertEqual([], result["targets"])
        self.assertTrue(
            any("without a deployable web entry" in warning for warning in result["warnings"])
        )

    def test_ignores_android_library_module(self):
        self.write(
            "libs/sdk/build.gradle.kts",
            'plugins { id("com.android.library") }\n',
        )
        self.write(
            "libs/sdk/src/main/AndroidManifest.xml",
            "<manifest />\n",
        )

        result = DETECTOR.detect(self.root)

        self.assertEqual([], result["targets"])
        self.assertTrue(
            any("non-application module" in warning for warning in result["warnings"])
        )

    def test_detects_android_application_version_catalog_alias(self):
        self.write(
            "app/build.gradle.kts",
            "plugins { alias(libs.plugins.androidApplication) }\n",
        )
        self.write("app/src/main/AndroidManifest.xml", "<manifest />\n")

        targets = self.targets()

        self.assertEqual(["android"], [target["platform"] for target in targets])

    def test_ignores_flutter_package_without_entry_or_platforms(self):
        self.write(
            "pubspec.yaml",
            "name: reusable\n\ndependencies:\n  flutter:\n    sdk: flutter\n",
        )
        self.write("lib/widget.dart", "class WidgetLibrary {}\n")

        result = DETECTOR.detect(self.root)

        self.assertEqual([], result["targets"])
        self.assertTrue(
            any("lacks lib/main.dart" in warning for warning in result["warnings"])
        )

    def test_xcode_multi_app_targets_receive_distinct_slots(self):
        self.write(
            "Apps.xcodeproj/project.pbxproj",
            """
            /* Begin PBXNativeTarget section */
            A = {
              isa = PBXNativeTarget;
              name = Consumer;
              productType = "com.apple.product-type.application";
            };
            B = {
              isa = PBXNativeTarget;
              name = Admin;
              productType = "com.apple.product-type.application";
            };
            /* End PBXNativeTarget section */
            IPHONEOS_DEPLOYMENT_TARGET = 17.0;
            """,
        )

        result = DETECTOR.detect(self.root)

        self.assertEqual(
            ["ios-admin", "ios-consumer"],
            result["targets"][0]["application_id_slots"],
        )
        self.assertTrue(
            any("multiple application targets" in warning for warning in result["warnings"])
        )

    def test_all_platform_eval_fixtures_are_detectable(self):
        fixtures = {
            "android-app": "android",
            "apple-mobile": "apple",
            "cpp-app": "cpp",
            "flutter-multiplatform": "flutter",
            "harmony-app": "harmonyos",
            "macos-app": "apple",
            "miniapp": "miniapp",
            "react-native-app": "react-native",
            "uniapp": "uniapp",
            "unity": "unity",
            "vue-existing": "web",
        }

        for fixture, platform in fixtures.items():
            with self.subTest(fixture=fixture, platform=platform):
                with tempfile.TemporaryDirectory() as temporary:
                    repository = Path(temporary) / fixture
                    shutil.copytree(EVAL_FILES / fixture, repository)
                    result = DETECTOR.detect(repository)
                    self.assertIn(
                        platform,
                        {target["platform"] for target in result["targets"]},
                    )

    def test_rejects_git_subdirectory_as_repository_root(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        nested = self.root / "apps" / "admin"
        nested.mkdir(parents=True)

        with self.assertRaisesRegex(ValueError, "use --scope"):
            DETECTOR.detect(nested)


if __name__ == "__main__":
    unittest.main()
