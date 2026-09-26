import fs from "fs";
import os from "os";
import path from "path";

const BASE_URL_V1 = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi";
const BASE_URL_V2 = "https://www.binance.com/bapi/composite/v2/public/pgc/openApi";
const POLL_INTERVAL_MS = 3000;
const MAX_POLL_RETRIES = 10;

const CONTENT_TYPE_MAP = {
  jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png", gif: "image/gif", webp: "image/webp",
};

export function getContentType(filePath) {
  const ext = path.extname(filePath).slice(1).toLowerCase();
  return CONTENT_TYPE_MAP[ext] || "application/octet-stream";
}

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export async function api(endpoint, apiKey, body, baseUrl = BASE_URL_V2) {
  const url = `${baseUrl}${endpoint}`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "X-Square-OpenAPI-Key": apiKey,
      "Content-Type": "application/json",
      clienttype: "binanceSkill",
    },
    body: JSON.stringify(body),
  });
  const raw = await res.text();

  if (endpoint === "/content/add" && res.status === 504) {
    return { id: null, shareLink: null, publishStatus: "success_without_post_id" };
  }

  let json;
  try {
    json = JSON.parse(raw);
  } catch {
    throw new Error(`Binance non-JSON response: HTTP ${res.status} ${res.statusText}; body=${raw.slice(0,500)}`);
  }
  if (json.code !== "000000") {
    throw new Error(`Binance API error [${json.code}]: ${json.message || "unknown"}`);
  }
  return json.data;
}

export async function uploadImage(apiKey, imgPath) {
  const imageName = path.basename(imgPath);
  const contentType = getContentType(imgPath);
  console.log(`Uploading: ${imageName}`);
  const ticket = await api("/image/presignedUrl", apiKey, { imageName });
  if (!ticket || typeof ticket !== "object" || !ticket.presignedUrl || !ticket.fileTicket) {
    throw new Error(`Binance image presignedUrl response incomplete: ${JSON.stringify(ticket)}`);
  }

  const upload = await fetch(ticket.presignedUrl, {
    method: "PUT",
    headers: { "Content-Type": contentType },
    body: fs.readFileSync(imgPath),
  });
  if (!upload.ok) throw new Error(`S3 upload failed: ${upload.status} ${upload.statusText}`);
  console.log("Uploaded to S3, polling status...");

  for (let i = 0; i < MAX_POLL_RETRIES; i++) {
    const data = await api("/image/imageStatus", apiKey, { fileTicket: ticket.fileTicket });
    if (data?.status === 1 && data?.imageUrl) {
      console.log(`Ready: ${data.imageUrl}`);
      return data.imageUrl;
    }
    if (data?.status === 2) throw new Error(`Processing failed: ${data.failedReason || "unknown"}`);
    await sleep(POLL_INTERVAL_MS);
  }
  throw new Error(`Poll timed out after ${MAX_POLL_RETRIES} retries`);
}

export async function publishImage(apiKey, text, imageUrl) {
  return api("/content/add", apiKey, { contentType: 1, bodyTextOnly: text, imageList: [imageUrl] }, BASE_URL_V1);
}
