import json
import os
from datetime import datetime, timezone
from pathlib import Path

from models import CaseIntake

AUDIT_PATH = Path(__file__).parent / 'audit_log.jsonl'


def append_event(run_id: str, mail: dict, mode: str, ai: CaseIntake,
                 approved: CaseIntake | None = None, path: Path = AUDIT_PATH) -> None:
    # Append-only gebeurtenissen bewaren ook runs die nog op review wachten.
    record = {'timestamp': datetime.now(timezone.utc).isoformat(),
              'run_id': run_id, 'event': 'goedgekeurd' if approved else 'ai_voorstel',
              'case': mail['id'], 'onderwerp': mail['onderwerp'], 'modus': mode,
              'ai_versie': ai.model_dump(mode='json'),
              'goedgekeurde_versie': approved.model_dump(mode='json') if approved else None}
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def field_diff(ai: CaseIntake, approved: CaseIntake) -> list[dict]:
    before, after = ai.model_dump(mode='json'), approved.model_dump(mode='json')
    return [{'veld': key, 'AI-voorstel': before[key], 'Goedgekeurd': after[key]}
            for key in before if before[key] != after[key]]
