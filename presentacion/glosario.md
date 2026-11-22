# Glosario de la presentación

Términos que aparecen en las slides o en el guion, explicados en simple y con ejemplos de nuestro proyecto. Están agrupados por tema; dentro de cada tema, en el orden en que aparecen en la presentación.

**Índice rápido:** [BM25](#bm25) · [nDCG](#ndcg10) · [Reciprocal Rank Fusion](#reciprocal-rank-fusion-rrf) · [Reranking](#reranking) · [Tesauro](#tesauro)

---

## 1. Problema y conceptos generales

### Recuperación de información (RI)
Disciplina que estudia cómo encontrar, dentro de una colección grande de documentos, los que responden a una necesidad de información expresada en una **consulta**. Un buscador es un sistema de RI. En nuestro caso, los documentos son los 3.505 trámites del catálogo y las consultas son lo que escribe el ciudadano.

### Vocabulary mismatch (diferencia de vocabulario)
Ocurre cuando el usuario y el documento usan palabras distintas para lo mismo. Es el problema central del proyecto.
> El usuario escribe "seguro de paro", pero el trámite se llama "Subsidio por desempleo por despido". No comparten ninguna palabra importante, así que un buscador por palabras clave no lo encuentra.

### Keyword matching (búsqueda por palabras clave)
Buscar documentos que contengan las mismas palabras que la consulta. Es lo que hace BM25 y, en esencia, el buscador actual de gub.uy. Funciona bien con nombres exactos y siglas, pero falla con sinónimos, lenguaje coloquial y errores de tipeo.

### Lenguaje natural vs. coloquial vs. exacto
Son las categorías de consultas que usamos al evaluar:
- **Exacta:** casi el nombre oficial ("solicitud de pasaporte").
- **Coloquial:** cómo se le dice en la calle ("seguro de paro", "renovar cedula").
- **Natural:** una frase o pregunta completa ("me quedé sin trabajo, qué puedo cobrar").
- **Tipeo:** con errores de escritura ("pasaprote", "cedla de identidad").
- **Sigla:** nombra al organismo por su sigla ("BPS jubilación", "UTE exoneración").

---

## 2. Datos e indexación

### Datos abiertos / catálogo de AGESIC
AGESIC (la agencia de gobierno electrónico de Uruguay) publica en catalogodatos.gub.uy un CSV con todos los trámites del Estado: nombre, descripción, organismo, requisitos, costo, canales, URL, etc. Es nuestro corpus.

### Corpus
El conjunto completo de documentos sobre el que se busca. Para nosotros, los 3.505 trámites.

### Scraping / crawler
Programa que descarga páginas web de forma automática. Lo usamos para bajar la ficha de cada trámite en gub.uy y completar datos que el CSV no tenía bien (como el costo). Es "cortés" porque espera entre pedidos para no sobrecargar el sitio, y guarda las páginas en disco (caché) para no descargarlas dos veces.

### Parser
Programa que lee un texto con estructura (acá, el HTML de la ficha) y extrae los datos que interesan: si tiene costo, los montos, los canales de atención.

### Casuística (páginas de)
Algunas fichas de gub.uy son sólo índices que derivan a sub-trámites ("según tu caso, mirá este o aquel trámite") y no tienen requisitos ni costos propios. Las marcamos y las bajamos en el ranking, porque casi nunca son la respuesta final.

### Índice / indexar
Indexar es procesar los documentos y guardarlos en una estructura que permita buscar rápido. Como el índice al final de un libro: para cada palabra, en qué documentos aparece. Nosotros indexamos en **Elasticsearch**.

### Elasticsearch
Motor de búsqueda open source. Guarda el índice, calcula BM25, permite filtros y facetas, resalta las palabras encontradas y también puede buscar por vectores (kNN). Lo levantamos con Docker.

### Analyzer (analizador)
La cadena de pasos que transforma un texto antes de indexarlo o buscarlo, para que coincidan variantes de la misma palabra. El nuestro, para español, hace:
1. **Minúsculas:** "Cédula" → "cédula".
2. **Quitar tildes (asciifolding):** "cédula" → "cedula". Por eso "renovar cedula" sin tilde funciona igual.
3. **Stopwords:** se descartan palabras muy frecuentes y sin contenido ("de", "la", "para", "el").
4. **Stemming:** cada palabra se reduce a su raíz: "renovación", "renovar" y "renueva" quedan parecidas ("renov…"), y coinciden entre sí.

### Fallback / degradación elegante
Plan alternativo automático cuando un componente no está disponible. Si se cae Elasticsearch, la API usa un índice BM25 local (librería `rank_bm25`). Si no hay acceso a Claude, usa Llama 3.2 local con Ollama; y si tampoco, devuelve el mejor resultado tal cual (respuesta **extractiva**).

---

## 3. Búsqueda

### BM25
*(Best Matching 25)*. El algoritmo clásico de búsqueda por palabras clave, y el que usan por defecto Elasticsearch y casi todos los buscadores. Le da un puntaje a cada documento según tres ideas:

1. **Frecuencia del término (TF):** si la palabra de la consulta aparece más veces en el documento, más puntaje… pero con rendimientos decrecientes (aparecer 20 veces no vale 20 veces más que aparecer 1).
2. **Rareza del término (IDF):** las palabras raras valen más. Que coincida "apostilla" (aparece en pocos trámites) dice mucho más que que coincida "certificado" (aparece en cientos).
3. **Largo del documento:** un documento muy largo tiene más chances de contener cualquier palabra de casualidad, así que se lo penaliza un poco.

Fórmula, por si la piden:

```
score(D, Q) = Σ  IDF(t) · tf(t,D) · (k1 + 1) / ( tf(t,D) + k1 · (1 − b + b · |D| / largo_promedio) )
            t∈Q
```

`k1` (≈1.2) controla la saturación de la frecuencia y `b` (≈0.75) cuánto pesa el largo del documento; son los valores por defecto de Elasticsearch.

**Fortaleza:** nombres exactos y siglas ("BPS", "DGI"). **Debilidad:** no sabe nada de significado: si no comparten palabras, no hay coincidencia.

### Tesauro
Un diccionario de sinónimos del dominio, armado por nosotros a mano (`src/synonyms.py`). Al buscar, la consulta se **expande** con sus sinónimos:
> "cédula" → también busca "documento de identidad"; "libreta" → "licencia de conducir".

Se aplica **en tiempo de consulta** (*query-time*): no hace falta reindexar los documentos para cambiarlo.
**Ventaja:** soluciona parte del vocabulary mismatch (las consultas coloquiales suben de 0.46 a 0.70 de nDCG).
**Riesgo:** si expande de más, mete ruido. Con "BPS jubilación" el nDCG cae de 0.70 a 0.00.

### Embeddings
Representar un texto como un vector de números (en nuestro caso, 384 números) de manera que **textos con significado parecido queden cerca** en ese espacio, aunque usen palabras distintas. "Seguro de paro" y "Subsidio por desempleo" quedan cerca. Los calcula un modelo de lenguaje entrenado para eso.

### multilingual-e5-small
El modelo de embeddings que usamos. Multilingüe (anda bien en español), chico (384 dimensiones, corre en CPU). Usa la convención de anteponer `query:` a las consultas y `passage:` a los documentos.

### Búsqueda semántica / densa
Buscar por significado en vez de por palabras: se calcula el embedding de la consulta y se buscan los documentos con embeddings más cercanos. Se le dice "densa" porque los vectores tienen valores en todas sus posiciones, a diferencia de BM25 ("dispersa": sólo cuentan las pocas palabras presentes).

### kNN (k vecinos más cercanos)
*(k-Nearest Neighbors)*. Encontrar los k vectores más cercanos a uno dado. En búsqueda semántica: los k trámites cuyo embedding está más cerca del de la consulta. La cercanía se mide con **similitud coseno** (el ángulo entre los vectores).
**Fortaleza:** lenguaje natural ("tuve un bebé, cómo lo registro"). **Debilidad:** errores de tipeo ("apostiya" da 0.00, porque el modelo no reconoce la palabra mal escrita).

### Búsqueda híbrida
Combinar búsqueda léxica (BM25) y semántica (kNN) para aprovechar lo mejor de cada una. Para combinar sus rankings usamos RRF.

### Reciprocal Rank Fusion (RRF)
Método para **fusionar varios rankings en uno solo** usando sólo las posiciones, no los puntajes. Cada documento suma, por cada ranking en que aparece:

```
RRF(d) = Σ  1 / (k + posición_de_d_en_el_ranking)      con k = 60
```

**¿Por qué no sumar los puntajes directamente?** Porque están en escalas distintas: BM25 puede dar 14.3 y la similitud coseno 0.82; sumarlos no tiene sentido. RRF las ignora y mira posiciones.

**Ejemplo:**

| Trámite | Posición en BM25 | Posición en kNN | Puntaje RRF |
|---|---|---|---|
| A | 1 | 3 | 1/61 + 1/63 = **0.0323** |
| B | 2 | — (no aparece) | 1/62 = 0.0161 |
| C | — | 1 | 1/61 = 0.0164 |

A gana porque está alto en **ambos** rankings: RRF premia el consenso. La constante k = 60 suaviza la diferencia entre la posición 1 y la 2; es el valor propuesto por Cormack et al. (2009), el paper original.

También usamos RRF para fusionar los resultados de las varias consultas que genera el LLM con los de la consulta original.

### Reranking (reordenamiento)
Segunda etapa: se toman los primeros resultados de la búsqueda (por ejemplo, 30) y un modelo más preciso pero más lento **los vuelve a ordenar**. Es costoso, por eso no se aplica a los 3.505 trámites, sólo a los mejores candidatos.

### Two-stage retrieval (recuperación en dos etapas)
El esquema "buscar rápido muchos candidatos y después reordenar con cuidado pocos". Etapa 1: BM25 + kNN + RRF (rápido, sobre todo el corpus). Etapa 2: reranking con cross-encoder (lento, sólo sobre el top-k).

### Cross-encoder vs. bi-encoder
- **Bi-encoder** (lo que usa kNN): codifica la consulta y el documento **por separado** y compara los vectores. Rápido, porque los vectores de los documentos se calculan una sola vez de antemano.
- **Cross-encoder** (lo que usa el reranking): lee la consulta y el documento **juntos** y da un puntaje de relevancia. Más preciso, porque ve la interacción entre ambos textos, pero hay que correrlo por cada par, así que es lento.

El nuestro es `mmarco-mMiniLMv2-L12-H384-v1`.

### mMARCO
Versión multilingüe (traducida) de MS MARCO, un gran dataset de búsquedas web reales de Bing con sus pasajes relevantes. Nuestro cross-encoder se entrenó ahí; nuestra hipótesis de por qué no mejoró es que ese dominio (web general) es distinto al de trámites.

### Facetas / filtros por facetas
Atributos para filtrar y agrupar resultados, mostrando cuántos hay de cada valor: organismo, canal (internet, presencial, teléfono) y gratuito. Como los filtros de "marca" o "precio" de una tienda online.

### Highlighting (resaltado)
Marcar en el resultado las palabras que coincidieron con la consulta, para que el usuario vea por qué apareció.

---

## 4. LLM y RAG

### LLM
*(Large Language Model)*. Modelo de lenguaje grande, como Claude o Llama. Genera y entiende texto. Lo usamos para reescribir consultas y para redactar respuestas.

### Reescritura de consultas (query rewriting)
Usar el LLM **antes** de buscar para traducir la pregunta del usuario al vocabulario oficial del catálogo:
> "me quedé sin trabajo, qué puedo cobrar" → "Subsidio por desempleo por despido", "Subsidio por desempleo", "Prestaciones BPS desempleo".

Cada consulta reescrita pasa por la búsqueda híbrida, y todo se fusiona con RRF **junto con la consulta original**, para que un error del LLM no arruine el resultado. Fue lo que más mejoró el sistema (nDCG de 0.59 a 0.84).

### Salida estructurada (structured output)
Pedirle al LLM que responda con un formato fijo (un objeto JSON con campos definidos) en vez de texto libre. Así el programa lo puede usar directamente. El nuestro devuelve: `consultas` (1 a 3), `canal` y `gratuito`. Por eso puede detectar "gratis" en la pregunta y aplicar el filtro solo.

### RAG
*(Retrieval-Augmented Generation)*. Generación aumentada por recuperación: primero se **recuperan** documentos relevantes con el buscador y después el LLM **genera** una respuesta usando sólo esos documentos como fuente. Evita que el modelo responda "de memoria" e invente, y permite citar las fuentes (los links a gub.uy).

### Alucinación
Cuando un LLM afirma algo falso o inventado con seguridad. El prompt del asistente lo limita: sólo puede usar los trámites recuperados, debe citar cada uno y, si ninguno responde, tiene que decirlo.

### Prompt
Las instrucciones y el contexto que se le pasan al LLM. En el RAG, el prompt incluye las reglas, los 5 trámites recuperados y la pregunta.

### Ollama / Llama 3.2
Ollama es un programa para correr LLMs en la propia computadora. Llama 3.2 es un modelo abierto de Meta. Es nuestro respaldo local si no hay acceso a Claude.

---

## 5. Evaluación

### Juicios de relevancia (qrels)
Para cada consulta, la lista de qué documentos son relevantes y cuánto. Es la "respuesta correcta" contra la que se compara al sistema. En archivos TREC se llaman *qrels* (`eval/qrels.tsv`).

### Relevancia graduada (0 / 1 / 2)
En vez de "relevante sí/no", usamos niveles:
- **2:** el trámite resuelve directamente lo que pide la consulta.
- **1:** relacionado y útil (paso previo, variante cercana).
- **0:** no relevante.

Los nuestros los generó un LLM leyendo nombre y organismo de cada candidato, y no se revisaron a mano (es una limitación).

### TREC / pooling
TREC es una conferencia que fijó la metodología estándar para evaluar buscadores. **Pooling**: como es imposible juzgar los 3.505 trámites para cada consulta, se juntan los top-10 de todos los sistemas a comparar (el *pool*) y sólo se juzga eso. Lo que no entró al pool se asume no relevante.

### Corrida (run)
La lista ordenada de resultados que devuelve un sistema para cada consulta. Guardamos una por sistema en `eval/runs/`.

### nDCG@10
*(normalized Discounted Cumulative Gain, en los primeros 10)*. Nuestra métrica principal. Mide qué tan bueno es el ranking teniendo en cuenta dos cosas:
1. **Ganancia:** cada resultado suma según su relevancia (2, 1 o 0).
2. **Descuento:** lo que aparece más abajo vale menos, porque el usuario mira sobre todo lo de arriba.

```
DCG@10  = Σ  relevancia_i / log2(i + 1)      (i = posición, de 1 a 10)
nDCG@10 = DCG@10 / DCG@10 del ranking ideal
```

**Normalizar** (dividir por el ranking ideal, el que pone los más relevantes primero) hace que el valor quede entre **0 y 1**: 1 = orden perfecto, 0 = nada relevante en el top 10.

**Ejemplo:** consulta con dos trámites de relevancia 2. Si el sistema los pone en las posiciones 1 y 2, nDCG = 1. Si los pone en las posiciones 3 y 4, nDCG ≈ 0.57: los encontró, pero no arriba.

### P@5 (precisión en 5)
De los primeros 5 resultados, qué fracción es relevante. P@5 = 0.6 → 3 de 5 son relevantes. No distingue el orden dentro de esos 5.

### MRR (Mean Reciprocal Rank)
Para cada consulta: 1 dividido la posición del **primer** resultado relevante. Se promedia entre consultas.
> Primer relevante en la posición 1 → 1; en la 2 → 0.5; en la 4 → 0.25.

Nuestro MRR de 0.94 con el LLM quiere decir que casi siempre el primer resultado ya sirve. En el código aparece como RR@10.

### R@10 (recall o exhaustividad en 10)
De todos los documentos relevantes que existen para la consulta, qué fracción aparece en el top 10. Responde "¿encontré todo lo que había?", mientras que la precisión responde "¿lo que mostré sirve?".

### Judged@10
Qué fracción del top 10 de cada sistema tiene un juicio de relevancia. 1.00 = todo lo que mostró cada sistema fue juzgado, así que ningún sistema queda perjudicado por tener resultados sin evaluar.

### Línea base (baseline)
El sistema de referencia contra el que se comparan las mejoras. La nuestra es BM25 sin tesauro.

### t-test pareado y p-valor
Prueba estadística para saber si la diferencia entre dos sistemas es real o puede ser casualidad. Es **pareado** porque compara los dos sistemas consulta por consulta (las mismas 36).
El **p-valor** es la probabilidad de ver una diferencia así de grande si en realidad los sistemas fueran igual de buenos. Por convención, **p < 0.05 = significativo**.
> Híbrida vs. BM25: p = 0.007 → la mejora es significativa.
> kNN vs. BM25: p = 0.306 → no podemos afirmar que sea mejor; puede ser ruido.

### ir_measures
Librería de Python que calcula las métricas de RI (nDCG, P, MRR, R…) a partir de las corridas y los qrels, de forma estándar y compatible con TREC.

---

## 6. Stack técnico

| Término | Qué es |
|---|---|
| **FastAPI** | Framework de Python para hacer APIs web. Es nuestro backend (`/api/search`, `/api/chat`). |
| **API / endpoint** | Interfaz que expone el backend; cada URL que responde (como `/api/search`) es un endpoint. |
| **React** | Librería de JavaScript para construir interfaces web. Es nuestro frontend. |
| **Tailwind CSS** | Framework de estilos basado en clases utilitarias. |
| **Vite** | Herramienta que levanta el servidor de desarrollo del frontend. |
| **Docker / docker-compose** | Corre servicios (como Elasticsearch) en contenedores aislados, con un solo comando. |
| **rank_bm25** | Librería de Python que implementa BM25 sin Elasticsearch; es nuestro respaldo local. |
| **sentence-transformers** | Librería de Python para usar modelos de embeddings y cross-encoders. |
