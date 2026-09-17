from __future__ import annotations
from pathlib import Path
from ghost.api import GhostAPI
from ghost.episode_store import SQLiteEpisodeArchive

EMOTION_STATE={"agent","baseline","dominant_emotion","dominant_salience","history","inertia","levels","raw_leader_emotion","raw_leader_salience","salience_bias","sensitivities","spotlight","spotlight_switch_margin"}
INTERP_STATE={"active","active_interpretations","agent","baseline","history","levels","rules","sensitivities","strongest_interpretation","strongest_level","thresholds"}
ATTN_STATE={"agent","attention_gain","config","flow_active","flow_depth","flow_pressure","history"}
ATTN_STEP={"agent","attended_salience","attention_gain","breakthrough","config","flow_active_after","flow_active_before","flow_depth","flow_pressure_after","flow_pressure_before","interrupt_strength","provenance","resurfaced","sequence","signals","source","support","target_flow_pressure","transition","underlying_salience"}
EMOTION_EVENT={"after","agent","base_impulses","before","deltas","effective_impulses","event","intensity","source","spotlight_transition","state"}
INTERP_EVENT={"active_interpretations","agent","contributions","objective_action","sequence","state","state_before","strongest_interpretation","strongest_level","transitions"}
SALIENCE={"agent","packet_version","salience","source_count","sources"}
CONT_EVENT={"action","activation","agent","attention","continuity","emotion","episodes","foreground","interpretation"}
RECALL={"activation","agent","attention","continuity","dimension","emotion","episode_id","foreground","lookup","meaning_unchanged","retrieval_strength"}
CONT_STATE={"activation","agent","current_leader","release_rate","switch_threshold"}

def keys(x): assert isinstance(x,dict); return set(x)
def make(path:Path):
    s=SQLiteEpisodeArchive(path); return GhostAPI(episode_store=s),s

def test_all_optimized_wrappers_preserve_established_public_packet_shapes(tmp_path):
    a,s=make(tmp_path/'episodes.sqlite')
    e=a.register_emotional_agent('npc',initial={'anger':.1,'fear':.05,'hope':.2},baseline={'anger':.1,'fear':.05,'hope':.2},inertia={'anger':.8,'fear':.9,'hope':.9})
    assert keys(e)==EMOTION_STATE and keys(a.emotional_state('npc'))==EMOTION_STATE
    ep=a.apply_emotional_event('npc','probe',impulse_overrides={'anger':.4,'fear':.2})
    assert keys(ep)==EMOTION_EVENT and keys(ep['state'])==EMOTION_STATE
    t=a.tick_emotions('npc',1); assert keys(t)=={'agents','event','steps'}; assert keys(t['agents'][0]['state'])==EMOTION_STATE
    i=a.register_interpretation_agent('npc',initial={'betrayal':0.,'respect':0.}); assert keys(i)==INTERP_STATE
    rule=a.configure_interpretation_rule('npc','betrayal_cue',{'betrayal':.9}); assert rule=={'agent':'npc','feature':'betrayal_cue','pressures':{'betrayal':.9}}
    assert keys(a.interpretation_state('npc'))==INTERP_STATE
    ev=a.evaluate_action_meaning('npc','betrayal',features={'betrayal_cue':1.},source='contract'); assert keys(ev)==INTERP_EVENT and keys(ev['state'])==INTERP_STATE
    at=a.register_attention_agent('npc'); assert keys(at)==ATTN_STATE and keys(a.attention_state('npc'))==ATTN_STATE
    adv=a.advance_attention('npc',signals={'novelty':.2},salience={'probe':.3}); assert keys(adv)==ATTN_STEP
    assert keys(a.persistent_salience('npc'))==SALIENCE
    br=a.advance_attention_from_state('npc',signals={'novelty':.1}); assert keys(br)=={'agent','attention','bridge'} and keys(br['attention'])==ATTN_STEP and keys(br['bridge'])==SALIENCE
    s.close()

def test_m3_packets_stay_stable_and_only_declared_tick_snapshot_contracts_differ(tmp_path):
    a,s=make(tmp_path/'episodes.sqlite')
    a.register_emotional_agent('npc',initial={'anger':.05,'fear':.02,'grief':.05,'hope':.15},baseline={'anger':.05,'fear':.02,'grief':.05,'hope':.15},inertia={'anger':.88,'fear':.86,'grief':.94,'hope':.92})
    a.register_interpretation_agent('npc',initial={'betrayal':0.}); a.configure_interpretation_rule('npc','betrayal_cue',{'betrayal':.9}); a.register_attention_agent('npc')
    x=a.continuity_event('npc','betrayal',features={'betrayal_cue':1.},emotion_event='betrayal',emotion_impulses={'anger':.4,'grief':.3},source='contract')
    assert keys(x)==CONT_EVENT and keys(x['continuity'])==CONT_STATE
    eid=x['episodes'][0]['episode_id']; assert keys(a.recall_episode(eid,.5))==RECALL; assert keys(a.recall_dimension('npc','betrayal',.5))==RECALL; assert keys(a.continuity_state('npc'))==CONT_STATE
    receipt=a.continuity_tick('npc',3); assert keys(receipt)=={'agent','steps','deferred','pending_steps','pending_calls'} and receipt['deferred'] is True
    snap=a.snapshot(); assert set(snap['continuity'])=={'runtime','episode_archive','history_archive','optimization'}
    restored=GhostAPI.from_snapshot(snap,episode_store=s)
    assert keys(restored.emotional_state('npc'))==EMOTION_STATE and keys(restored.interpretation_state('npc'))==INTERP_STATE and keys(restored.attention_state('npc'))==ATTN_STATE and keys(restored.continuity_state('npc'))==CONT_STATE
    s.close()
