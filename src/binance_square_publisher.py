"""Binance Square publisher with explicit verified/submitted/skipped states."""
from __future__ import annotations
import json, os, re, subprocess, urllib.error, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"; ANALYTICS=ROOT/"analytics"
PAYLOAD_PATH=LIVE/"publication_payload.json"; LOG_PATH=ANALYTICS/"publication_log.jsonl"; RESULT_PATH=LIVE/"publication_result.json"
CONTEXT_PATH=LIVE/"publication_context.json"; FROZEN_PATH=LIVE/"authoritative_opportunity.json"; WTE_PATH=LIVE/"write_to_earn_eligibility.json"
MONETIZATION_OS_PATH=LIVE/"nic_monetization_contract.json"; STORY_DISCOVERY_PATH=LIVE/"nic_story_discovery.json"; CRAFT_PATH=LIVE/"nic_content_craft_9.json"
ATTRIBUTION_LOG_PATH=ANALYTICS/"publication_attribution.jsonl"; VISUAL=LIVE/"visual.png"
ENDPOINT="https://www.binance.com/bapi/composite/v1/public/pgc/openApi/content/add"
NO_IMAGE_LANES={"education","commentary","community","text_only"}; DUPLICATE_HOURS=float(os.getenv("PUBLISH_DUPLICATE_HOURS","6"))

def now(): return datetime.now(timezone.utc).isoformat()
def load(path):
    try:
        v=json.loads(path.read_text(encoding="utf-8")); return v if isinstance(v,dict) else {}
    except Exception: return {}
def canonical_post_id(v):
    raw=str(v or "").strip().rstrip("/")
    if "/square/post/" in raw: raw=raw.split("/square/post/",1)[1].split("?",1)[0].split("#",1)[0].strip()
    return raw if re.fullmatch(r"[A-Za-z0-9_-]{1,128}",raw) else ""
def clean_symbol(v):
    s=re.sub(r"USDT$","",str(v or "").upper().replace("$","").strip()); return s if re.fullmatch(r"[A-Z0-9]{1,15}",s) else ""
def write_result(result):
    LIVE.mkdir(parents=True,exist_ok=True); RESULT_PATH.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8"); print(json.dumps(result,indent=2,ensure_ascii=False))
def fail(message,code,exit_code=2):
    write_result({"status":code,"message":message,"checked_at":now(),"endpoint":ENDPOINT,"post_id":None,"link":None,"publication_proof":"none"}); return exit_code
def skip(message,code,symbol="",category="",existing=None):
    existing=existing if isinstance(existing,dict) else {}; eid=canonical_post_id(existing.get("canonical_post_id") or existing.get("post_id") or existing.get("link")); link=str(existing.get("link") or "").strip() or (f"https://www.binance.com/square/post/{eid}" if eid else None); verified=code=="PUBLISH_BLOCKED_DUPLICATE" and bool(eid)
    write_result({"status":code,"message":message,"checked_at":now(),"endpoint":ENDPOINT,"post_id":None,"link":None,"symbol":symbol or None,"category":category or None,"publication_proof":"none","current_run_publication":"NO_NEW_PUBLICATION" if code=="PUBLISH_BLOCKED_DUPLICATE" else code,"publication_state":"CURRENT_RUN_NO_NEW_PUBLICATION — EXISTING_POST_VERIFIED" if verified else code,"existing_publication":{"verified":verified,"canonical_post_id":eid or None,"link":link,"status":str(existing.get("status") or "") or None,"published_at":existing.get("published_at") or existing.get("timestamp")}}); return 0
def text_payload():
    d=load(PAYLOAD_PATH); t=str(d.get("text") or d.get("bodyTextOnly") or d.get("content") or "").strip()
    if not t: raise RuntimeError("publication text is empty")
    if len(t)>10000: raise RuntimeError(f"publication text is too long ({len(t)})")
    return t
def recent_rows():
    if not LOG_PATH.exists(): return []
    accepted={"PUBLISHED_AUTONOMOUSLY","PUBLISHED_VERIFIED_BY_API_RESPONSE","VERIFIED_PUBLISHED","PUBLISHED_SUBMITTED_504"}; rows=[]
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines()[-300:]:
        try: r=json.loads(line)
        except Exception: continue
        if isinstance(r,dict) and str(r.get("status") or "") in accepted: rows.append(r)
    return rows
