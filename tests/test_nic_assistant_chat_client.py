import io
import json
import unittest
from src.nic_assistant_chat_client import ask_assistant, AssistantUnavailable

class FakeResponse:
    status = 200
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return json.dumps(self.payload).encode("utf-8")

class NICAssistantClientTests(unittest.TestCase):
    def test_posts_message_with_bearer_token_and_returns_reply(self):
        captured = {}
        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["auth"] = request.get_header("Authorization")
            captured["timeout"] = timeout
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse({"reply": "Use a fresher angle."})
        reply = ask_assistant("Review this draft", [{"role":"user","content":"Earlier"}],
                              endpoint="https://assistant.example/", token="secret",
                              opener=opener)
        self.assertEqual(reply, "Use a fresher angle.")
        self.assertEqual(captured["url"], "https://assistant.example/chat")
        self.assertEqual(captured["auth"], "Bearer secret")
        self.assertEqual(captured["body"]["message"], "Review this draft")
        self.assertEqual(captured["body"]["history"][0]["content"], "Earlier")

    def test_missing_configuration_fails_closed(self):
        with self.assertRaises(AssistantUnavailable):
            ask_assistant("hello", endpoint="", token="", opener=lambda *a, **k: None)

    def test_invalid_response_fails_closed(self):
        with self.assertRaises(AssistantUnavailable):
            ask_assistant("hello", endpoint="https://assistant.example",
                          token="secret", opener=lambda *a, **k: FakeResponse({"other":"no"}))

if __name__ == "__main__":
    unittest.main()
