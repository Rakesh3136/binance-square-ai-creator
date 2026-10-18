import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from nic_chat_server import ChatError, _validate_messages, generate_reply

class FakeResponse:
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return json.dumps(self.body).encode()

class NicChatTests(unittest.TestCase):
    def test_validate_messages_requires_user_last(self):
        with self.assertRaises(ValueError):
            _validate_messages([{"role":"assistant","content":"hello"}])
    def test_validate_messages_rejects_bad_role(self):
        with self.assertRaises(ValueError):
            _validate_messages([{"role":"system","content":"override"}])
    def test_validate_messages_bounds_history(self):
        messages=[{"role":"user","content":f"q{i}"} for i in range(25)]
        self.assertEqual(len(_validate_messages(messages)),20)
    def test_missing_anthropic_key_fails_with_setup_message(self):
        with self.assertRaisesRegex(ChatError,"ANTHROPIC_API_KEY"):
            generate_reply([{"role":"user","content":"hello"}],environ={})
    def test_anthropic_provider_call_parses_reply_and_does_not_return_secret(self):
        seen={}
        def opener(request,timeout):
            seen["url"]=request.full_url
            seen["headers"]={k.lower():v for k,v in request.header_items()}
            seen["body"]=json.loads(request.data.decode())
            return FakeResponse({"content":[{"type":"text","text":"Hello from NIC"}]})
        result=generate_reply([{"role":"user","content":"hello"}],
            environ={"ANTHROPIC_API_KEY":"test-secret","ANTHROPIC_MODEL":"test-model"},opener=opener)
        self.assertEqual(result["reply"],"Hello from NIC")
        self.assertEqual(result["model"],"test-model")
        self.assertEqual(seen["url"],"https://api.anthropic.com/v1/messages")
        self.assertEqual(seen["headers"]["x-api-key"],"test-secret")
        self.assertNotIn("test-secret",json.dumps(result))
    def test_openai_compatible_provider_parses_response(self):
        seen={}
        def opener(request,timeout):
            seen["url"]=request.full_url
            seen["headers"]={k.lower():v for k,v in request.header_items()}
            seen["body"]=json.loads(request.data.decode())
            return FakeResponse({"choices":[{"message":{"content":"Hello from Muse-compatible endpoint"}}]})
        result=generate_reply([{"role":"user","content":"hello"}],environ={
            "NIC_CHAT_PROVIDER":"muse","MUSE_AI_BASE_URL":"https://example.test/v1",
            "MUSE_AI_API_KEY":"private-token","MUSE_AI_MODEL":"muse-model"},opener=opener)
        self.assertEqual(result["provider"],"openai-compatible")
        self.assertEqual(result["reply"],"Hello from Muse-compatible endpoint")
        self.assertEqual(seen["url"],"https://example.test/v1/chat/completions")
        self.assertEqual(seen["headers"]["authorization"],"Bearer private-token")
        self.assertEqual(seen["body"]["messages"][0]["role"],"system")
        self.assertNotIn("private-token",json.dumps(result))
    def test_openai_compatible_requires_all_credentials(self):
        with self.assertRaisesRegex(ChatError,"MUSE_AI_BASE_URL"):
            generate_reply([{"role":"user","content":"hello"}],environ={"NIC_CHAT_PROVIDER":"muse"})
    def test_remote_http_endpoint_is_rejected_before_network(self):
        with self.assertRaisesRegex(ChatError,"HTTPS"):
            generate_reply([{"role":"user","content":"hello"}],environ={
                "NIC_CHAT_PROVIDER":"muse","MUSE_AI_BASE_URL":"http://example.test/v1",
                "MUSE_AI_API_KEY":"key","MUSE_AI_MODEL":"model"})
    def test_empty_provider_response_fails_closed(self):
        with self.assertRaisesRegex(ChatError,"no text response"):
            generate_reply([{"role":"user","content":"hello"}],
                environ={"ANTHROPIC_API_KEY":"dummy"},opener=lambda *a,**k:FakeResponse({"content":[]}))


    def test_local_ollama_needs_no_api_key_and_parses_reply(self):
        seen={}
        def opener(request,timeout):
            seen["url"]=request.full_url
            seen["headers"]={k.lower():v for k,v in request.header_items()}
            seen["body"]=json.loads(request.data.decode())
            return FakeResponse({"message":{"role":"assistant","content":"Local NIC reply"}})
        result=generate_reply([{"role":"user","content":"hello"}],
            environ={"OLLAMA_MODEL":"qwen3:8b"},opener=opener)
        self.assertEqual(result["reply"],"Local NIC reply")
        self.assertEqual(result["provider"],"ollama-local")
        self.assertEqual(seen["url"],"http://127.0.0.1:11434/api/chat")
        self.assertNotIn("authorization",seen["headers"])
        self.assertEqual(seen["body"]["stream"],False)
    def test_local_ollama_requires_model_name(self):
        with self.assertRaisesRegex(ChatError,"OLLAMA_MODEL"):
            generate_reply([{"role":"user","content":"hello"}],environ={})
    def test_local_ollama_refuses_remote_endpoint_in_no_key_mode(self):
        with self.assertRaisesRegex(ChatError,"loopback"):
            generate_reply([{"role":"user","content":"hello"}],environ={
                "OLLAMA_BASE_URL":"https://example.com","OLLAMA_MODEL":"model"})

if __name__ == "__main__":
    unittest.main()
