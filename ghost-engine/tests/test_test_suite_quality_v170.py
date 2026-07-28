"""Static quality gates that keep the test suite behavior-oriented."""

from __future__ import annotations

import ast
from pathlib import Path


ALLOWED_HELPER_FILES = {
    "__init__.py",
}

TEST_ROOT = Path(__file__).resolve().parent


def iter_test_files() -> list[Path]:
    return sorted(
        path
        for path in TEST_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts
        and "legacy_demos" not in path.parts
        and path.name not in ALLOWED_HELPER_FILES
        and (
            path.name.startswith("test_")
            or path.name.endswith("_test.py")
        )
    )


def is_pytest_raises(call: ast.Call) -> bool:
    return bool(
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "pytest"
        and call.func.attr == "raises"
    )


def is_assertion_helper_call(call: ast.Call) -> bool:
    if isinstance(call.func, ast.Name):
        return call.func.id.startswith("assert_")

    if isinstance(call.func, ast.Attribute):
        return call.func.attr.startswith("assert_")

    return False


def is_json_serialization_check(call: ast.Call) -> bool:
    return bool(
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "json"
        and call.func.attr == "dumps"
    )


def has_executable_verification(
    node: ast.FunctionDef,
) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            return True

        if isinstance(child, ast.Call):
            if is_pytest_raises(child):
                return True

            if is_assertion_helper_call(child):
                return True

            if is_json_serialization_check(child):
                return True

    return False


def is_broad_exception(
    handler: ast.ExceptHandler,
) -> bool:
    if handler.type is None:
        return True

    if isinstance(handler.type, ast.Name):
        return handler.type.id in {
            "Exception",
            "BaseException",
        }

    if isinstance(handler.type, ast.Tuple):
        return any(
            isinstance(item, ast.Name)
            and item.id in {
                "Exception",
                "BaseException",
            }
            for item in handler.type.elts
        )

    return False


def test_every_test_function_has_an_executable_verification():
    offenders = []

    for path in iter_test_files():
        tree = ast.parse(
            path.read_text(),
            filename=str(path),
        )

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue

            if not node.name.startswith("test_"):
                continue

            if not has_executable_verification(node):
                offenders.append(
                    f"{path.relative_to(TEST_ROOT.parent)}"
                    f"::{node.name}"
                )

    assert not offenders, (
        "Every test must contain an executable verification "
        "(assert, pytest.raises, assert_* helper, mock "
        "assertion, or JSON serialization check). "
        f"Missing: {offenders}"
    )


def test_suite_rejects_broad_exception_swallowing_and_global_rng():
    broad_exception_handlers = []
    global_rng_calls = []

    for path in iter_test_files():
        tree = ast.parse(
            path.read_text(),
            filename=str(path),
        )

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ExceptHandler)
                and is_broad_exception(node)
            ):
                broad_exception_handlers.append(
                    f"{path.relative_to(TEST_ROOT.parent)}:"
                    f"{node.lineno}"
                )

            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "random"
                and node.attr != "Random"
            ):
                global_rng_calls.append(
                    f"{path.relative_to(TEST_ROOT.parent)}:"
                    f"{node.lineno}"
                )

    assert not broad_exception_handlers, (
        "Tests may not swallow Exception/BaseException or use "
        "bare except handlers: "
        f"{broad_exception_handlers}"
    )

    assert not global_rng_calls, (
        "Tests must use a seeded random.Random instance, not "
        "module-level random calls: "
        f"{global_rng_calls}"
    )
