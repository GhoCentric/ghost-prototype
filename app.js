const $ = (id) => document.getElementById(id);
const screens = [...document.querySelectorAll('.screen')];
let worker, ready = false, reqId = 0, epistemicData = null, cognitiveData = null;
const pending = new Map();

function resetViewport(){
  document.documentElement.scrollTop=0;
  document.body.scrollTop=0;
  window.scrollTo({top:0,left:0,behavior:'auto'});
}
function screen(id){
  // Change scenes first, then reset again after layout settles so the fixed header never hides the next heading.
  screens.forEach(s=>s.classList.toggle('active',s.id===id));
  resetViewport();
  requestAnimationFrame(()=>{ resetViewport(); setTimeout(resetViewport,0); });
}
function pretty(v){ return String(v ?? '—').replaceAll('_',' '); }
function trust(v){ const n=Number(v); return `${n>=0?'+':''}${n.toFixed(3)}`; }
function toast(msg){ const el=$('toast'); el.textContent=msg; el.classList.add('show'); clearTimeout(toast.t); toast.t=setTimeout(()=>el.classList.remove('show'),1900); }
function status(kind,text,detail=''){ const el=$('runtime'); el.className=`runtime ${kind}`; el.querySelector('span').textContent=text; if(detail)$('loadDetail').textContent=detail; }
function request(type){ return new Promise((resolve,reject)=>{ const id=++reqId; pending.set(id,{resolve,reject}); worker.postMessage({id,type}); }); }
function bar(el,v,scale=1.6){ const n=Math.max(-scale,Math.min(scale,Number(v))), pct=Math.abs(n)/scale*50; if(n>=0){el.style.left='50%';el.style.width=`${pct}%`;el.style.background='var(--green)'}else{el.style.left=`${50-pct}%`;el.style.width=`${pct}%`;el.style.background='var(--red)'} }
function mini(el,v,scale=1){ const n=Math.max(-scale,Math.min(scale,Number(v))); el.style.width=`${50+(n/scale)*50}%`; el.style.background=n<0?'var(--red)':'var(--green)'; }
function confidence(barEl,textEl,v){ const n=Math.max(0,Math.min(1,Number(v))); barEl.style.width=`${n*100}%`; textEl.textContent=`confidence ${n.toFixed(3)}`; }
function emotionLevel(v){ const n=Math.max(0,Math.min(1,Number(v))); return n; }
function emotionBar(el,v){ const n=emotionLevel(v); el.style.width=`${n*100}%`; el.dataset.level=n.toFixed(3); }
function renderEmotion(prefix,obj){
 const levels=obj.levels||{};
 const state=String(obj.relationship?.state||'—').toUpperCase();
 $(`${prefix}Relation`).textContent=`${state} ${trust(obj.relationship?.trust)}`;
 for(const name of ['anger','fear','grief','hope','joy']){
   const value=emotionLevel(levels[name]??0);
   const cap=name[0].toUpperCase()+name.slice(1);
   $(`${prefix}${cap}Val`).textContent=value.toFixed(3);
   emotionBar($(`${prefix}${cap}Bar`),value);
 }
 $(`${prefix}Spotlight`).textContent=String(obj.dominant_emotion||'none').toUpperCase();
 $(`${prefix}Salience`).textContent=`salience ${Number(obj.dominant_salience||0).toFixed(3)} • switch margin ${Number(obj.spotlight_switch_margin||0).toFixed(2)}`;
}

function boot(){
 ready=false; $('start').disabled=true; $('start').querySelector('span').textContent='Loading Ghost…'; $('retry').classList.add('hidden');
 status('loading','Booting Ghost…','Pyodide → released 1.9.2 base → verified v1.10-dev overlay @ 123ebde6');
 if(worker) worker.terminate(); worker=new Worker('./ghost-worker.js?v=cognition-1100-1',{type:'module'});
 worker.onmessage=(e)=>{ const m=e.data;
   if(m.kind==='status'){status('loading',m.message,m.detail||'');return}
   if(m.kind==='ready'){ready=true;status('ready','v1.10 checkpoint ready','Validated: v1.9.2 base • exact v1.10 overlay • interpretation • salience bridge • attention/flow');$('start').disabled=false;$('start').querySelector('span').textContent='Enter Ghost State';return}
   if(m.kind==='fatal'){status('error','Ghost failed to load',m.error||'Unknown error');$('retry').classList.remove('hidden');return}
   if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.ok?p.resolve(m.result):p.reject(new Error(m.error||'Ghost request failed'));}
 };
 worker.onerror=(e)=>{status('error','Worker error',e.message||'Worker failed');$('retry').classList.remove('hidden')};
}
$('retry').onclick=boot; $('start').onclick=()=>ready&&screen('history');

