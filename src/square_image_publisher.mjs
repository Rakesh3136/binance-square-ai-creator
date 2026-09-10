#!/usr/bin/env node
// Minimal, repository-local adapter for Binance Square image posts.
// Uses the current Square media flow: presigned upload -> processing poll -> content/add.
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
  if(endpoint==='/content/add' && r.status===504) return {id:null,shareLink:null,publishStatus:'success_without_post_id'};
  let j;try{j=JSON.parse(raw)}catch{throw new Error(`Binance non-JSON ${r.status}: ${raw.slice(0,300)}`)}
  if(j.code!=='000000') throw new Error(`Binance API error [${j.code}]: ${j.message||'unknown'}`);
  return j.data;
}
async function main(){
  const imageName=path.basename(imagePath);
  const ticket=await api(V2,'/image/presignedUrl',{imageName});
  if(!ticket?.presignedUrl || !ticket?.fileTicket) throw new Error('Square image presigned upload response incomplete');
  const type=imagePath.toLowerCase().endsWith('.png')?'image/png':'image/jpeg';
  const bytes=fs.readFileSync(imagePath);
  const upload=await fetch(ticket.presignedUrl,{method:'PUT',headers:{'Content-Type':type},body:bytes});
  if(!upload.ok) throw new Error(`Square media upload failed: ${upload.status}`);
  let status;
  for(let i=0;i<10;i++){
    status=await api(V2,'/image/imageStatus',{fileTicket:ticket.fileTicket});
    if(status.status===1) break;
    if(status.status===2) throw new Error(`Square image processing failed: ${status.failedReason||'unknown'}`);
    await new Promise(r=>setTimeout(r,3000));
  }
  if(!status?.imageUrl) throw new Error('Square image processing timed out');
  const result=await api(V1,'/content/add',{contentType:1,bodyTextOnly:text,imageList:[status.imageUrl]});
  console.log(JSON.stringify({status:result.publishStatus==='success_without_post_id'?'PUBLISHED_UNKNOWN':'PUBLISHED_VERIFIED_BY_API_RESPONSE',post_id:result.id||null,link:result.shareLink||null,image_url:status.imageUrl},null,2));
}
main().catch(e=>{console.error(e.stack||e);process.exit(1)});
