#!/usr/bin/env node
import fs from "node:fs";
import { uploadImage, publishImage } from "./binance_square_skill_lib.mjs";

const key = process.env.BINANCE_SQUARE_OPENAPI_KEY?.trim();
const imagePath = process.argv[2];
const text = process.argv[3] || "";
if (!key) throw new Error("BINANCE_SQUARE_OPENAPI_KEY is not configured");
if (!imagePath || !fs.existsSync(imagePath)) throw new Error(`Image missing: ${imagePath}`);
if (!text.trim()) throw new Error("Publication text is empty");

async function main() {
  let imageUrl = await uploadImage(key, imagePath);
  try {
    const result = await publishImage(key, text, imageUrl);
    console.log(JSON.stringify({
      status: result?.publishStatus === "success_without_post_id" ? "PUBLISHED_SUBMITTED_504" : "PUBLISHED_VERIFIED_BY_API_RESPONSE",
      post_id: result?.id || null,
      link: result?.shareLink || null,
      image_url: imageUrl,
    }));
  } catch (firstError) {
    // Retry once with a completely fresh Binance media ticket. Do not post text-only.
    console.error(`Square image publication attempt 1 failed: ${firstError.message}`);
    imageUrl = await uploadImage(key, imagePath);
    const result = await publishImage(key, text, imageUrl);
    console.log(JSON.stringify({
      status: result?.publishStatus === "success_without_post_id" ? "PUBLISHED_SUBMITTED_504" : "PUBLISHED_VERIFIED_BY_API_RESPONSE",
      post_id: result?.id || null,
      link: result?.shareLink || null,
      image_url: imageUrl,
    }));
  }
}

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
