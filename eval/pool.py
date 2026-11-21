"""Pooling de candidatos para los juicios de relevancia.

Une el top-`POOL_DEPTH` de las corridas guardadas por eval/run.py
(pooling al estilo TREC) y lo vuelca a eval/pool.tsv para juzgar a mano.
Los documentos que no queden en el pool se asumen no relevantes.

Uso:
    python -m eval.run && python -m eval.pool
"""

import csv
from pathlib import Path

import pandas as pd

from eval.run import load_run, run_path
from eval.systems import SYSTEMS, load_queries

POOL_DEPTH = 10
POOL_TSV = Path("eval/pool.tsv")


def main() -> None:
    df = pd.read_csv("data/tramites.csv", dtype=str, keep_default_na=False)
    docs = df.drop_duplicates("id").set_index("id")
    runs = {name: load_run(name) for name in SYSTEMS if run_path(name).exists()}
    print(f"Corridas: {', '.join(runs)}")

    rows = []
    for q in load_queries():
        seen: dict[str, int] = {}
        for run in runs.values():
            for doc_id in run.get(q["qid"], [])[:POOL_DEPTH]:
                seen[doc_id] = seen.get(doc_id, 0) + 1
        for doc_id, n in seen.items():
            d = docs.loc[doc_id]
            rows.append({
                "qid": q["qid"],
                "consulta": q["consulta"],
                "doc_id": doc_id,
                "nombre": d["nombre_tramite"],
                "organismo": d["institucion_nombre"],
                "n_sistemas": n,
            })

    with open(POOL_TSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} pares consulta-documento en {POOL_TSV}")


if __name__ == "__main__":
    main()
