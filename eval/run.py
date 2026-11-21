"""Corre cada sistema sobre las consultas y guarda la corrida en disco.

Formato TREC run (qid Q0 doc_id rank score sistema) en eval/runs/. Si la
corrida de un sistema ya existe se saltea, así pool y métricas leen de
disco sin volver a buscar.

Uso:
    python -m eval.run                 # todos los sistemas faltantes
    python -m eval.run --no-rerank     # solo los baratos (sin cross-encoder)
    python -m eval.run --force         # recalcula todo
"""

import re
import sys
import time
from pathlib import Path

from unidecode import unidecode

from eval.systems import SYSTEMS, load_queries

DEPTH = 10
RUNS_DIR = Path("eval/runs")


def run_path(name: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "_", unidecode(name).lower()).strip("_")
    return RUNS_DIR / f"{slug}.tsv"


def load_run(name: str) -> dict[str, list[str]]:
    run: dict[str, list[str]] = {}
    for line in run_path(name).read_text(encoding="utf-8").splitlines():
        qid, _, doc_id, *_ = line.split("\t")
        run.setdefault(qid, []).append(doc_id)
    return run


def main() -> None:
    force = "--force" in sys.argv
    no_rerank = "--no-rerank" in sys.argv
    RUNS_DIR.mkdir(exist_ok=True)
    queries = load_queries()

    for name, fn in SYSTEMS.items():
        path = run_path(name)
        if no_rerank and "rerank" in name:
            continue
        if path.exists() and not force:
            print(f"{name:22} ya existe ({path.name})")
            continue
        t0 = time.time()
        lines = []
        try:
            for q in queries:
                for rank, doc_id in enumerate(fn(q["consulta"], DEPTH), 1):
                    lines.append(f"{q['qid']}\tQ0\t{doc_id}\t{rank}\t{DEPTH - rank + 1}\t{name}")
        except RuntimeError as e:
            print(f"{name:22} salteado: {e}")
            continue
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{name:22} {time.time() - t0:6.1f}s  -> {path.name}")


if __name__ == "__main__":
    main()
