import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent import process_email
from audit import append_event, field_diff
from models import CaseIntake

ROOT = Path(__file__).resolve().parents[1]


class DemoTests(unittest.TestCase):
    def test_all_mails_without_api_key(self):
        mails = json.loads((ROOT / 'data/mails.json').read_text(encoding='utf-8'))
        self.assertEqual(len(mails), 4)
        with patch.dict(os.environ, {'MISTRAL_API_KEY': ''}):
            for mail in mails:
                steps = []
                case, mode = process_email(mail, on_step=lambda title, detail: steps.append(title))
                self.assertIsInstance(case, CaseIntake)
                self.assertEqual(mode, 'mock')
                self.assertEqual(len(steps), 5)
                self.assertTrue(case.openstaande_vragen)

    def test_force_mock_and_approval_audit(self):
        mail = json.loads((ROOT / 'data/mails.json').read_text(encoding='utf-8'))[0]
        with patch.dict(os.environ, {'MISTRAL_API_KEY': 'not-a-real-key'}):
            ai, mode = process_email(mail, force_mock=True)
        approved = CaseIntake.model_validate({**ai.model_dump(), 'client_naam': 'Sofie Peeters (nagekeken)'})
        self.assertEqual([c['veld'] for c in field_diff(ai, approved)], ['client_naam'])
        self.assertEqual(field_diff(ai, ai), [])
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            path = Path(temp) / 'audit_log.jsonl'
            append_event('run-1', mail, mode, ai, path=path)
            append_event('run-1', mail, mode, ai, approved, path=path)
            records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(records), 2)
            self.assertIsNone(records[0]['goedgekeurde_versie'])
            self.assertEqual(records[1]['goedgekeurde_versie']['client_naam'], approved.client_naam)
            self.assertEqual(records[0]['ai_versie'], records[1]['ai_versie'])


if __name__ == '__main__':
    unittest.main()
