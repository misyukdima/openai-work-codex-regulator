#!/usr/bin/env python3
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

def fail(msg:str)->None:
    print(f"v4 routing validation FAILED: {msg}")
    raise SystemExit(1)

def main()->None:
    cap=json.loads((ROOT/"references/MODEL_CAPABILITY_SNAPSHOT.json").read_text())
    fx=json.loads((ROOT/"tests/fixtures/v4_routing_evals.json").read_text())
    models={m["alias"]:m for m in cap["models"]}
    if set(models)!={"ASTRA","SOL","LUNA"}: fail("capability snapshot must contain Astra, Sol and Luna")
    if "none" in models["ASTRA"]["reasoning_efforts"]: fail("Astra must not claim none reasoning")
    for alias in ("SOL","LUNA"):
        if models[alias].get("default_reasoning")!="medium": fail(f"{alias} default reasoning must be medium")
    seen=set()
    for case in fx.get("cases",[]):
        cid=case.get("id")
        if not cid or cid in seen: fail("fixture ids must be unique")
        seen.add(cid)
        m=case.get("expected_model"); e=case.get("expected_effort")
        if m and m not in models: fail(f"{cid}: unknown model")
        if m and e and e.lower() not in models[m]["reasoning_efforts"]: fail(f"{cid}: unsupported model/effort")
    if len(seen)<16: fail("need at least 16 deterministic cases")
    skill=(ROOT/"SKILL.md").read_text()
    mirror=(ROOT/"skills/openai-work-codex-regulator/SKILL.md").read_text()
    if skill!=mirror: fail("skill mirror mismatch")
    for marker in ["CHATGPT_PRIMARY_ORCHESTRATOR=YES","QUALITY_FLOOR=NON_NEGOTIABLE","TASK_DURATION_LIMIT=NONE","WORKDAY_START_LOCAL=09:00","WORKDAY_SOFT_END_LOCAL=22:00","WORKDAY_HARD_END_LOCAL=23:00","ACTIVE_LIMITS=DERIVED_FROM_CURRENT_SNAPSHOT","CAPABILITY_FAILURE != REASONING_DEPTH_FAILURE","UNKNOWN_IS_NOT_ZERO=YES"]:
        if marker not in skill: fail(f"SKILL missing {marker}")
    print(f"v4 routing validation OK — {len(seen)} deterministic fixtures")

if __name__=="__main__":
    main()
