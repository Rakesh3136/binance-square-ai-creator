"""Verified-revenue-only Winning Post DNA; never infer earnings from engagement."""
import json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(p):
 try:
  x=json.loads(p.read_text(encoding="utf-8")); return x if isinstance(x,dict) else {}
 except Exception:return {}
def build(engine,contract):
 rows=[]
 for r in engine.get("publication_funnel",[]):
  if not isinstance(r,dict):continue
  a=r.get("verified_activity") or {}; p=r.get("performance") or {}; rev=a.get("reward_amount_usdc")
  if a.get("revenue_verified") is True and rev is not None and (r.get("canonical_post_id") or r.get("post_id")):
   try: amount=float(rev)
   except (ValueError,TypeError):continue
   rows.append({"post_id":str(r.get("canonical_post_id") or r.get("post_id")),"category":str(r.get("category") or "unknown"),"revenue":amount,"views":float(p.get("views") or 0),"cashtag":bool(r.get("has_primary_cashtag")),"visual":bool(r.get("visual_attached"))})
 cats=defaultdict(lambda:{"posts":0,"revenue":0.0,"views":0.0,"cashtags":0,"visuals":0})
 for r in rows:
  c=cats[r["category"]];c["posts"]+=1;c["revenue"]+=r["revenue"];c["views"]+=r["views"];c["cashtags"]+=r["cashtag"];c["visuals"]+=r["visual"]
 ranked=sorted(cats.items(),key=lambda kv:(kv[1]["revenue"],kv[1]["posts"]),reverse=True)
 n=len(rows)
 return {"schema":"NIC-WINNING-POST-DNA-1.0","generated_at":datetime.now(timezone.utc).isoformat(),"status":"VERIFIED_PATTERN_CANDIDATES" if n>=3 else "INSUFFICIENT_VERIFIED_REVENUE","verified_revenue_post_count":n,"verified_revenue_total_usdc":round(sum(r["revenue"] for r in rows),6),"verified_post_ids":[r["post_id"] for r in rows],"category_evidence":{k:{"posts":v["posts"],"revenue_usdc":round(v["revenue"],6),"views":v["views"],"cashtag_rate":round(v["cashtags"]/v["posts"],3),"visual_rate":round(v["visuals"]/v["posts"],3)} for k,v in cats.items()},"editorial_contract":{"priority":"reader_value_then_evidence_then_actionability","required_sequence":["specific_hook","what_changed_and_why_now","evidence_not_hype","conditional_setup_or_watch_level","confirmation","invalidation_and_risk","reader_next_step"],"chart_requirements":["correct_asset_and_timeframe","verified_levels_only","show_confirmation_and_invalidation","annotate_the_thesis_not_decoration"],"variation_policy":["vary_hook_and_structure_from_evidence","one_primary_thesis_per_post","repeat_asset_only_for_material_new_evidence","never_invent_news_levels_or_revenue"],"truth_policy":{"views_are_not_revenue":True,"likes_are_not_revenue":True,"prediction_success_is_not_revenue":True,"missing_attribution_is_not_inferred":True},"historical_best_category_candidate":ranked[0][0] if n>=3 and ranked else None,"policy":"Advisory only; all existing safety, timing, cooldown, forecast, chart-truth and publication gates remain authoritative."},"next_actions":["Join eligible trade rewards to exact canonical post IDs.","Compare verified-revenue posts with zero-revenue posts.","Use controlled experiments; do not claim correlation is causation."]}
def main():
 root=Path(__file__).resolve().parents[1]; out=build(load(root/"analytics/creator_8_0_monetization_engine.json"),load(root/"data/live/nic_monetization_contract.json")); p=root/"data/live/nic_winning_post_dna.json";p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8");print(json.dumps({"status":out["status"],"verified_revenue_post_count":out["verified_revenue_post_count"]}));return out
if __name__=="__main__":main()
