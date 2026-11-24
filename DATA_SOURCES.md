# Super Scholar V3.11 — data, evidence and integration provenance

## V3.11 journal metadata provenance

| Field | Source used by Super Scholar | Rule |
|---|---|---|
| Fully-OA / DOAJ | OpenAlex Source | Public source-level metadata; `is_oa=false` is only “not fully OA / mixed”, never guessed as Hybrid/Subscription. |
| APC list price | OpenAlex Source `apc_prices` / `apc_usd` | Used only when OpenAlex actually returns a price. |
| APC CNY | OpenAlex APC + ECB EXR reference rates | CNY/USD is derived from CNY-per-EUR divided by USD-per-EUR; rate date and source are persisted. |
| OpenAlex 2yr mean citedness | OpenAlex `summary_stats.2yr_mean_citedness` | Display-only public citation statistic; explicitly **not JIF**. |
| WoS edition / SCIE / ESCI | Clarivate Web of Science Journals API | Optional entitled API only. Never inferred from OpenAlex or third-party lists. |
| JCR quartile | Clarivate Web of Science Journals API | Optional entitled API only; retain all returned category quartiles. |
| Journal Impact Factor | Clarivate Web of Science Journals API | Optional entitled API only. |
| Review speed | none in V3.11 | No unified authoritative cross-publisher API is assumed; Preferred is N/A, Required is unverifiable. |


## V3.10 recommendation evidence roles

The recommender distinguishes discovery, identity, academic-fit evidence and submission actionability. Missing evidence is Unknown rather than a fabricated zero.

- **OpenAlex global Works** discovers a semantic scholarly neighborhood and direct publication-source evidence.
- **Candidate Source/series resolution** binds journals by ISSN/name and conferences to a conservative set of recent annual proceedings Sources. Workshop/companion/tutorial variants are excluded.
- **Venue-conditioned OpenAlex Works** is the principal content signal: the research query is searched inside each bounded high-priority candidate Source/series over recent publication years.
- **CS subfield scope** is a deterministic guardrail for major CS venue families.
- **Semantic Scholar** contributes independent publication-venue evidence when available.
- **Structured manuscript References** contribute a low-weight community prior. Ambiguous short acronyms require citation/venue context.
- **OpenAlex Source topics** are aggregate metadata and are auxiliary only.
- **CCF / CORE / CCFDDL metadata** affect user preferences and actionability but do not create content similarity.

Nominal Research Match weights, renormalized over signals that are actually available:

```text
OpenAlex venue-conditioned recent works   48%
OpenAlex global publication evidence      14%
CS subfield scope fit                     18%
Semantic Scholar publication venue        8%
Structured manuscript References          8%
OpenAlex Source topics (auxiliary)         4%
```

For CCF journals, the seventh-edition catalog is validated as 295 official placements and canonicalized to 291 unique identities while preserving every placement in provenance. `U` means unverified/unknown; `N` means verified absent from a complete catalog. Academic Fit is separate from Current Actionability.

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
