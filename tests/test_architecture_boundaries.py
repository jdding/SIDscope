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


def internal_target_imports(path: Path) -> set[str]:
    allowed = allowed_target_imports()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            if not name.startswith("sidinspector."):
                continue
            module = name.split(".", 2)[1]
            if module in allowed:
                imports.add(module)
    return imports


class ArchitectureBoundaryTest(unittest.TestCase):
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
