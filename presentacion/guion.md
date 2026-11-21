# Guion de la presentación — Buscador mejorado de trámites de gub.uy

**Grupo 07 · Belén Olivera, Nicolás Pereira**
Duración total: 20 min → 15 min de presentación (incluye 5 min de demo) + 5 min de preguntas.

Es un guion de ejemplo: no hace falta leerlo literal. Sirve para fijar qué decir en cada slide y cuánto tiempo darle. Leído a ritmo normal, cada bloque entra en el tiempo marcado.

**División sugerida:** una persona presenta las slides 1–6 (contexto y solución) y la otra hace la demo y las slides 8–11 (evaluación y cierre). Las preguntas las responde quien mejor conozca cada tema.

| Minuto | Slide | Tiempo |
|---|---|---|
| 0:00 | 1. Portada | 0:30 |
| 0:30 | 2. El problema | 1:15 |
| 1:45 | 3. Los datos | 0:45 |
| 2:30 | 4. Arquitectura | 1:15 |
| 3:45 | 5. Búsqueda híbrida | 1:00 |
| 4:45 | 6. Dos usos del LLM | 1:00 |
| 5:45 | 7. Demo en vivo | 5:00 |
| 10:45 | 8. Evaluación | 1:00 |
| 11:45 | 9. Resultados | 1:15 |
| 13:00 | 10. Resultados por tipo de consulta | 1:15 |
| 14:15 | 11. Conclusiones | 0:45 |
| 15:00 | 12. ¿Preguntas? | 5:00 |

---

## Antes de empezar (checklist)

- [ ] Docker Desktop abierto y `docker compose up -d` (Elasticsearch).
- [ ] API: `.venv/bin/uvicorn src.api:app --port 8000`.
- [ ] Frontend: `cd frontend && npm run dev` → http://localhost:5173.
- [ ] `.env` con `ANTHROPIC_API_KEY` cargada.
- [ ] Abrir http://localhost:8000/api/health y verificar `backend: "elasticsearch"` y `llm` no nulo.
- [ ] Precalentar: hacer una búsqueda con rerank y una pregunta al asistente (la primera vez se cargan los modelos y tarda).
- [ ] Ensayar las 6 consultas de la demo y anotar qué aparece primero.
- [ ] Tener el navegador con zoom grande y las pestañas de slides y demo listas para alternar.

---

## 1. Portada (0:00 – 0:30)

> Buenas, somos Belén Olivera y Nicolás Pereira, del grupo 7. Les vamos a presentar un buscador mejorado para el catálogo de trámites del Estado uruguayo. La idea es simple: que el buscador entienda cómo pregunta la gente, no solamente las palabras exactas.
>
> Vamos a contar el problema, cómo lo resolvimos, hacer una demo en vivo y mostrar cómo lo evaluamos.

## 2. El problema (0:30 – 1:45)

> El portal gub.uy reúne miles de trámites. Pero el buscador funciona sobre todo por coincidencia de palabras, y la gente no busca con el nombre oficial del trámite.
>
> Estos son ejemplos reales de nuestro set de evaluación, con el puntaje que saca BM25, el algoritmo clásico de búsqueda por palabras clave. Alguien busca "seguro de paro", pero el trámite se llama "Subsidio por desempleo por despido". Resultado: nDCG de cero, no encuentra nada útil. "Renovar cédula": el trámite se llama "Documento Nacional de Identidad – Renovación". "Papeles para casarme": otra vez cero. Y con un error de tipeo como "cedla de identidad", también falla.
>
> Esto es lo que en recuperación de información se llama *vocabulary mismatch*. A eso se suman dos problemas: las consultas en lenguaje natural, que el matching por palabras no entiende, y la falta de filtros prácticos, como saber si el trámite es gratis o si se puede hacer por internet.

## 3. Los datos (1:45 – 2:30)

> Trabajamos con el catálogo de trámites que AGESIC publica como datos abiertos: 3.505 trámites de 144 organismos.
>
> Al usarlo encontramos un problema: el campo de costo estaba vacío en el 59% de los casos, y vacío podía significar tanto "es gratis" como "no hay dato". Entonces bajamos cada ficha de gub.uy con un crawler lento y con caché, y parseamos el HTML para sacar costos, montos y canales de atención. Con eso los trámites sin dato de costo bajaron al 11%, y el filtro de "gratuito" pasó a ser confiable.

## 4. Arquitectura (2:30 – 3:45)

