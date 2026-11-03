"""Descarga las páginas de trámites de gub.uy a data/pages/.

El CSV de AGESIC pierde datos que sí están en la web (p. ej. distingue
"sin costo" de "sin dato"). Este crawler baja cada `url` del catálogo
una sola vez y cachea el HTML en disco — el parseo se hace aparte con
src/parse_pages.py, así se puede iterar el parser sin re-scrapear.

Uso:
    python -m src.scrape_pages --sample 20   # prueba con 20 trámites
    python -m src.scrape_pages               # crawl completo (resumible)
"""

import gzip
import ssl
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import certifi
import pandas as pd

DATA_CSV = Path("data/tramites.csv")
PAGES_DIR = Path("data/pages")
UA = "webir-ri/1.0 (proyecto academico de recuperacion de informacion; contacto: estudiante udelaR)"
TIMEOUT = 30
DELAY = 0.4  # seg entre requests por worker — crawl cortés, ~5 req/s max
RETRIES = 3
# el Python del venv no ve el keychain de macOS: usar el bundle de certifi
SSL_CTX = ssl.create_default_context(cafile=certifi.where())


def url_slug(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def fetch(url: str, dest: Path) -> str:
    if dest.exists() and dest.stat().st_size > 1000:
        return "cache"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=SSL_CTX) as r:
                body = r.read()
                if r.headers.get("Content-Encoding") == "gzip" or body[:2] == b"\x1f\x8b":
                    body = gzip.decompress(body)
                dest.write_bytes(body)
            time.sleep(DELAY)
            return "ok"
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return f"http_{e.code}"
            time.sleep(2 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(2 * (attempt + 1))
    return "error"


def main() -> None:
    sample = 0
    workers = 2
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--sample":
            sample = int(args[i + 1])
        elif a == "--workers":
            workers = int(args[i + 1])

    df = pd.read_csv(DATA_CSV, dtype=str, keep_default_na=False)
    urls = df["url"].str.strip()
    urls = urls[urls != ""].drop_duplicates().tolist()
    if sample:
        urls = urls[:sample]
    PAGES_DIR.mkdir(parents=True, exist_ok=True)

    todo = [u for u in urls if not (PAGES_DIR / f"{url_slug(u)}.html").exists()]
    print(f"{len(urls)} urls, {len(urls) - len(todo)} ya en cache, {len(todo)} a bajar")

    t0 = time.time()
    stats = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(fetch, u, PAGES_DIR / f"{url_slug(u)}.html"): u for u in todo}
        for i, fut in enumerate(futures.items()):
            fu, url = fut
            status = fu.result()
            stats[status] = stats.get(status, 0) + 1
            if status not in ("ok", "cache") or (i + 1) % 100 == 0:
                print(f"[{i + 1}/{len(todo)}] {status:8} {url_slug(url)}")

    print(f"\nListo en {time.time() - t0:.0f}s — {stats}")
    fallos = {s: c for s, c in stats.items() if s not in ("ok", "cache")}
    if fallos:
        print(f"ATENCION: {fallos} — re-correr el script reintenta solo los que faltan")


if __name__ == "__main__":
    main()
