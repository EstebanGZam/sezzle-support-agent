# Informe técnico de asesoría — Sezzle Applied AI Engineer Take-Home

**Fecha:** 2026-09-27 · **Fase:** asesoría (sin implementación) · **Autor:** lead orchestrator (Claude Code, Opus 5.5)
**Soporte:** 7 investigaciones delegadas (Claude, solo lectura), en `advisory/research/`.
**Leyenda:** **[V]** verificado (fuente oficial o archivo del paquete) · **[I]** inferencia técnica · **[R]** recomendación · **[U]** no verificado / supuesto · **[OQ]** pregunta abierta.

> Idioma: explicaciones en español; todo artefacto técnico futuro (specs, prompts, código, commits) irá en inglés.

---

## 1. Resumen ejecutivo

1. **Lo que realmente se evalúa** [V, PROMPT.md "What we grade"]: (1) calidad de las decisiones de diseño y honestidad del "qué me haría cambiar de opinión", (2) el bucle de iteración medido, (3) ingeniería del LLM — sobre todo *qué impide estructuralmente el código* vs. qué solo se le "pide" al modelo, (4) juicio de escalamiento/autorización, (5) cómo diriges a tus herramientas de IA. **No** se evalúa scaffolding, proveedor ni líneas de código.
2. **Arquitectura recomendada:** un único agente LLM con *tool calling* acotado (≤2 rondas), **corpus de políticas completo en contexto (sin RAG ni vectores)**, herramientas **de solo lectura con `user_id` ligado en código**, que devuelven **hechos derivados calculados determinísticamente** (próxima cuota, elegibilidad de reprogramación, ventana de disputa, días hábiles del reembolso), **salida estructurada** `{route, answer, escalation_reason, cited_policies}` y un **validador de salida** en código (números/fechas anclados, frases prohibidas, IDs ajenos, fallo cerrado → escalamiento). Fallback más simple: una sola llamada con los datos del usuario pre-cargados.
3. **Proveedor:** Gemini en **proyecto con facturación (Paid Services)**: primario `gemini-3.5-flash-lite` (thinking `minimal`), respaldo `gemini-3.1-flash-lite`, SDK `google-genai` nativo. **El free tier no debe usarse con material de la evaluación** (Google puede usar los datos y revisarlos humanamente). Riesgo abierto crítico: *¿con qué clave correrán los revisores el hidden set?* → pregunta al hiring manager.
4. **Proceso:** SDD ligero en Markdown del repo (`AGENTS.md` + `specs/requirements.md` + `specs/tasks.md`); **nada de Spec Kit/OpenSpec**. Un implementador principal + un teammate paralelo en archivos disjuntos (harness de evaluación) + **revisor de otro proveedor** (Codex). Claude Cloud: **opcional y fuera de la ruta crítica** (el Orchestrator 0.5.4 no puede lanzarlo).
5. **Despliegue: no desplegar** (no lo pide el brief, no suma nota, añade riesgo de publicación y gasto). Si insistes: Cloud Run con cabecera secreta, 21 días ≈ **$4–8 esperado, ≤ $12 acotado**.
6. **Decisiones que necesito de ti:** §20 (10 puntos). La más urgente: **cómo contabilizar el tiempo de preparación** y **qué preguntas enviar al hiring manager antes de arrancar el reloj**.

---

## 2. Requisitos verificados (resumen de la matriz)

La matriz completa (57 filas, con fuente/línea, tipo, prioridad, criterio de aceptación y verificación) está en `research/requirements-analysis.md`. Lo esencial:

| ID | Requisito | Fuente | Tipo |
|---|---|---|---|
| F-01/F-02 | Asistente con **LLM funcional en el pipeline**; lógica determinista *alrededor* del modelo sí, *en lugar* del modelo no | PROMPT.md "The LLM is the assignment" | Explícito |
| C-01..C-04 | `python3 run_cases.py <cases.jsonl> <answers.jsonl>`; entrada `{id, question, user_id}` (tolerar claves extra), salida `{id, route, answer}`, `route ∈ {policy, tool, both, escalate}` | PROMPT.md "The one contract" | Explícito |
| C-07 | Hidden set con el mismo formato, calificado por regex `must_include`/`must_not_include`; "build for the problem, not the ten cases" | PROMPT.md | Explícito |
| F-06 | Fecha actual = `today` del JSON (**2026-07-01**), nunca el reloj del sistema | PROMPT.md, DATA L3 | Explícito |
| F-07..F-09 | (Eng II) guardrails ante input hostil: órdenes ajenas/inexistentes, exigencias de exención de cargos, "ignora tus reglas" | PROMPT.md "Level expectations" | Explícito |
| F-10..F-14 | Escalamientos obligatorios: disputas (05), hardship (09), fraude (11), motivo de rechazo/límite exacto (12), disputas de cargos (03/10), reportes de crédito (07), reembolso >10 días hábiles (04) | POLICY_* | Restricción documentada |
| F-11 | Una respuesta `escalate` **igual debe explicar la política permitida** (p. ej. v06 exige "disput", "90 days", "15 days", "paus") | CASES v05/v06/v09 | Restricción documentada |
| N-01..N-04 | ≥1 ADR sobre **100k preguntas/día, ~$50/día (= $0.0005/pregunta), p95 ≤ 3 s**; nivel Senior: "reads like it's been lived" | PROMPT.md "Design constraint" | Explícito |
| D-01..D-06 | Entregables: código + `run_cases.py`; `DECISIONS.md` con **exactamente 3** ADRs (≤~10 líneas: decisión · opciones · por qué · qué evidencia me haría cambiar); **primera y última corrida** + nota de iteración (Senior: *taxonomía de fallos*); `PROMPTS.md` (prompts de construcción **y** del sistema); `README.md` de media página con lo inacabado | PROMPT.md "Deliverables" | Explícito |
| S-01/S-02 | Entrega: zip **o** repo privado compartido con el revisor; **no publicar** el reto ni la solución | SUBMISSION.md | Explícito |
| T-01/T-02 | ~2 h; parar en el presupuesto; nota honesta de "unfinished" puntúa positivamente | PROMPT.md, SUBMISSION.md | Explícito |

