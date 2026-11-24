import test from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";

test("health reports Workers AI binding and never exposes secrets", async () => {
  const response = await worker.fetch(new Request("https://nic.test/healthz"), {});
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.status, "ok");
  assert.equal(body.model_configured, false);
  assert.equal(body.model_provider, "cloudflare_workers_ai");
  assert.equal(body.publishing_enabled, false);
  assert.equal(JSON.stringify(body).includes("Bearer"), false);
});

test("unknown route is not found", async () => {
  const response = await worker.fetch(new Request("https://nic.test/nope"), {});
  assert.equal(response.status, 404);
});

test("chat rejects missing authentication before inference", async () => {
  let called = false;
  const response = await worker.fetch(new Request("https://nic.test/chat", {
    method: "POST", headers: {"content-type":"application/json"},
    body: JSON.stringify({message:"hello"})
  }), { NIC_CHAT_ACCESS_TOKEN: "test-token", AI: { run: async () => { called = true; return {response:"unexpected"}; } } });
  assert.equal(response.status, 401);
  assert.equal(called, false);
});

test("chat uses Cloudflare Workers AI binding after owner authentication", async () => {
  let call;
  const response = await worker.fetch(new Request("https://nic.test/chat", {
    method: "POST",
    headers: {"content-type":"application/json", authorization:"Bearer test-token"},
    body: JSON.stringify({message:"Hello NIC"})
  }), {
    NIC_CHAT_ACCESS_TOKEN: "test-token",
    AI: { run: async (model, input) => { call = {model, input}; return {response:"I am NIC."}; } }
  });
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.reply, "I am NIC.");
  assert.equal(body.provider, "cloudflare_workers_ai");
  assert.equal(call.model, "@cf/zai-org/glm-4.7-flash");
  assert.equal(call.input.messages.at(-1).content, "Hello NIC");
});

test("chat reports missing Workers AI binding without any provider key", async () => {
  const response = await worker.fetch(new Request("https://nic.test/chat", {
    method: "POST",
    headers: {"content-type":"application/json", authorization:"Bearer test-token"},
    body: JSON.stringify({message:"hello"})
  }), { NIC_CHAT_ACCESS_TOKEN: "test-token" });
  assert.equal(response.status, 503);
  assert.equal((await response.json()).error, "workers_ai_binding_not_configured");
});

test("activity rejects missing owner authentication", async () => {
  const response = await worker.fetch(new Request("https://nic.test/activity"), { DB: {} });
  assert.equal(response.status, 401);
});
