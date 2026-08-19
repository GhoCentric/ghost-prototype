import { loadPyodide } from 'https://cdn.jsdelivr.net/pyodide/v0.28.3/full/pyodide.mjs';

let pyodide=null, readyPromise=null;
const postStatus=(message,detail='')=>self.postMessage({kind:'status',message,detail});

const PY=String.raw`
import io, json, hashlib
import ghost
from contextlib import redirect_stdout
from ghost import GhostAPI
from ghost.examples.epistemic_api_smoke_demo import run_demo as _epistemic_run_demo
# GHOST_AUDIT_HOTFIX_V1

def _rel(rel):
    d = rel.get("diagnostics") or {}
    return {
        "trust": float(rel["trust"]),
        "state": rel["state"],
        "maturity": float(rel.get("maturity", 0.0)),
        "volatility": float(rel.get("volatility", 0.0)),
        "pressure": d.get("pressure"),
        "near_break": bool(d.get("near_break", False)),
    }

def ghost_relationship_demo():
    def run(help_count):
        g = GhostAPI()
        for _ in range(help_count):
            g.apply_event("player", "guard", {"type":"help", "intensity":1.0})
        before = g.get_relationship("player", "guard")
        g.apply_event("player", "guard", {"type":"betrayal", "intensity":1.0})
        after = g.get_relationship("player", "guard")
        return {"before":_rel(before), "after":_rel(after)}
    return json.dumps({"short":run(2), "long":run(20)}, allow_nan=False)

def ghost_determinism_demo():
    def run_once():
        g = GhostAPI()
        for _ in range(2):
            g.apply_event("player", "guard", {"type":"help", "intensity":1.0})
        event_packet = g.apply_event("player", "guard", {"type":"betrayal", "intensity":1.0})
        relationship = g.get_relationship("player", "guard")
        payload = {"event_packet":event_packet, "relationship":relationship}
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)

    output_a = run_once()
    output_b = run_once()
    hash_a = hashlib.sha256(output_a.encode("utf-8")).hexdigest()
    hash_b = hashlib.sha256(output_b.encode("utf-8")).hexdigest()
    return json.dumps({
        "match": output_a == output_b,
        "hash_a": hash_a,
        "hash_b": hash_b,
        "bytes": len(output_a.encode("utf-8")),
    }, allow_nan=False)

def ghost_social_demo():
    g = GhostAPI()
    packet = g.propagate_social_event(
        source="player", target="merchant", event="betrayal",
        observers=["guard","elder"], weights={"guard":1.0,"elder":0.25}
    )
    return json.dumps({
        "merchant": _rel(g.get_relationship("player","merchant")),
        "guard": _rel(g.get_relationship("player","guard")),
        "elder": _rel(g.get_relationship("player","elder")),
        "heat": float(packet["heat"]),
        "pressure": packet["pressure"],
        "world_effects": packet["world_effects"],
    }, allow_nan=False)

def ghost_social_determinism_demo():
    # Determinism contract: same starting snapshot + same ordered input.
    base = GhostAPI()
    starting_snapshot = base.snapshot()

    def run_once():
        g = GhostAPI.from_snapshot(starting_snapshot)
        packet = g.propagate_social_event(
            source="player", target="merchant", event="betrayal",
            observers=["guard", "elder"], weights={"guard": 1.0, "elder": 0.25}
        )
        payload = {
            "merchant": _rel(g.get_relationship("player", "merchant")),
            "guard": _rel(g.get_relationship("player", "guard")),
            "elder": _rel(g.get_relationship("player", "elder")),
            "heat": float(packet["heat"]),
            "pressure": packet["pressure"],
            "world_effects": packet["world_effects"],
        }
        return json.dumps(
            payload,
            sort_keys=True, separators=(",", ":"), allow_nan=False
        )

    output_a = run_once()
    output_b = run_once()
    parsed = json.loads(output_a)
    return json.dumps({
        "match": output_a == output_b,
        "hash_a": hashlib.sha256(output_a.encode("utf-8")).hexdigest(),
        "hash_b": hashlib.sha256(output_b.encode("utf-8")).hexdigest(),
        "bytes": len(output_a.encode("utf-8")),
        "guard_trust": float(parsed["guard"]["trust"]),
        "elder_trust": float(parsed["elder"]["trust"]),
    }, allow_nan=False)

def ghost_emotion_demo():
    def profile(sensitivities=None):
        g = GhostAPI()
        for _ in range(20):
            g.apply_event(
                "player",
                "guard",
                {"type": "help", "intensity": 1.0},
            )
        g.register_emotional_agent(
            "guard",
            sensitivities=sensitivities,
        )
        packet = g.apply_layered_event(
            "player",
            "guard",
            {"type": "betrayal", "intensity": 1.0},
        )
        state = packet["layered_state"]
        return {
            "relationship": {
                "trust": float(state["trust"]),
                "state": state["relationship_state"],
            },
            "levels": {
                name: float(value)
                for name, value in state["emotional_levels"].items()
            },
            "dominant_emotion": state["dominant_emotion"],
            "dominant_salience": float(state["dominant_salience"] or 0.0),
            "raw_leader_emotion": state["raw_leader_emotion"],
            "raw_leader_salience": float(state["raw_leader_salience"] or 0.0),
            "spotlight_switch_margin": float(state["spotlight_switch_margin"]),
        }

    def run_once():
        balanced = profile()
        fear_sensitive = profile({
            "anger": 0.5,
            "fear": 3.0,
            "grief": 0.5,
        })
        return {
            "balanced": balanced,
            "fear_sensitive": fear_sensitive,
        }

    output_a = json.dumps(
        run_once(),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    output_b = json.dumps(
        run_once(),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    parsed = json.loads(output_a)
    balanced = parsed["balanced"]
    fear_sensitive = parsed["fear_sensitive"]
    same_relationship = (
        balanced["relationship"] == fear_sensitive["relationship"]
    )
    different_emotions = (
        balanced["levels"] != fear_sensitive["levels"]
    )
    different_spotlight = (
        balanced["dominant_emotion"]
        != fear_sensitive["dominant_emotion"]
    )
    return json.dumps({
        **parsed,
        "same_relationship": same_relationship,
        "different_emotions": different_emotions,
        "different_spotlight": different_spotlight,
        "match": output_a == output_b,
        "hash_a": hashlib.sha256(output_a.encode("utf-8")).hexdigest(),
        "hash_b": hashlib.sha256(output_b.encode("utf-8")).hexdigest(),
        "bytes": len(output_a.encode("utf-8")),
    }, allow_nan=False)

def _belief(b):
    cause=b["dimensions"]["cause"]
    quantity=b["dimensions"]["quantity"]
    return {
        "id": b["id"],
        "previous_belief_id": b.get("previous_belief_id"),
        "cause": {"candidate":cause["dominant_candidate"], "confidence":float(cause["confidence"])},
        "quantity": {"candidate":quantity["dominant_candidate"], "confidence":float(quantity["confidence"])},
    }

def ghost_epistemic_demo():
    buf=io.StringIO()
    with redirect_stdout(buf):
        r=_epistemic_run_demo()
    if not all(r["checks"].values()):
        raise RuntimeError("Packaged epistemic smoke checks failed: "+repr(r["checks"]))
    fact=r["fact"]; report=r["report"]
    return json.dumps({
        "fact": {"id":fact["id"], "fact_id":fact["fact_id"], "quantity":fact["attributes"]["quantity"], "location":fact["attributes"]["location"]},
        "report": {"id":report["id"], "statement":report["claim"]["statement"], "confidence":float(report["confidence"])},
        "initial": _belief(r["player_initial_belief"]),
        "revised": _belief(r["player_revised_belief"]),
        "checks": r["checks"],
    }, allow_nan=False)

def ghost_epistemic_determinism_demo():
    def run_once():
        payload = json.loads(ghost_epistemic_demo())
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)

    output_a = run_once()
    output_b = run_once()
    parsed = json.loads(output_a)
    checks = parsed["checks"]
    fact = parsed["fact"]
    initial = parsed["initial"]
    revised = parsed["revised"]
    return json.dumps({
        "match": output_a == output_b,
        "hash_a": hashlib.sha256(output_a.encode("utf-8")).hexdigest(),
        "hash_b": hashlib.sha256(output_b.encode("utf-8")).hexdigest(),
        "bytes": len(output_a.encode("utf-8")),
        "fact_id": fact["fact_id"],
        "fact_quantity": fact["quantity"],
        "fact_preserved": fact["fact_id"] == "millcross_food_001" and fact["quantity"] == 6,
        "initial_id": initial["id"],
        "revised_id": revised["id"],
        "revision_linked": revised["previous_belief_id"] == initial["id"],
        "snapshot_round_trip": bool(checks["snapshot_round_trip_matches"]),
    }, allow_nan=False)


def _configure_v110_cognition(g):
    g.register_emotional_agent(
        "sera",
        initial={"anger": 0.62, "fear": 0.28},
    )
    g.register_interpretation_agent(
        "sera",
        baseline={"betrayal": 0.10, "cooperation": 0.05},
        thresholds={
            "betrayal": {"enter": 0.60, "exit": 0.40},
            "cooperation": 0.70,
        },
        rules={
            "action:report_evidence_to_guards": {
                "betrayal": 0.15,
                "cooperation": 0.05,
            },
            "confidential_evidence_shared": {"betrayal": 0.70},
            "authority_involved": {"betrayal": 0.10},
        },
    )
    g.register_interpretation_agent(
        "rowan",
        baseline={"betrayal": 0.02, "cooperation": 0.12},
        thresholds={"betrayal": 0.75, "cooperation": 0.55},
        rules={
            "action:report_evidence_to_guards": {"cooperation": 0.65},
            "confidential_evidence_shared": {"betrayal": 0.05},
            "authority_involved": {"cooperation": 0.10},
        },
    )
    g.register_attention_agent("sera")


def _focus_signals(focus, repetition, stability, novelty=0.0, threat=0.0):
    return {
        "task_focus": focus,
        "repetition": repetition,
        "stability": stability,
        "novelty": novelty,
        "threat": threat,
        "contradiction": 0.0,
        "interpretation_impulse": 0.0,
    }


def _meaning_view(packet):
    state = packet["state"]
    return {
        "betrayal": float(state["levels"].get("betrayal", 0.0)),
        "cooperation": float(state["levels"].get("cooperation", 0.0)),
        "active": list(packet["active_interpretations"]),
        "strongest": packet["strongest_interpretation"],
        "strongest_level": float(packet["strongest_level"] or 0.0),
    }


def _cognitive_once():
    g = GhostAPI()
    _configure_v110_cognition(g)
    features = {
        "confidential_evidence_shared": 1.0,
        "authority_involved": 1.0,
    }
    sera = g.evaluate_action_meaning(
        "sera",
        "report_evidence_to_guards",
        features,
        source="player",
        provenance={"evidence_id": "millcross-ledger"},
    )
    rowan = g.evaluate_action_meaning(
        "rowan",
        "report_evidence_to_guards",
        features,
        source="player",
        provenance={"evidence_id": "millcross-ledger"},
    )

    source_before = {
        "emotion": g.emotional_state("sera"),
        "interpretation": g.interpretation_state("sera"),
    }
    bridge = g.persistent_salience("sera")
    trajectory = [
        _focus_signals(0.88, 0.55, 0.82, novelty=0.12),
        _focus_signals(0.94, 0.72, 0.88, novelty=0.06),
        _focus_signals(0.97, 0.86, 0.91, novelty=0.03),
        _focus_signals(1.00, 0.94, 0.95),
        _focus_signals(1.00, 1.00, 0.97),
        _focus_signals(1.00, 1.00, 1.00),
        _focus_signals(1.00, 1.00, 1.00),
        _focus_signals(1.00, 1.00, 1.00),
    ]
    steps = []
    last = None
    for signals in trajectory:
        last = g.advance_attention_from_state(
            "sera",
            signals=signals,
            provenance={"browser_demo": "task_focus"},
        )["attention"]
        steps.append({
            "pressure": float(last["flow_pressure_after"]),
            "active": bool(last["flow_active_after"]),
            "gain": float(last["attention_gain"]),
        })

    breakthrough = g.advance_attention_from_state(
        "sera",
        signals=_focus_signals(1.0, 1.0, 1.0, threat=1.0),
        provenance={"browser_demo": "strong_threat"},
    )["attention"]
    source_after = {
        "emotion": g.emotional_state("sera"),
        "interpretation": g.interpretation_state("sera"),
    }
    snapshot = g.snapshot()
    restored = GhostAPI.from_snapshot(snapshot)
    key = "interpretation:betrayal"
    return {
        "release_commit": "067bc8cd5003f5345ea15dfe94ae513462c295b7",
        "objective": {
            "action": "report_evidence_to_guards",
            "features": features,
        },
        "sera": _meaning_view(sera),
        "rowan": _meaning_view(rowan),
        "bridge": {
            "dimensions": len(bridge["salience"]),
            "sources": bridge["sources"],
        },
        "flow_steps": steps,
        "flow": {
            "pressure": float(last["flow_pressure_after"]),
            "active": bool(last["flow_active_after"]),
            "gain": float(last["attention_gain"]),
            "underlying_betrayal": float(last["underlying_salience"][key]),
            "attended_betrayal": float(last["attended_salience"][key]),
        },
        "breakthrough": {
            "breakthrough": bool(breakthrough["breakthrough"]),
            "resurfaced": bool(breakthrough["resurfaced"]),
            "gain": float(breakthrough["attention_gain"]),
            "attended_betrayal": float(breakthrough["attended_salience"][key]),
        },
        "source_immutable": source_before == source_after,
        "snapshot_match": restored.snapshot() == snapshot,
    }


def ghost_cognitive_demo():
    return json.dumps(_cognitive_once(), allow_nan=False)


def ghost_cognitive_determinism_demo():
    output_a = json.dumps(
        _cognitive_once(), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    output_b = json.dumps(
        _cognitive_once(), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    parsed = json.loads(output_a)
    return json.dumps({
        "match": output_a == output_b,
        "hash_a": hashlib.sha256(output_a.encode("utf-8")).hexdigest(),
        "hash_b": hashlib.sha256(output_b.encode("utf-8")).hexdigest(),
        "bytes": len(output_a.encode("utf-8")),
        "source_immutable": bool(parsed["source_immutable"]),
        "snapshot_match": bool(parsed["snapshot_match"]),
        "breakthrough": bool(parsed["breakthrough"]["breakthrough"]),
    }, allow_nan=False)


def ghost_preflight():
    a=json.loads(ghost_relationship_demo())
    d=json.loads(ghost_determinism_demo())
    b=json.loads(ghost_social_demo())
    c=json.loads(ghost_epistemic_demo())
    v110=json.loads(ghost_cognitive_demo())
    assert a["short"]["after"]["state"] == "hostile"
    assert d["match"] is True
    assert d["hash_a"] == d["hash_b"]
    assert a["long"]["after"]["state"] in ("friendly","neutral","hostile")
    assert b["merchant"]["trust"] < 0.0
    assert b["guard"]["trust"] < 0.0
    assert b["elder"]["trust"] < 0.0
    assert c["checks"]["ledger_revised_player_belief"] is True
    assert c["initial"]["id"] != c["revised"]["id"]
    assert ghost.__version__ == "1.10.0"
    assert hasattr(GhostAPI, "apply_layered_event")
    assert hasattr(GhostAPI, "evaluate_action_meaning")
    assert hasattr(GhostAPI, "advance_attention_from_state")
    assert v110["sera"]["betrayal"] > 0.90
    assert v110["rowan"]["cooperation"] > 0.70
    assert v110["flow"]["active"] is True
    assert v110["flow"]["gain"] < 1.0
    assert v110["source_immutable"] is True
    assert v110["breakthrough"]["breakthrough"] is True
    assert v110["breakthrough"]["gain"] == 1.0
    assert v110["snapshot_match"] is True
    return json.dumps({"package_version":"1.10.0","release_commit":"067bc8cd","relationship":True,"determinism":True,"social":True,"epistemic":True,"multi_emotion_api":True,"interpretation":True,"attention":True,"salience_bridge":True})
`;

