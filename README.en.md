# Super Scholar V3.11.0

Docker: run `docker compose up -d --build --wait`, then open `http://127.0.0.1:3000`. See [Docker deployment](DOCKER_DEPLOY.md) for persistence, configuration, and limitations.

Super Scholar is a local-first computer-science publication-venue assistant. The current product flow is:

```text
Landing → Workspace → Project → Materials → Research Profile → Publication Preferences → Recommendations → Compare → Select Venue
```

V3.10 retains the hardened research-evidence and scholarly-connection layers, then upgrades recommendation with venue-conditioned recent-work retrieval and a strict separation between academic fit and current submission actionability.


## V3.11 journal metadata enrichment + evidence explorer

V3.11 keeps the V3.10 venue-conditioned ranking pipeline and completes the journal recommendation metadata path without inventing unavailable values.

- **OpenAlex public journal metadata.** Resolved journal Sources now expose source-level fully-OA/DOAJ flags, published APC list prices when OpenAlex has them, and `2yr_mean_citedness` as a clearly labelled public citation statistic. The latter is never renamed to Journal Impact Factor.
- **APC conversion is evidence-backed.** When OpenAlex provides `apc_usd`, Super Scholar derives CNY using the latest available ECB EUR reference rates for USD and CNY and stores the FX date/provider/source alongside the converted amount. Missing APC or FX remains unavailable rather than guessed.
- **Clarivate is the optional authority for WoS/JCR/JIF.** A separately encrypted Web of Science Journals API key can be configured from Scholarly Data Sources. Only successfully resolved Clarivate records populate WoS edition, JCR quartile and JIF. Without an entitled key, Preferred constraints are marked N/A and do not pollute ranking; Required constraints remain unverifiable and therefore fail safely.
- **Review speed stays honest.** There is no unified cross-publisher public review-time API in this release. Preferred review-speed constraints therefore become N/A rather than repeated “Unknown”; Required review-speed constraints remain unverifiable.
- **Evidence explorer retains all returned works.** The UI shows the top 5 OpenAlex/Semantic Scholar works by default and can expand to every work actually returned and persisted in the recommendation run. No hidden evidence is silently discarded at the display layer.
- **Journal cards and compare view avoid fake Unknown clutter.** They show verified JIF/JCR/WoS where available, public OA/APC/ECB data where available, and otherwise use explicit `未核验`/`N/A` semantics rather than presenting unsupported fields as if a failed lookup produced a number.

Alembic revision `20260902_0009` adds the optional Clarivate scholarly-source settings.

## V3.10 venue-conditioned retrieval + actionability

V3.10 makes venue ranking depend primarily on evidence from the candidate venue itself instead of aggregate Source-topic histograms. It also separates **academic fit** from **current submission actionability**.

- **Venue-conditioned OpenAlex retrieval.** After bounded candidate identity resolution, Super Scholar runs semantic search inside each high-priority candidate Source (or the recent annual Sources that represent a conference series) over roughly the most recent five publication years. A successful checked query with no close works is a verified zero; an unresolved Source or failed request remains Unknown.
- **Conference series are not forced into one OpenAlex Source.** Recent yearly proceedings Sources are aggregated conservatively, while workshops, companion volumes, tutorials, doctoral consortia and similar side events are excluded. Journals continue to prefer stable ISSN-based Source identity.
- **Academic Fit and Current Actionability are separate.** A venue can remain an excellent academic target even when its current conference deadline is closed or not yet verifiable. The `当前可投` view contains only conference editions whose current actionability is actually verified as open and whose Required actionability constraints pass.
- **Structured bibliography matching.** Short/common acronyms such as FAST, CASE, DATE, CHI and SC require bibliography/venue context; ordinary prose such as “a fast segmentation network” no longer creates a false venue prior.
- **CCF semantics are strict.** The seventh-edition directory is validated as **295 official journal placements** and canonicalized to **291 unique journal identities** where the same journal appears in more than one CCF category. `U` means CCF status is not verified; `N` is used only when a complete verified catalog was available and the venue was confirmed absent. CCF remains preference metadata and does not enter Research Match.
- **Source topics are auxiliary only.** Aggregate OpenAlex Source topics contribute only 4% of Research Match. The nominal content weights are 48% venue-conditioned recent works, 14% global OpenAlex direct-publication evidence, 18% CS subfield scope, 8% Semantic Scholar, 8% structured References and 4% Source topics; missing signals are omitted and the available weights are renormalized.

