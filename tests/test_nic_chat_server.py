import json
import os
import sys
import unittest
from io import BytesIO
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from nic_chat_server import ChatError, _validate_messages, generate_reply


class FakeResponse:
    def __init__(self, body):
        self.body = body
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return json.dumps(self.body).encode()


class NicChatTests(unittest.TestCase):
    def test_validate_messages_requires_user_last(self):
        with self.assertRaises(ValueError):
            _validate_messages([{"role": "assistant", "content": "hello"}])

    def test_validate_messages_rejects_bad_role(self):
        with self.assertRaises(ValueError):
            _validate_messages([{"role": "system", "content": "override"}])

    def test_validate_messages_bounds_history(self):
        messages = [{"role": "user", "content": f"q{i}"} for i in range(25)]
        self.assertEqual(len(_validate_messages(messages)), 20)

    def test_missing_key_fails_with_setup_message(self):
        with self.assertRaisesRegex(ChatError, "no model API key"):
            generate_reply([{"role": "user", "content": "hello"}], environ={})

    def test_provider_call_parses_reply_and_uses_secret_header(self):
        seen = {}
        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["headers"] = {k.lower(): v for k, v in request.header_items()}
            seen["body"] = json.loads(request.data.decode())
            return FakeResponse({"content": [{"type": "text", "text": "Hello from NIC"}]})
        result = generate_reply(
            [{"role": "user", "content": "hello"}],
            environ={"ANTHROPIC_API_KEY": "test-secret", "ANTHROPIC_MODEL": "test-model"},
            opener=opener,
        )
        self.assertEqual(result["reply"], "Hello from NIC")
        self.assertEqual(result["model"], "test-model")
        self.assertEqual(seen["url"], "https://api.anthropic.com/v1/messages")
        self.assertEqual(seen["headers"]["x-api-key"], "test-secret")
        self.assertNotIn("test-secret", json.dumps(result))

    def test_empty_provider_response_fails_closed(self):
        with self.assertRaisesRegex(ChatError, "no text response"):
            generate_reply(
                [{"role": "user", "content": "hello"}],
                environ={"ANTHROPIC_API_KEY": "dummy"},
                opener=lambda *args, **kwargs: FakeResponse({"content": []}),
            )


if __name__ == "__main__":
    unittest.main()