$('betray').onclick=async()=>{
 const btn=$('betray'); btn.disabled=true; btn.textContent='GHOST IS RESOLVING…';
 try{
  const d=await request('relationship');
  for(const [prefix,obj] of [['short',d.short],['long',d.long]]){
    $(`${prefix}Trust`).textContent=`${trust(obj.before.trust)} → ${trust(obj.after.trust)}`;
    bar($(`${prefix}Bar`),obj.after.trust);
    $(`${prefix}State`).textContent=pretty(obj.after.state).toUpperCase();
    $(`${prefix}Maturity`).textContent=Number(obj.after.maturity).toFixed(3);
    $(`${prefix}Pressure`).textContent=pretty(obj.after.pressure).toUpperCase();
    const hostile=obj.after.state==='hostile';
    $(`${prefix}Card`).classList.add(hostile?'broken':'steady');
    $(`${prefix}Guard`).classList.add(hostile?'hostile':'steady');
    $(`${prefix}Tag`).textContent=hostile?'STATE: HOSTILE':'STATE: FRIENDLY';
    $(`${prefix}Tag`).classList.add(hostile?'hostile':'friendly');
  }
  $('historyCaption').textContent=`Ghost returned ${d.short.after.state} for A and ${d.long.after.state} for B.`;
  $('historyProof').classList.remove('hidden'); $('determinismPanel').classList.remove('hidden'); $('emotionLayer').classList.remove('hidden'); btn.textContent='SAME EVENT RESOLVED'; toast('Same event. Different accumulated state.');
 }catch(e){btn.disabled=false;btn.textContent='TRY AGAIN';$('historyCaption').textContent=e.message}
};


$('determinism').onclick=async()=>{
 const btn=$('determinism'); btn.disabled=true; btn.textContent='RUNNING TWICE…';
 try{
  const d=await request('determinism'), result=$('determinismResult');
  $('hashA').textContent=d.hash_a; $('hashB').textContent=d.hash_b;
  $('detVerdict').textContent=d.match?'MATCH — IDENTICAL CANONICAL JSON':'MISMATCH';
  $('detDetail').textContent=`${d.bytes} canonical JSON bytes compared directly • SHA-256 shown above`;
  result.classList.remove('hidden','fail'); if(!d.match)result.classList.add('fail');
  btn.textContent=d.match?'DETERMINISM VERIFIED':'MISMATCH DETECTED';
  toast(d.match?'Same input. Same output.':'Determinism check failed.');
 }catch(e){btn.disabled=false;btn.textContent='TRY AGAIN';$('historyCaption').textContent=e.message}
};

$('emotionAction').onclick=async()=>{
 const btn=$('emotionAction'); btn.disabled=true; btn.textContent='GHOST IS LAYERING STATE…';
 try{
  const d=await request('emotion');
  renderEmotion('balanced',d.balanced);
  renderEmotion('fear',d.fear_sensitive);
  $('emotionCompare').classList.remove('hidden');
  $('emotionProof').classList.remove('hidden');
  $('emotionRelationCheck').textContent=d.same_relationship?'SAME — CONTROL HELD':'MISMATCH';
  $('emotionVectorCheck').textContent=d.different_emotions&&d.different_spotlight?'DIFFERENT — ANGER ↔ FEAR':'CHECK FAILED';
  $('emotionReplayCheck').textContent=d.match?'MATCH — SAME CANONICAL JSON':'MISMATCH';
  $('emotionHash').textContent=d.hash_a;
  btn.textContent='EMOTIONAL STATE LAYERED';
  $('historyNext').classList.remove('hidden');
  toast('Same relationship. Different emotional state.');
 }catch(e){
  btn.disabled=false;btn.textContent='TRY EMOTION LAYER AGAIN';
  $('historyCaption').textContent=e.message;
 }
};