Research Match and Academic Fit are evidence/fit scores, not acceptance probabilities. No JCR/JIF/APC/review-speed value is fabricated when an authoritative source is unavailable.

## V3.9.1 candidate Source resolution + provider-profile persistence

V3.9.1 fixes two gaps discovered during live recommendation use:

- **OpenAlex Works health is now separated from candidate Venue Source resolution.** After semantic Works retrieval, a bounded research-relevant slice of CCF/CCFDDL catalog candidates is actively resolved through OpenAlex Sources. Journals prefer exact ISSN lookup; conferences/journals without ISSN use Source search over canonical/alternate/abbreviated names plus a conservative local identity threshold. Only confidently resolved identities receive `openalexSourceId` and Source topics. Recommendation health now reports `OpenAlex 论文 Sources` and `OpenAlex 候选 Venue Sources` separately, including attempted/resolved/topic counts.
- **OpenAI / DeepSeek / Custom configurations persist independently.** A new `ai_provider_profiles` table stores each provider's Base URL, model, protocol, output mode, capability flags and encrypted API key. Switching the active provider no longer overwrites another provider. The settings UI also keeps unsaved per-provider drafts during the current page session.
- **Semantic Scholar anonymous 429 is explicit.** Public-pool rate limiting is reported as `Limited / rate_limited`, and the settings panel links directly to the official API-key request form: `https://www.semanticscholar.org/product/api#api-key-form`.
- OpenAlex diagnostics now additionally exercises the same **candidate Venue → Source** identity-resolution path used by recommendation, so a green Works/Source hydration check cannot be mistaken for proof that catalog candidates were enriched.

Alembic revision `20260829_0008` adds `ai_provider_profiles` and migrates the currently active legacy provider configuration without exposing/decrypting the stored secret.

## V3.9 scholarly connections + recommendation reliability

The **App → 系统连接与解析 → 学术数据源** panel now configures the real external scholarly services used by recommendation:

- **OpenAlex** — primary semantic scholarly graph. A free API key can be stored encrypted; anonymous access is supported but is labelled `Limited`. Diagnostics separately exercise the rate-limit/authentication endpoint, semantic Works search, Source hydration, and Source topics.
- **Semantic Scholar** — independent paper/publication-venue evidence. Its API key is optional but recommended and is stored encrypted when supplied.
- **DBLP** — keyless computer-science venue canonicalization. It is used conservatively for dynamic conference Sources discovered from OpenAlex.
- **Crossref** — DOI/ISSN/journal identity and publisher verification. Public access works without credentials; a contact email enables polite access; an existing Metadata Plus token can be stored encrypted.
- **CCF official + CCFDDL + local manuscript References** remain managed evidence sources and require no secret.

A single “connection succeeded” badge is no longer enough. The settings page runs a real multi-step diagnostic, while each recommendation run persists `dataSourceHealth`. The Recommendation page displays `Ready / Limited / Degraded` per source and links back to settings when an enrichment path is unavailable.

V3.9 also tightens venue identity and evidence scoring:

- OpenAlex Source hydration uses the documented `ids.openalex` identity filter with a bounded single-Source fallback; Source `topic_share` is preferred before frequency-only `topics` when available.
- Direct publication-source matching is conservative (exact canonical/acronym identity or high distinctive-token overlap) so short/common venue tokens cannot give unrelated venues identical “direct paper” evidence.
- Semantic Scholar contributes an independent direct-publication-venue component rather than being folded into OpenAlex.
- Crossref and DBLP enrich aliases/identity; they do not create semantic fit by themselves.
- Manuscript venue prior is extracted only from the actual References/Bibliography tail, preventing publisher watermarks or front matter from leaking a known venue label into ranking.
- Missing evidence is represented as `null/Unknown` and omitted from the Research Match denominator. It is never displayed as zero evidence unless a real checked mismatch produced zero.

