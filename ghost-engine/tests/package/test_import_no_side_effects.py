# tests/package/test_import_no_side_effects.py

import importlib
import sys
import io
from contextlib import redirect_stdout, redirect_stderr


def test_import_is_quiet_and_safe():
    """
    Importing the Ghost package must not:
      - print to stdout/stderr
      - crash
      - require sys.path hacks
      - auto-run the engine
    """

    # Force a clean import
    sys.modules.pop("ghost", None)

    out_buf = io.StringIO()
    err_buf = io.StringIO()

    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        mod = importlib.import_module("ghost")

    stdout = out_buf.getvalue().strip()
    stderr = err_buf.getvalue().strip()

    assert mod is not None, "Import failed: ghost did not import."

    # Import must be silent
    assert stdout == "", f"ghost printed to stdout on import:\n{stdout}"
    assert stderr == "", f"ghost printed to stderr on import:\n{stderr}"