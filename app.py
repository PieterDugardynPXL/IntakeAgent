import json
from pathlib import Path
from uuid import uuid4

import streamlit as st
from dotenv import load_dotenv
from pydantic import ValidationError

from agent import configured_mode, process_email
from audit import append_event, field_diff
from models import CaseIntake, Rechtsdomein, Urgentie

ROOT = Path(__file__).parent
load_dotenv(ROOT / '.env')
st.set_page_config(page_title='Cliëntintake-Agent', page_icon='⚖️', layout='wide')
st.markdown('''<style>
.stApp {background-color: #f5f6f8;}
h1,h2,h3 {color: #172d45;}
.stButton>button[kind="primary"] {background: #173c54; border-color: #173c54;}
div[data-testid="stMetric"] {background: white; padding: 16px; border-radius: 8px;}
</style>''', unsafe_allow_html=True)
st.caption('ADVOCATUUR · INTAKE & DOSSIERVOORBEREIDING')
st.title('Cliëntintake-Agent')
st.write('Van klantmail naar controleerbaar conceptdossier, met goedkeuring door een advocaat.')
st.info('Sollicitatiedemo met fictieve gegevens. De advocaat beoordeelt feiten, juridische risico’s en vervolgstappen.')

mails = json.loads((ROOT / 'data' / 'mails.json').read_text(encoding='utf-8'))
with st.sidebar:
    st.header('Demo-instellingen')
    force_mock = st.toggle('Mock-modus forceren', value=False)
    mode = configured_mode(force_mock)
    st.success('MOCK · geen API-aanroep' if mode == 'mock' else 'MISTRAL · API actief')
    st.caption('Zonder API-key schakelt de demo automatisch naar vaste voorbeeldoutput.')
    st.divider()
    st.write('**Werkwijze**')
    st.write('1. Selecteer een mail\n2. Verwerk het bericht\n3. Controleer en bewerk\n4. Keur goed en bekijk de diff')
    st.caption('Auditbestand: audit_log.jsonl · tijdstempels in UTC')

left, right = st.columns([1, 2], gap='large')
with left:
    st.subheader('01 · Inbox')
    selected = st.radio('Kies een klantmail', range(len(mails)),
                        format_func=lambda i: f"{mails[i]['id']} · {mails[i]['onderwerp']}")
    mail = mails[selected]
    st.caption(f"Van: {mail['afzender']}  |  Ontvangen: {mail['ontvangen']}")
    st.text(mail['tekst'])

