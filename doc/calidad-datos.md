# Calidad de datos y enriquecimiento por scraping

Análisis de calidad del Catálogo de trámites y servicios del Estado
(AGESIC / catalogodatos.gub.uy, `data/tramites.csv`, 3.505 registros ×
31 columnas) y enriquecimiento automático scrapeando las fichas
originales de gub.uy.

## 1. Auditoría inicial

### Completitud

Los datos mínimos (`nombre_tramite`, `ques_es`, `institucion_*`, `url`)
están completos al 100%. El resto presenta vacíos importantes:

| Columna | % vacío | | Columna | % vacío |
|---|---|---|---|---|
| telefono_requisitos | 98.7 | | internet_como_se_hace | 41.5 |
| casuistica | 98.5 | | internet_url_del_tramite | 41.5 |
| telefono_como_se_hace | 94.2 | | mas_informacion_vinculos | 41.1 |
| persona_direcciones_listado | 90.3 | | otros_datos_de_interes | 40.5 |
| **valor** | **80.2** | | persona_como_se_hace | 34.2 |
| mas_informacion_adjuntos | 74.2 | | requisitos_generales | 10.9 |
| otros_costos | 66.0 | | email_de_consulta | 10.9 |
| internet_requisitos | 63.4 | | canales_de_atencion | 1.5 |
| categorias_de_organismo | 62.4 | | | |
| **tiene_costo / unidad** | **59.1** | | | |

### Problemas de consistencia detectados

1. **`tiene_costo` ambiguo.** Solo vale `"1"` (1.432 casos) o está vacío
   (2.073 = 59,1%): no existe `"0"`. El vacío mezcla *gratuito* con
   *sin dato*, y el buscador trataba todo vacío como gratuito — el
   filtro "solo gratuitos" devolvía 2.073 trámites con costo realmente
   desconocido.
2. **Montos sin estructurar.** De los 1.432 trámites con costo, 739
   (51,6%) tienen `unidad = "Sin definir"` y `valor` vacío: el monto
   está enterrado en texto libre en `otros_costos`
   ("Trámite común: 1,50 UR equivalentes hoy a $ 1.265").
3. **IDs duplicados.** 4 `id` repetidos (p. ej. `7907-1` ×3). Al usar
   `id` como `_id` de Elasticsearch, el bulk **sobrescribía
   documentos**: el índice quedaba con menos docs que el CSV.
4. **Inconsistencia de canales.** 222 trámites declaran canal
   "internet" pero no tienen `internet_como_se_hace`; 54 tienen
   `canales_de_atencion` vacío.
5. **Páginas índice disfrazadas de trámites.** 54 registros son
   páginas padre de casuística ("Permiso para menor de edad" lista 12
   sub-casos): no tienen costo ni canales propios, pero rankeaban alto
   por nombre genérico.
6. **Frescura.** 1.480 trámites (42%) sin actualizar hace >1 año.
7. **Menores:** 1 entidad HTML sin escapar (`&amp;amp`), 2 nombres en
   mayúsculas, 19 con doble espacio, formatos de `valor` mixtos (punto
   decimal vs separador de miles en texto).
8. **Cobertura desigual por organismo.** BPS: 341 trámites, 0% con
   costo informado, 2% con instrucciones online; en contraste
   División Recaudación: 92% y 100%.

## 2. Enriquecimiento por scraping

El CSV es un export que **pierde información presente en la fuente**:
la ficha web de cada trámite distingue "No tiene costo" de "sin dato"
y muestra los costos itemizados. Como cada registro trae su `url` de
gub.uy, el enriquecimiento es un crawl dirigido, no exploratorio.

### Pipeline

```bash
python -m src.scrape_pages            # descarga a data/pages/{slug}.html
python -m src.parse_pages             # -> data/tramites_enriquecido.csv
```

- **`src/scrape_pages.py`**: crawl cortés (~2-4 workers, delay entre
  requests, User-Agent identificable, reintentos con backoff, cache en
  disco → resumible). `robots.txt` de gub.uy no bloquea `/tramites/`.
  Las páginas son HTML server-side (Drupal): no requiere JS ni login.
