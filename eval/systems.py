"""Configuraciones de recuperación a comparar en la evaluación.

Cada sistema recibe una consulta y devuelve la lista ordenada de ids de
trámite (top `depth`). Reutiliza las funciones de src/api.py para que lo
evaluado sea exactamente lo que sirve la API.
"""

import csv
import json
from pathlib import Path

from elasticsearch import Elasticsearch

from src import api, llm

# La API usa 5s de timeout; en batch las consultas fuzzy largas lo superan.
api.es = Elasticsearch(api.ES_URL, request_timeout=60)

QUERIES_TSV = Path("eval/queries.tsv")


def load_queries() -> list[dict]:
    with open(QUERIES_TSV, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _ids(results: list[dict]) -> list[str]:
    return [r["id"] for r in results]


def bm25_nosyn(q: str, depth: int) -> list[str]:
    return _ids(api.es_search(q, depth, None, None, None, synonyms=False)["results"])


def bm25(q: str, depth: int) -> list[str]:
    return _ids(api.es_search(q, depth, None, None, None)["results"])


def knn(q: str, depth: int) -> list[str]:
    return [h["_source"]["id"] for h in api.knn_search(q, depth, [])]


def hybrid(q: str, depth: int) -> list[str]:
    return _ids(api.hybrid_search(q, depth, None, None, None)["results"])


def bm25_rerank(q: str, depth: int) -> list[str]:
    # Igual que la API con do_rerank: 3x candidatos y reordena.
    cands = api.es_search(q, depth * 3, None, None, None)["results"]
    return _ids(api.rerank(q, cands, depth))


def hybrid_rerank(q: str, depth: int) -> list[str]:
    cands = api.hybrid_search(q, depth * 3, None, None, None)["results"]
    return _ids(api.rerank(q, cands, depth))


REWRITES_JSON = Path("eval/rewrites.json")
_rewrites: dict[str, dict] | None = None


def get_plan(q: str) -> llm.QueryPlan:
    """Reescritura cacheada en disco: el LLM se llama una vez por consulta."""
    global _rewrites
    if _rewrites is None:
        _rewrites = json.loads(REWRITES_JSON.read_text(encoding="utf-8")) \
            if REWRITES_JSON.exists() else {}
    if q not in _rewrites:
        plan = llm.rewrite_query(q)
        if plan is None:
            raise RuntimeError("LLM no disponible (falta ANTHROPIC_API_KEY?)")
        _rewrites[q] = plan.model_dump()
        REWRITES_JSON.write_text(
            json.dumps(_rewrites, ensure_ascii=False, indent=2), encoding="utf-8")
    return llm.QueryPlan(**_rewrites[q])


def rewrite_fused(q: str, depth: int) -> list[str]:
    return _ids(api.rewrite_search(q, depth, get_plan(q))["results"])


def rewrite_only(q: str, depth: int) -> list[str]:
    return _ids(api.rewrite_search(q, depth, get_plan(q), include_original=False)["results"])


SYSTEMS = {
    "BM25 (sin tesauro)": bm25_nosyn,
    "BM25 + tesauro": bm25,
    "kNN (e5-small)": knn,
    "Híbrida (RRF)": hybrid,
    "BM25 + rerank": bm25_rerank,
    "Híbrida + rerank": hybrid_rerank,
    "Reescritura LLM (sola)": rewrite_only,
    "Reescritura LLM + original": rewrite_fused,
}
