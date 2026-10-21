from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Rechtsdomein(str, Enum):
    familierecht = 'familierecht'
    incasso = 'incasso'
    huurrecht = 'huurrecht'
    arbeidsrecht = 'arbeidsrecht'
    ander = 'ander'


class Urgentie(str, Enum):
    laag = 'laag'
    gemiddeld = 'gemiddeld'
    hoog = 'hoog'


class DossierModel(BaseModel):
    # Onbekende velden weigeren voorkomt stil verlies van modeloutput.
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class RelevanteDatum(DossierModel):
    datum: str = Field(min_length=1, description=(
        'Volledige ISO-datum (YYYY-MM-DD) alleen als dag, maand en jaar letterlijk '
        'in de mail staan; anders enkel het vermelde jaartal (YYYY) of onbekend. '
        'Verzin geen ontbrekende datumdelen; vermeld ontbrekende precisie in de toelichting.'
    ))
    type: str = Field(min_length=1)
    toelichting: str


class CaseIntake(DossierModel):
    rechtsdomein: Rechtsdomein
    client_naam: str = Field(min_length=1)
    contactgegevens: str = Field(min_length=1)
    kernfeiten: list[str]
    betrokken_partijen: list[str]
    relevante_datums: list[RelevanteDatum]
    urgentie: Urgentie
    urgentie_motivatie: str = Field(min_length=1)
    risico_vlaggen: list[str]
    voorgestelde_vervolgstappen: list[str]
    openstaande_vragen: list[str]