- **`src/parse_pages.py`**: state machine con `HTMLParser` (stdlib, sin
  dependencias nuevas) sobre el markup semántico de la ficha:
  - `<h4>Costos</h4>` → `<p>No tiene costo</p>` = gratuito confirmado;
    `<ul><li>…</li></ul>` = costos itemizados.
  - `data-canal="internet|presencial|telefono"` en los tabs = canales.
  - Presencia de `ul.Tramite-pre--casuistica` sin sección de contenido
    = página índice de casos.

### Cobertura del crawl

3.496 de 3.505 páginas (99,7%) en ~23 min. Fallaron 9:

- 4 URLs devuelven **404** — trámites dados de baja en la web que el
  CSV aún lista (dato de calidad adicional).
- 5 devuelven **403** (bloqueo del lado del servidor, también para
  navegador).
- 337 respuestas venían comprimidas sin `Content-Encoding` correcto;
  se detectó por magic bytes gzip y se descomprimieron.

## 3. Resultados: antes vs después

| Métrica | `tramites.csv` | `tramites_enriquecido.csv` |
|---|---|---|
| Estado de costo resuelto | 40,9% (1.432) | **88,7%** (3.108) |
| Ambiguos "gratis o desconocido" | 2.073 (59,1%) | 397 (11,3%) |
| Gratuitos **confirmados** | indistinguibles | **1.677** |
| Con costo sin monto legible | 739 de 1.432 | **1** de 1.431 |
| Registros con monto (valor o texto) | 693 | **1.430** |
| Páginas índice de casuística | no detectadas | 54 marcadas |
| Docs en Elasticsearch | 3.502 (dupes pisaban) | **3.505** |

Los 397 que siguen desconocidos: 54 casuística (por diseño, el dato
vive en los hijos), 6 no descargables y **337 páginas que
genuinamente no publican sección Costos** — límite de la fuente, no
del método. Además el scrape resolvió 1 discrepancia: un trámite
marcado `"1"` en el CSV que la web lista como gratuito (la web está
más fresca que el export).

## 4. Cambios aplicados al sistema

- **`src/catalog.py`** (nuevo): `catalog_csv()` prefiere el CSV
  enriquecido; `doc_key()` usa el slug de URL como `_id` (elimina los
  duplicados); `costo_flags()` centraliza el tri-estado.
- **`tiene_costo` tri-estado** (`si`/`no`/desconocido): el filtro
  `gratuito=true` ahora excluye desconocidos. Antes: devolvía 2.073
  ambiguos; ahora devuelve solo los 1.677 confirmados.
- **`costo_texto`** indexado y expuesto: el badge de resultados muestra
  el monto itemizado cuando no hay `valor`/`unidad` estructurados.
- **Badge tri-estado** en la UI: *Con costo* / *Gratuito* /
  *Costo no informado*.
- **Páginas de casuística demoradas** (`boosting` ×0,15 en ES, mismo
  factor en BM25 local) con badge "Página de casos": dejaban de tapar
  a los trámites reales (p. ej. el top-2 de "pasaporte").

## 5. Reproducir el índice completo

```bash
python -m src.scrape_pages          # ~23 min, una sola vez (cache)
python -m src.parse_pages           # data/tramites_enriquecido.csv
python -m src.index                 # BM25 local (fallback)
python -m src.es_index --recreate   # reindex ES con el nuevo mapping
python -m src.embeddings            # vectores para búsqueda híbrida
```

## 6. Limitaciones y trabajo futuro

- ~337 trámites no publican sección Costos en la web: única vía de
  mejora es la fuente (AGESIC) o inferencia heurística.
- `costo_texto` queda en texto libre itemizado; un segundo paso podría
  extraer montos numéricos (`$`, `UR`, `UI`) a campos estructurados
  para filtrar/ordenar por precio.
- Las 54 páginas padre de casuística podrían enlazarse con sus hijos
  (las URLs están en el HTML) para heredar metadatos o mejorar la
  navegación.
- Otros campos ~40-60% vacíos del CSV (`requisitos` por canal,
  `como_se_hace`, `direcciones`) también existen en el HTML — el
  parser ya tiene la máquina de estados, es cuestión de agregar
  secciones.
