"""Métricas de evaluación sobre las corridas guardadas.

Calcula con ir_measures nDCG@10, P@5, MRR (RR@10), R@10 y Judged@10 por
sistema, el desglose de nDCG@10 por categoría de consulta y un t-test
pareado de nDCG@10 contra la línea base (BM25 sin tesauro). Escribe la
tabla en eval/results.md.

Uso:
    python -m eval.run && python -m eval.judgments && python -m eval.evaluate
"""

from pathlib import Path

import ir_measures
from ir_measures import Judged, P, R, RR, nDCG
from scipy.stats import ttest_rel

from eval.run import load_run, run_path
from eval.systems import SYSTEMS, load_queries

QRELS_TSV = Path("eval/qrels.tsv")
RESULTS_MD = Path("eval/results.md")
BASELINE = "BM25 (sin tesauro)"
MEASURES = [nDCG @ 10, P @ 5, RR @ 10, R @ 10, Judged @ 10]
MAIN = nDCG @ 10


def load_qrels() -> list:
    qrels = []
    for line in QRELS_TSV.read_text(encoding="utf-8").splitlines():
        qid, _, doc_id, rel = line.split("\t")
        qrels.append(ir_measures.Qrel(qid, doc_id, int(rel)))
    return qrels


def to_scored(run: dict[str, list[str]]) -> list:
    return [
        ir_measures.ScoredDoc(qid, doc_id, float(len(docs) - i))
        for qid, docs in run.items()
        for i, doc_id in enumerate(docs)
    ]


def main() -> None:
    qrels = load_qrels()
    queries = load_queries()
    categories = sorted({q["categoria"] for q in queries})
    qid_cat = {q["qid"]: q["categoria"] for q in queries}

    agg: dict[str, dict] = {}
    per_query: dict[str, dict[str, float]] = {}
    for name in SYSTEMS:
        if not run_path(name).exists():
            continue
        run = to_scored(load_run(name))
        agg[name] = ir_measures.calc_aggregate(MEASURES, qrels, run)
        per_query[name] = {
            m.query_id: m.value
            for m in ir_measures.iter_calc([MAIN], qrels, run)
        }

    qids = [q["qid"] for q in queries]
    base = [per_query[BASELINE].get(q, 0.0) for q in qids]

    out = ["## Resultados globales (36 consultas)", "",
           "| Sistema | nDCG@10 | P@5 | MRR | R@10 | Judged@10 | p (vs base) |",
           "|---|---|---|---|---|---|---|"]
    for name, m in agg.items():
        vals = [per_query[name].get(q, 0.0) for q in qids]
        p = "—" if name == BASELINE else f"{ttest_rel(vals, base).pvalue:.3f}"
        out.append(
            f"| {name} | {m[nDCG@10]:.3f} | {m[P@5]:.3f} | {m[RR@10]:.3f} "
            f"| {m[R@10]:.3f} | {m[Judged@10]:.2f} | {p} |")

    out += ["", "## nDCG@10 por categoría de consulta", "",
            "| Sistema | " + " | ".join(categories) + " |",
            "|---|" + "---|" * len(categories)]
    for name in agg:
        cells = []
        for cat in categories:
            vals = [v for q, v in per_query[name].items() if qid_cat[q] == cat]
            cells.append(f"{sum(vals) / len(vals):.3f}")
        out.append(f"| {name} | " + " | ".join(cells) + " |")

    out += ["", "## nDCG@10 por consulta", "",
            "| qid | consulta | " + " | ".join(agg) + " |",
            "|---|---|" + "---|" * len(agg)]
    for q in queries:
        cells = [f"{per_query[n].get(q['qid'], 0.0):.2f}" for n in agg]
        out.append(f"| {q['qid']} | {q['consulta']} | " + " | ".join(cells) + " |")

    text = "\n".join(out) + "\n"
    RESULTS_MD.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
