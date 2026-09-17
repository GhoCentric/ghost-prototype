"""Run the frozen Stage-1 purpose-built baseline and emit evidence."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import tempfile

from .contract import contract_digest, contract_packet
from .metrics import source_metrics, storage_probe
from .purpose_built import PurposeBuiltContinuity
from .scenario_runner import run_frozen_suite


def _factory(root: Path, label: str, *, max_records=None, snapshot=None):
    return PurposeBuiltContinuity(
        root / f"{label}.sqlite",
        max_records=max_records,
        snapshot=snapshot,
    )


def build_report(work_root: Path, package_root: Path) -> dict:
    first = run_frozen_suite(_factory, work_root / "run1", "baseline")
    second = run_frozen_suite(_factory, work_root / "run2", "baseline")
    if first["deterministic_digest"] != second["deterministic_digest"]:
        raise RuntimeError("purpose-built baseline is nondeterministic")
    if first["competence"]["passes"] != first["competence"]["total"]:
        raise RuntimeError("purpose-built baseline failed frozen minimum-competence checks")
    report = {
        "stage": "npc_continuity_stage1_frozen_contract_and_purpose_built_baseline",
        "contract_digest": contract_digest(),
        "contract": contract_packet(),
        "baseline_result": deepcopy(first),
        "deterministic_rerun": True,
        "engineering": {
            "source": {
                name: source_metrics(package_root / name)
                for name in ("purpose_built.py", "scenario_runner.py", "contract.py")
            },
            "storage_probe": storage_probe(work_root / "storage"),
        },
        "claims_not_established": [
            "Ghost superiority",
            "NPC believability superiority",
            "developer productivity",
            "market value",
            "novelty or prior-art status",
            "human psychological accuracy",
        ],
        "next_stage_rule": (
            "Stage 2 may add a Ghost adapter only. The contract, scenario runner, "
            "purpose-built baseline, and Stage-1 baseline result must remain hash-frozen."
        ),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    package_root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="ghost_npc_continuity_stage1_") as temp:
        report = build_report(Path(temp), package_root)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
