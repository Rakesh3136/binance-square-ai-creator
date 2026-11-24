const SYSTEM_INSTRUCTIONS = `You are NIC, the user's Binance Square creator-workflow assistant.
Your mission is original, evidence-led creator content and learning from Binance Square performance and reward evidence. Do not drift into trading or order execution. Never guarantee earnings. Distinguish verified rewards from owner-reported rewards, views, likes, estimates, and assumptions. Do not copy creators' wording.
This Cloudflare edge bootstrap is a limited chat and activity service. It has no connected repository research tools, specialist-agent executor, Binance publishing integration, browser automation, or autonomous scheduler. Never claim to have researched live sources, published content, or executed an external action unless an enabled integration confirms it. Ask for explicit owner approval before any consequential action. `;

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff" },
  });
}

async function authorized(request, expected) {
  if (!expected) return false;
  const supplied = request.headers.get("authorization") || "";
  const candidate = supplied.startsWith("Bearer ") ? supplied.slice(7) : "";
  if (!candidate || candidate.length > 512) return false;
  const enc = new TextEncoder();
  const [a, b] = await Promise.all([
    crypto.subtle.digest("SHA-256", enc.encode(candidate)),
    crypto.subtle.digest("SHA-256", enc.encode(expected)),
  ]);
  const x = new Uint8Array(a), y = new Uint8Array(b);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

async function readBody(request) {
  const length = Number(request.headers.get("content-length") || 0);
  if (length > 30000) throw new Error("request_too_large");
  const raw = await request.text();
  if (!raw || raw.length > 30000) throw new Error("request_size_invalid");
  const data = JSON.parse(raw);
  if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("json_object_required");
  return data;
}

async function chat(request, env) {
  if (!(await authorized(request, env.NIC_CHAT_ACCESS_TOKEN))) return json({ error: "unauthorized" }, 401);
  if (!env.OPENAI_API_KEY) return json({ error: "assistant_provider_not_configured" }, 503);
  let payload;
  try { payload = await readBody(request); } catch (e) { return json({ error: e.message }, 400); }
  const message = payload.message;
  const history = payload.history ?? [];
  if (typeof message !== "string" || !message.trim() || message.length > 12000) return json({ error: "message_invalid" }, 400);
  if (!Array.isArray(history)) return json({ error: "history_must_be_array" }, 400);
  const input = history.slice(-12).filter(x => x && ["user", "assistant"].includes(x.role) && typeof x.content === "string")
    .map(x => ({ role: x.role, content: x.content.slice(0, 6000) }));
  input.push({ role: "user", content: message.trim() });
  let upstream;
  try {
    upstream = await fetch("https://api.openai.com/v1/responses", {
      method: "POST",
      headers: { authorization: `Bearer ${env.OPENAI_API_KEY}`, "content-type": "application/json" },
      body: JSON.stringify({ model: env.NIC_CHAT_MODEL || "gpt-4.1-mini", instructions: SYSTEM_INSTRUCTIONS, input, max_output_tokens: 1200 }),
    });
  } catch { return json({ error: "assistant_provider_unreachable" }, 502); }
  if (!upstream.ok) return json({ error: "assistant_provider_failed", provider_status: upstream.status }, 502);
  let result;
  try { result = await upstream.json(); } catch { return json({ error: "assistant_response_invalid" }, 502); }
  let reply = typeof result.output_text === "string" ? result.output_text : "";
  if (!reply && Array.isArray(result.output)) {
    reply = result.output.flatMap(item => item.content || []).filter(item => item.type === "output_text").map(item => item.text || "").join("\n");
  }
  if (!reply.trim()) return json({ error: "assistant_returned_no_text" }, 502);
  return json({ reply: reply.trim(), model: env.NIC_CHAT_MODEL || "gpt-4.1-mini", capability_mode: "edge_chat_limited" });
}

async function activity(request, env) {
  if (!(await authorized(request, env.NIC_OWNER_CONTROL_TOKEN))) return json({ error: "owner_unauthorized" }, 401);
  if (request.method === "GET") {
    const result = await env.DB.prepare("SELECT id, created_at, task_id, actor, action, status, summary, error_code FROM activity_events ORDER BY id DESC LIMIT 100").all();
    return json({ events: (result.results || []).reverse(), source: "nic_activity_journal", append_only: true, chain_of_thought_exposed: false });
  }
  let event;
  try { event = await readBody(request); } catch (e) { return json({ error: e.message }, 400); }
  const fields = ["task_id", "actor", "action", "status", "summary", "error_code"];
  if (Object.keys(event).some(k => !fields.includes(k))) return json({ error: "activity_event_fields_invalid" }, 400);
  for (const key of ["actor", "action", "status", "summary"]) {
    if (typeof event[key] !== "string" || !event[key].trim()) return json({ error: `activity_${key}_required` }, 400);
  }
  const limits = { task_id: 160, actor: 80, action: 120, status: 40, summary: 1200, error_code: 120 };
  for (const [key, max] of Object.entries(limits)) {
    if (event[key] != null && (typeof event[key] !== "string" || event[key].length > max)) return json({ error: `activity_${key}_invalid` }, 400);
  }
  const createdAt = new Date().toISOString();
  const saved = await env.DB.prepare("INSERT INTO activity_events (created_at, task_id, actor, action, status, summary, error_code) VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id")
    .bind(createdAt, event.task_id || null, event.actor.trim(), event.action.trim(), event.status.trim(), event.summary.trim(), event.error_code || null).first();
  return json({ event: { id: saved.id, created_at: createdAt, ...event }, source: "nic_activity_journal" }, 201);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/healthz") {
      return json({
        status: "ok",
        service: "nic-edge-chat",
        model_configured: Boolean(env.OPENAI_API_KEY),
        chat_token_configured: Boolean(env.NIC_CHAT_ACCESS_TOKEN),
        owner_control_token_configured: Boolean(env.NIC_OWNER_CONTROL_TOKEN),
        activity_database_bound: Boolean(env.DB),
        capability_mode: "edge_chat_limited",
        publishing_enabled: false,
      });
    }
    if (url.pathname === "/chat" && request.method === "POST") return chat(request, env);
    if (url.pathname === "/activity" && (request.method === "GET" || request.method === "POST")) {
      if (!env.DB) return json({ error: "activity_database_unavailable" }, 503);
      try { return await activity(request, env); } catch { return json({ error: "activity_journal_unavailable" }, 503); }
    }
    return json({ error: "not_found" }, 404);
  },
};
