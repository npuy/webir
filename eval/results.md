## Resultados globales (36 consultas)

| Sistema | nDCG@10 | P@5 | MRR | R@10 | Judged@10 | p (vs base) |
|---|---|---|---|---|---|---|
| BM25 (sin tesauro) | 0.590 | 0.500 | 0.757 | 0.549 | 1.00 | — |
| BM25 + tesauro | 0.651 | 0.539 | 0.799 | 0.604 | 1.00 | 0.192 |
| kNN (e5-small) | 0.645 | 0.544 | 0.854 | 0.602 | 1.00 | 0.306 |
| Híbrida (RRF) | 0.696 | 0.611 | 0.853 | 0.638 | 1.00 | 0.007 |
| BM25 + rerank | 0.635 | 0.500 | 0.827 | 0.576 | 1.00 | 0.349 |
| Híbrida + rerank | 0.641 | 0.517 | 0.832 | 0.556 | 1.00 | 0.338 |
| Reescritura LLM (sola) | 0.795 | 0.644 | 0.929 | 0.710 | 1.00 | 0.004 |
| Reescritura LLM + original | 0.842 | 0.672 | 0.940 | 0.760 | 1.00 | 0.000 |

## nDCG@10 por categoría de consulta

| Sistema | coloquial | exacta | natural | sigla | tipeo |
|---|---|---|---|---|---|
| BM25 (sin tesauro) | 0.459 | 0.919 | 0.383 | 0.874 | 0.718 |
| BM25 + tesauro | 0.695 | 0.919 | 0.460 | 0.698 | 0.718 |
| kNN (e5-small) | 0.635 | 0.848 | 0.627 | 0.736 | 0.388 |
| Híbrida (RRF) | 0.747 | 0.908 | 0.553 | 0.738 | 0.696 |
| BM25 + rerank | 0.707 | 0.854 | 0.518 | 0.716 | 0.499 |
| Híbrida + rerank | 0.698 | 0.836 | 0.575 | 0.702 | 0.438 |
| Reescritura LLM (sola) | 0.876 | 0.864 | 0.775 | 0.586 | 0.807 |
| Reescritura LLM + original | 0.861 | 0.924 | 0.831 | 0.627 | 0.910 |

## nDCG@10 por consulta

