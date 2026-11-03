"""Helpers compartidos para leer el catálogo de trámites.

Si existe data/tramites_enriquecido.csv (generado por src/parse_pages.py
a partir del scrape de gub.uy) se usa ese — tiene tiene_costo resuelto
("si" | "no" | "") en vez del "1"/"" ambiguo del export original,
`costo_texto` con los montos itemizados y canales completados.
"""

from pathlib import Path

DATA_CSV = Path("data/tramites.csv")
ENRICHED_CSV = Path("data/tramites_enriquecido.csv")


def catalog_csv() -> Path:
    return ENRICHED_CSV if ENRICHED_CSV.exists() else DATA_CSV


def doc_key(row) -> str:
    """Clave única y estable del documento: el slug de la URL.

    `id` tiene 4 duplicados en el CSV; `url` es única.
    """
    return row["url"].rstrip("/").rsplit("/", 1)[-1]


def costo_flags(row) -> tuple[bool, bool]:
    """(tiene_costo, costo_desconocido).

    Acepta ambos formatos: 'si'/'1' = con costo, 'no' = confirmado gratis,
    '' = desconocido (el CSV original mezclaba gratis y desconocido).
    """
    tc = str(row.get("tiene_costo", ""))
    return tc in ("si", "1"), tc not in ("si", "1", "no")
