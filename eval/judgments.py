"""Juicios de relevancia graduados sobre el pool (eval/pool.tsv).

Escala:
    2  el trámite resuelve directamente la necesidad de la consulta
       (incluye variantes por departamento o por tipo de persona).
    1  relacionado y útil: paso previo/posterior, variante cercana,
       o resuelve la necesidad sólo para un caso particular.
    0  no relevante (todo lo del pool que no figura acá).

Las páginas índice de casuística (es_casuistica = "si" en el catálogo
enriquecido) sólo derivan a sub-trámites sin requisitos ni costos
propios: su grado se limita a 1 aunque el tema coincida.

Los juicios fueron generados con asistencia de un LLM leyendo nombre y
organismo de cada candidato. Los documentos fuera del pool no están
juzgados y se asumen no relevantes.

Uso:
    python -m eval.judgments          # escribe eval/qrels.tsv
"""

import csv
from pathlib import Path

import pandas as pd

from src.catalog import catalog_csv

POOL_TSV = Path("eval/pool.tsv")
QRELS_TSV = Path("eval/qrels.tsv")

PASAPORTE = {
    **dict.fromkeys(["606", "606-1", "606-2", "606-3", "606-4",
                     "6889", "6889-1", "6889-2", "6889-3", "6889-4"], 2),
    "4678": 1, "3978": 1,
}
JUBILACION = {
    "7458": 2,
    **dict.fromkeys(["7352", "7342", "7356", "7441", "7442", "7344",
                     "7343", "7547", "7438", "7434", "3868"], 1),
}
ANTECEDENTES = {"307": 2, "5654": 2}

