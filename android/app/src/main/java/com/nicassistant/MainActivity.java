package com.nicassistant;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Typeface;
import android.view.View;
import android.widget.*;
import org.json.*;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private EditText server, chatToken, ownerToken, message;
    private TextView output, status;
    private LinearLayout root;
    private String base() { return server.getText().toString().trim().replaceAll("/+$", ""); }
    private String request(String path, String token, JSONObject body) throws Exception {
        URL url = new URL(base() + path);
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        c.setConnectTimeout(12000); c.setReadTimeout(30000); c.setRequestMethod(body == null ? "GET" : "POST");
        c.setRequestProperty("Accept", "application/json");
        if (token != null && !token.isEmpty()) c.setRequestProperty("Authorization", "Bearer " + token);
        if (body != null) {
            c.setDoOutput(true); c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            try (OutputStream os = c.getOutputStream()) { os.write(body.toString().getBytes(StandardCharsets.UTF_8)); }
        }
        int code = c.getResponseCode();
        InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        if (in != null) { byte[] buf = new byte[4096]; int n; while ((n=in.read(buf))!=-1) bytes.write(buf,0,n); in.close(); }
        c.disconnect();
        String text = bytes.toString("UTF-8");
        if (code < 200 || code >= 300) throw new IOException("HTTP " + code + ": " + text);
        return text;
    }
    private void addLabel(String s, int size, boolean bold) {
        TextView t = new TextView(this); t.setText(s); t.setTextSize(size);
        if (bold) t.setTypeface(null, Typeface.BOLD);
        t.setPadding(0, 10, 0, 8); root.addView(t);
    }
    private EditText field(String hint, boolean secret) {
        EditText e = new EditText(this); e.setSingleLine(true); e.setHint(hint);
        if (secret) e.setInputType(129);
        root.addView(e); return e;
    }
    private Button button(String label, Runnable action) {
        Button b = new Button(this); b.setText(label); root.addView(b);
        b.setOnClickListener(v -> action.run()); return b;
    }
    private void show(String text) { runOnUiThread(() -> output.setText(text)); }
    private void work(String label, Task task) {
        status.setText(label + "…");
        io.execute(() -> { try { String result = task.run(); runOnUiThread(() -> status.setText("Connected / ready")); show(result); }
            catch (Exception e) { runOnUiThread(() -> status.setText("Request failed")); show(e.getMessage()); } });
    }
    interface Task { String run() throws Exception; }
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll = new ScrollView(this); root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL); root.setPadding(24, 24, 24, 24); scroll.addView(root); setContentView(scroll);
        addLabel("NIC Assistant", 26, true);
        addLabel("Android companion • MVP", 14, false);
        server = field("HTTPS NIC server URL", false); server.setText(BuildConfig.DEFAULT_SERVER_URL);
        chatToken = field("Chat access token (memory only)", true);
        ownerToken = field("Owner control token (memory only)", true);
        status = new TextView(this); root.addView(status);
        button("Check server", () -> work("Checking server", () -> request("/healthz", null, null)));
        addLabel("Chat with NIC", 19, true);
        message = new EditText(this); message.setHint("Message NIC…"); message.setMinLines(2); root.addView(message);
        button("Send message", () -> {
            String prompt = message.getText().toString().trim();
            if (prompt.isEmpty()) { show("Enter a message first."); return; }
            work("Sending", () -> {
                JSONObject body = new JSONObject(); body.put("message", prompt); body.put("history", new JSONArray());
                JSONObject response = new JSONObject(request("/chat", chatToken.getText().toString(), body));
                return response.optString("reply", "No reply returned");
            });
        });
        addLabel("Owner activity", 19, true);
        button("Refresh activity journal", () -> work("Loading activity", () -> {
            JSONObject data = new JSONObject(request("/activity", ownerToken.getText().toString(), null));
            JSONArray events = data.optJSONArray("events"); StringBuilder out = new StringBuilder();
            if (events == null || events.length() == 0) return "No activity events recorded yet.";
            for (int i=0;i<events.length();i++) {
                JSONObject e = events.getJSONObject(i);
                out.append(e.optString("created_at")).append("  ")
                   .append(e.optString("actor")).append(" / ").append(e.optString("action"))
                   .append(" — ").append(e.optString("status")).append("\n")
                   .append(e.optString("summary")).append("\n\n");
            }
            return out.toString();
        }));
        addLabel("Response", 18, true);
        output = new TextView(this); output.setTextIsSelectable(true); output.setTextSize(15); root.addView(output);
        addLabel("Security: tokens stay in memory for this session and are not saved by this app. Use HTTPS. Chat and owner tokens are separate.", 12, false);
    }
    @Override protected void onDestroy() { super.onDestroy(); io.shutdownNow(); }
}