**Rúbrica de enrutamiento derivada** [I, a partir de políticas y casos golden]: `escalate` domina si hay una acción o juicio solo-humano (aunque se explique política) → `both` si se interpreta un pedido propio con una regla → `tool` si es consulta pura del registro → `policy` si es genérico (y **sin** datos de pedidos: v02 prohíbe `ord_`).

---

## 3. Información faltante y ambigüedades

**Discrepancias del paquete [V]:**
- `PROMPT.md` menciona `llm.py` (cliente opcional) y `data/mock_orders_api.py`: **no están en el paquete**.
- Las rutas documentadas (`data/policies/`, `data/orders.json`, `cases/golden_visible.jsonl`) no coinciden con los archivos planos entregados (`POLICY_-_01-…`, `DATA-orders.json`, `CASES_-_golden_visible.jsonl`).

**Anomalías de datos [V]** (un hidden set puede sondearlas):
- Cuotas `failed` con fecha de vencimiento **posterior** a hoy (ord_3002 07-09, ord_3016 07-10, ord_3017 07-02), mientras la cuenta sigue `active` → interpretar como "primer intento fallido, reintento pendiente" [I].
- `users[].reschedules_used` siempre `{}` frente a `orders[].reschedules_used` 0/1/2 → **tomar el del pedido como autoritativo** (la política es "por pedido") [I].
- Reembolsos `processing` en pedidos **totalmente pagados** (todo vuelve al medio de pago en 3–10 días hábiles) vs. **parcialmente pagados** (ord_3009: el reembolso se aplica a las cuotas pendientes, la última primero).
- 5 usuarios tienen **dos pedidos con el mismo comerciante** → desambiguación.
- Pedidos con `reschedules_used=2` → la siguiente reprogramación cuesta $5 y es la última permitida.
- Importes con redondeo desigual (v01 espera **118.36**, no 25 % del total).

**Ambigüedades de especificación [OQ]:**
- Si el tiempo de preparación cuenta dentro de las 2 h.
- Cómo se puntúa `route` y si las regex son case-insensitive (se asume `re.I`).
- Etiqueta esperada para órdenes ajenas/inexistentes.
- Con qué proveedor y clave correrán los revisores.
- Festivos en la aritmética de días hábiles (el 2026-07-03 es festivo federal observado).
- Si el hidden set usa el mismo `DATA-orders.json`.

