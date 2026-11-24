import test from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";

test("health reports missing secrets without exposing them", async () => {
  const response = await worker.fetch(new Request("https://nic.test/healthz"), {});
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.status, "ok");
  assert.equal(body.model_configured, false);
  assert.equal(body.publishing_enabled, false);
  assert.equal(JSON.stringify(body).includes("Bearer"), false);
});

test("unknown route is not found", async () => {
  const response = await worker.fetch(new Request("https://nic.test/nope"), {});
  assert.equal(response.status, 404);
});

test("chat rejects missing authentication", async () => {
  const response = await worker.fetch(new Request("https://nic.test/chat", {
    method: "POST", headers: {"content-type":"application/json"},
    body: JSON.stringify({message:"hello"})
  }), { OPENAI_API_KEY: "not-used" });
  assert.equal(response.status, 401);
});

test("activity rejects missing owner authentication", async () => {
  const response = await worker.fetch(new Request("https://nic.test/activity"), { DB: {} });
  assert.equal(response.status, 401);
});
