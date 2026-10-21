import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from streamlit.proto.TextInput_pb2 import TextInput

from audit import append_event

ROOT = Path(__file__).resolve().parents[1]


class ReviewFlowTests(unittest.TestCase):
    def test_date_warning_helper(self):
        # Laad de helper in een Streamlit-context zonder .env of echte API-aanroep.
        script = f'''
import runpy
import streamlit as st
namespace = runpy.run_path({str(ROOT / 'app.py')!r})
helper = namespace['has_suspicious_january_first']
Datum = namespace['RelevanteDatum']
st.session_state['warning_results'] = [
    helper([Datum(datum=value, type='test', toelichting='Controle')])
    for value in ['2014-01-01', '2014', '2026-09-01', '2014-01-01extra']
]
st.session_state['empty_warning'] = helper([])
'''
        with patch.dict(os.environ, {'MISTRAL_API_KEY': ''}), patch('dotenv.load_dotenv'):
            app = AppTest.from_string(script, default_timeout=30).run()
            self.assertEqual(len(app.exception), 0)
            for value, result, expected in zip(
                ['2014-01-01', '2014', '2026-09-01', '2014-01-01extra'],
                app.session_state['warning_results'], [True, False, False, False]
            ):
                with self.subTest(datum=value):
                    self.assertEqual(result, expected)
            self.assertFalse(app.session_state['empty_warning'])

    def test_date_warning_does_not_block_approval(self):
        from mock_agent import mock_intake
        from models import CaseIntake

        data = mock_intake('FAM-001').model_dump()
        data['relevante_datums'][0]['datum'] = '2014-01-01'
        proposal = CaseIntake.model_validate(data)
        with patch.dict(os.environ, {'MISTRAL_API_KEY': ''}), patch('dotenv.load_dotenv'), patch(
            'agent.process_email', return_value=(proposal, 'mock')
        ), patch('audit.append_event') as audit:
            app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
            app.button[0].click().run()
            self.assertTrue(any('Controleer deze datum' in message.value for message in app.info))
            next(button for button in app.button if button.label == 'Advocaat keurt goed').click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(audit.call_count, 2)
            self.assertEqual(audit.call_args.args[4].relevante_datums[0].datum, '2014-01-01')

    def test_review_edit_approve_and_switch_mail(self):
        # Een echt formuliertraject controleert dat menselijke wijzigingen bewaard blijven.
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            audit_path = Path(temp) / 'audit.jsonl'
            def save(*args):
                append_event(*args, path=audit_path)
            with patch.dict(os.environ, {'MISTRAL_API_KEY': ''}), patch('dotenv.load_dotenv'), patch('audit.append_event', side_effect=save):
                app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
                self.assertEqual(len(app.exception), 0)
                app.button[0].click().run()
                self.assertEqual(len(app.exception), 0)
                next(field for field in app.text_input if field.label == 'Cliëntnaam').set_value('Sofie Peeters — gecontroleerd')
                next(button for button in app.button if button.label == 'Advocaat keurt goed').click().run()
                self.assertEqual(len(app.exception), 0)
                records = [json.loads(line) for line in audit_path.read_text(encoding='utf-8').splitlines()]
                self.assertEqual(len(records), 2)
                self.assertEqual(records[1]['goedgekeurde_versie']['client_naam'], 'Sofie Peeters — gecontroleerd')
                self.assertNotEqual(records[1]['ai_versie']['client_naam'], records[1]['goedgekeurde_versie']['client_naam'])
                app.run()
                self.assertEqual(len(audit_path.read_text(encoding='utf-8').splitlines()), 2)
                app.radio[0].set_value(1).run()
                self.assertFalse(any(field.label == 'Cliëntnaam' for field in app.text_input))
                app.button[0].click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertIn('Jacobs', next(field for field in app.text_input if field.label == 'Cliëntnaam').value)

    def test_session_key_uses_mistral_and_is_not_audited(self):
        from mock_agent import mock_intake

        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            audit_path = Path(temp) / 'audit.jsonl'
            def save(*args):
                append_event(*args, path=audit_path)
            with patch.dict(os.environ, {'MISTRAL_API_KEY': ''}), patch('dotenv.load_dotenv'), patch(
                'audit.append_event', side_effect=save
            ), patch('agent.request_intake', return_value=mock_intake('FAM-001')) as request:
                app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
                field = next(field for field in app.text_input if field.label == 'Mistral API-key')
                self.assertEqual(field.proto.type, TextInput.PASSWORD)
                field.set_value('test-key-only').run()
                app.button[0].click().run()
                self.assertEqual(len(app.exception), 0)
                request.assert_called_once()
                self.assertEqual(request.call_args.args[1], 'test-key-only')
                contents = audit_path.read_text(encoding='utf-8')
                self.assertNotIn('test-key-only', contents)
                self.assertEqual(json.loads(contents)['modus'], 'mistral')


if __name__ == '__main__':
    unittest.main()