$('historyNext').onclick=()=>screen('social');

$('socialAction').onclick=async()=>{
 const btn=$('socialAction'); btn.disabled=true; btn.textContent='PROPAGATING…';
 try{
  const d=await request('social'), market=$('market'); market.classList.remove('go'); void market.offsetWidth; market.classList.add('go');
  setTimeout(()=>{$('merchantTrust').textContent=`trust ${trust(d.merchant.trust)}`;mini($('merchantBar'),d.merchant.trust)},180);
  setTimeout(()=>{$('guardTrust').textContent=`trust ${trust(d.guard.trust)}`;mini($('guardBar'),d.guard.trust);$('guardNode').querySelector('.avatar').classList.add('hostile')},550);
  setTimeout(()=>{$('elderTrust').textContent=`trust ${trust(d.elder.trust)}`;mini($('elderBar'),d.elder.trust)},820);
  setTimeout(()=>{$('socialCaption').textContent=`Social heat ${Number(d.heat).toFixed(3)} • pressure ${pretty(d.pressure)}`;$('socialProof').classList.remove('hidden');$('socialAuditPanel').classList.remove('hidden');$('socialNext').classList.remove('hidden')},1200);
  btn.textContent='EVENT PROPAGATED'; toast('The event moved beyond its target.');
 }catch(e){btn.disabled=false;btn.textContent='TRY AGAIN';$('socialCaption').textContent=e.message}
};
$('socialDeterminism').onclick=async()=>{
 const btn=$('socialDeterminism'); btn.disabled=true; btn.textContent='RUNNING PROPAGATION TWICE…';
 try{
  const d=await request('social_determinism'), result=$('socialDeterminismResult');
  $('socialHashA').textContent=d.hash_a; $('socialHashB').textContent=d.hash_b;
  $('socialDetVerdict').textContent=d.match?'MATCH — PROPAGATION REPRODUCED':'MISMATCH';
  $('socialDetDetail').textContent=`guard ${trust(d.guard_trust)} @ 1.00 • elder ${trust(d.elder_trust)} @ 0.25 • ${d.bytes} canonical JSON bytes`;
  result.classList.remove('hidden','fail'); if(!d.match)result.classList.add('fail');
  btn.textContent=d.match?'PROPAGATION VERIFIED':'MISMATCH DETECTED';
  toast(d.match?'Same event. Same weighted propagation.':'Propagation replay failed.');
 }catch(e){btn.disabled=false;btn.textContent='TRY AGAIN';$('socialCaption').textContent=e.message}
};

$('socialNext').onclick=()=>screen('belief');

function renderBelief(b,statusText){ $('beliefStatus').textContent=statusText; $('cause').textContent=pretty(b.cause.candidate).toUpperCase(); $('quantity').textContent=pretty(b.quantity.candidate).toUpperCase(); confidence($('causeConf'),$('causeText'),b.cause.confidence); confidence($('quantityConf'),$('quantityText'),b.quantity.confidence); }
$('hear').onclick=async()=>{
 const btn=$('hear'); btn.disabled=true; btn.textContent='GHOST IS EVALUATING…';
 try{
  epistemicData=await request('epistemic'); const d=epistemicData;
  $('factText').textContent=`${d.fact.quantity} food units were confiscated at ${pretty(d.fact.location)}.`;
  $('speech').textContent=`“${d.report.statement}”`; renderBelief(d.initial,'HELD');
  btn.textContent='REPORT EVALUATED'; $('inspect').classList.remove('hidden'); $('beliefCaption').textContent='The player formed a belief from the report. The world fact remains separate.'; toast('Report ≠ objective truth.');
 }catch(e){btn.disabled=false;btn.textContent='TRY AGAIN';$('beliefCaption').textContent=e.message}
};
$('inspect').onclick=()=>{
 if(!epistemicData)return; const btn=$('inspect'); btn.disabled=true; btn.textContent='EVIDENCE APPLIED'; $('ledger').classList.add('active'); $('beliefCard').classList.remove('flash'); void $('beliefCard').offsetWidth; $('beliefCard').classList.add('flash'); renderBelief(epistemicData.revised,'REVISED'); $('beliefCaption').textContent=`Belief ${epistemicData.initial.id} → ${epistemicData.revised.id}. Objective fact unchanged.`; $('beliefProof').classList.remove('hidden'); $('beliefAuditPanel').classList.remove('hidden'); $('finish').classList.remove('hidden'); toast('Evidence revised belief, not reality.');
};

