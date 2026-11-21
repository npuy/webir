"""API de búsqueda de trámites.

Backend principal: Elasticsearch (BM25 + analyzer español + facetas +
highlighting + kNN para búsqueda semántica). Si ES no está disponible,
cae al índice BM25 local (data/index.pkl) construido por src/index.py.

Endpoints:
    GET  /api/search  búsqueda BM25 | híbrida (RRF) | +rerank
    POST /api/chat    respuesta RAG con Ollama (fallback extractivo)

Uso:
    uvicorn src.api:app --reload --port 8000
"""

import json
import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path

from elasticsearch import Elasticsearch
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src import llm

ES_URL = "http://localhost:9200"
ES_INDEX = "tramites"
LOCAL_INDEX = Path("data/index.pkl")
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"
RRF_K = 60  # constante de Reciprocal Rank Fusion

es = Elasticsearch(ES_URL, request_timeout=5)
local_index = None
_cross_encoder = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global local_index
    app.state.backend = "elasticsearch" if es.ping() else "bm25"
    if app.state.backend == "bm25":
        if not LOCAL_INDEX.exists():
            raise RuntimeError(
                "Sin backend: Elasticsearch no responde y no existe "
                f"{LOCAL_INDEX}. Corré `python -m src.index` o levantá ES."
            )
        from src.index import load_index

        local_index = load_index()
    yield