**Preguntas propuestas al hiring manager** (preguntar bien puntúa positivamente [V, SUBMISSION.md]):
1. The package is flat and doesn't include `llm.py` / `mock_orders_api.py` referenced in PROMPT.md — intentional? Will the hidden set use this same `DATA-orders.json` (`today` = 2026-07-01)?
2. When you run the hidden set, which provider/API key will you use (so I support the right env vars)? Is Gemini acceptable, or should I also support Anthropic/OpenAI?
3. Is `route` scored as exact match separately from the regex checks, and are regexes case-insensitive? For an order ID that isn't the shopper's (or doesn't exist), which route do you expect?
4. Should order-level `reschedules_used` be treated as authoritative, and `failed` installments with future due dates as "first attempt failed, retry pending"?
5. Does preparation (reading materials, environment/provider setup) count toward the ~2 hours?

---

## 4. Contexto de negocio y marca de Sezzle

**Qué es y cómo gana dinero [V]:**
- Sezzle es un BNPL de EE. UU./Canadá, *Public Benefit Corporation* y B Corp. Su misión declarada es "financially empower the next generation".
- Ingresos FY2025: 29 % comisiones a comercios y 22 % suscripciones (Premium/Anywhere); el resto son cargos al consumidor y otros ([10-K](https://www.sec.gov/Archives/edgar/data/1662991/000166299126000016/szl-20251231.htm)).
- Q2 2026: 3,16 M consumidores activos; 97,2 % de los pedidos son de compradores recurrentes.

**Relevancia para la evaluación [I]:**
- **Retención:** la base es recurrente y por suscripción, así que un soporte que se equivoca o promete de más en pagos fallidos, reprogramaciones y reembolsos cuesta dinero real.
- **Correspondencia con el problema:** centro de ayuda → `policy`; panel de pedidos → `tool`; "¿por qué no puedo reprogramar?" → `both`; formulario de disputa, fraude, hardship y reportes de crédito → `escalate`.

**Voz de marca aplicable al system prompt** (12 reglas en `research/brand-report.md`), en resumen:
- Segunda persona, frases cortas y lenguaje llano. Primero la respuesta (sí/no/importe/fecha), después 2–3 pasos.
- **Cifras y fechas solo de las políticas o de los resultados de herramientas.** Conservar las matizaciones de la política ("may").
- Nunca prometer exenciones, aprobaciones ni efectos en el puntaje crediticio.
- Tono cálido sin exclamaciones ni upsell. Fechas en formato largo ("July 11, 2026") y dinero con dos decimales.

**Reglas de uso de la marca:**
- **Los documentos de la evaluación mandan sobre la web pública.** Por ejemplo, el sitio actual ya no publica importes de cargos, mientras que las políticas del paquete sí: la memoria del modelo sobre Sezzle es obsoleta e irrelevante.
- **No suplantar a Sezzle:** nada de logos, gradiente "S" ni tipografía de la marca, y la leyenda "unofficial take-home prototype; synthetic data" ([brand assets](https://sezzle.com/brand-assets/) prohíbe recrear el logo).
- **UI: no construirla** salvo que sobre tiempo. No puntúa.

---

## 5. Metodología SDD y herramientas

**Comparativa** (detalle en `research/sdd-report.md`):
- **GitHub Spec Kit:** instalación y ceremonia de constitución → spec → plan → tasks. Unos 20–30 min [U] y mucho contexto.
- **OpenSpec:** más ligero, pero es otra herramienta que aprender con el reloj corriendo.
- **Markdown nativo del repo:** sin instalación, compatible con Claude Code, Codex y cualquier teammate del Orchestrator. → **Recomendado.**

**Estructura mínima (sin duplicar entregables obligatorios):**

```
AGENTS.md              # single source of truth for agent rules (≤60 lines)
CLAUDE.md              # exactly "@AGENTS.md" (official import; Claude never reads it twice)
specs/requirements.md  # R-IDs + acceptance criteria + verification + status (incl. I/O contracts)
specs/tasks.md         # task → R-ID → owner → verify command → status
```

- **Descartados de tu lista original:**
  - `architecture.md` y `docs/decisions.md` → su contenido va en `DECISIONS.md`, que es obligatorio.
  - `prompt-log.md` → `PROMPTS.md`, obligatorio.
  - `evaluation.md` → `ITERATION.md`.
  - `time-log.md` → sección del README.
  - `api-contracts.md` y `acceptance-criteria.md` → dentro de `requirements.md`.
- **Motivo:** menos archivos significa menos deriva y contradicciones ([Claude Code memory docs](https://code.claude.com/docs/en/memory): "If two rules contradict each other, Claude may pick one arbitrarily").
- **Trazabilidad:** R-ID → T-ID → commit (`feat(tools): … [R3]`) → test → caso de eval → fila en `ITERATION.md`.

---

## 6. Alternativas de arquitectura

| Criterio | A. Recuperación determinista + tools explícitas | B. RAG ligero + tool calling | C. RAG agéntico con ejecución controlada | D. LangGraph u otro framework |
|---|---|---|---|---|
| Cobertura funcional | Alta, si el LLM compone la respuesta | Alta | Alta | Alta |
| Esfuerzo en 2 h | **Bajo** | Medio (indexar y afinar el recall) | Alto | Alto (curva de aprendizaje + abstracciones) |
| Fiabilidad / testabilidad | **Alta**: contexto fijo y tools puras | Media: fallos de recall | Media-baja: bucles abiertos | Media |
| Seguridad / explicabilidad | **Alta**: todo acotado en código | Media | Baja-media: más agencia | Media |
| Latencia (p95 ≤ 3 s) | 1–2 llamadas | 1–2 llamadas + retrieval | 2–5 llamadas ✗ | Igual que C, con más overhead |
| Encaje con la evaluación | **Máximo**: muestra "structurally prevented" | Bueno | Sobreingeniería | Sobreingeniería, y el brief pide ver *tus* decisiones |

**¿Hace falta retrieval?** [V/I]
- El corpus son **12 documentos ≈ 8,5 KB ≈ 2,2 k tokens**. Cabe completo en el contexto con holgura (los modelos admiten 1 M de tokens).
- Embeddings, base vectorial, búsqueda híbrida o reranking solo añaden fallos de recall y latencia sin beneficio.
- BM25/keywords solo tendría sentido como **optimización de coste** a escala (bajar el prefijo a unos 1,5 k tokens). Es un argumento para el ADR, no algo que implementar.

---

## 7. Arquitectura recomendada

**Primaria: "A" — un agente con tools acotadas, contexto completo y guardrails estructurales.**

```
run_cases.py ─► for each {id, question, user_id}:
  1. Input guard [code]: length cap, strip control chars; forced flags via
     cheap pre-classifier (fraud / hardship keywords) → escalation cannot be unset.
  2. Context [code]: system prompt (rules + brand voice + canary) + ALL 12 policies
     with doc IDs + frozen today=2026-07-01. User text delimited as untrusted data.
  3. LLM loop [model] (google-genai, AFC disabled, manual loop, ≤2 tool rounds):
     tools (read-only, closure over user_id — the model never passes a user_id):
       • get_my_orders(merchant?: str, order_id?: str) → caller's orders only,
         plus DERIVED FACTS computed in code: next_upcoming installment,
         reschedule {eligible, reason, next_fee, remaining, hours_until_due},
         failed → "repay, not reschedulable", dispute_window_end,
         refund_application {to_unpaid_installments, to_payment_method,
         business_days_elapsed}. Foreign and nonexistent IDs → the SAME not_found.
     final: structured JSON {route, answer, escalation_reason|null, cited_policies[]}
  4. Output validator [code]: schema/enum; numbers/dates ⊆ (tool results ∪ policy
     constants ∪ derived facts); forbidden phrases (action claims "I've paused/waived",
     "your limit is"); foreign ord_ IDs; canary; fraud mode redacts details.
     Fail → 1 repair retry → safe escalation template (fail closed).
  5. Route reconciliation [code]: forced/declared escalation ⇒ "escalate";
     route=policy with order data ⇒ repair; enum enforced.
  6. Trace [code]: per case → tool calls, validator verdicts, model, tokens, latency.
```

**Por qué cada componente** (trazabilidad con los requisitos):
- **Tools con `user_id` en closure y not-found idéntico:** F-07 (IDOR) y el nivel Eng II. Es la restricción estructural más fuerte.
- **Solo lectura:** F-18 y LLM06. El modelo no puede reprogramar, eximir ni pausar porque esas funciones no existen.
- **Hechos derivados en código:** F-05, F-16, F-17 y los casos v01/v03/v04/v10. Evitan la aritmética de fechas del LLM, la fuente principal de alucinación.
- **Salida estructurada con `escalation_reason`:** C-04 y F-10. La escalada es un dato, no una frase.
- **Validador:** F-04, F-21 y F-24. Las regex del evaluador buscan subcadenas aunque estén negadas: "waived" falla incluso en "I haven't waived".
- **Contexto completo:** grounding sin fallos de recall.
- **Fallo cerrado → escalar:** la única respuesta determinista es "te paso con un humano", nunca una respuesta inventada por código. Esto respeta F-02.

**Fallback (más simple), si el bucle de tools se complica o falta tiempo:**
- **Una sola llamada.** Las órdenes del usuario se precargan en el contexto, filtradas en código.
- Salida estructurada más el mismo validador.
- Pierdes la señal "¿llamó a la herramienta?" para el enrutamiento y expones más datos por llamada.
- A cambio ganas latencia y coste: aproximadamente la mitad [U], y es la opción que el ADR de coste propondrá para escala.

**Stack:**
- Python 3.12/3.13, `uv` (lockfile), `google-genai==2.25.0` [V], `pydantic`, `pytest`, `ruff`.
- **Sin FastAPI** en el MVP: el contrato es un CLI; FastAPI solo si decides desplegar.
- **Sin LangChain / LangGraph / LlamaIndex:** ningún requisito los justifica y ocultarían exactamente lo que se evalúa.

---

## 8. Estrategia de RAG y tool calling

- **Políticas:** inyección completa y estable al inicio del prompt, lo que favorece el caché implícito. Cada documento lleva un ID (`POL-01`…`POL-12`) que el modelo debe citar en `cited_policies`.
- **Herramienta única** `get_my_orders`, con filtros opcionales, que devuelve **todas** las coincidencias (con dos pedidos del mismo comerciante el modelo desambigua con pistas como "missed" → failed, o responde por ambos). Dos tools (`list_my_orders` / `get_my_order`) también valen; una sola reduce errores de selección [R].
- **Modo de function calling:**
  - `AUTO` y `allowed_function_names`.
  - `VALIDATED`, que valida los argumentos contra el esquema con decodificación restringida [V, [ToolConfig](https://ai.google.dev/api/caching#ToolConfig)].
  - **Automatic function calling desactivado:** el bucle es propio para autorizar, registrar y limitar cada llamada [V, [python-genai](https://github.com/googleapis/python-genai)].
- **Gemini 3:** reenviar `response.candidates[0].content` sin modificar en el historial, para no perder las *thought signatures* (error `missing_thought_signature`) [V, [api-errors](https://ai.google.dev/gemini-api/docs/api-errors)].
- **Salida estructurada + tools** en la misma llamada: soportado en la serie Gemini 3 [V, [structured-output](https://ai.google.dev/gemini-api/docs/structured-output)]. Si falla en la práctica, se usa una llamada final separada con `NONE` + schema.

---

## 9. Responsabilidades de los agentes de desarrollo

**Principio:** un propietario por archivo; implementador ≠ revisor. Paralelizar solo trabajo disjunto.

| Rol | Agente | Qué hace | Archivos |
|---|---|---|---|
| Lead / arquitectura / integración | Claude Code (esta sesión) | Specs, aprobación, prompts por etapa, integración (`orchestrator land`), `DECISIONS.md` con tu criterio | `specs/`, `DECISIONS.md` |
| Implementador principal | Teammate Claude (effort high), worktree | Pipeline: loader, tools con hechos derivados, prompt, bucle, validador, `run_cases.py` | `src/`, `run_cases.py`, `tests/` |
| Harness de evaluación (paralelo) | Teammate Claude o Codex (tras el reset de su ventana), worktree | `evals/score.py` (regex con `re.I` + route), reporte de taxonomía, diff entre corridas | `evals/` |
| Revisor independiente | **Codex** (otro proveedor) | Revisión del diff contra los ACs y las amenazas OWASP; solo lectura | — |
| Documentación | Tú + lead | `ITERATION.md`, `README.md`, `PROMPTS.md`: el juicio es tuyo | docs raíz |

- **¿Paralelizar la implementación? No.**
  - El núcleo son unas 400–600 líneas acopladas.
  - Dos implementadores en paralelo generan conflictos y overhead de coordinación.
  - Lo único disjunto y paralelizable es el harness de evaluación.
- **Capacidad actual [V, `orchestrator usage`]:**
  - Claude: 31 % de la ventana de 5 h y 4 % de la semanal.
  - Codex: **90 % de la ventana de 5 h** (se reinicia a las 21:48 de hoy) y 20 % de la semanal.
  - agy y opencode: cuota desconocida, se trata como desconocida.
  - → Programar la sesión cronometrada para cuando Codex tenga margen de revisión, o usar agy/opencode como revisor tras una prueba.

---

## 10. Viabilidad de Claude Cloud

**Verificado** ([docs](https://code.claude.com/docs/en/claude-code-on-the-web), CLI local v2.1.283, plan Pro):
- **Cómo se lanzan las sesiones:** desde la web (claude.ai/code), el móvil o el escritorio, o desde el CLI con `claude --cloud "<task>"` (`--remote` sigue como alias obsoleto).
- **Seguimiento:** `claude -p "…" --cloud <id> --output-format json` envía mensajes de seguimiento; `claude --teleport` trae la sesión a local.
- **Origen del código:** clona desde el **remote de GitHub**, no desde tus archivos locales; hay que hacer push antes.
- **Acceso al repo:** con la **Claude GitHub App** instalada en el repo, que pide permisos amplios de lectura/escritura (Contents, PRs, Actions, Workflows), o con `/web-setup`, que envía tu token de `gh`. Ese token tiene scope `admin:org`, así que es más arriesgado.
- **Resultado:** diff en la web → "Create PR" → `gh pr checkout` local.
- **API:** no hay una API general para crear sesiones. Solo existe el *Routines API trigger*, en research preview.
- **GitHub Actions** (`claude-code-action`) corre en runners de GitHub, no en cloud sessions.
- **Consumo:** las sesiones cloud comparten los límites de tu plan; los *usage credits* se cobran a tarifa API.
- **Limitaciones:**
  - La red por defecto ("Trusted") **no incluye APIs de LLM de terceros**: correr Gemini en la nube exige la opción Custom.
  - Las variables de entorno las lee cualquiera que use ese entorno.
  - Las sesiones deben quedar en **Private**.
- **Orchestrator 0.5.4 no puede lanzar ni seguir sesiones cloud** [V: su código no referencia `--cloud` ni `teleport`].

**No verificado:**
- Tus "~100 créditos" serían muy probablemente la **promoción de $100 para Pro en sesiones cloud**. Solo lo confirman fuentes secundarias: *reclamar antes del 7 oct, caduca el 4 nov*. → Comprueba el saldo en `claude.ai/settings/usage`.
- Si cubre `ultrareview` o routines.

**Recomendación:** la nube como **complemento opcional**, no en la ruta crítica. El único uso que compensa el setup (repo privado + GitHub App) es **1–2 tareas acotadas lanzadas en los primeros 15 min**: el harness de evaluación o una revisión independiente final vía PR. Automatizarlo desde el Orchestrator no está soportado; no lo intentes bajo presión de tiempo.

---

## 11. Gemini: primario de pago y respaldo

**Modelos y precios** [V, [pricing](https://ai.google.dev/gemini-api/docs/pricing), actualizado 2026-09-24; disponibilidad confirmada con una llamada a `models.list` usando tu clave, sin imprimirla]:

| Modelo | Entrada / salida por 1 M tokens | Uso |
|---|---|---|
| `gemini-3.5-flash-lite` | $0,30 / $2,50 | **Primario** (thinking `minimal`) |
| `gemini-3.1-flash-lite` | $0,25 / $1,50 (caché $0,025) | **Respaldo** (cuota separada por modelo) |
| `gemini-3.8-flash` | $0,75 / $3,75 hasta el 31-12-2026, luego ×2 | Solo si la calidad lo exige; no admite `minimal` |

**Condiciones de datos [V, [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms)]:**
- **Free / unpaid:** "used to improve… human reviewers may read… **Do not submit sensitive, confidential…**".
- **Paid:** no se usa para entrenar; solo se registra un tiempo limitado para detectar abusos.
- El acceso es "paid" **solo si el proyecto de Cloud tiene facturación activa**.
- Un proyecto de AI Studio sin facturación **sí da acceso programático gratuito real**, pero bajo las condiciones *unpaid* y con cuotas por modelo no publicadas (solo se ven en AI Studio).

**Configuración propuesta:**

```
LLM_PROVIDER=gemini                     # gemini | fake   (fake = CI/tests)
GEMINI_PRIMARY_MODEL=gemini-3.5-flash-lite
GEMINI_FALLBACK_MODEL=gemini-3.1-flash-lite
GOOGLE_API_KEY=<billed-project-key>      # NOTE: SDK prefers GOOGLE_API_KEY over GEMINI_API_KEY
GEMINI_FREE_API_KEY=<optional>           # never auto-selected
GEMINI_ALLOW_FREE_TIER=0
LLM_TIMEOUT_S=2.5
LLM_MAX_ATTEMPTS=2
```

**Taxonomía de errores:**

| Error | ¿Reintentar? | ¿Failover? | Comportamiento para el usuario |
|---|---|---|---|
| 429 por minuto | 1 vez, con jitter | Sí, al modelo de respaldo | Transparente |
| 429 cuota diaria | No | Sí | Transparente, con alerta al operador |
| 5xx / 503 / timeout | 1 vez (o ninguna, por latencia) | Sí | Transparente |
| 404 modelo inexistente | No | Sí; además error de configuración al arrancar | Transparente |
| 400 esquema inválido | No | No (es un bug) | Escalamiento seguro y log |
| Clave inválida / 403 facturación o región | No | No: **nunca** al free tier salvo opt-in | Escalamiento seguro; fallo rápido al arrancar |
| `finish_reason` SAFETY | No | No | `escalate` neutral |

- Los reintentos del SDK vienen **desactivados** por defecto, y sus valores por defecto (5 intentos, hasta 60 s) rompen el p95. Configurarlos explícitamente y de forma acotada [V].
- **Respaldo sin pago:** mi recomendación es **no implementarlo** en las 2 h. Queda como configuración documentada: cambiar de clave requiere opt-in explícito, y el free tier no debe procesar el material de la evaluación.
- **Riesgo:** ¿tu `GEMINI_API_KEY` pertenece a un proyecto con facturación? `models.list` no lo revela → compruébalo en AI Studio (Billing / Rate limits) y fija un presupuesto con alerta.
- **Riesgo para la calificación:** si los revisores solo tienen claves de Anthropic u OpenAI, un sistema solo-Gemini podría no ejecutarse en su lado → pregunta 2 al hiring manager. Si responden "Anthropic/OpenAI", se añade un segundo adaptador tras la misma interfaz `complete(messages, tools, schema)` (unos 15–20 min).

**Coste frente a la restricción de $0,0005 por pregunta** [cálculos de `research/gemini-report.md`; tokens estimados, **U** hasta medirlos]:

| Diseño | Modelo | Coste por pregunta |
|---|---|---|
| Bucle de 2 llamadas | 3.1 Flash-Lite, con caché | ≈ $0,0006 (justo encima del presupuesto) |
| 1 llamada con datos precargados | 3.1 Flash-Lite, con caché | ≈ **$0,00036 (unos $36/día) ✓** |
| — | 3.8 Flash o Claude Haiku 4.5 | ≈ $0,0012 ✗ |

→ Este es el núcleo "vivido" del ADR de coste/latencia: **qué sacrificas** (la segunda llamada, el thinking, el tamaño de modelo) y **cómo degradas** (timeout → respaldo → escalar).

---

## 12. Skills y MCP

**Auditoría [V, `claude mcp list` / `codex mcp list`]:**
- Tienes muchos conectores ajenos al proyecto: Notion, Gmail, Drive, Calendar, Figma, Excalidraw, pencil, Expedia y otros, varios sin autenticar.
- En Codex: azure, terraform, aws-knowledge, microsoft-learn, livekit-docs y eraser.

**Recomendación:**
- **Añadir como máximo uno:** el MCP oficial de documentación de Gemini (`https://gemini-api-docs-mcp.dev`, alojado por Google, solo lectura [V, [coding-agents](https://ai.google.dev/gemini-api/docs/coding-agents)]), y solo si confirmamos Gemini.
- **No añadir:** Context7 (documentación comunitaria, superficie de inyección), Spec Kit ni OpenSpec.
- **Desactivar durante la sesión de implementación** Notion, Gmail, Drive, Calendar, Figma, pencil, Excalidraw y el resto. Ahorra contexto y elimina el riesgo de que un agente suba material de la evaluación a servicios externos.
- **Mantener:** `codebase-memory-mcp` (opcional; el repo es pequeño).

---

## 13. Flujo de GitHub y estándares

- **Repositorio:**
  - **Directorio nuevo** (p. ej. `~/Documents/Sezzle/sezzle-support-agent`) con los datos **copiados** a las rutas documentadas (`data/policies/`, `data/orders.json`, `cases/golden_visible.jsonl`). Los originales no se tocan.
  - Repo **privado** en GitHub: permitido explícitamente por SUBMISSION.md, y la alternativa es el zip.
- **Estructura propuesta:**

  ```
  README.md  DECISIONS.md  PROMPTS.md  ITERATION.md  AGENTS.md  CLAUDE.md
  run_cases.py  pyproject.toml  uv.lock  .env.example  .gitignore
  specs/{requirements,tasks}.md
  src/support_agent/{config,data,facts,tools,prompts,agent,guards}.py
  src/support_agent/llm/{base,gemini,fake}.py
  data/policies/*.md  data/orders.json
  cases/{golden_visible,adversarial_dev,adversarial_holdout}.jsonl
  evals/score.py   evals/runs/<NNN>_<label>/{answers,trace}.jsonl + score.md
  tests/   .github/workflows/ci.yml
  ```

- **Commits:** Conventional Commits 1.0.0 con scopes `data`, `tools`, `agent`, `guards`, `llm`, `eval`, `docs`, `ci`, más la referencia al R-ID. Historia real: nada de reescribir ni fabricar.
- **Ramas:** `main` estable más ramas cortas `feat/<R-id>-slug`, una por worktree del Orchestrator, con merge en menos de ~30 min tras pasar `ruff` y `pytest`.
- **Protección de ramas:** **no disponible en repos privados con plan Free** [V, [GitHub plans](https://docs.github.com/en/get-started/learning-about-github/githubs-plans)]. No compres Pro: el gate es `orchestrator land` + CI + tu revisión, y así se documenta.
- **CI mínima:** gitleaks, `ruff check`/`format --check` y `pytest` con `LLM_PROVIDER=fake`, sin secretos ni coste. Unos 2.000 min/mes gratis en repos privados [V]. Las corridas reales de evaluación son locales y se commitean como artefactos.

---

## 14. Seguridad y confidencialidad

Informe completo en `research/security-report.md`, basado en el OWASP LLM Top 10 2025 ([genai.owasp.org](https://genai.owasp.org/llm-top-10/)). Controles **estructurales** (en código), por orden de prioridad:

1. **LLM02/LLM01:** `user_id` solo desde el harness, nunca como argumento de una tool; filtrado *antes* de buscar; not-found idéntico para pedidos ajenos e inexistentes (no hay oráculo); el validador bloquea `ord_` ajenos.
2. **LLM06:** solo herramientas de lectura; el escalamiento es un campo estructurado; se bloquean afirmaciones de acción ("I've rescheduled/waived/paused").
3. **LLM09:** hechos derivados en código; validador de números y fechas contra el conjunto anclado, con normalización ("two weeks" = "14 days").
4. **LLM07:** el prompt no contiene secretos ni lógica de autorización, y lleva un canary.
5. **LLM05:** esquema y enum validados; texto plano.
6. **LLM10:** límite de longitud de entrada, `max_output_tokens`, ≤2 rondas de tools y timeout.
7. **Fraude:** el pre-clasificador fuerza el escalamiento y retira las tools de pedidos; el validador redacta detalles.

**Higiene:**
- Claves solo en `.env`, que se añade a `.gitignore` **antes del primer commit**; `.env.example` con placeholders.
- gitleaks antes de cada push o zip.
- Revisar `PROMPTS.md`, trazas y capturas en busca de claves.
- Clave dedicada con **alerta de presupuesto**, revocada tras la entrega.
- Nada de free tier, despliegue público, Notion/Drive ni gists.

**Casos adversariales:** hay 29 en borrador en `research/adversarial_cases.draft.jsonl` (IDOR, inyección, exigencias de exención, límites de reprogramación, reembolsos, fraude). **Hay que revisarlos** antes de usarlos. Los generó un agente y algunas etiquetas de ruta son discutibles (adv14, adv21, adv29).

---

## 15. Despliegue y coste a 21 días

**Recomendación: no desplegar.**
- Los revisores califican localmente con `run_cases.py`.
- Una URL pública roza el "don't post publicly", expone tu presupuesto de Gemini y consume minutos de las 2 h.

**Si quieres una demo de ~21 días** (detalle en `research/deploy-report.md`):

| Opción | Coste de hosting | Inconvenientes |
|---|---|---|
| **Cloud Run** (min 0 / max 1 instancias, `X-Demo-Key`, tope de 3.000 preguntas en la app, Secret Manager, alerta a $10) | $0 dentro del free tier [V] | Requiere facturación en GCP; los presupuestos **alertan pero no cortan** [V] |
| Render Free | $0 | Arranque en frío de ~1 min, sin opción privada |
| HF Spaces | Docker requiere PRO | — |
| Fly / Railway | Pequeño pero > 0 | — |

**Coste total a 21 días (Gemini + hosting):**
- Mejor caso (200 preguntas): **≈ $1**.
- Esperado (2.000 preguntas): **≈ $4–8**.
- Acotado (tope de la app): **≤ $12**.
- Las cifras de tokens por pregunta son supuestas [U].
- Ningún free tier garantiza disponibilidad continua.

**Runbook de despliegue, rollback y teardown:** en el informe de despliegue (comandos `gcloud` no ejecutados).

---

## 16. Estrategia de evaluación

- **Conjuntos:**
  - `golden_visible` (10).
  - `adversarial_dev`: unos 20 casos revisados de los 29.
  - `adversarial_holdout`: unos 9 que **no se miran al iterar**. Es la prueba honesta de "build for the problem, not the ten cases".
- **Puntuación** (`evals/score.py`): `must_include` y `must_not_include` con `re.I`, coincidencia exacta de `route`, métricas agregadas y por categoría, latencia p50/p95, tokens y coste estimado por caso.
- **Taxonomía de fallos:**

| Categoría | Qué indica |
|---|---|
| `ROUTE_MISS` | Ruta equivocada |
| `GROUNDING_MISS` | Falta un hecho requerido |
| `HALLUCINATION` | Número o fecha no anclado |
| `UNSAFE_PROMISE` | Promete una exención o acción |
| `AUTHZ_LEAK` | Revela datos de otro usuario |
| `OVER_ESCALATION` | Escala cuando no tocaba |
| `REGEX_PHRASING` | Respuesta correcta que falla por la redacción; se documenta y no se "trampea" |
| `CONTRACT` / `PROVIDER_ERROR` | Formato de salida o fallo del proveedor |

- **Iteración obligatoria:**
  1. Corrida 001 como *baseline*: se commitea intacta.
  2. Diagnóstico por categoría.
  3. Cambio mínimo y justificado.
  4. Corrida 002…N.
  5. Tabla de delta en `ITERATION.md`.
  6. Corrida final que incluye el holdout.
- **Fallos del proveedor:** se prueban con el `FakeLLM` y con la inyección de 429/503/timeout en tests, para no gastar ni depender de la red.
- **Honestidad:** no se fabrican puntuaciones y se reporta lo que falle en el holdout.

---

## 17. Checklist de preparación (antes de arrancar el reloj)

Solo cosas **no específicas de la aplicación**, o que se declaran explícitamente:

- [ ] Tomar las decisiones de la §20.
- [ ] Enviar las preguntas al hiring manager (§3) y decidir si esperar la respuesta.
- [ ] En AI Studio: confirmar que la clave es de un proyecto **con facturación**, ver las cuotas de los dos modelos Flash-Lite y fijar una alerta de presupuesto (~$10).
- [ ] Comprobar el saldo o la promoción de Claude Cloud en `claude.ai/settings/usage`, solo si decides usarla (fecha límite no verificada: 7 oct).
- [ ] Actualizar el Orchestrator si lo apruebas (la comprobación de versión pide reinstalar una vez desde la fuente original).
- [ ] Desactivar para la sesión los MCP ajenos (§12).
- [ ] Revisar y podar los 29 casos adversariales y separar `dev` / `holdout`.
- [ ] Convertir este informe en `AGENTS.md` + `specs/requirements.md` + `specs/tasks.md` (en inglés), **si decides que la redacción de specs cuenta como preparación declarada**.
- [ ] Planificar el arranque con Codex con margen (su ventana de 5 h se reinicia hoy a las 21:48).

---

## 18. Asignación del tiempo cronometrado (120 min)

| Minutos | Ruta crítica (implementador + lead) | En paralelo |
|---|---|---|
| 0–10 | `git init`, copia de datos, `uv` + dependencias, `.gitignore`/`.env.example`, specs finales, `FakeLLM` | — |
| 10–45 | Loader + `facts.py` (hechos derivados, con tests) → tools con scope → prompt → bucle Gemini → salida estructurada → `run_cases.py` | Harness de evaluación (`evals/score.py` + taxonomía) |
| 45–55 | **Corrida 001 (baseline)** sobre golden + adversarial_dev; commit sin tocar | — |
| 55–85 | Diagnóstico → validador y guards → ajustes de prompt → corridas 002/003 | Revisión independiente (Codex) del diff |
| 85–95 | **Corrida final** incluido el holdout; latencia p95 y coste medidos | — |
| 95–115 | `DECISIONS.md` (3 ADRs), `ITERATION.md`, `README.md` (con lo inacabado), `PROMPTS.md` | — |
| 115–120 | gitleaks, push o zip. **Parar.** | — |

**Reglas del reloj:**
- Si en el minuto 45 no hay baseline, se cambia al **fallback de una llamada**.
- La UI, el despliegue y el segundo adaptador de proveedor solo entran si sobra tiempo; si no, se mencionan en "unfinished".

**Tres ADRs sugeridos:**
1. *Dónde viven los guardrails* (código frente a prompt).
2. *Recuperación* (contexto completo frente a BM25 frente a embeddings).
3. *Coste y latencia* (bucle de 2 llamadas frente a una llamada precargada, tamaño de modelo, caché, degradación).

---

## 19. Riesgos principales y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Los revisores no pueden ejecutar Gemini | Hidden set sin correr | Preguntar al hiring manager; interfaz de proveedor lista para un 2.º adaptador |
| Sobreajuste a los 10 casos golden | Mala nota en el hidden set | Holdout adversarial intacto; reglas generales, no casos concretos |
| Fallos de regex por subcadenas negadas ("waived") | Fallos falsos | Validador de frases prohibidas y guía de estilo en el prompt |
| Aritmética de fechas del LLM | Alucinaciones | Hechos derivados en código, con tests |
| p95 > 3 s con 2 llamadas | ADR débil | Medir desde la corrida 001; thinking `minimal`; timeouts acotados; fallback de una llamada |
| Errores de *thought signature* en Gemini 3 / modelos nuevos | Bucle roto | Reenviar el content íntegro; IDs de modelo fijados; respaldo 3.1 |
| Sobrecarga de orquestación | Se agota el tiempo | 1 implementador + 1 tarea paralela disjunta + revisor; nube fuera de la ruta crítica |
| Tiempo de preparación mal declarado | Pérdida de confianza | Registro de tiempo honesto y `PROMPTS.md` con la fase de planificación incluida (incluido este prompt maestro) |
| Filtración de clave o material | Grave | gitleaks, `.env` ignorado, sin free tier, sin despliegue público, MCP ajenos desactivados |
| Anomalías de datos | Respuestas inconsistentes | Supuestos explícitos en el README; pregunta 4 al hiring manager |

---

## 20. Decisiones que requieren tu aprobación

1. **Contabilidad del tiempo:** ¿el reloj de 2 h incluye escribir specs y revisar los casos adversariales, o los declaramos como preparación previa? *Recomiendo:* declararlo todo con tiempos en el README y `PROMPTS.md`; empezar el reloj en `git init`.
2. **Preguntas al hiring manager:** ¿envío las 5 de la §3 (o un subconjunto)? ¿Esperamos respuesta antes de implementar? *Recomiendo:* enviar las 1–3 y 5; esperar como máximo hasta mañana.
3. **Proveedor:** Gemini de pago (`3.5-flash-lite` / `3.1-flash-lite`), condicionado a confirmar que la clave es de un proyecto con facturación. ¿Segundo adaptador (Anthropic/OpenAI) solo si el hiring manager lo pide?
4. **Arquitectura:** ¿apruebas la primaria de la §7 y el fallback de una llamada con el umbral del minuto 45?
5. **Repositorio:** ¿directorio nuevo + repo **privado** en GitHub (`gh repo create --private`) + CI, o solo local + zip?
6. **Estrategia de agentes:** lead + 1 implementador Claude + 1 teammate para el harness + revisor Codex. ¿De acuerdo?
7. **Claude Cloud:** ¿no usarlo (recomendado) o usarlo para 1–2 tareas acotadas (requiere instalar la GitHub App en el repo privado)?
8. **Despliegue:** ¿ninguno (recomendado) o Cloud Run protegido con ≤ $12 acotado?
9. **Herramientas:** ¿añadir el MCP oficial de documentación de Gemini y desactivar los MCP ajenos durante la sesión?
10. **Orchestrator:** ¿reinstalo o actualizo desde su fuente (la comprobación de versión lo indica)?

---

## Hoja de ruta de preparación priorizada

1. Tú: decisiones 1–5 de la §20 (desbloquean todo lo demás).
2. Tú: verificar la facturación y las cuotas de la clave de Gemini en AI Studio y fijar una alerta de presupuesto.
3. Lead: redactar el correo al hiring manager (en inglés) para que lo envíes.
4. Lead + tú: revisar y podar los casos adversariales y separar dev/holdout.
5. Lead: generar `AGENTS.md`, `CLAUDE.md`, `specs/requirements.md` y `specs/tasks.md` (en inglés) y los prompts por etapa (cortos, secuenciales, con criterios de aceptación).
6. Tú: preparar la sesión (MCP desactivados; Codex con margen) → **arrancar el reloj con tu autorización explícita**.

*Espero tu autorización explícita antes de pasar a cualquier implementación.*
