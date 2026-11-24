# Super Scholar V3.9 — data, evidence and integration provenance

## V3.9 recommendation evidence roles

The venue recommender now treats scholarly connectivity as a first-class, diagnosable dependency. No source is silently treated as present merely because a configuration field exists.

- **OpenAlex Works** is the primary semantic-neighborhood source. A free API key is recommended for a larger personal budget; anonymous/keyless access is accepted only as a `Limited` state.
- **OpenAlex Sources** hydrate real publication venues with canonical identity, aliases, ISSN, OA metadata and aggregate `topic_share`/`topics`. Missing Source enrichment is Unknown, not a zero-fit claim.
- **OpenAlex candidate Source resolution (V3.9.1)** is a separate stage from semantic-Work Source hydration. A bounded shortlist of catalog Venue candidates is resolved by exact ISSN where available or by Source search plus conservative name/type identity scoring. A successful Works diagnostic therefore no longer implies that every candidate Venue has Source topics; the run reports attempted/resolved/topic counts independently.
- **Semantic Scholar Academic Graph** is an independent second paper/publication-venue evidence source. Its output does not overwrite OpenAlex and is scored separately.
- **DBLP venue search** is a keyless CS-specific canonicalization layer for conference/source aliases. Its matches are conservative identity evidence only.
- **Crossref REST API** verifies journal identity through ISSN and supplies canonical title/publisher metadata. Public access requires no credential; a contact email enables polite access; an existing Metadata Plus token is optional. Crossref is not used as a semantic ranker.
- **CCF official seventh edition / CCFDDL** provide ranking and actionable conference-edition metadata where available. CCF/CCFDDL are metadata authorities, not the unrestricted candidate universe unless the user makes CCF a Required condition.
- **Manuscript References** provide a low-weight community prior extracted strictly from the References/Bibliography tail. Front matter, publisher watermarks and known publication labels are excluded.
- **CS subfield scope ontology** is a deterministic guardrail for major CS venue families and remains available when external graphs are degraded.

Nominal Research Match weights, renormalized over the evidence that actually exists:

```text
OpenAlex related-paper venue evidence    25%
OpenAlex Source topic fit                25%
CS subfield scope fit                    22%
Semantic Scholar publication venue      12%
Manuscript References prior              12%
CCF area weak prior                       4%
```

Research Match is a venue-fit/evidence score, not an acceptance probability. `null/Unknown` is distinct from a verified zero and is preserved through the API/UI.

### Scholarly source configuration

The preferred configuration surface is **App → 系统连接与解析 → 学术数据源**. Secret values are encrypted locally before SQLite persistence; GET APIs return masked hints only. Headless/legacy environment fallback:

```text
SUPER_SCHOLAR_OPENALEX_API_KEY=
SUPER_SCHOLAR_OPENALEX_MAX_RESULTS=50
SUPER_SCHOLAR_CROSSREF_EMAIL=
SUPER_SCHOLAR_CROSSREF_API_KEY=
SUPER_SCHOLAR_SEMANTIC_SCHOLAR_API_KEY=
# Official key request: https://www.semanticscholar.org/product/api#api-key-form
SUPER_SCHOLAR_SCHOLARLY_REQUEST_TIMEOUT_SECONDS=20
```

Blank values mean unconfigured; no credential or fabricated quota is bundled. DBLP, CCF and CCFDDL require no API key. The obsolete OpenAlex `mailto` polite-pool setting is not used.

### Runtime diagnostics and provenance

`POST /api/v1/settings/scholarly/test` performs bounded real requests:

1. OpenAlex rate-limit/auth state;
2. OpenAlex semantic Works;
3. OpenAlex Source hydration;
4. OpenAlex Source topics;
5. candidate Venue → OpenAlex Source identity resolution;
6. Crossref Works + ISSN→journal resolution;
7. Semantic Scholar paper search;
8. DBLP venue search.

Recommendation runs persist a `dataSourceHealth` snapshot so historical rankings retain the state under which they were produced. `Ready`, `Limited`, `Degraded`, `Error`, and `Disabled` are not interchangeable.

## 1. User research materials

Uploaded research files are stored by the local FastAPI backend under `backend/storage/` and represented by material rows in SQLite.

V3 deterministic parsers:

- PDF: PyMuPDF native text, table detection, embedded raster images, selected page renders; selective OCR on low-text pages when Tesseract is available.
- DOCX: python-docx paragraph/table traversal plus embedded media extraction.
- ZIP/source: Python zip parser with archive path validation, source-type filtering, notebook cell normalization, repository metadata and bounded source evidence.
- Spreadsheet: openpyxl for XLSX, xlrd for XLS, CSV/TSV parser for delimited text.
- Images: dimensions + persisted visual artifact; optional local OCR when Tesseract is available.

Every structured text evidence item receives an evidence ID. Every extracted visual asset receives an artifact ID.

## 2. OCR

OCR is local and optional. V3 uses Tesseract through `pytesseract` only when a usable Tesseract executable is detected/configured.

OCR is not run indiscriminately on every PDF page. Low-text pages are the main OCR candidates because OCR is substantially more expensive than native PDF text extraction.

If Tesseract or a requested language pack is missing, V3 records OCR as unavailable/failed and continues with the other parsers.

## 3. Research understanding and provider configuration

V3.6 supports OpenAI, DeepSeek, and custom OpenAI-compatible providers from **App → 模型与解析**. The settings page is the primary configuration surface; `.env` remains a fallback for headless/legacy startup.

Saved API keys are encrypted locally before SQLite persistence. The browser receives only a masked hint.

### Text-first / vision-separate data flow