app = FastAPI(title="Trámites UY — API de búsqueda", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- Elasticsearch

SEARCH_FIELDS = [
    "nombre_tramite^3",
    "ques_es^2",
    "casuistica",
    "requisitos_generales",
    "otros_datos_de_interes",
    "institucion_nombre",
    "institucion_padre_organizacional_nombre",
    "categorias_de_organismo",
]


def _filters(organismo: str | None, canal: str | None,
             gratuito: bool | None) -> list[dict]:
    filters = []
    if organismo:
        filters.append({"term": {"institucion_padre_organizacional_nombre.keyword": organismo}})
    if canal:
        filters.append({"term": {"canales_de_atencion": canal}})
    if gratuito is not None:
        filters.append({"term": {"tiene_costo": not gratuito}})
        if gratuito:
            # los trámites sin dato de costo no son "gratuitos"
            filters.append({"term": {"costo_desconocido": False}})
    return filters


def _hit_to_result(h: dict, score: float | None = None) -> dict:
    src = h["_source"]
    return {
        "id": src["id"],
        "es_casuistica": src.get("es_casuistica", False),
        "nombre": src["nombre_tramite"],
        "organismo": src["institucion_nombre"],
        "organismo_padre": src["institucion_padre_organizacional_nombre"],
        "descripcion": src["ques_es"],
        "highlight": (h.get("highlight", {}).get("ques_es") or [None])[0],
        "tiene_costo": src["tiene_costo"],
        "costo_desconocido": src.get("costo_desconocido", False),
        "costo": f"{src.get('valor', '')} {src.get('unidad', '')}".strip()
                if src.get("valor", "").strip() else "",
        "costo_texto": src.get("costo_texto", ""),
        "otros_costos": src.get("otros_costos", ""),
        "canales": src["canales_de_atencion"],
        "url": src["url"],
        "url_tramite": src.get("internet_url_del_tramite", ""),
        "score": round(score if score is not None else h["_score"], 4),
    }


def _demote_casuistica(query: dict) -> dict:
    """Envuelve la consulta demorando las páginas índice de casuística.

    Son listas de sub-casos, no trámites: suman ruido arriba del ranking
    por tener nombres genéricos ("Solicitud de pasaporte - Renovación").
    """
    return {
        "boosting": {
            "positive": query,
            "negative": {"term": {"es_casuistica": True}},
            "negative_boost": 0.15,
        }
    }


def _bm25_body(q: str, size: int, filters: list[dict],
               synonyms: bool = True,
               post_filter: list[dict] | None = None) -> dict:
    """multi_match ponderado + highlighting + facetas.

    Consulta vacía = todo el catálogo (para navegar sólo con filtros).
    synonyms=False fuerza el analyzer sin tesauro (para evaluar su aporte).
    post_filter filtra los hits pero no las facetas, así la lista de
    organismos no se reduce al elegido.
    """
    body: dict = {
        "size": size,
        "aggs": {
            "organismos": {
                "terms": {"field": "institucion_padre_organizacional_nombre.keyword", "size": 80}
            },
            "canales": {"terms": {"field": "canales_de_atencion", "size": 5}},
        },
    }
    if q.strip():
        multi_match = {
            "query": q,
            "fields": SEARCH_FIELDS,
            "type": "best_fields",
            "operator": "or",
            "fuzziness": "AUTO",
            "prefix_length": 2,
        }
        if not synonyms:
            multi_match["analyzer"] = "spanish_custom"
        body["query"] = {"bool": {
            "must": _demote_casuistica({"multi_match": multi_match}),
            "filter": filters,
        }}
        body["highlight"] = {
            "fields": {"ques_es": {"fragment_size": 200, "number_of_fragments": 1}},
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
        }
    else:
        body["query"] = {"bool": {"must": {"match_all": {}}, "filter": filters}}
    if post_filter:
        body["post_filter"] = {"bool": {"filter": post_filter}}
    return body


# Las intendencias figuran como organismo padre con el nombre del
# departamento en mayúsculas ("FLORIDA", "SAN JOSE").
DEPARTAMENTOS = {
    "ARTIGAS", "CANELONES", "CERRO LARGO", "COLONIA", "DURAZNO", "FLORES",
    "FLORIDA", "LAVALLEJA", "MALDONADO", "MONTEVIDEO", "PAYSANDU",
    "RIO NEGRO", "RIVERA", "ROCHA", "SALTO", "SAN JOSE", "SORIANO",
    "TACUAREMBO", "TREINTA Y TRES",
}


def _facets(aggs: dict) -> dict:
    buckets = [
        {"value": b["key"], "count": b["doc_count"]}
        for b in aggs.get("organismos", {}).get("buckets", [])
        if b["key"].strip()
    ]
    return {
        "departamentos": [b for b in buckets if b["value"] in DEPARTAMENTOS],
        "organismos": [b for b in buckets if b["value"] not in DEPARTAMENTOS],
        "canales": [
            {"value": b["key"], "count": b["doc_count"]}
            for b in aggs.get("canales", {}).get("buckets", [])
        ],
    }


def es_search(q: str, top_k: int, organismo: str | None, canal: str | None,
              gratuito: bool | None, synonyms: bool = True) -> dict:
    body = _bm25_body(q, top_k, _filters(None, canal, gratuito), synonyms,
                      post_filter=_filters(organismo, None, None))
    res = es.search(index=ES_INDEX, body=body)
    return {
        "backend": "elasticsearch",
        "total": res["hits"]["total"]["value"],
        "results": [_hit_to_result(h) for h in res["hits"]["hits"]],
        "facets": _facets(res.get("aggregations", {})),
    }


# ------------------------------------------------- búsqueda híbrida (BM25+kNN)

def knn_search(q: str, top_k: int, filters: list[dict]) -> list[dict]:
    """Búsqueda semántica: kNN sobre el campo embedding."""
    from src.embeddings import embed_query

    knn: dict = {
        "field": "embedding",
        "query_vector": embed_query(q),
        "k": top_k,
        "num_candidates": top_k * 10,
    }
    if filters:
        knn["filter"] = filters
    res = es.search(index=ES_INDEX, body={"knn": knn, "size": top_k})
    return res["hits"]["hits"]


def rrf_fuse(rankings: list[list[dict]], k: int = RRF_K,
             key: str = "_id") -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: score(d) = Σ 1/(k + rank(d))."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, 1):
            scores[hit[key]] = scores.get(hit[key], 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def hybrid_search(q: str, top_k: int, organismo: str | None,
                  canal: str | None, gratuito: bool | None,
                  synonyms: bool = True) -> dict:
    """BM25 + kNN fusionados con RRF."""
    base = _filters(None, canal, gratuito)
    org = _filters(organismo, None, None)
    fetch_k = top_k * 5

    bm25_res = es.search(index=ES_INDEX, body=_bm25_body(
        q, fetch_k, base, synonyms, post_filter=org))
    bm25_hits = bm25_res["hits"]["hits"]
    knn_hits = knn_search(q, fetch_k, base + org)

    fused = rrf_fuse([bm25_hits, knn_hits])
    by_id = {h["_id"]: h for h in bm25_hits + knn_hits}

    hits = [
        _hit_to_result(by_id[doc_id], score)
        for doc_id, score in fused[:top_k]
        if doc_id in by_id
    ]

    return {
        "backend": "hybrid",
        "total": bm25_res["hits"]["total"]["value"],
        "results": hits,
        "facets": _facets(bm25_res.get("aggregations", {})),
    }


# ---------------------------------------------- reescritura de consultas (LLM)

def rewrite_search(q: str, top_k: int, plan: "llm.QueryPlan",
                   include_original: bool = True) -> dict:
    """Búsqueda híbrida por cada consulta reescrita, fusionadas con RRF.

    La consulta original se incluye en la fusión para no depender sólo
    de la reescritura (si el LLM se equivoca, la original sigue aportando).
    """
    queries = ([q] if include_original else []) + plan.consultas
    searches = [
        hybrid_search(qq, top_k, None, plan.canal, plan.gratuito)
        for qq in queries
    ]
    rankings = [s["results"] for s in searches]
    by_id = {r["id"]: r for ranking in rankings for r in ranking}
    results = [
        {**by_id[doc_id], "score": round(score, 4)}
        for doc_id, score in rrf_fuse(rankings, key="id")[:top_k]
    ]
    return {
        **searches[0],
        "backend": "hybrid+rewrite",
        "results": results,
        "consultas": plan.consultas,
    }


# ------------------------------------------------------- rerank (cross-encoder)

def get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder

        _cross_encoder = CrossEncoder("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
    return _cross_encoder


def rerank(q: str, results: list[dict], top_k: int) -> list[dict]:
    """Re-ordena resultados con un cross-encoder (two-stage retrieval)."""
    if not results:
        return results
    ce = get_cross_encoder()
    pairs = [(q, f"{r['nombre']} {r['descripcion']}") for r in results]
    scores = ce.predict(pairs)
    for r, s in zip(results, scores):
        r["score"] = round(float(s), 4)
    return sorted(results, key=lambda r: r["score"], reverse=True)[:top_k]


# ------------------------------------------------------------------ BM25 local

def bm25_search(q: str, top_k: int, organismo: str | None, canal: str | None,
                gratuito: bool | None) -> dict:
    from src.search import search

    results = search(local_index, q, top_k=top_k * 4)
    for doc in results:  # mismo demote que en ES: índices de casos abajo
        if doc.get("es_casuistica") == "si":
            doc["score"] *= 0.15
    results.sort(key=lambda d: d["score"], reverse=True)
    hits = []
    for doc in results:
        canales = [c.strip() for c in doc.get("canales_de_atencion", "").split(",") if c.strip()]
        if organismo and doc["institucion_padre_organizacional_nombre"] != organismo:
            continue
        if canal and canal not in canales:
            continue
        tc = doc.get("tiene_costo", "")
        tiene_costo = tc in ("si", "1")
        desconocido = tc not in ("si", "1", "no")
        if gratuito is not None:
            es_gratis = not tiene_costo and not desconocido
            if (gratuito and not es_gratis) or (not gratuito and not tiene_costo):
                continue
        hits.append({
            "id": doc["id"],
            "es_casuistica": doc.get("es_casuistica") == "si",
            "nombre": doc["nombre_tramite"],
            "organismo": doc["institucion_nombre"],
            "organismo_padre": doc["institucion_padre_organizacional_nombre"],
            "descripcion": doc["ques_es"],
            "highlight": None,
            "tiene_costo": tiene_costo,
            "costo_desconocido": desconocido,
            "costo": f"{doc.get('valor', '')} {doc.get('unidad', '')}".strip()
                    if doc.get("valor", "").strip() else "",
            "costo_texto": doc.get("costo_texto", ""),
            "otros_costos": doc.get("otros_costos", ""),
            "canales": canales,
            "url": doc["url"],
            "url_tramite": doc.get("internet_url_del_tramite", ""),
            "score": doc["score"],
        })
        if len(hits) >= top_k:
            break
    return {
        "backend": "bm25",
        "total": len(hits),
        "results": hits,
        "facets": {"departamentos": [], "organismos": [], "canales": []},
    }


# ------------------------------------------------------------------- endpoints

@app.get("/api/health")
def health():
    return {"status": "ok", "backend": app.state.backend,
            "llm": llm.MODEL if llm.available() else None}


@app.get("/api/search")
def search_endpoint(
    q: str = "",
    top_k: int = Query(10, ge=0, le=50),
    organismo: str | None = None,
    canal: str | None = None,
    gratuito: bool | None = None,
    hybrid: bool = False,
    do_rerank: bool = False,
):
    if not q.strip():
        # Sin texto: navegar el catálogo por filtros (y obtener facetas).
        do_rerank = False
    if app.state.backend == "elasticsearch":
        if not q.strip():
            data = es_search("", top_k, organismo, canal, gratuito)
        elif hybrid:
            data = hybrid_search(q, top_k if not do_rerank else top_k * 3,
                                 organismo, canal, gratuito)
        else:
            data = es_search(q, top_k if not do_rerank else top_k * 3,
                             organismo, canal, gratuito)
    else:
        data = bm25_search(q, top_k, organismo, canal, gratuito)
    if do_rerank:
        data["results"] = rerank(q, data["results"], top_k)
        data["backend"] += "+rerank"
    return data


# ------------------------------------------------------------------ chat (RAG)

class ChatRequest(BaseModel):
    message: str
    top_k: int = 5


PROMPT_TEMPLATE = """Sos el asistente de un buscador de trámites del Estado \
uruguayo. Tu texto se muestra como respuesta única a una búsqueda: no es \
una conversación y el usuario no puede contestarte.

PASO 1 — Evaluá: ¿alguno de los trámites listados responde DIRECTAMENTE \
lo que pregunta el usuario? Ojo: que un trámite mencione el tema no \
significa que responda la pregunta.

PASO 2 — Respondé según el caso:
- Si hay un trámite que responde directamente: explicá qué es, qué \
necesita y cómo se hace.
- Si NO hay ninguno que responda directamente: empezá tu respuesta con \
"No encontré un trámite específico para eso en el catálogo" y después \
mencioná los trámites relacionados aclarando que son opciones \
relacionadas, NO requisitos.
- Si la respuesta depende de la situación del usuario (destino, edad, \
etc.), indicá qué trámite corresponde en cada caso.
- NUNCA uses conocimiento externo ni afirmes que algo es obligatorio si \
el documento no lo dice explícitamente.

Formato (Markdown):
- Citá cada trámite como enlace a su URL: [Nombre del trámite](URL) \
(organismo). No repitas la URL suelta.
- Terminá con la información del último trámite: sin preguntas al \
usuario, sin ofrecer más ayuda y sin pedirle más datos.

Trámites recuperados (pueden no ser relevantes):
{context}

Pregunta del usuario: {question}

Respuesta:"""


def _build_context(results: list[dict]) -> str:
    blocks = []
    for i, r in enumerate(results, 1):
        blocks.append(
            f"[{i}] {r['nombre']} ({r['organismo']})\n"
            f"    {r['descripcion'][:400]}\n"
            f"    Costo: {r['costo'] or 'no informado'} | "
            f"Canales: {', '.join(r['canales'])} | URL: {r['url']}"
        )
    return "\n\n".join(blocks)


def _ollama_generate(prompt: str) -> str | None:
    """Llama a Ollama local. None si no está disponible."""
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 400},
    }).encode()
    try:
        req = urllib.request.Request(
            OLLAMA_URL, data=payload,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())["response"].strip()
    except Exception:
        return None


