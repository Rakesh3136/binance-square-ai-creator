"""NIC 14.1 — Post-publication outcome loop with canonical metrics bridging."""
from __future__ import annotations
import json, re
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AN=ROOT/"analytics"; LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
PUB=AN/"publication_log.jsonl"; ATTR=AN/"publication_attribution.jsonl"
REW=AN/"wte_reward_events.jsonl"; EXT=AN/"external_reward_events.jsonl"
PERF=AN/"square_performance.jsonl"; POST_METRICS=AN/"post_metrics.jsonl"
OUT=LIVE/"nic_post_publication_outcome_14.json"; REPORT=INTEL/"nic_post_publication_outcome_14_report.json"
WINDOW=7
ALIASES={"views":("views","view_count","viewCount","impressions"),"likes":("likes","like_count","likeCount"),"replies":("replies","comments","comment_count","commentCount","replyCount"),"shares":("shares","share_count","shareCount"),"quotes":("quotes","quote_count","quoteCount"),"followers_gained":("followers_gained","follower_growth","followersGained")}
def rows(path):
 if not path.exists(): return []
 out=[]
 for line in path.read_text(encoding="utf-8",errors="ignore").splitlines():
  try:
   x=json.loads(line)
   if isinstance(x,dict): out.append(x)
  except Exception: pass
 return out
def pid(x):
 raw=str(x.get("canonical_post_id") or x.get("post_id") or x.get("publication_id") or "").strip()
 for pat in (r"/(?:square/)?post/([A-Za-z0-9_-]+)",r"/uni-qr/cpos/([A-Za-z0-9_-]+)",r"/(?:square/)?content/([A-Za-z0-9_-]+)"):
  m=re.search(pat,raw,flags=re.I)
  if m: raw=m.group(1); break
 return raw.lower() if re.fullmatch(r"[a-z0-9_-]{1,128}",raw.lower()) else ""
def dt(v):
 try:
  x=datetime.fromisoformat(str(v).replace("Z","+00:00"))
  return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
 except Exception: return None
def num(x):
 try:
  if x is None or isinstance(x,bool) or str(x).strip()=="": return None
  return float(x)
 except (TypeError,ValueError): return None
def metric_snapshot(row):
 nested=row.get("metrics") if isinstance(row.get("metrics"),dict) else {}; out={}
 for target,aliases in ALIASES.items():
  for key in aliases:
   value=num(row.get(key))
   if value is None: value=num(nested.get(key))
   if value is not None and value>=0:
    out[target]=int(value) if value.is_integer() else value; break
 return out
def newest_metric_rows(paths):
 result={}
 for path in paths:
  for row in rows(path):
   post=pid(row); metrics=metric_snapshot(row)
   if not post or not metrics: continue
   stamp=dt(row.get("collected_at") or row.get("observed_at") or row.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc)
   old=result.get(post); old_stamp=dt(old.get("collected_at") or old.get("observed_at") or old.get("timestamp")) if old else None
   if old is None or old_stamp is None or stamp>=old_stamp:
    result[post]={**row,"_normalized_metrics":metrics,"_metric_source":str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name}
 return result
def main():
 now=datetime.now(timezone.utc); pubs={}
 for row in rows(PUB):
  p=pid(row)
  if p: pubs[p]=row
 for row in rows(ATTR):
  p=pid(row)
  if p: pubs[p]={**pubs.get(p,{}),**row}
 rewards={}; unattributed=[]
 for source in (REW,EXT):
  for row in rows(source):
   if row.get("verified") is not True and source==REW: continue
   p=pid(row); amount=num(row.get("reward_amount_usdc"))
   if p and amount is not None: rewards[p]=rewards.get(p,0.0)+max(0,amount)
   elif amount is not None and row.get("verified") is True: unattributed.append({"event_id":row.get("event_id"),"amount_usdc":amount,"observed_at":row.get("observed_at")})
 performance=newest_metric_rows((PERF,POST_METRICS)); outcomes=[]; maturity=Counter(); reward_posts=[]; metric_posts=0
 for p,row in pubs.items():
  published=dt(row.get("published_at") or row.get("recorded_at") or row.get("timestamp")); age=(now-published).total_seconds()/86400 if published else None
  reward=rewards.get(p); perf=performance.get(p,{}); metrics=perf.get("_normalized_metrics",{})
  if metrics: metric_posts+=1
  if reward is not None: state="VERIFIED_REWARD"; reward_posts.append(p)
  elif age is not None and age>=WINDOW: state="CLOSED_NO_VERIFIED_REWARD"
  else: state="OPEN_OBSERVATION"
  maturity[state]+=1
  outcomes.append({"post_id":p,"published_at":row.get("published_at") or row.get("recorded_at") or row.get("timestamp"),"symbol":row.get("symbol"),"category":row.get("category"),"content_lane":row.get("content_lane") or row.get("story_lane"),"content_format":row.get("content_format") or row.get("format"),"visual_type":row.get("visual_type"),"cashtag":row.get("cashtag"),"age_days":round(age,3) if age is not None else None,"observation_closes_at":(published+timedelta(days=WINDOW)).isoformat() if published else None,"outcome_state":state,"verified_reward_usdc":round(reward,8) if reward is not None else None,"explicit_audience_metrics":metrics,"performance_evidence_status":"EXPLICIT" if metrics else "UNKNOWN","performance_observed_at":perf.get("collected_at") or perf.get("observed_at"),"performance_source":perf.get("_metric_source"),"causality_claim_allowed":False})
 recent=sorted(outcomes,key=lambda x:x.get("published_at") or "")[-12:]
 def repeated(field):
  counts=Counter(x.get(field) for x in recent if x.get(field))
  return counts.most_common(1)[0][0] if counts and counts.most_common(1)[0][1]>=4 else None
 adaptation={"force_new_lane":repeated("content_lane"),"force_new_format":repeated("content_format"),"force_new_visual":repeated("visual_type"),"rules":["Use explicit verified reward evidence only for monetization learning.","Treat missing audience metrics as UNKNOWN, not failure.","Do not infer causality from a single post.","Change creative variables only when evidence supports an adaptation.","Keep exact post-ID lineage; never assign an unattributed reward."]}
 result={"version":"14.1","status":"READY","generated_at":now.isoformat(),"policy":{"seven_day_observation_window":WINDOW,"exact_post_id_lineage":True,"nested_and_flat_metrics_supported":True,"explicit_reward_only":True,"unknown_is_neutral":True,"no_causality_from_single_post":True,"no_private_reasoning":True},"summary":{"publication_records":len(outcomes),"maturity":dict(maturity),"posts_with_explicit_performance_metrics":metric_posts,"verified_reward_posts":len(reward_posts),"unattributed_verified_rewards":len(unattributed)},"outcomes":outcomes[-500:],"adaptation":adaptation,"unattributed_rewards":unattributed[-50:],"next_cycle":{"consume_with":"nic_creative_evolution_11 / nic_audience_response_12 / nic_creative_compiler_13","goal":"turn closed, explicit outcomes into bounded creative adaptation"}}
 LIVE.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
 REPORT.write_text(json.dumps({"version":"14.1","status":"READY","summary":result["summary"],"adaptation":adaptation,"output":str(OUT.relative_to(ROOT))},indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"status":"READY",**result["summary"]}))
if __name__=="__main__": main()
