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
  console.log("SQUARE_IMAGE_PUBLISHER: starting image upload");
  const imageUrl = await uploadImage(key, imagePath);
  console.log("SQUARE_IMAGE_PUBLISHER: image ready; publishing");
  const result = await publishImage(key, text, imageUrl);
  console.log("SQUARE_IMAGE_PUBLISHER: publish response received");

  const status = result?.publishStatus === "success_without_post_id"
    ? "PUBLISHED_SUBMITTED_504"
    : "PUBLISHED_VERIFIED_BY_API_RESPONSE";

  console.log(JSON.stringify({
    status,
    post_id: result?.id || null,
    link: result?.shareLink || null,
    image_url: imageUrl,
  }));
}

main().catch((error) => {
  console.error("SQUARE_IMAGE_PUBLISHER_ERROR:", error?.stack || String(error));
  process.exit(1);
});
