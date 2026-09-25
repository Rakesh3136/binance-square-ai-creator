#!/usr/bin/env node
// Binance Square image publisher adapter aligned with the current official
// Binance Skills Hub square-post image flow. A 504 from content/add is
// submitted-but-unverified; never fabricate a post id.
import fs from 'node:fs';
import path from 'node:path';

const key = process.env.BINANCE_SQUARE_OPENAPI_KEY?.trim();
const imagePath = process.argv[2];
const text = process.argv[3] || '';
if (!key) throw new Error('BINANCE_SQUARE_OPENAPI_KEY is not configured');
if (!imagePath || !fs.existsSync(imagePath)) throw new Error(`Image missing: ${imagePath}`);

const V2 = 'https://www.binance.com/bapi/composite/v2/public/pgc/openApi';
const V1 = 'https://www.binance.com/bapi/composite/v1/public/pgc/openApi';

function contentType(filePath) {
  const ext = path.extname(filePath).slice(1).toLowerCase();
  return ({jpg:'image/jpeg',jpeg:'image/jpeg',png:'image/png',gif:'image/gif',webp:'image/webp'})[ext] || 'application/octet-stream';
}

async function api(base, endpoint, body) {
  const r = await fetch(base + endpoint, {
    method: 'POST',
    headers: {
      'X-Square-OpenAPI-Key': key,
      'Content-Type': 'application/json',
      'clienttype': 'binanceSkill',
    },
    body: JSON.stringify(body),
  });
  const raw = await r.text();

  if (endpoint === '/content/add' && r.status === 504) {
    return { id: null, shareLink: null, publishStatus: 'submitted_unknown_504' };
  }

  let j;
  try {
    j = JSON.parse(raw);
  } catch {
    throw new Error(`Binance non-JSON response: HTTP ${r.status} ${r.statusText}; body=${raw.slice(0,500)}`);
  }

  if (j.code !== '000000') {
    const message = j.message ?? 'unknown';
    // Keep the upstream status/code/message visible so a backend parser error
    // cannot be collapsed into a generic Python exception.
    throw new Error(`Binance API error: HTTP ${r.status}; code=${j.code}; message=${message}; endpoint=${endpoint}`);
  }
  return j.data;
}

async function uploadAndProcess() {
  const imageName = path.basename(imagePath);
  const ticket = await api(V2, '/image/presignedUrl', { imageName });
  if (!ticket?.presignedUrl || !ticket?.fileTicket) {
    throw new Error('Square image presigned upload response incomplete');
  }

  const upload = await fetch(ticket.presignedUrl, {
    method: 'PUT',
    headers: { 'Content-Type': contentType(imagePath) },
    body: fs.readFileSync(imagePath),
  });
  if (!upload.ok) {
    throw new Error(`S3 upload failed: HTTP ${upload.status} ${upload.statusText}`);
  }

  for (let i = 0; i < 10; i++) {
    const status = await api(V2, '/image/imageStatus', { fileTicket: ticket.fileTicket });
    if (status?.status === 1 && status?.imageUrl) return status.imageUrl;
    if (status?.status === 2) {
      throw new Error(`Square image processing failed: ${status.failedReason || 'unknown'}`);
    }
    await new Promise(r => setTimeout(r, 3000));
  }
  throw new Error('Square image processing timed out');
}

async function publish(imageUrl) {
  return await api(V1, '/content/add', {
    contentType: 1,
    bodyTextOnly: text,
    imageList: [imageUrl],
  });
}

async function main() {
  // First upload + publish attempt.
  let imageUrl = await uploadAndProcess();
  try {
    const result = await publish(imageUrl);
    console.log(JSON.stringify({
      status: result.publishStatus === 'submitted_unknown_504'
        ? 'PUBLISHED_SUBMITTED_504'
        : 'PUBLISHED_VERIFIED_BY_API_RESPONSE',
      post_id: result.id || null,
      link: result.shareLink || null,
      image_url: imageUrl,
    }));
    return;
  } catch (firstError) {
    // Retry exactly once with a fresh processed media URL. Do not downgrade
    // an image-required publication to text-only.
    console.error(`Image publication attempt 1 failed: ${firstError.message}; retrying with fresh media...`);
    imageUrl = await uploadAndProcess();
    const result = await publish(imageUrl);
    console.log(JSON.stringify({
      status: result.publishStatus === 'submitted_unknown_504'
        ? 'PUBLISHED_SUBMITTED_504'
        : 'PUBLISHED_VERIFIED_BY_API_RESPONSE',
      post_id: result.id || null,
      link: result.shareLink || null,
      image_url: imageUrl,
    }));
  }
}

main().catch(e => {
  console.error(e.stack || e);
  process.exit(1);
});
