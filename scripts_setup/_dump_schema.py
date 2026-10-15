import json, os
R = "/data1/liborui/fastwam_bench/results"
for name in ("gate9b_control_oa_t0", "gate9b_world_oa_t0"):
    p = os.path.join(R, name, "records.jsonl")
    if not os.path.exists(p):
        print(name, "MISSING"); continue
    recs = [json.loads(l) for l in open(p) if l.strip()]
    ee = next((r for r in recs if r["event"] == "episode_end"), {})
    rp = next((r for r in recs if r["event"] == "replan"), {})
    st = [r for r in recs if r["event"] == "step"]
    ep0 = [r for r in st if r["episode"] == 0]
    print(f"--- {name}")
    print("   replan_steps(record):", rp.get("replan_steps"), " pending_len:", rp.get("pending_len"))
    print("   ep0 steps:", len(ep0), " n_episodes:", len({r['episode'] for r in st}))
    print("   intervention_enabled:", ee.get("intervention_enabled"),
          "world_enabled:", ee.get("world_intervention_enabled"),
          "mode:", ee.get("intervention_mode"))
    print("   first 3 ep0 actions t=0,1,2:",
          [ [round(x,4) for x in r["action"]] for r in ep0[:3] ])
    print("   ep0 actions at t=38,39,40:",
          [ (r["t"], [round(x,4) for x in r["action"]]) for r in ep0 if r["t"] in (38,39,40) ])
