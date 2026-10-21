# Cliëntintake-Agent

Lokale sollicitatiedemo voor een Belgisch advocatenkantoor. Vier fictieve klantmails worden omgezet naar een gestructureerd conceptdossier. Een advocaat kan elk veld aanpassen en de uiteindelijke versie goedkeuren. De app toont vervolgens welke velden zijn gewijzigd.

## Installeren en starten

Python 3.11 of hoger. Voer vanuit deze projectmap uit (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open het lokale adres dat Streamlit toont, doorgaans http://localhost:8501. Activeren van de virtual environment is niet nodig. Op macOS/Linux gebruik je `.venv/bin/python` en `cp .env.example .env`.

## Mock of Mistral

Met een lege of ontbrekende `MISTRAL_API_KEY` werkt de volledige demo zonder netwerk of API-kosten. De sidebar kan mock-modus ook forceren wanneer een key aanwezig is. De output komt dan expliciet uit vaste fixtures, niet uit een LLM.

Voor echte verwerking: vul `MISTRAL_API_KEY` in `.env` in. `MISTRAL_MODEL` is instelbaar (standaard `mistral-small-latest`). Herstart de app na configuratiewijzigingen. De vier dummy-mails worden bij API-gebruik naar Mistral gestuurd. Een API-fout wordt getoond; de app schakelt dan niet ongemerkt over naar mock-output. Mistral-toegang en modelbeschikbaarheid hangen af van je account.

De integratie gebruikt `mistralai` v2, `client.chat.parse` en Pydantic structured output, volgens de [officiële Mistral-documentatie](https://docs.mistral.ai/studio/conversations/structured-output/custom).

## Demonstratie in drie minuten

1. Kies de ontslagmail en klik **Verwerk met AI-agent**.
2. Bekijk de vier stappen: classificatie, extractie, gevalideerde dossieropbouw en vervolgstappen.
3. Wijzig bijvoorbeeld de urgentiemotivatie en voeg een openstaande vraag toe. Alle dossieronderdelen, ook de datumrijen, zijn bewerkbaar.
4. Klik **Advocaat keurt goed**. Bekijk de vergelijking per gewijzigd veld en download het dossier.
5. Open `audit_log.jsonl` om voorstel en goedkeuring terug te vinden met dezelfde run-ID. Een nieuwe verwerking maakt altijd een nieuwe run.

De agent doet één gestructureerde LLM-aanvraag. Het zichtbare verslag beschrijft verifieerbare resultaten van de verwerking, geen interne modelgedachten. In mock-modus is hetzelfde verslag gebaseerd op de fixtures. Juridische termijnen worden niet berekend; de voorbeelden vragen menselijke controle en doen geen definitieve juridische uitspraken.

## Bestanden en audit

- `app.py`: inbox, procesverslag, reviewformulier en vergelijking.
- `models.py`: dossier, enums en datumstructuur.
- `agent.py`: moduskeuze en Mistral-aanroep.
- `mock_agent.py`, `data/mails.json`, `data/mock_intakes.json`: vaste mailvoorbeelden en gevalideerde mock-output.
- `audit.py`: append-only JSONL-gebeurtenissen en veldvergelijking.
- `tests/`: controles van fixtures, audit en de Streamlit-reviewworkflow.

Een succesvolle verwerking schrijft meteen een `ai_voorstel`-regel met UTC-timestamp, case-ID, run-ID, modus, AI-versie en `goedgekeurde_versie: null`. Goedkeuring voegt een tweede regel toe met beide versies. Daardoor blijven ook nog niet goedgekeurde runs zichtbaar. Mislukte verwerkingen leveren geen dossier op en worden niet als succesvolle run gelogd. Een opslagfout verhindert een succesvolle goedkeuringsmelding.

Het auditbestand wordt bij de eerste verwerking aangemaakt naast `app.py`. De reviewstatus zit alleen in de Streamlit-sessie; de app herstelt geen onafgewerkte reviews uit het log. Geen login, database, echte mailintegratie, juridische termijnengine, bewijs van identiteit of manipulatiebestendige auditopslag. De goedkeuringsknop simuleert de menselijke rol in deze lokale demo.

## Controle

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Gebruik uitsluitend fictieve gegevens. `.env`, virtual environment en het gegenereerde auditbestand staan in `.gitignore`.
