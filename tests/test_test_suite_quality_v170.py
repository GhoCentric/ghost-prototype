from pathlib import Path


ALLOWED_HELPER_FILES = {
    "__init__.py",
}


def test_no_test_file_is_only_a_print_demo():
    root = Path("tests")

    offenders = []

    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue

        if "legacy_demos" in path.parts:
            continue

        if path.name in ALLOWED_HELPER_FILES:
            continue

        text = path.read_text()

        is_test_file = (
            path.name.startswith("test_")
            or path.name.endswith("_test.py")
        )

        if not is_test_file:
            continue

        has_test_function = "def test_" in text
        has_assertion = "assert " in text or "pytest.raises" in text
        has_hypothesis = "@given" in text

        if not has_test_function:
            offenders.append(str(path))
            continue

        if not has_assertion and not has_hypothesis:
            offenders.append(str(path))

    assert offenders == []