async function boot(){
  postStatus('Loading Python runtime…','Downloading Pyodide 0.28.3');
  pyodide=await loadPyodide({indexURL:'https://cdn.jsdelivr.net/pyodide/v0.28.3/full/'});
  postStatus('Loading package installer…','Preparing micropip');
  await pyodide.loadPackage('micropip');
  const micropip=pyodide.pyimport('micropip');
  postStatus('Installing released Ghost v1.10.0…','Fetching the pure-Python wheel from PyPI');
  await micropip.install('ghocentric-ghost-engine==1.10.0');
  micropip.destroy();
  postStatus('Validating released v1.10.0 cognitive paths…','Interpretation • persistent salience • attention/flow • breakthrough • replay');
  await pyodide.runPythonAsync(PY);
  JSON.parse(await pyodide.runPythonAsync('ghost_preflight()'));
  self.postMessage({kind:'ready'});
}
readyPromise=boot().catch(err=>{self.postMessage({kind:'fatal',error:err?.stack||err?.message||String(err)});throw err});

async function execute(type){
  await readyPromise;
  const code={relationship:'ghost_relationship_demo()',determinism:'ghost_determinism_demo()',emotion:'ghost_emotion_demo()',social:'ghost_social_demo()',social_determinism:'ghost_social_determinism_demo()',epistemic:'ghost_epistemic_demo()',epistemic_determinism:'ghost_epistemic_determinism_demo()',cognitive:'ghost_cognitive_demo()',cognitive_determinism:'ghost_cognitive_determinism_demo()'}[type];
  if(!code)throw new Error(`Unknown request: ${type}`);
  return JSON.parse(await pyodide.runPythonAsync(code));
}
self.onmessage=async e=>{const {id,type}=e.data||{};if(!id||!type)return;try{self.postMessage({id,ok:true,result:await execute(type)})}catch(err){self.postMessage({id,ok:false,error:err?.stack||err?.message||String(err)})}};