with right:
    st.subheader('02 · Agentverwerking')
    if st.button('Verwerk met AI-agent', type='primary', width='stretch'):
        steps = []
        # Oude review blijft niet gekoppeld aan een nieuwe verwerking.
        st.session_state.pop('run', None)
        try:
            with st.status('Agent verwerkt de klantmail…', expanded=True) as status:
                def report(title, detail):
                    steps.append((title, detail))
                    st.markdown(f'**{title}**')
                    st.text(detail)
                ai, used_mode = process_email(mail, force_mock, report)
                run_id = str(uuid4())
                append_event(run_id, mail, used_mode, ai)
                st.session_state.run = dict(id=run_id, case_id=mail['id'], ai=ai,
                                            mode=used_mode, steps=steps, approved=None)
                status.update(label='Conceptdossier klaar voor menselijke review', state='complete')
        except Exception:
            # Toon geen ruwe API-fout met mogelijk gevoelige requestgegevens.
            st.error('Verwerking of opslag mislukt. Controleer API-key, model, netwerk en schrijfrechten. Kies eventueel mock-modus en probeer opnieuw.')

    run = st.session_state.get('run')
    if run and run['case_id'] != mail['id']:
        st.info('Deze mail is nog niet verwerkt. Klik op “Verwerk met AI-agent”.')
        run = None
    if run:
        st.caption(f"Run {run['id']} · bron: {run['mode']}")
        with st.expander('Verwerkingsverslag bekijken'):
            for title, detail in run['steps']:
                st.markdown(f'**{title}**')
                st.text(detail)
        if run['approved'] is None:
            st.subheader('03 · Review door advocaat')
            ai = run['ai']
            st.caption('Controleer alle velden. Lijsten: één item per regel. Datums: voeg rijen toe of verwijder ze.')
            # Een unieke form-key voorkomt vermenging van verschillende runs.
            with st.form(f"review_{run['id']}"):
                domain = st.selectbox('Rechtsdomein', [x.value for x in Rechtsdomein], index=list(Rechtsdomein).index(ai.rechtsdomein))
                name = st.text_input('Cliëntnaam', ai.client_naam)
                contact = st.text_area('Contactgegevens', ai.contactgegevens)
                values = {}
                for field, label in [('kernfeiten','Kernfeiten'), ('betrokken_partijen','Betrokken partijen')]:
                    values[field] = st.text_area(label, '\n'.join(getattr(ai, field)), height=130)
                dates = st.data_editor([d.model_dump() for d in ai.relevante_datums], num_rows='dynamic',
                                       column_order=['datum','type','toelichting'],
                                       column_config={k: st.column_config.TextColumn(k.capitalize(), required=True) for k in ['datum','type','toelichting']},
                                       width='stretch', key=f"dates_{run['id']}")
                urgency = st.selectbox('Urgentie', [x.value for x in Urgentie], index=list(Urgentie).index(ai.urgentie))
                motivation = st.text_area('Motivatie urgentie', ai.urgentie_motivatie)
                for field, label in [('risico_vlaggen','Risicovlaggen'), ('voorgestelde_vervolgstappen','Voorgestelde vervolgstappen'), ('openstaande_vragen','Openstaande vragen')]:
                    values[field] = st.text_area(label, '\n'.join(getattr(ai, field)), height=130)
                submitted = st.form_submit_button('Advocaat keurt goed', type='primary', width='stretch')
            if submitted:
                try:
                    approved = CaseIntake(rechtsdomein=domain, client_naam=name,
                        contactgegevens=contact, relevante_datums=dates,
                        urgentie=urgency, urgentie_motivatie=motivation,
                        **{k: [line.strip() for line in v.splitlines() if line.strip()] for k,v in values.items()})
                    # Pas na duurzame opslag tonen we goedkeuring als geslaagd.
                    append_event(run['id'], mail, run['mode'], ai, approved)
                    run['approved'] = approved
                    st.rerun()
                except ValidationError as exc:
                    st.error('Controleer de verplichte velden en datumrijen. De goedkeuring is niet opgeslagen.')
                    st.json(exc.errors(include_url=False, include_context=False))
                except OSError:
                    st.error('Audit-log kon niet worden opgeslagen. Controleer schrijfrechten en probeer opnieuw; het dossier is nog niet goedgekeurd.')
        else:
            st.subheader('03 · Goedgekeurd dossier')
            st.success('De advocaat heeft deze versie goedgekeurd. De goedkeuring is opgeslagen in het audit-log.')
            changes = field_diff(run['ai'], run['approved'])
            st.markdown('**Menselijke wijzigingen**')
            if not changes:
                st.info('Geen wijzigingen: het AI-voorstel is ongewijzigd goedgekeurd.')
            for change in changes:
                with st.expander(change['veld'].replace('_',' ').capitalize(), expanded=True):
                    before, after = st.columns(2)
                    before.write('**AI-voorstel**')
                    before.write(change['AI-voorstel'])
                    after.write('**Goedgekeurd**')
                    after.write(change['Goedgekeurd'])
            with st.expander('Volledig goedgekeurd dossier'):
                st.json(run['approved'].model_dump(mode='json'))
            st.download_button('Download goedgekeurd dossier',
                               run['approved'].model_dump_json(indent=2),
                               file_name=f"{mail['id']}_goedgekeurd.json", mime='application/json')