$('beliefDeterminism').onclick=async()=>{
 const btn=$('beliefDeterminism'); btn.disabled=true; btn.textContent='RUNNING REVISION TWICE…';
 try{
  const d=await request('epistemic_determinism'), result=$('beliefDeterminismResult');
  $('beliefHashA').textContent=d.hash_a; $('beliefHashB').textContent=d.hash_b;
  $('beliefDetVerdict').textContent=d.match&&d.fact_preserved&&d.revision_linked?'MATCH — REVISION REPRODUCED':'CHECK FAILED';
  $('beliefDetDetail').textContent=`fact ${d.fact_id}: quantity ${d.fact_quantity} preserved • belief ${d.initial_id} → ${d.revised_id} • snapshot restore ${d.snapshot_round_trip?'PASS':'FAIL'}`;
  result.classList.remove('hidden','fail'); if(!(d.match&&d.fact_preserved&&d.revision_linked&&d.snapshot_round_trip))result.classList.add('fail');
  btn.textContent=d.match&&d.fact_preserved?'REVISION VERIFIED':'CHECK FAILED';
  toast(d.match&&d.fact_preserved?'Same evidence path. Same revision.':'Epistemic replay failed.');
 }catch(e){btn.disabled=false;btn.textContent='TRY AGAIN';$('beliefCaption').textContent=e.message}
};

$('finish').onclick=()=>screen('cognition');


function levelBar(el,v){const n=Math.max(0,Math.min(1,Number(v)));el.style.width=`${n*100}%`;}
function pct(v){return `${Math.round(Math.max(0,Math.min(1,Number(v)))*100)}%`;}
function exact(v){return Number(v).toFixed(3);}
function meaningLabel(obj){
 const active=obj.active||[];
 if(active.length)return `engine: active ${active.join(', ')}`;
 return `engine: strongest ${pretty(obj.strongest||'none')} ${exact(obj.strongest_level||0)}`;
}
function setReplayCheck(id,ok){
 const el=$(id);el.classList.remove('pass','fail');el.classList.add(ok?'pass':'fail');
}

$('cognitiveAction').onclick=async()=>{
 const btn=$('cognitiveAction');btn.disabled=true;btn.textContent='GHOST IS INTERPRETING…';
 try{
  cognitiveData=await request('cognitive');
  for(const [prefix,obj] of [['sera',cognitiveData.sera],['rowan',cognitiveData.rowan]]){
   $(`${prefix}Betrayal`).textContent=pct(obj.betrayal);
   $(`${prefix}Cooperation`).textContent=pct(obj.cooperation);
   levelBar($(`${prefix}BetrayalBar`),obj.betrayal);levelBar($(`${prefix}CooperationBar`),obj.cooperation);
   $(`${prefix}MeaningLabel`).textContent=meaningLabel(obj);
   $(`${prefix}MeaningCard`).classList.add('resolved');
  }
  $('cognitiveCaption').textContent=`Sera reads the event mainly as ${pretty(cognitiveData.sera.strongest)}. Rowan reads it mainly as ${pretty(cognitiveData.rowan.strongest)}.`;
  $('meaningProof').classList.remove('hidden');$('flowPanel').classList.remove('hidden');
  btn.textContent='SAME ACTION — DIFFERENT MEANING';toast('Same action. Different persistent meaning.');
 }catch(e){btn.disabled=false;btn.textContent='TRY AGAIN';$('cognitiveCaption').textContent=e.message}
};

