import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from mistralai.client import Mistral

from agent import AgentError, configured_mode, process_email
from mock_agent import mock_intake

ROOT = Path(__file__).resolve().parents[1]


class MistralTests(unittest.TestCase):
    def setUp(self):
        self.mail = json.loads((ROOT / 'data/mails.json').read_text(encoding='utf-8'))[0]
        self.case = mock_intake(self.mail['id'])

    def run_request(self, handler):
        # De echte SDK voert JSON-opbouw en parsing uit; HTTP blijft volledig lokaal.
        client = httpx.Client(transport=httpx.MockTransport(handler))
        with patch.dict(os.environ, {'MISTRAL_API_KEY': ''}), patch(
            'mistralai.client.Mistral', side_effect=lambda **kwargs: Mistral(**kwargs, client=client)
        ):
            return process_email(self.mail, api_key='test-key-only', model='test-model')

    def test_sdk_request_and_pydantic_response(self):
        requests = []

        def handler(request):
            requests.append(request)
            self.assertEqual(request.method, 'POST')
            self.assertEqual(request.url.path, '/v1/chat/completions')
            self.assertEqual(request.headers['authorization'], 'Bearer test-key-only')
            body = json.loads(request.content)
            self.assertEqual(body['model'], 'test-model')
            self.assertEqual(json.loads(body['messages'][1]['content']), self.mail)
            self.assertEqual(body['response_format']['type'], 'json_schema')
            return httpx.Response(200, json={
                'id': 'test-completion', 'object': 'chat.completion', 'created': 0,
                'model': 'test-model',
                'choices': [{'index': 0, 'message': {'role': 'assistant',
                    'content': self.case.model_dump_json()}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20},
            })

        case, mode = self.run_request(handler)
        self.assertEqual(mode, 'mistral')
        self.assertEqual(case, self.case)
        self.assertEqual(len(requests), 1)

    def test_invalid_key_is_safe_error_without_mock_fallback(self):
        with self.assertRaises(AgentError) as caught:
            self.run_request(lambda request: httpx.Response(401, json={
                'message': 'do not expose test-key-only', 'type': 'unauthorized'}))
        self.assertIn('geweigerd', str(caught.exception))
        self.assertNotIn('test-key-only', str(caught.exception))

    def test_timeout_is_safe_error(self):
        def timeout(request):
            raise httpx.ReadTimeout('do not expose test-key-only', request=request)
        with self.assertRaisesRegex(AgentError, '60 seconden'):
            self.run_request(timeout)

    def test_session_key_and_force_mock(self):
        with patch.dict(os.environ, {'MISTRAL_API_KEY': ''}):
            self.assertEqual(configured_mode(api_key='test-key-only'), 'mistral')
            with patch('agent.request_intake') as request:
                case, mode = process_email(self.mail, force_mock=True, api_key='test-key-only')
                request.assert_not_called()
                self.assertEqual(mode, 'mock')
                self.assertEqual(case, self.case)


if __name__ == '__main__':
    unittest.main()