The V3.9 Research Match uses the available subset of these components, renormalized at runtime: **OpenAlex related-paper venue evidence (25%) + OpenAlex Source topic fit (25%) + CS subfield scope fit (22%) + Semantic Scholar publication-venue evidence (12%) + manuscript References prior (12%) + CCF area weak prior (4%)**. Research Match remains a fit/evidence score, **not an acceptance probability**.

V3.8 retains the V3.7.1 hardened research-evidence layer: final synthesis is salvaged field-by-field, PDF figures/tables are reconstructed as caption-anchored crops, and evidence chips now open an interactive source viewer instead of exposing raw internal IDs.


## V3.8 CS hybrid-evidence venue recommendation

V3.8 replaces the V3.7 direct-source-only recommender with a multi-evidence retrieval/ranking pipeline. CCF/CCFDDL is now a **verified metadata layer**, not the candidate universe: OpenAlex sources discovered from the manuscript's semantic neighborhood can become additional journal/conference-series candidates when the user did not require CCF.

Research Match is built from available evidence and renormalizes when a source is unavailable: **related-paper publication evidence (30%) + OpenAlex Source topic fit (30%) + CS subfield scope fit (25%) + manuscript References venue/community prior (12%) + CCF area weak prior (3%)**. One direct related-paper hit cannot become 100 merely because all other venues have zero hits; several high-ranked hits are required for saturation. If OpenAlex is unavailable, the system falls back to CS-scope + bibliography + weak CCF-area evidence and caps confidence.

The bibliography prior is extracted only from the References/Bibliography tail. Front-matter text such as “This CVPR paper is the Open Access version” is deliberately excluded so regression tests with already-published papers do not leak their true venue into that signal. Generic words such as “agent” are also excluded from the multi-agent ontology: a model implemented as several internal agents is not therefore an AAMAS paper.

OpenAlex-only conference series are allowed as semantic discovery candidates, but they display `TBD / 未核验` for the current edition, deadline and location until CCFDDL/official metadata resolves them. Required deadline/location constraints therefore still reject unverifiable candidates; Preferred unknown remains neutral.

## V3.7 CS venue-recommendation flow

The current scope is intentionally limited to **computer science** and stops after the user selects a target venue:

```text
Upload research
      ↓
Evidence-grounded research understanding

V3.7.1 also separates **page/evidence coverage** from **raw character sampling** in the
AI request plan. A low character-sampling percentage is a provider-budget compression
signal, not a claim that the remaining PDF pages were ignored.
      ↓
CCF / CCFDDL candidate catalog
      +
OpenAlex semantic search over similar scholarly works
      ↓
Aggregate where the most similar works were published
      ↓
Required constraint filter
      ↓
Semantic fit + Preferred preference reranking
      ↓
Top-N conferences / journals
      ↓
Compare → Select Venue
```

Important V3.7 rules:

- CCF category is a **weak prior**, never the main research-fit score.
- Direct OpenAlex evidence that semantically similar works were published in a venue dominates Research Match.
- If OpenAlex is unavailable, the system explicitly uses a low-confidence fallback and caps the score so unrelated venues in the same CCF area cannot all receive a fabricated high fit.
- Conference deadline/location/edition data come from CCFDDL; CCF rank/category are overlaid from the official CCF seventh-edition directory when the official pages are available.
- Required unknown fields remain disqualifying; Preferred unknown fields are neutral rather than presented as satisfied.
- Research Match is **not an acceptance probability**.
- Existing pre-V3.7 venue caches are schema-checked and automatically refreshed after an in-place upgrade; if an upstream source is temporarily unavailable, the last successful cache remains an explicitly stale fallback.

### PDF visual evidence

Caption-anchored **Figure / Table crops** are now the primary visual evidence. PyMuPDF page geometry is used to reconstruct a logical figure from vector/raster components around its caption; detected tables are merged by caption before rendering. Full-page renders remain fallback/navigation artifacts, and raw embedded image blocks remain trace-only because they can be fragments of one composite figure.

### Human-readable evidence

