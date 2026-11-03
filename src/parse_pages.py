"""Parsea el HTML cacheado en data/pages/ y enriquece el CSV.

Lo que recupera de cada página de gub.uy:

- `tiene_costo`: el CSV lo tiene vacío para 59% de los trámites,
  ambiguando "gratuito" con "sin dato". La página lo resuelve:
  <h4>Costos</h4> seguido de <p>No tiene costo</p> o de una lista <ul>.
- `costo_items`: los <li> de la sección Costos (montos en texto).
- `canales`: tabs `data-canal` (internet/presencial/telefono).

Genera data/tramites_enriquecido.csv: igual al original más las columnas
`tiene_costo` corregida ("si" | "no" | ""), `costo_texto` y canales
completados cuando estaban vacíos.

Uso:
    python -m src.parse_pages
"""

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd

DATA_CSV = Path("data/tramites.csv")
PAGES_DIR = Path("data/pages")
OUT_CSV = Path("data/tramites_enriquecido.csv")

CANAL_MAP = {"internet": "internet", "presencial": "persona", "telefono": "telefono"}
WS = re.compile(r"\s+")


class TramitePage(HTMLParser):
    """State machine sobre el markup semántico de la ficha de trámite."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.heading = None        # tag de heading abierto (h2-h4) o None
        self.hbuf = []             # texto del heading
        self.section = None        # 'costos' | 'requisitos' | None
        self.capture = None        # tag de texto abierto dentro de la sección
        self.buf = []
        self.costo_items = []
        self.canales = set()

    def handle_starttag(self, tag, attrs):
        if tag in ("h2", "h3", "h4"):
            self.heading, self.hbuf = tag, []
            self.section = None
        elif self.section == "costos" and tag in ("li", "p"):
            self.capture, self.buf = tag, []
        canal = dict(attrs).get("data-canal")
        if canal in CANAL_MAP:
            self.canales.add(CANAL_MAP[canal])

    def handle_endtag(self, tag):
        if tag == self.heading:
            title = WS.sub(" ", " ".join(self.hbuf)).strip().lower()
            self.section = "costos" if title == "costos" else None
            self.heading = None
        elif tag == self.capture:
            text = WS.sub(" ", " ".join(self.buf)).strip()
            if text:
                self.costo_items.append(text)
            self.capture = None

    def handle_data(self, data):
        if self.heading:
            self.hbuf.append(data)
        elif self.capture:
            self.buf.append(data)


def parse_file(path: Path) -> dict:
    p = TramitePage()
    html = path.read_text(encoding="utf-8", errors="replace")
    p.feed(html)
    items = p.costo_items
    # "No tiene costo" suele venir como <p> único dentro de la sección.
    if len(items) == 1 and re.fullmatch(
            r"(no tiene costo|gratuito|sin costo)\.?", items[0], re.I):
        estado, items = "no", []
    elif items:
        estado = "si"
    else:
        estado = ""
    # Página índice de casos (selector de casuística, sin ficha propia):
    # tiene la lista de variantes pero ninguna sección de contenido.
    es_cas = "si" if ("Tramite-pre--casuistica" in html and estado == "") else ""
    return {
        "scrape_costo": estado,
        "costo_texto": " | ".join(items),
        "scrape_canales": ",".join(sorted(p.canales)),
        "es_casuistica": es_cas,
    }


def main() -> None:
    only_check = "--check" in sys.argv
    df = pd.read_csv(DATA_CSV, dtype=str, keep_default_na=False)
    slug = df["url"].str.strip().str.rstrip("/").str.rsplit("/", n=1).str[-1]

    rows, missing = [], []
    for s in slug:
        f = PAGES_DIR / f"{s}.html"
        if f.exists():
            rows.append(parse_file(f))
        else:
            missing.append(s)
            rows.append({"scrape_costo": "", "costo_texto": "",
                         "scrape_canales": "", "es_casuistica": ""})
    scraped = pd.DataFrame(rows)
    out = pd.concat([df.reset_index(drop=True), scraped], axis=1)

    # tiene_costo: "si"/"no" de la web; cae al CSV si la página no lo tiene
    out["tiene_costo"] = out["scrape_costo"].where(out["scrape_costo"] != "", out["tiene_costo"])
    out["tiene_costo"] = out["tiene_costo"].replace({"1": "si", "": ""})
    # otros_costos vacío + lista scrapeada -> costo_texto queda como respaldo
    # canales vacíos -> usar los del scrape
    faltan = out["canales_de_atencion"].str.strip() == ""
    out.loc[faltan, "canales_de_atencion"] = out.loc[faltan, "scrape_canales"]

    print(f"parseadas {len(df) - len(missing)}/{len(df)} páginas (faltan {len(missing)})")
    print("\ntiene_costo enriquecido:", out["tiene_costo"].value_counts().to_dict())
    print("costo_texto recuperado donde CSV no tenía valor:",
          ((out["costo_texto"] != "") & (df["valor"] == "")).sum())
    print("canales completados:", (faltan & (out["canales_de_atencion"] != "")).sum())
    print("páginas índice de casuística:", (out["es_casuistica"] == "si").sum())

    if not only_check:
        out.drop(columns=["scrape_costo", "scrape_canales"]).to_csv(OUT_CSV, index=False)
        print(f"\n-> {OUT_CSV}")


if __name__ == "__main__":
    main()
