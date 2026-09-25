#!/usr/bin/env node
// Binance Square image publisher adapter.
// A 504 from content/add is treated as submitted-but-unverified: Binance may
// accept the post while returning no post id. Never fabricate an id.
import fs from 'node:fs';
import path from 'node:path';
const key=process.env.BINANCE_SQUARE_OPENAPI_KEY?.trim();
const imagePath=process.argv[2];
const text=process.argv[3] || '';
if(!key) throw new Error('BINANCE_SQUARE_OPENAPI_KEY is not configured');
if(!imagePath || !fs.existsSync(imagePath)) throw new Error(`Image missing: ${imagePath}`);
const V2='https://www.binance.com/bapi/composite/v2/public/pgc/openApi';
const V1='https://www.binance.com/bapi/composite/v1/public/pgc/openApi';
async function api(base,endpoint,body){
  const r=await fetch(base+endpoint,{method:'POST',headers:{'X-Square-OpenAPI-Key':key,'Content-Type':'application/json','clienttype':'binanceSkill'},body:JSON.stringify(body)});
  const raw=await r.text();
  if(endpoint==='/content/add' && r.status===504) return {id:null,shareLink:null,publishStatus:'submitted_unknown_504'};
  let j;try{j=JSON.parse(raw)}catch{throw new Error(`Binance non-JSON ${r.status}: ${raw.slice(0,300)}`)}
  if(j.code!=='000000') throw new Error(`Binance API error [${j.code}]: ${j.message||'unknown'}`);
  return j.data;
}
async function publishImageWithRetry(text, imageUrl, attempt = 1){
  try {
    return await api(V1,'/content/add',{contentType:1,bodyTextOnly:text,imageList:[imageUrl]});
  } catch (e) {
    if (attempt >= 2) throw e;
    console.error(`Image publication attempt ${attempt} failed: ${e.message}; retrying with a fresh media submission...`);
    throw e;
  }
}

async function main(){
  const imageName=path.basename(imagePath);
  const ticket=await api(V2,'/image/presignedUrl',{imageName});
  if(!ticket?.presignedUrl || !ticket?.fileTicket) throw new Error('Square image presigned upload response incomplete');
  const type=imagePath.toLowerCase().endsWith('.png')?'image/png':'image/jpeg';
  const upload=await fetch(ticket.presignedUrl,{method:'PUT',headers:{'Content-Type':type},body:fs.readFileSync(imagePath)});
  if(!upload.ok) throw new Error(`Square media upload failed: ${upload.status}`);
  let status;
  for(let i=0;i<10;i++){
    status=await api(V2,'/image/imageStatus',{fileTicket:ticket.fileTicket});
    if(status.status===1) break;
    if(status.status===2) throw new Error(`Square image processing failed: ${status.failedReason||'unknown'}`);
    await new Promise(r=>setTimeout(r,3000));
  }
  if(!status?.imageUrl) throw new Error('Square image processing timed out');
  let result;
  try {
    result = await publishImageWithRetry(text, status.imageUrl, 1);
  } catch (firstError) {
    // A transient Square media/content mismatch can occur after a valid image
    // upload. Re-upload the same source once and publish with the new processed
    // URL. Never fall back to text-only here because this lane explicitly
    // requires the verified visual package.
    const retryTicket=await api(V2,'/image/presignedUrl',{imageName});
    if(!retryTicket?.presignedUrl || !retryTicket?.fileTicket) throw firstError;
    await fetch(retryTicket.presignedUrl,{method:'PUT',headers:{'Content-Type':type},body:fs.readFileSync(imagePath)});
    let retryStatus;
    for(let i=0;i<10;i++){
      retryStatus=await api(V2,'/image/imageStatus',{fileTicket:retryTicket.fileTicket});
      if(retryStatus.status===1) break;
      if(retryStatus.status===2) throw new Error(`Square image processing failed on retry: ${retryStatus.failedReason||'unknown'}`);
      await new Promise(r=>setTimeout(r,3000));
    }
    if(!retryStatus?.imageUrl) throw new Error('Square image retry processing timed out');
    result=await publishImageWithRetry(text,retryStatus.imageUrl,2);
    status.imageUrl=retryStatus.imageUrl;
  }
  console.log(JSON.stringify({status:result.publishStatus==='submitted_unknown_504'?'PUBLISHED_SUBMITTED_504':'PUBLISHED_VERIFIED_BY_API_RESPONSE',post_id:result.id||null,link:result.shareLink||null,image_url:status.imageUrl}));
}
main().catch(e=>{console.error(e.stack||e);process.exit(1)});