Stable internal IDs such as `ev_material_<uuid>_pdf_page_5` are retained for grounding and validation, but the UI renders labels such as `论文 · p.5`, `论文 · Figure 4 · p.5`, `代码 · models/model.py`, or `结果 · Sheet1`. Hovering shows a human-readable source preview. Clicking a chip opens an evidence viewer; PDF evidence is positioned at the cited page, while Figure/Table evidence opens the reconstructed crop with a link back to the original page. The raw ID is hidden inside collapsed technical trace details.

### Scholarly data-source configuration

The primary configuration surface is **App → 系统连接与解析 → 学术数据源**. Secrets are encrypted before SQLite persistence and only masked hints are returned to the browser. Headless deployments may use environment fallback values:

```text
SUPER_SCHOLAR_OPENALEX_API_KEY=
SUPER_SCHOLAR_OPENALEX_MAX_RESULTS=50
SUPER_SCHOLAR_CROSSREF_EMAIL=
SUPER_SCHOLAR_CROSSREF_API_KEY=
SUPER_SCHOLAR_SEMANTIC_SCHOLAR_API_KEY=
# Optional paid/entitled Clarivate Web of Science Journals API. Prefer the UI.
SUPER_SCHOLAR_CLARIVATE_JOURNALS_API_KEY=
SUPER_SCHOLAR_CLARIVATE_JOURNAL_LIMIT=36
SUPER_SCHOLAR_SCHOLARLY_REQUEST_TIMEOUT_SECONDS=20
```

Blank values mean “not configured”; they are not demo credentials. DBLP, CCF and CCFDDL do not require API keys. OpenAlex anonymous access may still work at the basic keyless budget, but the UI intentionally reports it as `Limited` rather than `Ready`.

## Research-understanding flow

### 1. Automatic local baseline

After usable materials are parsed, the browser automatically creates a deterministic local research profile. This stage does not call an external LLM.

### 2. Optional AI deep understanding

The user explicitly starts AI analysis from Research Profile. The backend then performs:

```text
PDF / DOCX / LaTeX / source ZIP / spreadsheet / image
                    ↓
              local parsing
                    ↓
     native text / table / OCR / code evidence
                    ↓
             text evidence selection
                    ↓
       small text-only provider requests
                    ↓
          compact grounded research facts
                    ↓
        optional one-image-at-a-time vision
                    ↓
          compact visual observations
                    ↓
        one compact text-only synthesis
                    ↓
          evidence-ID hard validation
                    ↓
               Research Profile
```

The normal V3.6 pipeline does **not** upload the original PDF file to the model provider.

## Why text and images are separate

A provider that is good at text does not necessarily support image/file inputs, and an OpenAI-compatible gateway does not necessarily implement every OpenAI feature. V3.6 therefore does not require one request to combine text, images, structured output, Files API and reasoning. V3.6.1 additionally salvages locally-invalid JSON fields from successful paid extraction calls instead of aborting the whole run.

- Text extraction requests contain text only.
- Vision requests contain exactly one visual asset each.
- Vision is optional; failed vision does not discard already-completed text extraction.
- Final synthesis contains compact extracted facts only, never the full document again.
- If final synthesis fails after successful extraction, Super Scholar preserves the paid extraction results and deterministically assembles a partial grounded profile locally instead of retrying the provider.

## Provider-specific adapters

### OpenAI

Default preset:

- Responses API;
- structured output;
- streaming enabled;
- vision enabled;
- SDK retries disabled.

### DeepSeek

V3.6 treats DeepSeek as a text provider instead of pretending it is identical to OpenAI.

Default preset:

```text
Base URL        https://api.deepseek.com
Model           deepseek-v4-pro
Protocol        Chat Completions
Output          JSON Object
Streaming       enabled
Vision          disabled
Files           disabled
```

DeepSeek text requests use a plain string user message. Scanned/image-only material must first become text through local OCR, or the user can select a separate vision-capable provider instead.

### Custom OpenAI-compatible provider

No capability is assumed from the phrase “OpenAI-compatible”. The user configures the exact Base URL, model, protocol, output mode and capabilities in **App → 模型与解析**.

With transport profile `auto`, a custom provider uses the conservative Edge-safe profile:

- text chunk ceiling: 2,800 characters;
- short extraction output;
- text and vision never mixed;
- at most one optional visual call;
- synthesis reasoning disabled;
- SDK automatic retries disabled.