def duplicate_match(text,symbol,category,context,frozen):
    target=clean_symbol(symbol); direction=str(context.get("direction") or (context.get("prediction") or {}).get("direction") or frozen.get("direction") or (frozen.get("prediction") or {}).get("direction") or "").upper(); trigger=context.get("entry_trigger") or frozen.get("entry_trigger") or frozen.get("trigger") or frozen.get("entry"); invalidation=context.get("sl") or frozen.get("sl") or frozen.get("invalidation"); now_dt=datetime.now(timezone.utc)
    for row in reversed(recent_rows()):
        rs=clean_symbol(row.get("symbol") or row.get("selected_lane_symbol")); rc=str(row.get("category") or row.get("content_category") or "").lower()
        try: age=now_dt-datetime.fromisoformat(str(row.get("published_at") or row.get("timestamp") or "").replace("Z","+00:00"))
        except Exception: continue
        if age>timedelta(hours=DUPLICATE_HOURS): continue
        old=str(row.get("text") or row.get("post") or row.get("content") or "").strip()
        if old and old==text.strip(): return f"exact_text_duplicate_within_{DUPLICATE_HOURS:g}h",row
        if not (target and rs==target and rc==str(category or "").lower()): continue
        od=str(row.get("direction") or row.get("side") or "").upper(); ot=row.get("trigger") or row.get("entry_trigger"); oi=row.get("invalidation") or row.get("sl")
        if direction:
            if od and direction==od and (trigger is None or ot is None or str(trigger)==str(ot)) and (invalidation is None or oi is None or str(invalidation)==str(oi)): return f"same_asset_category_and_setup_within_{DUPLICATE_HOURS:g}h",row
        elif not od and not any(k in text.lower() for k in ("result","outcome","invalidated","follow-up","follow up")): return f"same_asset_and_category_within_{DUPLICATE_HOURS:g}h",row
    return "",None
def append(row):
    ANALYTICS.mkdir(parents=True,exist_ok=True)
    with LOG_PATH.open("a",encoding="utf-8") as h: h.write(json.dumps(row,ensure_ascii=False)+"\n")
def append_attribution(row):
    ANALYTICS.mkdir(parents=True,exist_ok=True)
    with ATTRIBUTION_LOG_PATH.open("a",encoding="utf-8") as h: h.write(json.dumps(row,ensure_ascii=False)+"\n")
def preflight():
    required=[("publication_payload",PAYLOAD_PATH),("publication_context",CONTEXT_PATH),("authoritative_opportunity",FROZEN_PATH),("write_to_earn_eligibility",WTE_PATH),("content_craft",CRAFT_PATH)]
    missing=[f"{n}:{p}" for n,p in required if not p.exists()]
    if missing: raise RuntimeError("publisher preflight missing: "+", ".join(missing))
