const SYSTEM_INSTRUCTIONS = `You are NIC, the user's general-purpose personal AI assistant across Android and Windows. Help with research, writing, coding, planning, documents, files, and supported app or desktop workflows. Be honest about which tools and device integrations are actually connected; never claim to have clicked, changed, sent, installed, or executed anything unless a tool confirms it. Ask for explicit approval before consequential actions such as sending messages, purchases, deleting or overwriting files, installing software, changing security settings, or publishing externally. Never bypass operating-system permissions, authentication, security controls, or user consent. Treat 'do anything' as broad task assistance within the user's permissions and the tools actually available, not unrestricted access. This edge service currently provides authenticated AI chat and persistent D1 conversation memory only; it does not yet control Android or Windows, access local files, operate a browser, or execute desktop actions. Never pretend those capabilities are live.`
const DEFAULT_MODEL="@cf/zai-org/glm-4.7-flash";
function json(data,status=200){return new Response(JSON.stringify(data),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff"}});}
async function authorized(request,expected){if(!expected)return false;const supplied=request.headers.get("authorization")||"";const candidate=supplied.startsWith("Bearer ")?supplied.slice(7):"";if(!candidate||candidate.length>512)return false;const enc=new TextEncoder();const[a,b]=await Promise.all([crypto.subtle.digest("SHA-256",enc.encode(candidate)),crypto.subtle.digest("SHA-256",enc.encode(expected))]);const x=new Uint8Array(a),y=new Uint8Array(b);let diff=0;for(let i=0;i<x.length;i++)diff|=x[i]^y[i];return diff===0;}
async function readBody(request){const length=Number(request.headers.get("content-length")||0);if(length>30000)throw new Error("request_too_large");const raw=await request.text();if(!raw||raw.length>30000)throw new Error("request_size_invalid");const data=JSON.parse(raw);if(!data||typeof data!=="object"||Array.isArray(data))throw new Error("json_object_required");return data;}
function extractReply(result){if(typeof result==="string")return result;if(typeof result?.response==="string")return result.response;const choice=result?.choices?.[0]?.message?.content;if(typeof choice==="string")return choice;if(Array.isArray(choice))return choice.map(p=>p?.text||"").join("\n");return "";}
function validConversationId(v){return typeof v==="string"&&/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(v);}
async function chat(request,env){
 if(!(await authorized(request,env.NIC_CHAT_ACCESS_TOKEN)))return json({error:"unauthorized"},401);
 if(!env.AI||typeof env.AI.run!=="function")return json({error:"workers_ai_binding_not_configured"},503);
 if(!env.DB)return json({error:"conversation_memory_database_not_configured"},503);
 let p;try{p=await readBody(request);}catch(e){return json({error:e.message},400);}
 if(typeof p.message!=="string"||!p.message.trim()||p.message.length>12000)return json({error:"message_invalid"},400);
 if(Object.keys(p).some(k=>!["message","conversation_id"].includes(k)))return json({error:"chat_payload_fields_invalid"},400);
 if(p.conversation_id!=null&&!validConversationId(p.conversation_id))return json({error:"conversation_id_invalid"},400);
 const id=p.conversation_id||crypto.randomUUID(),now=new Date().toISOString(),model=env.NIC_CHAT_MODEL||DEFAULT_MODEL;
 let history;
 try{
  await env.DB.prepare("INSERT INTO nic_conversations (id, created_at, updated_at) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at").bind(id,now,now).run();
  const stored=await env.DB.prepare("SELECT role, content FROM nic_messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?").bind(id,12).all();
  history=(stored.results||[]).reverse();
  await env.DB.prepare("INSERT INTO nic_messages (conversation_id, created_at, role, content) VALUES (?, ?, 'user', ?)").bind(id,now,p.message.trim()).run();
 }catch{return json({error:"conversation_memory_unavailable"},503);}
 const messages=[{role:"system",content:SYSTEM_INSTRUCTIONS},...history.filter(x=>x&&["user","assistant"].includes(x.role)&&typeof x.content==="string").map(x=>({role:x.role,content:x.content.slice(0,6000)})),{role:"user",content:p.message.trim()}];
 let result;try{result=await env.AI.run(model,{messages,max_tokens:1200});}catch{return json({error:"workers_ai_inference_failed",conversation_id:id},502);}
 const reply=extractReply(result);if(!reply.trim())return json({error:"assistant_returned_no_text",conversation_id:id},502);
 try{
  await env.DB.prepare("INSERT INTO nic_messages (conversation_id, created_at, role, content) VALUES (?, ?, 'assistant', ?)").bind(id,new Date().toISOString(),reply.trim()).run();
  await env.DB.prepare("UPDATE nic_conversations SET updated_at=? WHERE id=?").bind(new Date().toISOString(),id).run();
 }catch{return json({error:"conversation_memory_write_failed",conversation_id:id},503);}
 return json({reply:reply.trim(),conversation_id:id,memory:"persistent_d1",history_messages_used:history.length,model,provider:"cloudflare_workers_ai",capability_mode:"edge_chat_with_persistent_memory"});
}
async function activity(request,env){
 if(!(await authorized(request,env.NIC_OWNER_CONTROL_TOKEN)))return json({error:"owner_unauthorized"},401);
 if(request.method==="GET"){const r=await env.DB.prepare("SELECT id, created_at, task_id, actor, action, status, summary, error_code FROM activity_events ORDER BY id DESC LIMIT 100").all();return json({events:(r.results||[]).reverse(),source:"nic_activity_journal",append_only:true,chain_of_thought_exposed:false});}
 let e;try{e=await readBody(request);}catch(x){return json({error:x.message},400);}
 const fields=["task_id","actor","action","status","summary","error_code"];if(Object.keys(e).some(k=>!fields.includes(k)))return json({error:"activity_event_fields_invalid"},400);
 for(const k of ["actor","action","status","summary"])if(typeof e[k]!=="string"||!e[k].trim())return json({error:`activity_${k}_required`},400);
 const limits={task_id:160,actor:80,action:120,status:40,summary:1200,error_code:120};for(const[k,m]of Object.entries(limits))if(e[k]!=null&&(typeof e[k]!=="string"||e[k].length>m))return json({error:`activity_${k}_invalid`},400);
 const at=new Date().toISOString(),saved=await env.DB.prepare("INSERT INTO activity_events (created_at, task_id, actor, action, status, summary, error_code) VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id").bind(at,e.task_id||null,e.actor.trim(),e.action.trim(),e.status.trim(),e.summary.trim(),e.error_code||null).first();
 return json({event:{id:saved.id,created_at:at,...e},source:"nic_activity_journal"},201);
}

const VIRTUAL_DEVICE_TYPES=["android","windows"];
function validHostBase(value){try{const u=new URL(value);return u.protocol==="https:"&&u.username===""&&u.password===""?u.toString().replace(/\/$/,""):null;}catch{return null;}}
async function callDeviceHost(env,path,options={}){
 const base=validHostBase(env.NIC_DEVICE_HOST_URL||"");
 if(!base||!env.NIC_DEVICE_HOST_TOKEN)return {configured:false,response:null,body:null};
 const headers=new Headers(options.headers||{});
 headers.set("authorization","Bearer "+env.NIC_DEVICE_HOST_TOKEN);
 headers.set("accept","application/json");
 if(options.body)headers.set("content-type","application/json");
 let response;try{response=await fetch(base+path,{...options,headers,signal:AbortSignal.timeout(12000)});}catch{return {configured:true,unavailable:true,response:null,body:null};}
 let body;try{body=await response.json();}catch{body=null;}
 return {configured:true,response,body};
}
function dbLifecycleState(state){return state==="failed"?"error":state==="stopping"?"provisioning":state==="blocked_no_provider"?"not_provisioned":state;}
function dbProviderState(state){if(["connected","healthy"].includes(state))return "connected";if(["disconnected","unreachable"].includes(state))return "disconnected";if(state==="no_provider")return "no_provider";return "configured";}
function hostDeviceIsValid(d){
 return d&&VIRTUAL_DEVICE_TYPES.includes(d.device_type)&&typeof d.lifecycle_state==="string"&&["not_provisioned","provisioning","running","stopping","stopped","failed","blocked_no_provider"].includes(d.lifecycle_state)&&typeof d.provider_state==="string"&&typeof d.screen_streaming_live==="boolean"&&typeof d.remote_input_live==="boolean";
}
async function virtualDevices(request,env){
 if(!(await authorized(request,env.NIC_OWNER_CONTROL_TOKEN)))return json({error:"owner_unauthorized"},401);
 if(!env.DB)return json({error:"virtual_device_database_unavailable"},503);
 if(request.method==="GET"){
  try{
   const now=new Date().toISOString();
   for(const type of VIRTUAL_DEVICE_TYPES){const id="nic-"+type;await env.DB.prepare("INSERT INTO nic_virtual_devices (id, device_type, display_name, lifecycle_state, provider_state, created_at, updated_at) VALUES (?, ?, ?, 'not_provisioned', 'no_provider', ?, ?) ON CONFLICT(id) DO NOTHING").bind(id,type,type==="android"?"NIC Virtual Android":"NIC Virtual Windows",now,now).run();}
   const host=await callDeviceHost(env,"/v1/devices",{method:"GET"});
   if(host.configured&&host.response?.ok&&Array.isArray(host.body?.devices)&&host.body.devices.length===2&&VIRTUAL_DEVICE_TYPES.every(t=>host.body.devices.filter(d=>d.device_type===t).length===1)&&host.body.devices.every(hostDeviceIsValid)){
    for(const d of host.body.devices){
     const id="nic-"+d.device_type;
     await env.DB.prepare("UPDATE nic_virtual_devices SET lifecycle_state=?, provider_state=?, provider_name=?, external_instance_id=?, updated_at=? WHERE id=?").bind(dbLifecycleState(d.lifecycle_state),dbProviderState(d.provider_state),d.provider_name||"external-linux-host",d.external_instance_id||null,now,id).run();
    }
    const r=await env.DB.prepare("SELECT id, device_type, display_name, lifecycle_state, provider_state, provider_name, external_instance_id, created_at, updated_at FROM nic_virtual_devices ORDER BY device_type").all();
    return json({devices:r.results||[],source:"nic_virtual_device_registry",provider_connected:true,virtualization_live:(r.results||[]).some(d=>d.lifecycle_state==="running"),screen_streaming_live:host.body.devices.some(d=>d.screen_streaming_live),remote_input_live:host.body.devices.some(d=>d.remote_input_live)});
   }
   const r=await env.DB.prepare("SELECT id, device_type, display_name, lifecycle_state, provider_state, provider_name, external_instance_id, created_at, updated_at FROM nic_virtual_devices ORDER BY device_type").all();
   return json({devices:r.results||[],source:"nic_virtual_device_registry",provider_connected:false,virtualization_live:false,screen_streaming_live:false,remote_input_live:false,provider_status:host.configured?(host.unavailable?"unreachable":"invalid_or_unhealthy_response"):"not_configured"});
  }catch{return json({error:"virtual_device_registry_unavailable"},503);}
 }
 const match=new URL(request.url).pathname.match(/^\/virtual-devices\/(android|windows)\/actions$/);
 if(!match)return json({error:"not_found"},404);
 let p;try{p=await readBody(request);}catch(e){return json({error:e.message},400);}
 if(Object.keys(p).some(k=>k!=="action")||!["start","stop","restart"].includes(p.action))return json({error:"device_action_invalid"},400);
 const type=match[1],id="nic-"+type,now=new Date().toISOString(),requestId=crypto.randomUUID();
 try{
  const device=await env.DB.prepare("SELECT id, lifecycle_state, provider_state FROM nic_virtual_devices WHERE id=?").bind(id).first();
  if(!device)return json({error:"virtual_device_not_registered"},404);
  const host=await callDeviceHost(env,"/v1/devices/"+type+"/actions",{method:"POST",body:JSON.stringify({action:p.action,request_id:requestId})});
  if(!host.configured||!host.response?.ok||!host.body||host.body.device_type!==type||host.body.request_id!==requestId||!["provisioning","running","stopping","stopped","failed"].includes(host.body.lifecycle_state)||typeof host.body.performed!=="boolean"||typeof host.body.screen_streaming_live!=="boolean"||typeof host.body.remote_input_live!=="boolean"||(host.body.performed&&p.action==="start"&&(host.body.lifecycle_state!=="running"||!host.body.screen_streaming_live||!host.body.remote_input_live))||(host.body.performed&&p.action==="restart"&&(host.body.lifecycle_state!=="running"||!host.body.screen_streaming_live||!host.body.remote_input_live))||(host.body.performed&&p.action==="stop"&&(host.body.lifecycle_state!=="stopped"||host.body.remote_input_live))){
   const code=!host.configured?"vm_provider_not_configured":host.unavailable?"vm_provider_unreachable":"vm_provider_response_invalid";
   await env.DB.prepare("INSERT INTO nic_device_action_requests (id, device_id, action, requested_at, request_state, result_code) VALUES (?, ?, ?, ?, 'blocked_no_provider', ?)").bind(requestId,id,p.action,now,code).run();
   await env.DB.prepare("INSERT INTO activity_events (created_at, task_id, actor, action, status, summary, error_code) VALUES (?, ?, 'owner', ?, 'blocked', ?, ?)").bind(now,requestId,"virtual_device_"+p.action,"No verified VM host action was performed.",code).run();
   return json({request_id:requestId,device_id:id,action:p.action,status:code==="vm_provider_not_configured"?"blocked_no_provider":"provider_unavailable",performed:false,message:"No verified VM host action was completed. Check the NIC device-host connection and health before retrying."},202);
  }
  await env.DB.prepare("INSERT INTO nic_device_action_requests (id, device_id, action, requested_at, request_state, result_code) VALUES (?, ?, ?, ?, ?, ?)").bind(requestId,id,p.action,now,host.body.performed?"succeeded":host.body.lifecycle_state==="failed"?"failed":"accepted",host.body.result_code||null).run();
  await env.DB.prepare("UPDATE nic_virtual_devices SET lifecycle_state=?, provider_state=?, provider_name=?, external_instance_id=?, updated_at=? WHERE id=?").bind(dbLifecycleState(host.body.lifecycle_state),dbProviderState(host.body.provider_state||"connected"),host.body.provider_name||"external-linux-host",host.body.external_instance_id||null,new Date().toISOString(),id).run();
  await env.DB.prepare("INSERT INTO activity_events (created_at, task_id, actor, action, status, summary, error_code) VALUES (?, ?, 'owner', ?, ?, ?, ?)").bind(now,requestId,"virtual_device_"+p.action,host.body.performed?"completed":"blocked",host.body.message||"Host adapter returned an action result.",host.body.result_code||null).run();
  return json({request_id:requestId,device_id:id,action:p.action,status:host.body.lifecycle_state,performed:host.body.performed,message:host.body.message||"Host adapter response recorded."},host.body.performed?200:202);
 }catch{return json({error:"virtual_device_action_record_failed"},503);}
}
export default {async fetch(request,env){const u=new URL(request.url);if(request.method==="GET"&&u.pathname==="/healthz")return json({status:"ok",service:"nic-edge-chat",model_configured:Boolean(env.AI),model_provider:"cloudflare_workers_ai",model:env.NIC_CHAT_MODEL||DEFAULT_MODEL,chat_token_configured:Boolean(env.NIC_CHAT_ACCESS_TOKEN),owner_control_token_configured:Boolean(env.NIC_OWNER_CONTROL_TOKEN),device_host_configured:Boolean(validHostBase(env.NIC_DEVICE_HOST_URL||"")&&env.NIC_DEVICE_HOST_TOKEN),activity_database_bound:Boolean(env.DB),conversation_memory:Boolean(env.DB),capability_mode:"edge_chat_with_persistent_memory",publishing_enabled:false});if((u.pathname==="/virtual-devices"||/^\/virtual-devices\/(android|windows)\/actions$/.test(u.pathname))&&(request.method==="GET"||request.method==="POST"))return virtualDevices(request,env);if(u.pathname==="/chat"&&request.method==="POST")return chat(request,env);if(u.pathname==="/activity"&&(request.method==="GET"||request.method==="POST")){if(!env.DB)return json({error:"activity_database_unavailable"},503);try{return await activity(request,env);}catch{return json({error:"activity_journal_unavailable"},503);}}return json({error:"not_found"},404);}};