## No hidden retries

V3.6 creates the OpenAI-compatible SDK client with:

```python
max_retries=0
```

Super Scholar also does not automatically resend a failed provider request. One planned provider call corresponds to at most one real HTTP request. The first failed text-extraction call stops the run.

## Connection diagnostics

The Model & Parsing settings page performs separate real checks for:

- basic text;
- SSE streaming when enabled;
- selected structured-output mode;
- **researchProbe** — a small text-first extraction shaped like the real research pipeline;
- vision when enabled;
- Files API when enabled (optional unless direct-file use is explicitly required).

`researchProbe` is intentionally more meaningful than a one-word “OK” test. If it fails, the user should fix provider compatibility before sending a real manuscript.

Failed research calls persist safe diagnostics where available:

- pipeline phase;
- actual provider call count;
- HTTP status;
- provider request ID;
- safe response headers;
- input character count;
- visual count;
- approximate payload bytes;
- elapsed time;
- provider error body preview;
- local JSON/Pydantic validation failure separately from provider transport failure.

API keys and full research prompts are not written into diagnostics.

## Transport profiles and cost guard

The settings page exposes:

```text
Analysis profile      auto / standard / edge_safe
Text chunk size
Maximum real API calls
Chunk output tokens
Synthesis input ceiling
Request timeout
```

Effective built-in safety limits:

```text
Custom + auto (Edge-safe)
  text chunk          <= 2,800 chars
  chunk output        <= 1,100 tokens
  synthesis packet    <= 7,000 chars
  synthesis output    <= 2,000 tokens
  optional visual     <= 1 image
  synthesis reasoning disabled

DeepSeek standard
  text chunk          <= 6,000 chars
  chunk output        <= 900 tokens
  synthesis packet    <= 10,000 chars
  synthesis output    <= 2,000 tokens
  vision disabled

OpenAI standard
  uses the configured bounded values
```

The hard project-level provider call budget includes text extraction, optional vision calls and final synthesis.

## OCR

OCR is optional and local. Native PDF text is preferred. Tesseract is used only for low-text PDF pages or image material when configured and available.

Windows example:

```text
C:/Program Files/Tesseract-OCR/tesseract.exe
```

Languages:

```text
eng
eng+chi_sim
```

Use **模型与解析 → 保存并检测 OCR** to verify the executable and installed language packs.

## Backend setup

Requirements: Python 3.11+.

```bash
cd backend
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Linux/macOS:

```bash
source .venv/bin/activate
cp .env.example .env
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health/API docs:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
```

## Frontend setup

Requirements: Node.js 20+ and npm.

```bash
cd frontend
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env.local
npm install
npm run dev
```

Linux/macOS:

```bash
cp .env.example .env.local
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

`npm run dev` and `npm run build` first clear stale `.next` / `.turbo` caches, preventing old dynamic-route manifests after an in-place upgrade.

## Upgrading from V3.1–V3.5

Back up these together before replacing code:

```text
backend/data/super_scholar.db
backend/data/.credential_key
backend/storage/
```

The credential key is required to decrypt API keys already saved from the Settings page.

Then run:

```powershell
cd backend
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
```

Relevant later migrations include:

```text
20260828_0006_text_first_provider_adapters
20260829_0007_scholarly_data_settings
```

The V3.9 migration adds scholarly-source settings separately from AI-provider settings. Existing projects/materials and previously encrypted AI keys are not rewritten. Keep `backend/data/.credential_key` when upgrading so existing encrypted secrets remain readable.

## V3.5 UI/route fixes retained

- Settings switches use a fixed, non-deforming track/thumb component.
- Connection diagnostics stay in normal document flow; no sticky panel covers results.
- Dynamic project pages recover a missing browser project directly from the backend before showing “not found”.
- frontend dev/build scripts clear stale Next/Turbopack caches.

## Verification performed for this package

See `V3.9_NOTES.md` for the exact checks performed for this build. The current backend suite passes 58 tests, the Alembic chain upgrades through `20260829_0007`, Python compilation succeeds, and the modified TS/TSX files pass TypeScript syntax diagnostics. A full Next.js production build is not claimed unless frontend dependencies are installed in the target environment.