JUDGMENTS: dict[str, dict[str, int]] = {
    # ---- exacta
    "q01": PASAPORTE,
    "q02": ANTECEDENTES,
    "q03": {"118": 2, "6439": 1, "4857": 1, "6656": 1, "4074": 1},
    "q04": {"3582": 2, "7339": 2, "3581": 2, "1430": 1, "7433": 1, "7421": 1},
    "q05": {
        **dict.fromkeys(["4622", "6233", "6233-1", "6233-2", "6191-1",
                         "6701", "6699"], 2),
        **dict.fromkeys(["5089", "231-1", "5165", "6266", "3885", "5026-1"], 1),
    },
    "q06": {"584": 2, "481": 1, "480": 1},
    # ---- coloquial
    "q07": {
        **dict.fromkeys(["6538", "6538-1", "6538-2", "6538-4", "6538-5", "6538-6", "6538-7",
                         "6538-8", "6538-9"], 2),
        **dict.fromkeys(["4678", "5167", "5167-1", "5167-2", "5167-3",
                         "607", "607-1", "607-7", "2123", "5800"], 1),
    },
    "q08": {
        **dict.fromkeys(["4293", "6404", "6410", "6410-1", "6410-3", "6410-4",
                         "6410-5", "6410-7", "4824", "6221", "6404-1", "6404-2", "6531",
                         "4824-1"], 2),
        **dict.fromkeys(["4694", "6407", "6411", "6411-1", "6411-2", "6411-3",
                         "6411-4", "6411-5", "6411-7", "4828", "6219", "4827",
                         "6434", "4372", "4826", "5565", "6533", "5566", "3459", "6407-1",
                         "6407-2", "6407-3", "6411-6", "6222", "6481"], 1),
    },
    "q09": {"1835": 2, "4756": 2, "6224": 2},
    "q10": ANTECEDENTES,
    "q11": {"3587": 2, "7462": 2, "7390": 1, "2314": 1, "7369": 1, "7621": 1},
    "q12": {
        **dict.fromkeys(["4594", "6232", "6502", "6703", "6191-2"], 2),
        **dict.fromkeys(["5168", "6282", "6700", "4595", "6236", "6697",
                         "5026-1", "5165", "6266"], 1),
    },
    "q13": {
        **dict.fromkeys(["2020", "7638", "7640", "7639", "7642", "7643",
                         "2088", "7645"], 2),
        **dict.fromkeys(["2090", "2079", "7514", "7508"], 1),
    },
    "q14": {"1441": 2, "2642": 1, "1968": 1, "4527": 1, "1920": 1},
    # ---- sigla / organismo
    "q15": JUBILACION,
    "q16": {
        **dict.fromkeys(["7637", "7648", "7649", "7650", "2090", "2115"], 2),
        **dict.fromkeys(["7651", "7653", "7654", "7656", "7761", "7781",
                         "7762", "7782", "2614", "5297"], 1),
    },
    "q17": {"7359": 2, "4650": 2, "2603": 2, "4677": 1, "4647": 1},
    "q18": {"4748": 2, "1409": 2, "1417": 2},
    # ---- error de tipeo
    "q19": {**PASAPORTE, "7888": 1},
    "q20": JUBILACION,
    "q21": {"1441": 2, "1968": 1, "4527": 1},
    "q22": {
        **dict.fromkeys(["5165", "6266", "231-1", "5026-1", "4771", "6700"], 2),
        **dict.fromkeys(["6907", "5026", "5089", "4622", "6191-1", "6233",
                         "6233-1", "6233-2", "6701"], 1),
    },
    "q23": {
        **dict.fromkeys(["6538", "6538-1", "6538-7", "6538-8", "6538-9", "607",
                         "607-1", "607-2", "607-3", "607-5", "607-7", "607-8",
                         "6538-2", "6538-6"], 2),
        **dict.fromkeys(["2123", "5800", "5167", "5167-1", "5167-2", "5167-3",
                         "6271", "7888"], 1),
    },
    # ---- pregunta en lenguaje natural
    "q24": {"7462": 2, "3587": 2, "7428": 1, "276": 1, "2314": 1, "7369": 1,
            "7390": 1, "7621": 1},
    "q25": {
        **dict.fromkeys(["261", "261-1", "261-2"], 2),
        **dict.fromkeys(["261-3", "261-4", "261-5", "261-6", "261-7",
                         "261-10", "261-11", "261-12", "617"], 1),
    },
    "q26": {"4695": 2},
    "q27": {
        **dict.fromkeys(["4622", "6233", "6233-1", "6701"], 2),
        **dict.fromkeys(["6233-2", "4593", "6239"], 1),
    },
    "q28": {"3440": 2, "6063": 1},
    "q29": {
        "7458": 2,
        **dict.fromkeys(["7352", "7343", "7547", "7442", "7344", "7434",
                         "7438", "7898", "7899", "3868"], 1),
    },
    "q30": {**ANTECEDENTES, "2555": 1},
    "q31": {
        **dict.fromkeys(["6538", "6538-1", "6538-2", "6538-6", "6538-7",
                         "6538-8", "6538-9"], 2),
        **dict.fromkeys(["607", "607-1", "607-7", "607-8", "2123", "4678", "5167", "5167-2"], 1),
    },
    "q32": {
        "585": 2,
        **dict.fromkeys(["6537", "2599", "2599-1", "2599-2", "2599-3",
                         "2599-5", "7104"], 1),
    },
    "q33": {"233": 2, "2291": 2, "276": 1, "7559": 1, "7588": 1, "7408": 1},
    "q34": {
        "1827": 2,
        **dict.fromkeys(["231-4", "6283", "5169", "6700", "7383", "5026-2", "4591",
                         "6191-3", "6234", "6698"], 1),
    },
    "q35": {"159": 2, "7695": 1},
    "q36": {"6293": 2, "6272": 2},
}


def main() -> None:
    with open(POOL_TSV, encoding="utf-8") as f:
        pool = [(r["qid"], r["doc_id"]) for r in csv.DictReader(f, delimiter="\t")]

    catalog = pd.read_csv(catalog_csv(), dtype=str, keep_default_na=False)
    casuistica = set()
    if "es_casuistica" in catalog.columns:
        casuistica = set(catalog.loc[catalog["es_casuistica"] == "si", "id"])

    pairs = {(qid, doc_id): 0 for qid, doc_id in pool}
    # Relevantes conocidos fuera del pool también se incluyen.
    for qid, rels in JUDGMENTS.items():
        for doc_id, rel in rels.items():
            pairs[(qid, doc_id)] = min(rel, 1) if doc_id in casuistica else rel

    lines = [f"{qid}\t0\t{doc_id}\t{rel}" for (qid, doc_id), rel in sorted(pairs.items())]
    QRELS_TSV.write_text("\n".join(lines) + "\n", encoding="utf-8")

    n_rel = sum(1 for r in pairs.values() if r > 0)
    print(f"{len(pairs)} juicios ({n_rel} relevantes) en {QRELS_TSV}")
    missing = {q for q, _ in pool} - JUDGMENTS.keys()
    if missing:
        print(f"Consultas sin juicios: {sorted(missing)}")


if __name__ == "__main__":
    main()
