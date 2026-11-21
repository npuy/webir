"""Cliente LLM (Claude) para reescritura de consultas y respuestas RAG.

Reescritura: la pregunta del usuario se transforma en 1-3 consultas con
el vocabulario oficial del catálogo, más filtros explícitos (canal,
gratuito). Generación: redacta la respuesta a partir de los trámites
recuperados.

Credenciales: ANTHROPIC_API_KEY (variable de entorno o archivo .env).
Modelo: LLM_MODEL (por defecto claude-opus-5-5). Si no hay credenciales
o la llamada falla, las funciones devuelven None y la API usa su
fallback (Ollama / respuesta extractiva).
"""

import os
from typing import Literal

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

MODEL = os.getenv("LLM_MODEL", "claude-opus-5-5")
# Reintenta en otro modelo si el clasificador de seguridad rechaza.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic | None:
    global _client
    if _client is None and os.getenv("ANTHROPIC_API_KEY"):
        _client = anthropic.Anthropic(timeout=60.0)
    return _client


def available() -> bool:
    return get_client() is not None


# ------------------------------------------------------------- reescritura

class QueryPlan(BaseModel):
    consultas: list[str] = Field(
        description="1 a 3 consultas de búsqueda cortas con el vocabulario "
                    "oficial del catálogo de trámites.")
    canal: Literal["internet", "persona", "telefono"] | None = Field(
        description="Canal de atención sólo si el usuario lo pide explícitamente.")
    gratuito: bool | None = Field(
        description="true sólo si el usuario pide explícitamente trámites gratuitos.")


REWRITE_SYSTEM = """Convertís preguntas de ciudadanos uruguayos en consultas \
para un buscador sobre el catálogo oficial de trámites del Estado (gub.uy).

El catálogo usa nombres formales, por ejemplo: "Documento Nacional de \
Identidad - Renovación" (cédula), "Subsidio por desempleo por despido" \
(seguro de paro), "Inscripción de nacimiento", "Solicitud de jubilación", \
"Certificado de antecedentes judiciales" (buena conducta), "Carné de salud", \
"Libreta de conducir primera vez", "Apostilla y/o legalización de documentos".

Reglas:
- Devolvé de 1 a 3 consultas cortas (2 a 6 palabras), como títulos de \
trámites del catálogo, sin palabras de relleno ("quiero", "cómo", "necesito").
- La primera consulta es la interpretación más probable; las demás cubren \
otras interpretaciones o trámites complementarios.
- Corregí errores de tipeo.
- Si el usuario menciona un departamento (Florida, Maldonado...), incluilo \
en la consulta.
- Siglas de organismos (BPS, DGI, MIDES, UTE) se mantienen.
- canal y gratuito sólo si el usuario los pide explícitamente; si no, null."""


def rewrite_query(question: str) -> QueryPlan | None:
    client = get_client()
    if client is None:
        return None
    try:
        response = client.beta.messages.parse(
            model=MODEL,
            max_tokens=2000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            output_config={"effort": "low"},
            system=REWRITE_SYSTEM,
            messages=[{"role": "user", "content": question}],
            output_format=QueryPlan,
        )
    except anthropic.APIError:
        return None
    if response.stop_reason == "refusal" or response.parsed_output is None:
        return None
    plan = response.parsed_output
    plan.consultas = [c.strip() for c in plan.consultas if c.strip()][:3]
    return plan if plan.consultas else None


# --------------------------------------------------------------- generación

def generate(prompt: str) -> str | None:
    client = get_client()
    if client is None:
        return None
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError:
        return None
    if response.stop_reason == "refusal":
        return None
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    return text or None