@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    """RAG: reescribe la pregunta con el LLM, recupera trámites y genera
    la respuesta (Claude → Ollama local → extractiva)."""
    plan = llm.rewrite_query(req.message)
    if app.state.backend == "elasticsearch":
        try:
            if plan:
                data = rewrite_search(req.message, req.top_k, plan)
            else:
                data = hybrid_search(req.message, req.top_k, None, None, None)
        except Exception:
            data = es_search(req.message, req.top_k, None, None, None)
    else:
        data = bm25_search(req.message, req.top_k, None, None, None)

    results = data["results"]
    consultas = data.get("consultas", [])
    sources = [
        {"nombre": r["nombre"], "organismo": r["organismo"], "url": r["url"]}
        for r in results
    ]
    if not results:
        return {
            "answer": "No encontré trámites relacionados con tu consulta.",
            "sources": [],
            "consultas": consultas,
            "generated": False,
        }

    prompt = PROMPT_TEMPLATE.format(
        context=_build_context(results), question=req.message)
    answer = llm.generate(prompt) or _ollama_generate(prompt)
    generated = answer is not None

    if answer is None:
        # Fallback extractivo: descripción del mejor resultado.
        top = results[0]
        answer = (
            f"El trámite más relacionado es **[{top['nombre']}]({top['url']})** "
            f"({top['organismo']}). {top['descripcion'][:300]} "
            f"Revisá las fuentes para más opciones. "
            f"(Respuesta extractiva — LLM no disponible)"
        )
    return {"answer": answer, "sources": sources, "consultas": consultas,
            "generated": generated}