> Esta es la arquitectura. A la izquierda, los datos: el CSV enriquecido se indexa en Elasticsearch con un analizador en español —minúsculas, sin tildes, sin palabras vacías y con stemming— y un tesauro de sinónimos que se aplica al consultar. En el mismo índice guardamos los embeddings de cada trámite para la búsqueda semántica.
>
> En el centro está la API en FastAPI, que orquesta todo: la búsqueda léxica, la semántica, la fusión de resultados, el reranking y el asistente.
>
> A la derecha, el frontend en React y el modelo de lenguaje.
>
> Algo que cuidamos es que el sistema degrade bien: si se cae Elasticsearch, la API usa un índice BM25 local; si no hay acceso a Claude, usa Llama 3.2 local con Ollama; y si tampoco, responde de forma extractiva con el mejor resultado.

## 5. Búsqueda híbrida (3:45 – 4:45)

> El corazón del buscador es una recuperación híbrida.
>
> Primero, BM25 con el tesauro. Lo mantenemos porque es imbatible para nombres exactos y siglas como BPS o DGI.
>
> En paralelo, búsqueda semántica con kNN sobre embeddings del modelo multilingual-e5-small. Compara por significado, no por palabras.
>
> Como los puntajes de una y otra están en escalas que no se pueden comparar, los combinamos con Reciprocal Rank Fusion, que sólo mira la posición de cada documento en cada ranking. Usamos k igual a 60.
>
> Opcionalmente, un cross-encoder reordena los primeros resultados. Y arriba de todo, filtros por organismo, canal y gratuidad.

## 6. Dos usos del LLM (4:45 – 5:45)

> El modelo de lenguaje lo usamos de dos formas.
>
> La primera, y la que más impacto tuvo, es **antes** de buscar: reescribir la consulta. Le damos la pregunta del usuario y devuelve, en formato estructurado, entre una y tres consultas con el vocabulario oficial del catálogo, más los filtros si el usuario los pidió. Por ejemplo, "me quedé sin trabajo, qué puedo cobrar" se convierte en "Subsidio por desempleo por despido". Cada reescritura pasa por la búsqueda híbrida y se fusiona con la consulta original, para no depender sólo de lo que diga el LLM.
>
> La segunda es **después**: un asistente RAG que toma los cinco mejores trámites y redacta una respuesta con reglas estrictas: sólo usar esos trámites, citar los links oficiales y avisar si ninguno responde la pregunta.
>
> Ahora lo vemos funcionando.

## 7. Demo en vivo (5:45 – 10:45)

*(Cambiar al navegador.)*

**0:00 — "solicitud de pasaporte"**
> Empezamos con una búsqueda exacta. Acá el resultado correcto aparece primero; ven el resaltado de los términos y las facetas por organismo y canal.

**0:45 — "papeles para casarme"**
> Ahora una consulta coloquial. Si desactivo la búsqueda híbrida y dejo sólo BM25… no trae nada relevante: en nuestra evaluación da cero. Activo la híbrida y aparecen trámites relacionados con el matrimonio. *(Ajustar según lo que se vio al ensayar.)*

**1:45 — "pasaprote"**
> Un error de tipeo. El resultado correcto sigue arriba.

**2:15 — Filtros**
> Borro la consulta y navego sólo con filtros: trámites gratuitos que se pueden hacer por internet. Este filtro funciona gracias al enriquecimiento con scraping que contamos antes.

**3:00 — Asistente: "me quedé sin trabajo, qué puedo cobrar"**
> Paso al modo asistente. Acá ven las consultas que generó el LLM —"Subsidio por desempleo…"— y la respuesta, que cita cada trámite con su link a gub.uy.

**4:15 — Asistente: "quiero castrar a mi perro gratis"**
> Un último ejemplo: no marqué ningún filtro, pero el LLM detectó la palabra "gratis" y aplicó el filtro de gratuito automáticamente.

*(Volver a las slides.)*

## 8. Evaluación (10:45 – 11:45)

> Para no quedarnos en "se ve mejor", hicimos una evaluación formal, con la metodología de TREC.
>
> Armamos 36 consultas en cinco categorías que reflejan cómo busca la gente: lenguaje natural, coloquial, nombre exacto, errores de tipeo y siglas. Corrimos ocho configuraciones del sistema, juntamos los diez primeros resultados de cada una en un pool y juzgamos cada par consulta–trámite en una escala de 0 a 2. En total, 1.050 juicios.
>
> Hay que ser transparentes: los juicios los generó un LLM leyendo el nombre y el organismo de cada trámite, y no los revisamos a mano. Es una limitación del trabajo.
>
> Medimos con la librería ir_measures —nDCG@10 como métrica principal, además de P@5, MRR y recall— y usamos un t-test pareado contra BM25 para ver qué diferencias son significativas.