The normal V3.6 AI path does not upload the original PDF. Deterministic local parsers first produce evidence IDs and visual artifact IDs. AI analysis then sends:

1. bounded **text-only** evidence chunks;
2. optional visual assets **one image per request**, only after text extraction has succeeded;
3. one final **text-only** synthesis packet containing compact grounded facts rather than the original manuscript.

This separation prevents a text provider from being forced through an unsupported image/file protocol and reduces the payload presented to OpenAI-compatible gateways.

### OpenAI preset

The OpenAI preset uses Responses, structured output, streaming, and vision by default. SDK retries are disabled so Super Scholar owns the call budget.

### DeepSeek preset

DeepSeek is treated as a text-only provider in Super Scholar. The default V3.6 path uses Chat Completions + JSON Object with `deepseek-v4-pro`; text messages are serialized using the text-string shape documented by DeepSeek. Vision and Files are disabled. Scanned/image-only material requires local OCR before DeepSeek can use it.

### Custom provider

Custom providers receive no inferred `/v1`, Vision, Files, or protocol capability. With transport profile `auto`, Super Scholar uses the conservative Edge-safe text-first limits.

### Grounding

Code evidence is secret-redacted before provider use. Model facts must cite current-run evidence/artifact IDs. Final contributions, research questions, claimed novelty, gaps, and visual observations without valid current-project references are removed before persistence.

### Visual-only material

A visual-only project can be processed by local OCR or a configured vision-capable provider. A text-only provider such as the DeepSeek preset is not asked to consume unsupported image inputs.

## 4. What V3.6 does not claim

- `claimedNovelty` is a description of novelty claimed/supported by the uploaded project materials. It is not a literature-wide novelty verification.
- Research stage is a material-maturity signal, not an acceptance probability or absolute research-quality score.
- Research Match in venue recommendation is not an acceptance probability.

## 5. CCF conferences and journals

Primary authority for CCF rank/category: China Computer Federation (CCF), seventh edition of the Recommended International Academic Conferences and Journals list.

Runtime strategy retained from V2.1:

1. CCF official category pages.
2. A structured public conversion derived from the official seventh-edition PDF, accepted only after metadata/domain/count/anchor validation.
3. The last successful database cache if a later refresh fails.

No CCF rank is inferred merely from a venue name.

Official directory:
https://www.ccf.org.cn/Academic_Evaluation/By_category/

Validated structured fallback project:
https://github.com/haozhou-wong/ccf-recommended-list-2026-markdown

## 6. Conference deadlines and logistics

Source: CCFDDL structured conference dataset. CCFDDL supplies edition/year/deadline/timezone/date/place/CORE. V3.7 attempts to overlay CCF rank and CCF category from the official CCF seventh-edition pages; when official retrieval is unavailable, the item is explicitly labelled as using the CCFDDL CCF field rather than silently claiming official verification.

Fields consumed when present:

- CCF rank
- CORE rank
- conference edition/year
- abstract deadline
- paper deadline
- source timezone
- conference date
- place
- edition/official link

AoE, PT, explicit IANA names and UTC offsets are normalized for comparison. An unresolvable timezone no longer invalidates the entire catalog.

Repository:
https://github.com/ccfddl/ccf-deadlines


## 7. Scholarly APIs used by recommendation

### OpenAlex

Endpoints used:

```text
GET https://api.openalex.org/rate-limit
GET https://api.openalex.org/works?search.semantic=...
GET https://api.openalex.org/sources?filter=ids.openalex:...
GET https://api.openalex.org/sources/{S...}   # bounded fallback
```

The API key is sent as the documented `api_key` query parameter. Source hydration uses `ids.openalex` identity filtering and reads `topic_share` before frequency-only `topics` when both are present. A Source hydration failure does not become a false zero topic score.

### Semantic Scholar

Endpoint used:

```text
GET https://api.semanticscholar.org/graph/v1/paper/search
```

When configured, the key is sent in the documented `x-api-key` header. The returned `publicationVenue`/`venue` values are treated as an independent evidence component and are matched conservatively to candidate venue identities.

### DBLP

Endpoint used:

```text
GET https://dblp.org/search/venue/api?q=...&format=json
```

DBLP is used for CS venue aliases/canonicalization, not for research-topic scoring. Requests are bounded and concurrent work is limited.

### Crossref

Endpoints used:

```text
GET https://api.crossref.org/works
GET https://api.crossref.org/journals/{issn}
```

Public mode uses no authentication. Polite mode adds the configured contact email. If the user has a Metadata Plus subscription, the token is sent as `Crossref-Plus-API-Token: Bearer ...`. Crossref metadata verifies journal identity/publisher; it does not supply JCR/JIF.

### Venue identity safety

Dynamic candidates and direct-paper evidence are joined only by conservative canonical/acronym/distinctive-token matching. Common words such as “international”, “conference”, “computer”, or a generic “agent” token do not establish venue identity or subfield fit.

## 8. JCR / JIF / APC / review speed

The UI can express these user preferences, but V3 does not create values when no verifiable data source has been connected. Required constraints with unknown source data remain unknown rather than silently passing.

## Transport compatibility notes (V3.6 retained in V3.7)

Research-understanding transport uses OpenAI-compatible SSE streaming when enabled. This is based on the documented `stream=true` behavior of the OpenAI Responses API / Python SDK. Streaming is a transport choice only; it does not change evidence grounding or source provenance.

Tencent EdgeOne documents 524/554 as an origin-response timeout after the edge node has successfully connected to and forwarded the request to the origin. Super Scholar therefore treats a `Server: TencentEdgeOne` + HTTP 554 response as an edge/origin timeout diagnostic, not as an OpenAI-specific model error.