| qid | consulta | BM25 (sin tesauro) | BM25 + tesauro | kNN (e5-small) | Híbrida (RRF) | BM25 + rerank | Híbrida + rerank | Reescritura LLM (sola) | Reescritura LLM + original |
|---|---|---|---|---|---|---|---|---|---|
| q01 | solicitud de pasaporte | 0.96 | 0.96 | 0.87 | 0.98 | 1.00 | 0.89 | 0.97 | 1.00 |
| q02 | certificado de antecedentes judiciales | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.92 | 1.00 |
| q03 | registro de marcas | 0.84 | 0.84 | 0.71 | 0.73 | 0.77 | 0.77 | 0.84 | 0.84 |
| q04 | asignación familiar | 0.75 | 0.75 | 0.72 | 0.75 | 0.76 | 0.76 | 0.89 | 0.83 |
| q05 | inscripción de nacimiento | 0.96 | 0.96 | 0.92 | 0.99 | 0.95 | 0.95 | 0.60 | 0.87 |
| q06 | credencial cívica primera vez | 1.00 | 1.00 | 0.86 | 1.00 | 0.64 | 0.64 | 0.96 | 1.00 |
| q07 | renovar cedula | 0.23 | 0.84 | 0.17 | 0.56 | 0.52 | 0.34 | 0.96 | 0.90 |
| q08 | sacar la libreta de conducir | 0.59 | 0.53 | 0.75 | 0.66 | 0.64 | 0.63 | 0.78 | 0.73 |
| q09 | carnet de salud | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| q10 | certificado de buena conducta | 0.61 | 0.82 | 0.61 | 0.85 | 0.82 | 0.88 | 1.00 | 0.92 |
| q11 | seguro de paro | 0.00 | 0.97 | 0.38 | 0.84 | 0.96 | 0.70 | 1.00 | 1.00 |
| q12 | papeles para casarme | 0.00 | 0.00 | 0.60 | 0.36 | 0.13 | 0.48 | 0.80 | 0.76 |
| q13 | abrir una empresa unipersonal | 0.66 | 0.66 | 0.93 | 0.81 | 0.80 | 0.76 | 0.74 | 0.81 |
| q14 | legalizar documentos para usar afuera | 0.59 | 0.74 | 0.64 | 0.90 | 0.79 | 0.79 | 0.73 | 0.78 |
| q15 | BPS jubilación | 0.70 | 0.00 | 0.23 | 0.08 | 0.24 | 0.18 | 0.26 | 0.14 |
| q16 | DGI monotributo | 0.81 | 0.81 | 0.85 | 0.90 | 0.73 | 0.73 | 0.87 | 0.91 |
| q17 | MIDES tarjeta uruguay social | 0.98 | 0.98 | 0.86 | 0.98 | 0.90 | 0.90 | 0.92 | 0.99 |
| q18 | UTE exoneración | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.29 | 0.47 |
| q19 | pasaprote | 0.86 | 0.86 | 0.19 | 0.84 | 0.10 | 0.18 | 0.85 | 1.00 |
| q20 | jubilasion | 0.82 | 0.82 | 0.66 | 0.78 | 0.69 | 0.32 | 0.38 | 0.67 |
| q21 | apostiya | 0.64 | 0.64 | 0.00 | 0.64 | 0.64 | 0.64 | 0.98 | 0.95 |
| q22 | partida de nasimiento | 0.92 | 0.92 | 0.74 | 0.86 | 0.76 | 0.76 | 0.83 | 0.93 |
| q23 | cedla de identidad | 0.35 | 0.35 | 0.36 | 0.36 | 0.30 | 0.29 | 1.00 | 1.00 |
| q24 | me quedé sin trabajo, qué puedo cobrar | 0.00 | 0.00 | 0.36 | 0.00 | 0.00 | 0.41 | 0.87 | 0.87 |
| q25 | quiero viajar con mi hijo menor al exterior | 0.62 | 0.62 | 0.74 | 0.71 | 0.81 | 0.81 | 0.98 | 0.98 |
| q26 | quiero traer a mi perro de otro país | 0.29 | 0.63 | 0.43 | 0.63 | 0.43 | 0.00 | 0.63 | 1.00 |
| q27 | tuve un bebé, cómo lo registro | 0.17 | 0.17 | 0.66 | 0.48 | 0.11 | 0.79 | 0.65 | 0.73 |
| q28 | sufro violencia de género, dónde pido ayuda | 1.00 | 1.00 | 0.88 | 1.00 | 0.87 | 0.76 | 0.95 | 0.95 |
| q29 | quiero jubilarme, qué tengo que hacer | 0.00 | 0.00 | 0.75 | 0.11 | 0.19 | 0.31 | 0.39 | 0.36 |
| q30 | necesito demostrar que no tengo antecedentes para un trabajo | 0.47 | 0.47 | 0.74 | 0.76 | 1.00 | 1.00 | 0.80 | 0.95 |
| q31 | perdí la cédula | 0.12 | 0.98 | 0.00 | 0.38 | 0.58 | 0.34 | 0.64 | 0.70 |
| q32 | me quiero hacer ciudadano uruguayo | 0.46 | 0.46 | 0.89 | 0.56 | 0.47 | 0.47 | 0.61 | 0.68 |
| q33 | quiero denunciar a mi empleador porque no me paga | 0.20 | 0.20 | 0.35 | 0.42 | 0.46 | 0.46 | 0.78 | 0.80 |
| q34 | mi papá falleció y necesito el certificado | 0.00 | 0.00 | 0.60 | 0.23 | 0.05 | 0.36 | 0.87 | 0.88 |
| q35 | quiero estudiar en el exterior con una beca | 0.95 | 0.95 | 0.76 | 0.91 | 0.76 | 0.76 | 0.90 | 0.91 |
| q36 | quiero castrar a mi perro gratis | 0.69 | 0.50 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
