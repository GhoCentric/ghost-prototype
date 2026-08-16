import { loadPyodide } from 'https://cdn.jsdelivr.net/pyodide/v0.28.3/full/pyodide.mjs';

let pyodide=null, readyPromise=null;
const postStatus=(message,detail='')=>self.postMessage({kind:'status',message,detail});

const PY=String.raw`
import io, json
from contextlib import redirect_stdout
from ghost import GhostAPI
from ghost.examples.epistemic_api_smoke_demo import run_demo as _epistemic_run_demo

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
        "fact": {"id":fact["id"], "quantity":fact["attributes"]["quantity"], "location":fact["attributes"]["location"]},
        "report": {"id":report["id"], "statement":report["claim"]["statement"], "confidence":float(report["confidence"])},
        "initial": _belief(r["player_initial_belief"]),
        "revised": _belief(r["player_revised_belief"]),
        "checks": r["checks"],
    }, allow_nan=False)

def ghost_preflight():
    a=json.loads(ghost_relationship_demo())
    b=json.loads(ghost_social_demo())
    c=json.loads(ghost_epistemic_demo())
    assert a["short"]["after"]["state"] == "hostile"
    assert a["long"]["after"]["state"] in ("friendly","neutral","hostile")
    assert b["merchant"]["trust"] < 0.0
    assert b["guard"]["trust"] < 0.0
    assert b["elder"]["trust"] < 0.0
    assert c["checks"]["ledger_revised_player_belief"] is True
    assert c["initial"]["id"] != c["revised"]["id"]
    return json.dumps({"relationship":True,"social":True,"epistemic":True})
`;

async function boot(){
  postStatus('Loading Python runtime…','Downloading Pyodide 0.28.3');
  pyodide=await loadPyodide({indexURL:'https://cdn.jsdelivr.net/pyodide/v0.28.3/full/'});
  postStatus('Loading package installer…','Preparing micropip');
  await pyodide.loadPackage('micropip');
  const micropip=pyodide.pyimport('micropip');
  postStatus('Installing Ghost v1.9.1…','Fetching the released pure-Python wheel from PyPI');
  await micropip.install('ghocentric-ghost-engine==1.9.1');
  micropip.destroy();
  postStatus('Validating engine paths…','Relationship history • social propagation • epistemic revision');
  await pyodide.runPythonAsync(PY);
  JSON.parse(await pyodide.runPythonAsync('ghost_preflight()'));
  self.postMessage({kind:'ready'});
}
readyPromise=boot().catch(err=>{self.postMessage({kind:'fatal',error:err?.stack||err?.message||String(err)});throw err});

async function execute(type){
  await readyPromise;
  const code={relationship:'ghost_relationship_demo()',social:'ghost_social_demo()',epistemic:'ghost_epistemic_demo()'}[type];
  if(!code)throw new Error(`Unknown request: ${type}`);
  return JSON.parse(await pyodide.runPythonAsync(code));
}
self.onmessage=async e=>{const {id,type}=e.data||{};if(!id||!type)return;try{self.postMessage({id,ok:true,result:await execute(type)})}catch(err){self.postMessage({id,ok:false,error:err?.stack||err?.message||String(err)})}};
