from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "src" / "sidinspector"
SIDSCOPE_ROOT = ROOT / "src" / "sidscope"
TOOLS_ROOT = ROOT / "tools"

MATRIX_PATH = ROOT / "docs" / "reproducibility" / "sidscope_module_dependencies.json"


def matrix_document() -> dict:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def application_rules() -> dict:
    return matrix_document()["application_rules"]


def allowed_target_imports() -> dict[str, set[str]]:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    return {
        module: set(config["allowed_internal_imports"])
        for module, config in matrix["modules"].items()
    }


def _module_name_for(path: Path, package_root: Path, prefix: str) -> str:
    relative = path.relative_to(package_root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join((prefix, *parts)) if parts else prefix


def _resolved_import_names_for(path: Path, package_root: Path, prefix: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    current = _module_name_for(path, package_root, prefix).split(".")
    current_package = current if path.name == "__init__.py" else current[:-1]
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level == 0:
            if node.module:
                imports.add(node.module)
            continue
        remove = node.level - 1
        if remove > len(current_package):
            imports.add("<invalid-relative-import>")
            continue
        base = current_package[: len(current_package) - remove]
        suffix = node.module.split(".") if node.module else []
        imports.add(".".join((*base, *suffix)))
    return imports


def _module_name(path: Path) -> str:
    return _module_name_for(path, PACKAGE_ROOT, "sidinspector")


def _resolved_import_names(path: Path) -> set[str]:
    return _resolved_import_names_for(path, PACKAGE_ROOT, "sidinspector")


def internal_target_imports(path: Path) -> set[str]:
    targets = allowed_target_imports()
    imports: set[str] = set()
    for name in _resolved_import_names(path):
        if not name.startswith("sidinspector."):
            continue
        module = name.split(".", 2)[1]
        if module in targets:
            imports.add(module)
    return imports


def private_cross_module_imports(path: Path) -> set[str]:
    targets = allowed_target_imports()
    current = _module_name(path).split(".")[1]
    failures: set[str] = set()
    for name in _resolved_import_names(path):
        parts = name.split(".")
        if len(parts) < 3 or parts[0] != "sidinspector":
            continue
        target = parts[1]
        if target in targets and target != current:
            failures.add(name)
    return failures


class ArchitectureBoundaryTest(unittest.TestCase):
    def test_current_diagram_matches_code_and_inventory(self) -> None:
        from tools.verify_sidscope_architecture_inventory import verify_diagram
        self.assertEqual(verify_diagram()["owned_layers"], 6)

    def test_diagram_rejects_certification_promotion(self) -> None:
        from tools.verify_sidscope_architecture_inventory import DIAGRAM_BASE, validate_diagram
        document = json.loads((ROOT / (DIAGRAM_BASE + ".json")).read_text())
        document["view"] = "public_2_0_certified"
        with self.assertRaisesRegex(ValueError, "scope_drift"):
            validate_diagram(document)

    def test_diagram_rejects_nonexistent_implementation(self) -> None:
        from tools.verify_sidscope_architecture_inventory import DIAGRAM_BASE, validate_diagram
        document = json.loads((ROOT / (DIAGRAM_BASE + ".json")).read_text())
        document["layers"][0]["code_paths"] = ["src/nonexistent_service"]
        with self.assertRaisesRegex(ValueError, "missing_code_path"):
            validate_diagram(document)

    def test_diagram_rejects_broken_edge(self) -> None:
        from tools.verify_sidscope_architecture_inventory import DIAGRAM_BASE, validate_diagram
        document = json.loads((ROOT / (DIAGRAM_BASE + ".json")).read_text())
        document["edges"][0]["target"] = "missing"
        with self.assertRaisesRegex(ValueError, "broken_edge"):
            validate_diagram(document)

    def test_diagram_rejects_wrong_version_layers_and_flow(self) -> None:
        from tools.verify_sidscope_architecture_inventory import DIAGRAM_BASE, validate_diagram
        import copy
        original = json.loads((ROOT / (DIAGRAM_BASE + ".json")).read_text())
        mutations = [
            ("version_drift", lambda d: d.update(product_version="2.0.0")),
            ("layer_drift", lambda d: d["layers"].pop()),
            ("duplicate_or_missing_id", lambda d: d["layers"].append(d["layers"][0])),
            ("flow_drift", lambda d: d["edges"][0].update(target="evidence")),
            ("flow_drift", lambda d: d["edges"].append(d["edges"][0])),
            ("missing_code_path", lambda d: d["layers"][0].update(code_paths=[])),
        ]
        for error, mutate in mutations:
            with self.subTest(error=error):
                document = copy.deepcopy(original)
                mutate(document)
                with self.assertRaisesRegex(ValueError, error):
                    validate_diagram(document)

    def test_target_modules_follow_allowed_dependency_matrix(self) -> None:
        matrix = allowed_target_imports()
        failures: list[str] = []
        for module, allowed in matrix.items():
            module_root = PACKAGE_ROOT / module
            if not module_root.is_dir():
                continue
            for path in sorted(module_root.rglob("*.py")):
                forbidden = sorted(internal_target_imports(path) - allowed)
                if forbidden:
                    failures.append(
                        f"{path.relative_to(ROOT)} imports forbidden target modules {forbidden}"
                    )

        self.assertEqual(failures, [])

    def test_dependency_matrix_is_complete_and_acyclic(self) -> None:
        matrix = allowed_target_imports()
        expected = {
            "contracts",
            "sdk",
            "schemas",
            "trace",
            "evaluation",
            "conformance_core",
            "evidence",
            "submission",
            "adapters_core",
            "cli",
        }
        self.assertEqual(set(matrix), expected)
        for module, allowed in matrix.items():
            self.assertIn(module, allowed)
            self.assertLessEqual(allowed, expected)
        self.assertEqual(matrix["contracts"], {"contracts"})
        self.assertNotIn("cli", set().union(*(v for k, v in matrix.items() if k != "cli")))

        graph = {module: allowed - {module} for module, allowed in matrix.items()}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(module: str) -> None:
            if module in visiting:
                self.fail(f"dependency cycle reaches {module}")
            if module in visited:
                return
            visiting.add(module)
            for dependency in graph[module]:
                visit(dependency)
            visiting.remove(module)
            visited.add(module)

        for module in graph:
            visit(module)

    def test_cross_module_imports_use_public_package_facades(self) -> None:
        failures: list[str] = []
        for module in allowed_target_imports():
            module_root = PACKAGE_ROOT / module
            for path in sorted(module_root.rglob("*.py")):
                private = sorted(private_cross_module_imports(path))
                if private:
                    failures.append(
                        f"{path.relative_to(ROOT)} imports private cross-module paths {private}"
                    )
        self.assertEqual(failures, [])

    def test_contracts_never_import_legacy_or_optional_adapter_runtime(self) -> None:
        forbidden_prefixes = (
            "sidinspector.adapters",
            "sidinspector.conformance",
            "torch",
            "transformers",
            "faiss",
        )
        failures: list[str] = []
        for path in sorted((PACKAGE_ROOT / "contracts").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    if name.startswith(forbidden_prefixes):
                        failures.append(f"{path.relative_to(ROOT)} imports {name}")

        self.assertEqual(failures, [])


class ApplicationBoundaryTest(unittest.TestCase):
    """D03: workflow, application and tool edges have explicit directions."""

    LEGACY_MODULES = {"metrics", "churn", "adapters", "conformance", "d7_trace",
                      "interface", "preflight", "trace_analysis"}

    def _sidscope_module_name(self, path: Path) -> str:
        relative = path.relative_to(SIDSCOPE_ROOT).with_suffix("")
        parts = list(relative.parts)
        if parts[-1] == "__init__":
            parts.pop()
        return parts[0] if parts else "__init__"

    def test_sidscope_workflow_modules_follow_recorded_matrix(self) -> None:
        matrix = matrix_document()["sidscope_modules"]
        failures: list[str] = []
        seen: set[str] = set()
        for path in sorted(SIDSCOPE_ROOT.rglob("*.py")):
            name = self._sidscope_module_name(path)
            seen.add(name)
            rules = matrix.get(name)
            if rules is None:
                failures.append(f"{path.relative_to(ROOT)} is missing from sidscope_modules")
                continue
            for name_full in sorted(_resolved_import_names_for(path, SIDSCOPE_ROOT, "sidscope")):
                parts = name_full.split(".")
                if parts[0] == "sidinspector":
                    target = parts[1]
                    if target in self.LEGACY_MODULES:
                        if target not in rules["allowed_legacy_imports"]:
                            failures.append(f"{path.relative_to(ROOT)} imports legacy {name_full} not allowed")
                    elif target not in rules["allowed_core_imports"]:
                        failures.append(f"{path.relative_to(ROOT)} imports core {name_full} not allowed")
                elif parts[0] == "sidscope":
                    target = parts[1] if len(parts) > 1 else "__init__"
                    if target != name and target not in rules["allowed_sidscope_imports"]:
                        failures.append(f"{path.relative_to(ROOT)} imports workflow {name_full} not allowed")
        self.assertEqual(failures, [])
        self.assertEqual(seen, set(matrix))

    def test_core_never_imports_workflow_cli_or_tools(self) -> None:
        failures = [
            f"{path.relative_to(ROOT)} imports {name}"
            for path in sorted(PACKAGE_ROOT.rglob("*.py"))
            for name in sorted(_resolved_import_names(path))
            if name == "sidscope" or name.startswith(("sidscope.", "tools"))
        ]
        self.assertEqual(failures, [])

    def test_sidscope_never_imports_tools(self) -> None:
        failures = [
            f"{path.relative_to(ROOT)} imports {name}"
            for path in sorted(SIDSCOPE_ROOT.rglob("*.py"))
            for name in sorted(_resolved_import_names_for(path, SIDSCOPE_ROOT, "sidscope"))
            if name == "tools" or name.startswith("tools.")
        ]
        self.assertEqual(failures, [])

    def test_tool_to_tool_edges_match_recorded_allowlist(self) -> None:
        recorded = application_rules()["tool_to_tool_imports"]
        actual: dict[str, set[str]] = {}
        for path in sorted(TOOLS_ROOT.glob("*.py")):
            targets = {
                name.split(".", 1)[1]
                for name in _resolved_import_names_for(path, ROOT, "tools")
                if name == "tools" or name.startswith("tools.")
            }
            if targets:
                actual[path.stem] = targets
        failures = []
        for tool, targets in sorted(actual.items()):
            allowed = set(recorded.get(tool, []))
            for extra in sorted(targets - allowed):
                failures.append(f"tools/{tool}.py imports tools.{extra} without a matrix entry")
        for tool, allowed in sorted(recorded.items()):
            for stale in sorted(set(allowed) - actual.get(tool, set())):
                failures.append(f"matrix records stale edge tools/{tool}.py -> tools.{stale}")
        self.assertEqual(failures, [])

    def test_dynamic_module_loading_only_in_producer_entry(self) -> None:
        allowed_files = set(application_rules()["dynamic_module_loading_allowed_files"])
        failures = []
        for path in sorted((PACKAGE_ROOT.rglob("*.py"))) + sorted(SIDSCOPE_ROOT.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            dynamic = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    function = node.func
                    if isinstance(function, ast.Attribute) and function.attr == "import_module":
                        dynamic.append("importlib.import_module")
                    elif isinstance(function, ast.Name) and function.id == "__import__":
                        dynamic.append("__import__")
            if dynamic and "src/sidscope/pipeline.py" != str(path.relative_to(ROOT)):
                failures.append(f"{path.relative_to(ROOT)} performs dynamic module loading {sorted(set(dynamic))}")
        self.assertEqual(failures, [])
        self.assertIn("src/sidscope/pipeline.py", allowed_files)

    def test_violation_fixtures_in_temp_dir_are_detected(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            core_like = tmp_root / "suspicious.py"
            core_like.write_text("import tools.inventored_helper\nfrom sidinspector import contracts\n")
            from_core = [
                name for name in _resolved_import_names_for(core_like, tmp_root, "sidinspector")
                if name.startswith("tools")
            ]
            self.assertEqual(from_core, ["tools.inventored_helper"])
            workflow_like = tmp_root / "workflow_child.py"
            workflow_like.write_text("from .workflows import run\n\n\ndef run():\n    import tools.secret_entry\n")
            resolved = _resolved_import_names_for(workflow_like, tmp_root, "sidscope")
            self.assertIn("sidscope.workflows", resolved)
            self.assertIn("tools.secret_entry", resolved)
            tool_like = tmp_root / "new_tool.py"
            tool_like.write_text("from tools.sidscope_release_profiles import load_release_profiles\n")
            edges = {
                name.split(".", 1)[1]
                for name in _resolved_import_names_for(tool_like, tmp_root, "tools")
                if name.startswith("tools.")
            }
            recorded = application_rules()["tool_to_tool_imports"].get("new_tool", [])
            self.assertEqual(sorted(edges - set(recorded)), ["sidscope_release_profiles"])

    def test_imported_facades_stay_lightweight_in_this_process(self) -> None:
        import sys
        import sidinspector  # noqa: F401
        import sidscope  # noqa: F401
        forbidden = [name for name in sys.modules if name.split(".")[0] in {"torch", "transformers", "faiss", "tensorflow", "vllm"}]
        self.assertEqual(forbidden, [])


if __name__ == "__main__":
    unittest.main()
