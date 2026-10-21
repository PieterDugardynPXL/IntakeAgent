import json
from pathlib import Path

from models import CaseIntake


def mock_intake(case_id: str) -> CaseIntake:
    # Vaste fixtures maken de sollicitatiedemo herhaalbaar zonder API-kosten.
    examples = json.loads((Path(__file__).parent / 'data' / 'mock_intakes.json').read_text(encoding='utf-8'))
    return CaseIntake.model_validate(examples[case_id])