$('flowAction').onclick=()=>{
 if(!cognitiveData)return;
 const f=cognitiveData.flow;
 $('flowPressure').textContent=`engine pressure ${exact(f.pressure)}`;levelBar($('flowPressureBar'),f.pressure);
 $('flowState').textContent=f.active?'HIGH — FLOW ACTIVE':'BUILDING';
 $('underlyingBetrayal').textContent=pct(f.underlying_betrayal);
 $('underlyingExact').textContent=`exact source ${exact(f.underlying_betrayal)}`;
 $('attendedBetrayal').textContent=pct(f.attended_betrayal);
 $('attentionGain').textContent=`only ${pct(f.gain)} of the stored interpretation reaches the foreground · exact gain ${exact(f.gain)}`;
 $('sourceInvariant').textContent=cognitiveData.source_immutable?'YES — SOURCE UNCHANGED':'CHECK FAILED';
 const steps=$('flowSteps');steps.innerHTML='';
 cognitiveData.flow_steps.forEach((step,i)=>{const el=document.createElement('span');el.textContent=`${i+1} · ${Number(step.pressure).toFixed(2)}`;el.title=`attention update ${i+1}`;if(step.active)el.classList.add('active');steps.appendChild(el)});
 $('flowReadout').classList.remove('hidden');$('breakthroughAction').classList.remove('hidden');
 $('flowAction').disabled=true;$('flowAction').textContent='SERA IS IN DEEP FOCUS';toast('Stored meaning stayed. Foreground access narrowed.');
};

$('breakthroughAction').onclick=()=>{
 if(!cognitiveData)return;
 const b=cognitiveData.breakthrough, stored=cognitiveData.flow.underlying_betrayal;
 const ok=b.breakthrough&&b.resurfaced;
 $('breakthroughVerdict').textContent=ok?'BETRAYAL RETURNS TO THE FOREGROUND':'CHECK FAILED';
 $('breakthroughDetail').textContent=ok?'Sera did not have to recreate the interpretation. It was already stored, and the strong threat restored full access to it.':'The expected breakthrough did not occur.';
 $('breakthroughStored').textContent=pct(stored);
 $('breakthroughForeground').textContent=pct(b.attended_betrayal);
 $('breakthroughExact').textContent=`source ${exact(stored)} · foreground ${exact(b.attended_betrayal)} · attention gain ${exact(b.gain)}`;
 $('breakthroughReadout').classList.remove('hidden');$('cognitiveAuditPanel').classList.remove('hidden');$('cognitionFinish').classList.remove('hidden');
 $('breakthroughAction').disabled=true;$('breakthroughAction').textContent='THREAT BROKE THROUGH';toast('The stored meaning returned to the foreground.');
};

$('cognitiveDeterminism').onclick=async()=>{
 const btn=$('cognitiveDeterminism');btn.disabled=true;btn.textContent='RUNNING THE SAME CHAIN TWICE…';
 try{
  const d=await request('cognitive_determinism'), result=$('cognitiveDeterminismResult');
  $('cognitiveHashA').textContent=d.hash_a;$('cognitiveHashB').textContent=d.hash_b;
  const ok=d.match&&d.source_immutable&&d.snapshot_match&&d.breakthrough;
  $('cognitiveDetVerdict').textContent=ok?'MATCH — THE FULL CHAIN REPRODUCED':'CHECK FAILED';
  $('cognitiveDetDetail').textContent=`${d.bytes} canonical JSON bytes compared · exact hashes available below`;
  setReplayCheck('replayMatch',d.match);
  setReplayCheck('replayImmutable',d.source_immutable);
  setReplayCheck('replaySnapshot',d.snapshot_match);
  setReplayCheck('replayBreakthrough',d.breakthrough);
  result.classList.remove('hidden','fail');if(!ok)result.classList.add('fail');
  btn.textContent=ok?'FULL CHAIN VERIFIED':'CHECK FAILED';toast(ok?'Same ordered inputs. Same cognitive state chain.':'Cognitive replay failed.');
 }catch(e){btn.disabled=false;btn.textContent='TRY AGAIN';$('cognitiveCaption').textContent=e.message}
};

$('cognitionFinish').onclick=()=>screen('final');
$('restart').onclick=()=>location.reload();

boot();

// V1100_GHOCENTRIC_COPY_REFRESH_V2