## 9. Resultados (11:45 – 13:00)

> Estos son los resultados, de menor a mayor. BM25 solo da 0.59 de nDCG.
>
> Cada componente por separado mejora un poco, pero la primera mejora significativa es la búsqueda híbrida: 0.70, un 18% más, con p igual a 0.007.
>
> El gran salto es la reescritura con LLM: 0.84 cuando se combina con la consulta original, un 43% sobre la base. El MRR de 0.94 significa que casi siempre el primer resultado relevante está en la primera posición. Y combinar con la consulta original suma frente a usar sólo la reescritura: de 0.80 a 0.84.
>
> Algo que no esperábamos: el reranking con cross-encoder no mejora; incluso empeora la híbrida.

## 10. Resultados por tipo de consulta (13:00 – 14:15)

> Si miramos por categoría, se entiende por qué conviene combinar.
>
> El tesauro sube las consultas coloquiales de 0.46 a 0.70, pero perjudica las siglas: "BPS jubilación" pasa de 0.70 a cero, porque la expansión de sinónimos mete ruido.
>
> kNN es el mejor componente clásico en lenguaje natural, pero se cae con los errores de tipeo: 0.39. La híbrida compensa una cosa con la otra.
>
> El LLM gana en cuatro de las cinco categorías. Su punto débil son las siglas: con "UTE exoneración" reescribe a algo más genérico y pierde el trámite exacto que BM25 encontraba perfecto.
>
> Sobre el reranking, nuestra hipótesis es que el cross-encoder fue entrenado con mMARCO, que es texto web general, y no conoce el dominio de trámites.

## 11. Conclusiones (14:15 – 15:00)

> Para cerrar, tres ideas.
>
> Uno: combinar búsqueda léxica y semántica con RRF es simple y funciona: 18% de mejora, significativa.
>
> Dos: el LLM rinde más como traductor de la pregunta al vocabulario del catálogo que sólo como generador de respuestas.
>
> Tres: tenemos limitaciones claras —siglas, pocas consultas, juicios sin revisión manual y el costo del LLM— y un camino para seguir: un tesauro que respete siglas, un reranker ajustado al dominio, consultas reales de usuarios y evaluar la fidelidad de las respuestas del asistente.
>
> Muchas gracias. ¿Preguntas?

## 12. Preguntas (15:00 – 20:00)

Respuestas preparadas para las preguntas más probables:

**¿Por qué RRF y no una suma ponderada de puntajes?**
Los puntajes de BM25 y de similitud coseno están en escalas distintas y no se pueden comparar directamente. RRF sólo usa posiciones, no necesita normalizar ni ajustar pesos, y k = 60 es el valor propuesto en el paper original de Cormack et al. (2009).

**¿Por qué multilingual-e5-small?**
Es multilingüe con buen desempeño en español, genera vectores de 384 dimensiones y corre en CPU, así que todo el sistema funciona en una notebook.

**¿Por qué el reranking empeora?**
Hipótesis: el cross-encoder se entrenó con mMARCO (búsqueda web general) y no conoce el dominio de trámites. Además, el top-k de la híbrida ya es bastante bueno, así que hay poco margen y mucho riesgo de desordenarlo. Ajustarlo al dominio queda como trabajo futuro.

**¿Los juicios generados con LLM no sesgan la evaluación?**
Es una limitación real: no se revisaron a mano. Lo mitigamos en parte con pooling de 8 sistemas (Judged@10 = 1.00, todo el top-10 de cada sistema está juzgado) y una escala graduada con criterios explícitos. Como trabajo futuro, revisar una muestra a mano y medir el acuerdo con el LLM.

**¿Cuánto cuesta y cuánto tarda el LLM?**
En el asistente son dos llamadas por pregunta: reescritura y respuesta. Si no hay acceso a la API, el sistema usa Llama 3.2 local con Ollama o una respuesta extractiva, así que nunca queda sin funcionar.

**¿Cómo evitan que el asistente invente cosas?**
El prompt limita la respuesta a los trámites recuperados, obliga a citar el link oficial de cada uno y, si ninguno responde la pregunta, el asistente tiene que decirlo explícitamente.

**¿Qué pasa si se cae Elasticsearch?**
La API detecta que no está disponible y usa un índice BM25 local construido con rank_bm25.
