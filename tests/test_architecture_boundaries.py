from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "src" / "sidinspector"

MATRIX_PATH = ROOT / "docs" / "reproducibility" / "sidscope_module_dependencies.json"


def allowed_target_imports() -> dict[str, set[str]]:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    return {
        module: set(config["allowed_internal_imports"])
        for module, config in matrix["modules"].items()
    }


def _module_name(path: Path) -> str:
    relative = path.relative_to(PACKAGE_ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(("sidinspector", *parts))


def _resolved_import_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    current = _module_name(path).split(".")
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


if __name__ == "__main__":
    unittest.main()