def main():
    key=(os.getenv("BINANCE_SQUARE_OPENAPI_KEY") or os.getenv("BINANCE_SQUARE_API_KEY") or "").strip()
    if not key: return fail("BINANCE_SQUARE_OPENAPI_KEY/BINANCE_SQUARE_API_KEY is not configured","PUBLISHER_NOT_CONFIGURED")
    try:
        preflight(); text=text_payload(); context=load(CONTEXT_PATH); frozen=load(FROZEN_PATH); monetization_os=load(MONETIZATION_OS_PATH); story_discovery=load(STORY_DISCOVERY_PATH); craft=load(CRAFT_PATH)
        symbol=clean_symbol(context.get("symbol") or context.get("primary_symbol") or frozen.get("symbol") or frozen.get("symbol_usdt")); category=str(context.get("category") or context.get("content_category") or frozen.get("category") or frozen.get("content_category") or "").lower()
        if not symbol: raise RuntimeError("publication symbol is missing")
        wte=load(WTE_PATH)
        if wte and wte.get("eligible") is False:
            reason=str(wte.get("reason") or "w2e eligibility gate rejected publication"); append({"timestamp":now(),"status":"PUBLISH_SKIPPED_WTE_INELIGIBLE","post_id":None,"link":None,"symbol":symbol,"category":category,"reason":reason,"publication_proof":"none"}); return skip(f"Publication skipped by W2E eligibility gate: {reason}","PUBLISH_SKIPPED_WTE_INELIGIBLE",symbol,category)
        dup,existing=duplicate_match(text,symbol,category,context,frozen)
        if dup:
            eid=canonical_post_id(existing.get("canonical_post_id") or existing.get("post_id") or existing.get("link")); elink=str(existing.get("link") or "").strip() or (f"https://www.binance.com/square/post/{eid}" if eid else None)
            append({"timestamp":now(),"status":"PUBLISH_BLOCKED_DUPLICATE","post_id":None,"link":None,"existing_post_id":eid or None,"existing_post_link":elink,"existing_publication_status":str(existing.get("status") or "") or None,"existing_publication_verified_at":existing.get("published_at") or existing.get("timestamp"),"symbol":symbol,"category":category,"text":text,"reason":dup,"publication_proof":"existing_verified_publication_log"}); return skip(f"Duplicate publication blocked: {dup}","PUBLISH_BLOCKED_DUPLICATE",symbol,category,existing)
        visual_requested=bool(context.get("visual_requested") or context.get("visual_required") or context.get("visual_verified") or context.get("tradingview_verified") or (context.get("visual_decision") or {}).get("required")); require_image=visual_requested or category not in NO_IMAGE_LANES; use_image=VISUAL.exists() and VISUAL.stat().st_size>10000 and require_image
        if require_image and not use_image: raise RuntimeError(f"Required TradingView visual is missing or too small for {symbol}: {VISUAL}")
        if use_image:
            p=subprocess.run(["node",str(ROOT/"src/square_image_publisher.mjs"),str(VISUAL),text],env={**os.environ,"BINANCE_SQUARE_OPENAPI_KEY":key},cwd=ROOT,text=True,capture_output=True,check=False)
            if p.stdout.strip(): print(p.stdout)
            if p.returncode!=0: raise RuntimeError(p.stderr.strip() or "image publisher failed")
            lines=[x.strip() for x in p.stdout.splitlines() if x.strip()]
            if not lines: raise RuntimeError("image publisher returned no result")
            api_result=json.loads(lines[-1])
        else:
            body=json.dumps({"bodyTextOnly":text},ensure_ascii=False).encode("utf-8"); req=urllib.request.Request(ENDPOINT,data=body,method="POST",headers={"X-Square-OpenAPI-Key":key,"Content-Type":"application/json","clienttype":"binanceSkill","User-Agent":"binance-square-ai-creator/1.7"})
            try:
                with urllib.request.urlopen(req,timeout=30) as response: api=json.loads(response.read().decode("utf-8",errors="replace"))
            except urllib.error.HTTPError as e:
                if e.code==504: api={"code":"504","data":{},"message":"submitted without post id"}
                else: raise
            code=str(api.get("code","")); data=api.get("data") if isinstance(api.get("data"),dict) else {}; pid=canonical_post_id(data.get("id") or data.get("contentId")); api_result={"status":"PUBLISHED_VERIFIED_BY_API_RESPONSE" if code=="000000" and pid else ("PUBLISHED_SUBMITTED_504" if code=="504" else "PUBLISH_REJECTED"),"post_id":pid or None,"link":data.get("shareLink") or "","api_code":code,"error":api.get("message")}
        status=str(api_result.get("status") or "")
        if status=="PUBLISHED_VERIFIED_BY_API_RESPONSE":
            post_id=canonical_post_id(api_result.get("post_id") or api_result.get("id"));
            if not post_id: raise RuntimeError("Binance response claimed success without a canonical post id")
            link=str(api_result.get("link") or api_result.get("shareLink") or "").strip() or f"https://www.binance.com/square/post/{post_id}"; proof="binance_openapi_response_post_id"; exit_code=0
        elif status=="PUBLISHED_SUBMITTED_504": post_id=""; link=""; proof="binance_content_add_http_504_submission_unknown"; exit_code=0
        else: raise RuntimeError(api_result.get("error") or "Binance rejected publication")
    except Exception as exc:
        append({"timestamp":now(),"status":"PUBLISH_FAILED","post_id":None,"link":None,"error":str(exc),"publication_proof":"none"}); return fail(str(exc),"PUBLISH_FAILED")
    direction=str(context.get("direction") or (context.get("prediction") or {}).get("direction") or frozen.get("direction") or (frozen.get("prediction") or {}).get("direction") or "").upper()
    row={"timestamp":now(),"published_at":now(),"status":status,"post_id":post_id or None,"canonical_post_id":post_id or None,"link":link or None,"text":text,"text_length":len(text),"symbol":symbol,"category":category,"direction":direction,"story_id":str(context.get("story_id") or (context.get("story_discovery") or {}).get("story_id") or story_discovery.get("story_id") or monetization_os.get("story_id") or ""),"story_type":str(context.get("story_type") or (context.get("story_discovery") or {}).get("story_kind") or story_discovery.get("story_kind") or context.get("story_kind") or ""),"craft_id":str(craft.get("craft_id") or context.get("craft_id") or ""),"craft_pattern":str(craft.get("archetype") or ""),"portfolio_plan_id":str(monetization_os.get("portfolio_plan_id") or context.get("portfolio_plan_id") or ""), "portfolio_slot_id":str(monetization_os.get("portfolio_slot_id") or context.get("portfolio_slot_id") or ""), "portfolio_strategy":str(monetization_os.get("portfolio_strategy") or context.get("portfolio_strategy") or ""), "portfolio_lane":str(monetization_os.get("portfolio_lane") or context.get("portfolio_lane") or ""), "portfolio_format":str(monetization_os.get("portfolio_format") or context.get("portfolio_format") or ""), "portfolio_hook_type":str(monetization_os.get("portfolio_hook_type") or context.get("portfolio_hook_type") or ""), "portfolio_visual_type":str(monetization_os.get("portfolio_visual_type") or context.get("portfolio_visual_type") or ""), "portfolio_reader_payoff_type":str(monetization_os.get("portfolio_reader_payoff_type") or context.get("portfolio_reader_payoff_type") or ""), "experiment_id":str(monetization_os.get("experiment_id") or context.get("experiment_id") or frozen.get("experiment_id") or ""),"campaign_day":monetization_os.get("campaign_day"),"content_lane":str(monetization_os.get("content_lane") or context.get("content_lane") or category),"content_format":str(monetization_os.get("content_format") or context.get("content_format") or ""),"hook_type":str(monetization_os.get("hook_type") or context.get("hook_type") or ""),"visual_type":str(monetization_os.get("visual_type") or context.get("visual_type") or ""),"reader_payoff_type":str(monetization_os.get("reader_payoff_type") or context.get("reader_payoff_type") or ""),"experiment_variable":str(monetization_os.get("experiment_variable") or context.get("experiment_variable") or ""),"experiment_treatment":str(monetization_os.get("experiment_treatment") or context.get("experiment_treatment") or ""),"cycle_id":str(monetization_os.get("cycle_id") or context.get("cycle_id") or ""),"cashtag":str(monetization_os.get("cashtag") or ("$"+symbol if symbol else "")),"reference_price":frozen.get("reference_price") or context.get("reference_price"),"trigger":frozen.get("trigger") or frozen.get("entry"),"invalidation":frozen.get("invalidation"),"targets":frozen.get("targets") or frozen.get("take_profit") or [],"visual_attached":use_image,"visual_path":str(VISUAL) if use_image else None,"visual_url":api_result.get("image_url"),"editorial_style":str(context.get("editorial_style") or ""),"publication_id_verified":bool(post_id),"publication_proof":proof,"monetization":{"wte_eligible":bool(wte.get("eligible")) if isinstance(wte,dict) else None,"required_attribution":bool(wte.get("required_attribution")) if isinstance(wte,dict) else None,"cashtag":str(wte.get("cashtag") or f"${symbol}") if isinstance(wte,dict) else f"${symbol}","has_primary_cashtag":bool(wte.get("has_primary_cashtag")) if isinstance(wte,dict) else None,"verified_widget":wte.get("verified_widget") if isinstance(wte,dict) else False,"revenue_verified":False,"qualified_trade_count":None,"reward_amount_usdc":None,"status":"AWAITING_VERIFIED_READER_ACTIVITY"}}
    append(row); append_attribution({"recorded_at":row["published_at"],**{k:row[k] for k in ("post_id","canonical_post_id","published_at","symbol","portfolio_plan_id","portfolio_slot_id","portfolio_strategy","portfolio_lane","portfolio_format","portfolio_hook_type","portfolio_visual_type","portfolio_reader_payoff_type","category","direction","story_id","story_type","craft_id","craft_pattern","experiment_id","campaign_day","content_lane","content_format","hook_type","visual_type","reader_payoff_type","experiment_variable","experiment_treatment","cycle_id","reference_price","trigger","invalidation","targets","visual_attached","visual_url","publication_proof")},"cashtag":row["monetization"]["cashtag"],"has_primary_cashtag":row["monetization"]["has_primary_cashtag"],"verified_widget":row["monetization"]["verified_widget"],"revenue_verified":False,"qualified_trade_count":None,"reward_amount_usdc":None,"status":"AWAITING_VERIFIED_READER_ACTIVITY","lineage_policy":"exact_post_id_first; revenue_only_from_explicit_verified_fields"})
    write_result({"status":status,"checked_at":now(),"post_id":post_id or None,"canonical_post_id":post_id or None,"link":link or None,"symbol":symbol,"category":category,"visual_attached":use_image,"visual_url":api_result.get("image_url"),"id_verification":"verified" if post_id else "unavailable","publication_proof":proof,"experiment_id":row["experiment_id"],"campaign_day":row["campaign_day"],"content_lane":row["content_lane"],"content_format":row["content_format"],"hook_type":row["hook_type"],"visual_type":row["visual_type"],"reader_payoff_type":row["reader_payoff_type"],"experiment_variable":row["experiment_variable"],"experiment_treatment":row["experiment_treatment"],"cycle_id":row["cycle_id"],"cashtag":row["monetization"]["cashtag"]}); return exit_code
if __name__=="__main__": raise SystemExit(main())
