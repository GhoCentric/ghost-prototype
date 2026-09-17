"""Stage 10: production hot-path autopsy for failed optimized continuity candidate.

The experiment never edits production Ghost. It compares the exact Stage-9-selected
predecessor with the exact failed optimized production candidate in isolated import
roots, then decomposes event/recall latency and runs causal storage toggles.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
from typing import Any

STAGE = "npc_continuity_stage10_production_hotpath_autopsy"


from continuity_benchmark_v1110.stage10_hotpath_analysis import build_summary, classify_hotpath


def _worker_source() -> str:
    # Kept as a standalone worker so baseline and candidate never share imported ghost modules.
    return r'''
from __future__ import annotations
import argparse, gc, json, statistics, tempfile, time
from pathlib import Path
from ghost.api import GhostAPI
from ghost.episode_store import SQLiteEpisodeArchive

DIMS=("respect","threat","betrayal")

def med(fn,reps=3):
    xs=[]
    for _ in range(reps):
        gc.collect(); t=time.perf_counter_ns(); fn(); xs.append((time.perf_counter_ns()-t)/1000.0)
    return float(statistics.median(xs))

def setup(root):
    root.mkdir(parents=True,exist_ok=True)
    store=SQLiteEpisodeArchive(root/"episodes.sqlite")
    api=GhostAPI(episode_store=store); a="npc"
    api.register_interpretation_agent(a)
    api.register_attention_agent(a,config={"release_rate":0.08})
    api.register_emotional_agent(a,inertia={"anger":0.88,"fear":0.86,"grief":0.94,"hope":0.92},spotlight_switch_margin=0.05)
    for d in DIMS: api.configure_interpretation_rule(a,f"action:probe_{d}",{d:1.0})
    return api,store

def ev(api,i):
    d=DIMS[i%3]
    imp={"hope":0.08} if d=="respect" else ({"fear":0.08} if d=="threat" else {"anger":0.08})
    return api.continuity_event("npc",f"probe_{d}",intensity=0.006,source=f"p{i}",emotion_event="probe",emotion_impulses=imp,signals={"interpretation_impulse":0.006})

def seed(api,n=6):
    ids=[]
    for i in range(n): ids += [x["episode_id"] for x in ev(api,i)["episodes"]]
    return ids

def measure_total(root,kind):
    api,s=setup(root)
    try:
        if kind=="event":
            seed(api,6); c=[100]
            def f():
                for _ in range(4): ev(api,c[0]); c[0]+=1
            return med(f)/4.0
        ids=seed(api,6); eid=ids[-1]
        def f():
            for _ in range(4): api.recall_episode(eid,0.2)
        return med(f)/4.0
    finally: s.close()

def timed_patch(obj,name,bucket,label):
    original=getattr(obj,name)
    def wrapped(*args,**kwargs):
        t=time.perf_counter_ns()
        try: return original(*args,**kwargs)
        finally:
            row=bucket.setdefault(label,{"calls":0,"us":0.0}); row["calls"]+=1; row["us"]+=(time.perf_counter_ns()-t)/1000.0
    setattr(obj,name,wrapped)
    return original

def profile_event(root,n=8):
    api,s=setup(root); seed(api,6); bucket={}; restores=[]
    try:
        if hasattr(api,"_continuity_agent_checkpoint"):
            restores.append((api,"_continuity_agent_checkpoint",timed_patch(api,"_continuity_agent_checkpoint",bucket,"checkpoint")))
        else:
            restores.append((api,"snapshot",timed_patch(api,"snapshot",bucket,"checkpoint")))
        for name,label in [("_ensure_continuity_agent","ensure_agent"),("_apply_continuity_emotion","emotion"),("_evaluate_continuity_meaning","interpretation"),("advance_attention_from_state","attention"),("_record_continuity_episodes","episode_register")]:
            restores.append((api,name,timed_patch(api,name,bucket,label)))
        restores.append((api.continuity,"ingest_interpretation_result",timed_patch(api.continuity,"ingest_interpretation_result",bucket,"activation")))
        if hasattr(api,"_compact_continuity_history"):
            restores.append((api,"_compact_continuity_history",timed_patch(api,"_compact_continuity_history",bucket,"history_compaction")))
            h=getattr(api._continuity_optimization,"history",None)
            if h is not None:
                restores.append((h,"store_batch",timed_patch(h,"store_batch",bucket,"cold_store_batch_inclusive")))
                restores.append((h,"_encoded_row",timed_patch(h,"_encoded_row",bucket,"cold_encode_inclusive")))
        t=time.perf_counter_ns()
        for i in range(n): ev(api,200+i)
        total=(time.perf_counter_ns()-t)/1000.0
    finally:
        for obj,name,orig in reversed(restores): setattr(obj,name,orig)
        s.close()
    top=("checkpoint","ensure_agent","emotion","interpretation","activation","attention","episode_register","history_compaction")
    per={k:v["us"]/n for k,v in bucket.items()}
    top_total=sum(per.get(k,0.0) for k in top)
    per["unattributed"] = max(0.0,total/n-top_total)
    shares={k:(per.get(k,0.0)/(total/n) if total>0 else 0.0) for k in top+("unattributed",)}
    return {"total_instrumented_us":total/n,"component_us":per,"top_level_share":shares,"calls":{k:v["calls"] for k,v in bucket.items()}}

def profile_recall(root,n=8):
    api,s=setup(root); ids=seed(api,6); eid=ids[-1]; bucket={}; restores=[]
    try:
        restores.append((s,"get",timed_patch(s,"get",bucket,"episode_lookup")))
        for obj,name,label in [(api,"_ensure_continuity_agent","ensure_agent"),(api.continuity,"recall","continuity_recall"),(api,"apply_emotional_event","emotion_reactivation"),(api,"advance_attention_from_state","attention")]:
            restores.append((obj,name,timed_patch(obj,name,bucket,label)))
        if hasattr(api,"_compact_continuity_history"):
            restores.append((api,"_compact_continuity_history",timed_patch(api,"_compact_continuity_history",bucket,"history_compaction")))
            h=getattr(api._continuity_optimization,"history",None)
            if h is not None:
                restores.append((h,"store_batch",timed_patch(h,"store_batch",bucket,"cold_store_batch_inclusive")))
                restores.append((h,"_encoded_row",timed_patch(h,"_encoded_row",bucket,"cold_encode_inclusive")))
        t=time.perf_counter_ns()
        for _ in range(n): api.recall_episode(eid,0.2)
        total=(time.perf_counter_ns()-t)/1000.0
    finally:
        for obj,name,orig in reversed(restores): setattr(obj,name,orig)
        s.close()
    top=("episode_lookup","ensure_agent","continuity_recall","emotion_reactivation","attention","history_compaction")
    per={k:v["us"]/n for k,v in bucket.items()}
    top_total=sum(per.get(k,0.0) for k in top)
    per["unattributed"] = max(0.0,total/n-top_total)
    shares={k:(per.get(k,0.0)/(total/n) if total>0 else 0.0) for k in top+("unattributed",)}
    return {"total_instrumented_us":total/n,"component_us":per,"top_level_share":shares,"calls":{k:v["calls"] for k,v in bucket.items()}}

def candidate_toggle(root,kind,toggle):
    api,s=setup(root); ids=seed(api,6); eid=ids[-1]
    try:
        history=api._continuity_optimization.history
        original=api._compact_continuity_history
        if toggle in {"no_compaction","deferred"}:
            api._compact_continuity_history=lambda agent: None
        elif toggle=="sync_off":
            history._con.execute("PRAGMA synchronous=OFF")
        c=[300]
        if kind=="event":
            def f():
                for _ in range(4): ev(api,c[0]); c[0]+=1
        else:
            def f():
                for _ in range(4): api.recall_episode(eid,0.2)
        hot=med(f)/4.0
        flush=None
        if toggle=="deferred":
            api._compact_continuity_history=original
            t=time.perf_counter_ns(); api._continuity_optimization.compact("npc",strict=True); flush=(time.perf_counter_ns()-t)/1000.0
        return hot,flush
    finally: s.close()

def representative_rows(root):
    api,s=setup(root)
    try:
        seed(api,6); h=api._continuity_optimization.history; rows=[]
        for subsystem in ("interpretation","emotion","attention"):
            recs=h.records(subsystem,"npc")
            if recs: rows.append((subsystem,"npc",recs[-1]))
        return rows
    finally:s.close()

def durability_probe(root):
    from ghost.continuity_history import CompactContinuityHistoryArchive
    rows=representative_rows(root/"seed")
    if len(rows)!=3: raise RuntimeError("expected three representative cold-history rows")
    encode=med(lambda:[CompactContinuityHistoryArchive._encoded_row(*r) for r in rows],reps=5)
    out={"encode_three_rows_us":encode}
    modes=[("full_delete","FULL","DELETE"),("normal_delete","NORMAL","DELETE"),("normal_wal","NORMAL","WAL"),("off_delete","OFF","DELETE")]
    for label,sync,journal in modes:
        vals=[]
        for i in range(3):
            p=root/f"{label}_{i}.sqlite"; h=CompactContinuityHistoryArchive(p)
            try:
                h._con.execute(f"PRAGMA journal_mode={journal}"); h._con.execute(f"PRAGMA synchronous={sync}")
                t=time.perf_counter_ns(); h.store_batch(rows); vals.append((time.perf_counter_ns()-t)/1000.0)
            finally:h.close()
        out[f"{label}_store_batch_us"]=float(statistics.median(vals))
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--kind",choices=("baseline","candidate"),required=True); ap.add_argument("--root",required=True); ap.add_argument("--out",required=True); a=ap.parse_args()
    root=Path(a.root); result={"kind":a.kind,"totals":{"event_us":measure_total(root/"tot_event","event"),"recall_us":measure_total(root/"tot_recall","recall")},"event_profile":profile_event(root/"prof_event"),"recall_profile":profile_recall(root/"prof_recall")}
    if a.kind=="candidate":
        ne,_=candidate_toggle(root/"toggle_no_event","event","no_compaction"); nr,_=candidate_toggle(root/"toggle_no_recall","recall","no_compaction")
        se,_=candidate_toggle(root/"toggle_off_event","event","sync_off"); sr,_=candidate_toggle(root/"toggle_off_recall","recall","sync_off")
        de,defl=candidate_toggle(root/"toggle_def_event","event","deferred"); dr,drfl=candidate_toggle(root/"toggle_def_recall","recall","deferred")
        result["toggles"]={"no_compaction_event_us":ne,"no_compaction_recall_us":nr,"sync_off_event_us":se,"sync_off_recall_us":sr,"deferred_event_hot_us":de,"deferred_event_flush_us":defl,"deferred_recall_hot_us":dr,"deferred_recall_flush_us":drfl}
        result["durability_probe_us"]=durability_probe(root/"durability")
    Path(a.out).write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
if __name__=="__main__": main()
'''


def _run_worker(script: Path, import_root: Path, kind: str, work_root: Path, out: Path) -> dict[str, Any]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(import_root) + (os.pathsep + existing if existing else "")
    subprocess.run(
        [sys.executable, str(script), "--kind", kind, "--root", str(work_root), "--out", str(out)],
        check=True,
        env=env,
        stdout=subprocess.DEVNULL,
    )
    value = json.loads(out.read_text(encoding="utf-8"))
    if value.get("kind") != kind:
        raise RuntimeError("hot-path worker returned wrong kind")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_autopsy(baseline_root: Path, candidate_root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ghost_stage10_hotpath_") as td:
        temp = Path(td)
        worker = temp / "worker.py"
        worker.write_text(_worker_source(), encoding="utf-8")
        baseline = _run_worker(worker, baseline_root, "baseline", temp / "baseline_work", temp / "baseline.json")
        candidate = _run_worker(worker, candidate_root, "candidate", temp / "candidate_work", temp / "candidate.json")
    result = {
        "stage": STAGE,
        "production_modified": False,
        "frozen_evidence_modified": False,
        "baseline_source_hashes": {
            name: _sha256(baseline_root / "ghost" / name)
            for name in ("api.py", "attention.py", "episode_store.py")
        },
        "candidate_source_hashes": {
            name: _sha256(candidate_root / "ghost" / name)
            for name in (
                "api.py",
                "attention.py",
                "episode_store.py",
                "continuity_history.py",
                "continuity_optimization.py",
            )
        },
        "baseline": baseline,
        "candidate": candidate,
    }
    result["summary"] = build_summary(result)
    result["strict_verdict"] = classify_hotpath(result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_autopsy(args.baseline_root.resolve(), args.candidate_root.resolve())
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
