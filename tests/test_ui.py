import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from audit import append_event

ROOT = Path(__file__).resolve().parents[1]


class ReviewFlowTests(unittest.TestCase):
    def test_review_edit_approve_and_switch_mail(self):
        # Een echt formuliertraject controleert dat menselijke wijzigingen bewaard blijven.
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            audit_path = Path(temp) / 'audit.jsonl'
            def save(*args):
                append_event(*args, path=audit_path)
            with patch.dict(os.environ, {'MISTRAL_API_KEY': ''}), patch('audit.append_event', side_effect=save):
                app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
                self.assertEqual(len(app.exception), 0)
                app.button[0].click().run()
                self.assertEqual(len(app.exception), 0)
                app.text_input[0].set_value('Sofie Peeters — gecontroleerd')
                next(button for button in app.button if button.label == 'Advocaat keurt goed').click().run()
                self.assertEqual(len(app.exception), 0)
                records = [json.loads(line) for line in audit_path.read_text(encoding='utf-8').splitlines()]
                self.assertEqual(len(records), 2)
                self.assertEqual(records[1]['goedgekeurde_versie']['client_naam'], 'Sofie Peeters — gecontroleerd')
                self.assertNotEqual(records[1]['ai_versie']['client_naam'], records[1]['goedgekeurde_versie']['client_naam'])
                app.run()
                self.assertEqual(len(audit_path.read_text(encoding='utf-8').splitlines()), 2)
                app.radio[0].set_value(1).run()
                self.assertEqual(len(app.text_input), 0)
                app.button[0].click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertIn('Jacobs', app.text_input[0].value)


if __name__ == '__main__':
    unittest.main()
