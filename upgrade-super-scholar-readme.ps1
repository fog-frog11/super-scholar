Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ============================================================
# Super Scholar - Professional GitHub Landing Page Upgrade
# PowerShell 5.1+ / PowerShell 7+
#
# Run from the repository root:
#   Set-ExecutionPolicy -Scope Process Bypass
#   .\upgrade-super-scholar-readme.ps1
#
# Default behavior:
#   - validates repository is otherwise clean
#   - ignores this helper script locally (not committed)
#   - backs up existing README files outside the repo
#   - creates original SVG brand assets
#   - replaces README.md with a product-first GitHub landing page
#   - creates README.zh-CN.md
#   - creates docs/README.md
#   - stages, commits and pushes changes
# ============================================================

function Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Info([string]$Message) {
    Write-Host "    $Message" -ForegroundColor DarkGray
}

function Warn([string]$Message) {
    Write-Host ""
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Fail([string]$Message) {
    Write-Host ""
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 1
}

function Write-Utf8NoBom([string]$Path, [string]$Content) {
    $absolute = Join-Path (Get-Location) $Path
    $parent = Split-Path -Parent $absolute
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($absolute, $Content, $encoding)
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Fail "没有找到 Git。请先安装 Git for Windows。"
}

$repoRoot = (& git rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($repoRoot)) {
    Fail "当前目录不是 Git 仓库。请把本脚本放在 Super Scholar 仓库根目录运行。"
}

Set-Location $repoRoot
$repoRoot = (Get-Location).Path
Step "仓库位置：$repoRoot"

# ------------------------------------------------------------
# Ignore this helper script locally, so running it from the repo
# does not make the clean-working-tree check fail.
# ------------------------------------------------------------
$scriptPath = $MyInvocation.MyCommand.Path
if (-not [string]::IsNullOrWhiteSpace($scriptPath)) {
    $scriptName = Split-Path -Leaf $scriptPath
    $gitDir = (& git rev-parse --git-dir).Trim()
    $excludePath = Join-Path $gitDir "info\exclude"
    $excludeDir = Split-Path -Parent $excludePath
    if (-not (Test-Path -LiteralPath $excludeDir)) {
        New-Item -ItemType Directory -Force -Path $excludeDir | Out-Null
    }
    if (-not (Test-Path -LiteralPath $excludePath)) {
        New-Item -ItemType File -Path $excludePath | Out-Null
    }
    $exclude = Get-Content -LiteralPath $excludePath -ErrorAction SilentlyContinue
    if ($exclude -notcontains "/$scriptName") {
        Add-Content -LiteralPath $excludePath -Value "/$scriptName"
    }
}

# ------------------------------------------------------------
# Validate clean repo
# ------------------------------------------------------------
$status = (& git status --porcelain)
if (-not [string]::IsNullOrWhiteSpace(($status -join "`n"))) {
    Write-Host ""
    & git status --short
    Fail "仓库存在其他未提交修改。请先 commit 或 stash，再运行本脚本。脚本本身已经自动忽略。"
}

$branch = (& git branch --show-current).Trim()
if ([string]::IsNullOrWhiteSpace($branch)) {
    Fail "当前处于 detached HEAD，无法自动提交。"
}

$remoteUrl = (& git remote get-url origin 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($remoteUrl)) {
    Fail "没有找到 origin remote。"
}
$remoteUrl = $remoteUrl.Trim()

# GitHub slug from either HTTPS or SSH remote.
$repoSlug = ""
if ($remoteUrl -match 'github\.com[/:](?<slug>[^/]+/[^/]+?)(?:\.git)?$') {
    $repoSlug = $Matches["slug"]
}
if ([string]::IsNullOrWhiteSpace($repoSlug)) {
    Warn "无法从 origin 自动识别 GitHub owner/repo，将使用当前 Super Scholar 仓库名。"
    $repoSlug = "ZhangChristmas/Super-Scholar"
}

Step "目标仓库：$repoSlug"
Info "分支：$branch"
Info "Remote：$remoteUrl"

# ------------------------------------------------------------
# Backup
# ------------------------------------------------------------
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path (Split-Path -Parent $repoRoot) "super-scholar-readme-backup-$stamp"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

foreach ($file in @("README.md", "README.zh-CN.md", "CHANGELOG.md", "docs\README.md")) {
    if (Test-Path -LiteralPath $file) {
        $safeName = ($file -replace '[\\/]', '__')
        Copy-Item -LiteralPath $file -Destination (Join-Path $backupDir $safeName) -Force
    }
}

Step "已备份现有 README"
Info $backupDir

# ------------------------------------------------------------
# Brand assets
# ------------------------------------------------------------
Step "生成 Super Scholar 原创品牌资产"

New-Item -ItemType Directory -Force -Path ".github\assets" | Out-Null

$heroSvg = @'
<svg width="1600" height="640" viewBox="0 0 1600 640" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="84" y1="28" x2="1516" y2="612" gradientUnits="userSpaceOnUse">
      <stop stop-color="#0B1020"/>
      <stop offset="0.52" stop-color="#12162A"/>
      <stop offset="1" stop-color="#171326"/>
    </linearGradient>
    <linearGradient id="accent" x1="430" y1="130" x2="1160" y2="505" gradientUnits="userSpaceOnUse">
      <stop stop-color="#8B7CFF"/>
      <stop offset="0.52" stop-color="#60A5FA"/>
      <stop offset="1" stop-color="#41D1B7"/>
    </linearGradient>
    <radialGradient id="glow1" cx="0" cy="0" r="1" gradientTransform="translate(1240 100) rotate(128) scale(520 720)">
      <stop stop-color="#725BFF" stop-opacity=".28"/>
      <stop offset="1" stop-color="#725BFF" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glow2" cx="0" cy="0" r="1" gradientTransform="translate(240 570) rotate(-40) scale(480 580)">
      <stop stop-color="#24C8B4" stop-opacity=".17"/>
      <stop offset="1" stop-color="#24C8B4" stop-opacity="0"/>
    </radialGradient>
    <filter id="shadow" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="0" dy="16" stdDeviation="20" flood-color="#000000" flood-opacity=".28"/>
    </filter>
  </defs>

  <rect width="1600" height="640" rx="32" fill="url(#bg)"/>
  <rect width="1600" height="640" rx="32" fill="url(#glow1)"/>
  <rect width="1600" height="640" rx="32" fill="url(#glow2)"/>

  <g opacity=".08" stroke="#D8DDF6">
    <path d="M0 110H1600"/><path d="M0 220H1600"/><path d="M0 330H1600"/>
    <path d="M0 440H1600"/><path d="M0 550H1600"/>
    <path d="M160 0V640"/><path d="M320 0V640"/><path d="M480 0V640"/>
    <path d="M640 0V640"/><path d="M800 0V640"/><path d="M960 0V640"/>
    <path d="M1120 0V640"/><path d="M1280 0V640"/><path d="M1440 0V640"/>
  </g>

  <!-- Logo mark -->
  <g transform="translate(116 118)" filter="url(#shadow)">
    <rect width="112" height="112" rx="28" fill="#11172B" stroke="#8B7CFF" stroke-width="2"/>
    <path d="M25 43C42 31 70 31 87 43V77C70 66 42 66 25 77V43Z" stroke="url(#accent)" stroke-width="5" stroke-linejoin="round"/>
    <path d="M56 35V78" stroke="url(#accent)" stroke-width="5" stroke-linecap="round"/>
    <path d="M74 25L77.2 32.8L85 36L77.2 39.2L74 47L70.8 39.2L63 36L70.8 32.8L74 25Z" fill="#A79CFF"/>
  </g>

  <text x="264" y="164" fill="#F6F7FB" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="30" font-weight="700" letter-spacing="5">SUPER SCHOLAR</text>
  <text x="116" y="308" fill="#FFFFFF" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="72" font-weight="720">From research to the</text>
  <text x="116" y="390" fill="url(#accent)" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="72" font-weight="720">right venue.</text>
  <text x="118" y="449" fill="#AEB8D3" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="25" font-weight="400">
    Evidence-grounded research understanding · multi-source venue recommendation
  </text>

  <!-- Flow -->
  <g transform="translate(118 504)">
    <g>
      <rect width="198" height="58" rx="16" fill="#161D36" stroke="#303B62"/>
      <text x="99" y="36" text-anchor="middle" fill="#E8EBF8" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="19" font-weight="600">Understand</text>
    </g>
    <path d="M216 29H270" stroke="#667399" stroke-width="2"/><path d="M260 21L270 29L260 37" stroke="#667399" stroke-width="2" fill="none"/>
    <g transform="translate(286 0)">
      <rect width="198" height="58" rx="16" fill="#161D36" stroke="#3F4E78"/>
      <text x="99" y="36" text-anchor="middle" fill="#E8EBF8" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="19" font-weight="600">Ground evidence</text>
    </g>
    <path d="M502 29H556" stroke="#667399" stroke-width="2"/><path d="M546 21L556 29L546 37" stroke="#667399" stroke-width="2" fill="none"/>
    <g transform="translate(572 0)">
      <rect width="198" height="58" rx="16" fill="#161D36" stroke="#4A5D83"/>
      <text x="99" y="36" text-anchor="middle" fill="#E8EBF8" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="19" font-weight="600">Recommend</text>
    </g>
    <path d="M788 29H842" stroke="#667399" stroke-width="2"/><path d="M832 21L842 29L832 37" stroke="#667399" stroke-width="2" fill="none"/>
    <g transform="translate(858 0)">
      <rect width="198" height="58" rx="16" fill="#161D36" stroke="#4E6A83"/>
      <text x="99" y="36" text-anchor="middle" fill="#E8EBF8" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="19" font-weight="600">Compare</text>
    </g>
  </g>

  <!-- right-side research graph -->
  <g transform="translate(1210 280)" opacity=".72">
    <path d="M0 22L105 -34L202 44L165 151L45 166L0 22Z" stroke="#5C6E9A" stroke-width="2" fill="none"/>
    <path d="M0 22L165 151M105 -34L45 166M202 44L45 166M105 -34L165 151" stroke="#344166" stroke-width="1.5"/>
    <circle cx="0" cy="22" r="9" fill="#8B7CFF"/>
    <circle cx="105" cy="-34" r="9" fill="#6D98FF"/>
    <circle cx="202" cy="44" r="9" fill="#53B5E8"/>
    <circle cx="165" cy="151" r="9" fill="#41D1B7"/>
    <circle cx="45" cy="166" r="9" fill="#62BCA9"/>
    <circle cx="101" cy="79" r="16" fill="#161D36" stroke="#A79CFF" stroke-width="3"/>
  </g>
</svg>
'@

$logoSvg = @'
<svg width="256" height="256" viewBox="0 0 256 256" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="g" x1="44" y1="50" x2="211" y2="207" gradientUnits="userSpaceOnUse">
      <stop stop-color="#8B7CFF"/>
      <stop offset=".52" stop-color="#60A5FA"/>
      <stop offset="1" stop-color="#41D1B7"/>
    </linearGradient>
  </defs>
  <rect width="256" height="256" rx="64" fill="#0E1428"/>
  <rect x="2" y="2" width="252" height="252" rx="62" stroke="#2A355A" stroke-width="4"/>
  <path d="M53 98C89 72 167 72 203 98V174C167 149 89 149 53 174V98Z" stroke="url(#g)" stroke-width="12" stroke-linejoin="round"/>
  <path d="M128 80V177" stroke="url(#g)" stroke-width="12" stroke-linecap="round"/>
  <path d="M169 53L176 70L193 77L176 84L169 101L162 84L145 77L162 70L169 53Z" fill="#A79CFF"/>
</svg>
'@

Write-Utf8NoBom ".github/assets/super-scholar-hero.svg" $heroSvg
Write-Utf8NoBom ".github/assets/super-scholar-logo.svg" $logoSvg

# ------------------------------------------------------------
# English README
# ------------------------------------------------------------
Step "生成专业英文 README"

$readme = @'
<p align="center">
  <img src=".github/assets/super-scholar-hero.svg" alt="Super Scholar — From research to the right venue" width="100%" />
</p>

<p align="center">
  <a href="#quick-start"><strong>Quick Start</strong></a> ·
  <a href="#what-super-scholar-does"><strong>Features</strong></a> ·
  <a href="#how-it-works"><strong>How it works</strong></a> ·
  <a href="docs/README.md"><strong>Docs</strong></a> ·
  <a href="CHANGELOG.md"><strong>Changelog</strong></a>
</p>

<p align="center">
  <a href="https://github.com/__REPO_SLUG__/stargazers"><img src="https://img.shields.io/github/stars/__REPO_SLUG__?style=flat-square&color=7C6CF2" alt="GitHub stars"></a>
  <a href="https://github.com/__REPO_SLUG__/forks"><img src="https://img.shields.io/github/forks/__REPO_SLUG__?style=flat-square&color=5F8FEF" alt="GitHub forks"></a>
  <a href="https://github.com/__REPO_SLUG__/commits/main"><img src="https://img.shields.io/github/last-commit/__REPO_SLUG__?style=flat-square&color=41BFA8" alt="Last commit"></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Next.js-Frontend-000000?style=flat-square&logo=nextdotjs&logoColor=white" alt="Next.js">
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
</p>

<p align="center">
  <a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a>
</p>

---

## Why Super Scholar?

Most venue recommenders start with a few keywords.

**Super Scholar starts with the research itself.**

It parses manuscripts, code, experiments and supporting material into an evidence-grounded research profile, then combines scholarly graphs, venue metadata and user constraints to recommend conferences and journals — with an explanation of **why** each venue fits.

| Traditional venue matching | Super Scholar |
|---|---|
| Keywords → venue list | Research → evidence-grounded profile → venue evidence |
| One catalog or ranking list | OpenAlex + Semantic Scholar + CCF/CCFDDL + DBLP + Crossref |
| Opaque score | Inspectable evidence components |
| Missing data often becomes a guess | Unknown stays **Unknown** |
| Generic subject matching | Problem / method / experiment / contribution-aware matching |

> [!IMPORTANT]
> **Research Match is not an acceptance probability.** Super Scholar ranks fit from available evidence and explicitly exposes missing or degraded data sources.

---

## What Super Scholar does

<table>
<tr>
<td width="50%" valign="top">

### 🧠 Understand research
Build a structured profile from PDFs, DOCX, LaTeX, code, spreadsheets, experiment outputs and figures.

</td>
<td width="50%" valign="top">

### 🔎 Ground every claim
Keep research understanding tied to source evidence instead of presenting unsupported model output as fact.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🎯 Recommend venues
Retrieve and rank relevant conferences and journals from multiple scholarly and CS-specific sources.

</td>
<td width="50%" valign="top">

### ⚖️ Compare before submitting
Apply Required / Preferred constraints and compare candidates by fit, metadata, deadline, location and evidence coverage.

</td>
</tr>
</table>

### Reliability by design

- **Local-first parsing** — uploaded research is parsed locally before optional external AI calls.
- **Evidence-grounded profiles** — claims remain traceable to source materials.
- **Multi-source retrieval** — no single scholarly provider becomes the entire recommendation truth.
- **Honest unknowns** — `Unknown ≠ 0`, `Unknown ≠ Pass`.
- **Bounded provider behavior** — AI calls and retries are controlled rather than silently multiplied.
- **Encrypted credentials** — configured provider/API secrets are persisted encrypted locally.

---

## Quick Start

### Requirements

- Python **3.11+**
- Node.js **20+**
- npm
- Git

Clone the repository:

```bash
git clone https://github.com/__REPO_SLUG__.git
cd Super-Scholar
```

### 1. Backend

```bash
cd backend
python -m venv .venv
```

**Windows PowerShell**

```powershell
.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Git Bash / Linux / macOS**

```bash
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate
cp .env.example .env
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend API:

- `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/docs`

### 2. Frontend

Open a second terminal:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open **http://localhost:3000**.

### 3. One-command development start

After dependencies are installed:

```powershell
.\run-dev.ps1
```

or:

```bash
./run-dev.sh
```

---

## How it works

```mermaid
flowchart LR
    A["Research materials"] --> B["Local parsing"]
    B --> C["Evidence-grounded<br/>Research Profile"]
    C --> D["Publication<br/>Preferences"]

    D --> E["Candidate retrieval"]
    E --> OA["OpenAlex"]
    E --> SS["Semantic Scholar"]
    E --> CCF["CCF / CCFDDL"]
    E --> DB["DBLP"]
    E --> CR["Crossref"]

    OA --> R["Evidence ranking"]
    SS --> R
    CCF --> R
    DB --> R
    CR --> R
    C --> R

    R --> V["Venue recommendations"]
    V --> X["Compare"]
    X --> S["Select target venue"]
```

### 1. Research understanding

Super Scholar builds a research profile from signals such as:

`research problem` · `core idea` · `CS areas` · `topics` · `methods` · `datasets` · `models` · `metrics` · `experiments` · `contributions`

The AI layer follows a text-first, evidence-preserving workflow:

```text
Research files
      ↓
Local extraction
      ↓
Text / code / table evidence
      ↓
Bounded AI extraction
      ↓
Optional visual analysis
      ↓
Grounded synthesis
      ↓
Research Profile
```

### 2. Publication preferences

Constraints have explicit semantics:

- **Required** — a hard constraint. Failed or unverifiable required conditions can exclude a candidate.
- **Preferred** — a ranking preference. Unknown values remain neutral.

### 3. Venue evidence

| Source | Role in Super Scholar |
|---|---|
| **OpenAlex** | Semantic works, publication evidence, Source identity, Source topics |
| **Semantic Scholar** | Independent related-paper and publication-venue evidence |
| **CCF** | CS ranking / area metadata |
| **CCFDDL** | Conference edition, deadline, date and location |
| **DBLP** | CS venue canonicalization, aliases and acronyms |
| **Crossref** | Journal / ISSN / publisher identity |
| **Manuscript references** | Local community / venue prior from the actual bibliography |

Missing components are excluded from the available-evidence denominator instead of being fabricated as zero.

---

## Candidate Venue → OpenAlex Source

OpenAlex Works retrieval and candidate Venue Source resolution are separate stages.

**Journal identity**

```text
ISSN → OpenAlex Source
```

**Conference / name-based identity**

```text
Venue name + acronym + aliases
            ↓
      Source search
            ↓
 strict local identity check
            ↓
confident match only
```

A successful semantic Works search does not automatically imply that every catalog candidate has Source topics.

The recommendation run therefore tracks:

- OpenAlex Works
- Sources attached to semantic papers
- candidate Venue Sources attempted
- candidate Venue Sources resolved
- resolved candidate Sources with topics

---

## Data-source health

External integrations are not reduced to a single green check.

Super Scholar distinguishes:

`Ready` · `Limited` · `Degraded` · `Error` · `Disabled` · `N/A`

For example:

```text
OpenAlex Works               Ready
OpenAlex paper Sources       Ready
OpenAlex candidate Sources   Limited
Semantic Scholar             Rate limited
DBLP                         Ready
CCFDDL                       Ready
```

This makes partial evidence visible instead of silently pretending the whole pipeline is healthy.

---

## AI providers

Supported provider profiles:

- **OpenAI**
- **DeepSeek**
- **Custom OpenAI-compatible endpoint**

Each profile persists independently:

`Base URL` · `model` · `protocol` · `output mode` · `reasoning` · `streaming` · `vision/files capabilities` · `transport profile` · `encrypted API key`

Switching providers does not overwrite another provider's saved configuration.

---

## Project structure

<details>
<summary><strong>Repository layout</strong></summary>

```text
Super-Scholar/
├── backend/
│   ├── app/
│   │   ├── routers/
│   │   ├── services/
│   │   ├── models.py
│   │   └── schemas.py
│   ├── migrations/
│   └── tests/
├── frontend/
│   └── src/
│       ├── app/
│       ├── components/
│       └── lib/
├── docs/
│   ├── DATA_SOURCES.md
│   └── releases/
├── .github/
│   └── assets/
├── scripts/
├── CHANGELOG.md
├── README.md
├── README.zh-CN.md
├── run-dev.ps1
└── run-dev.sh
```

</details>

---

## Current scope & roadmap

Super Scholar currently focuses on **computer science**.

- [x] Multi-format research ingestion
- [x] Evidence-grounded research profile
- [x] Publication preferences
- [x] Conference / journal candidate retrieval
- [x] Multi-source evidence ranking
- [x] Venue comparison and selection
- [x] Scholarly-source health diagnostics
- [x] Independent AI-provider profiles
- [ ] Venue-specific related-paper retrieval
- [ ] Venue style / writing-pattern analysis
- [ ] RAG-assisted manuscript guidance
- [ ] Public evaluation benchmark
- [ ] Packaged deployment / hosted demo

---

## Documentation

- **[Data Sources & Provenance](docs/DATA_SOURCES.md)** — what each external source contributes and how missing evidence is treated.
- **[Changelog](CHANGELOG.md)** — concise project evolution.
- **[Release Archive](docs/releases/)** — detailed historical engineering notes.
- **[中文 README](README.zh-CN.md)** — 简体中文项目说明.

---

## Project status

Super Scholar is an actively developed **research prototype**. The current implementation prioritizes evidence traceability, transparent uncertainty and reliable venue identity over producing a confident-looking answer at any cost.

If you find a reproducible issue, open a GitHub Issue with the relevant logs and steps to reproduce.

---

<p align="center">
  <img src=".github/assets/super-scholar-logo.svg" width="64" alt="Super Scholar logo" />
</p>

<p align="center">
  <strong>Super Scholar</strong><br/>
  <sub>From research understanding to evidence-grounded publication decisions.</sub>
</p>
'@

$readme = $readme.Replace("__REPO_SLUG__", $repoSlug)
Write-Utf8NoBom "README.md" $readme

# ------------------------------------------------------------
# Chinese README
# ------------------------------------------------------------
Step "生成简体中文 README"

$zh = @'
<p align="center">
  <img src=".github/assets/super-scholar-hero.svg" alt="Super Scholar — 从研究到合适的投稿 Venue" width="100%" />
</p>

<p align="center">
  <a href="#快速开始"><strong>快速开始</strong></a> ·
  <a href="#super-scholar-能做什么"><strong>核心能力</strong></a> ·
  <a href="#工作流程"><strong>工作流程</strong></a> ·
  <a href="docs/README.md"><strong>文档</strong></a> ·
  <a href="CHANGELOG.md"><strong>更新历史</strong></a>
</p>

<p align="center">
  <a href="https://github.com/__REPO_SLUG__/stargazers"><img src="https://img.shields.io/github/stars/__REPO_SLUG__?style=flat-square&color=7C6CF2" alt="GitHub stars"></a>
  <a href="https://github.com/__REPO_SLUG__/forks"><img src="https://img.shields.io/github/forks/__REPO_SLUG__?style=flat-square&color=5F8FEF" alt="GitHub forks"></a>
  <a href="https://github.com/__REPO_SLUG__/commits/main"><img src="https://img.shields.io/github/last-commit/__REPO_SLUG__?style=flat-square&color=41BFA8" alt="Last commit"></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Next.js-Frontend-000000?style=flat-square&logo=nextdotjs&logoColor=white" alt="Next.js">
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
</p>

<p align="center">
  <a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a>
</p>

---

## 为什么是 Super Scholar？

大多数投稿 Venue 推荐器从几个关键词开始。

**Super Scholar 从研究本身开始。**

它先把论文、代码、实验与辅助材料理解成一个有证据支撑的 Research Profile，再结合学术图谱、Venue 元数据和用户约束推荐会议与期刊，并解释每个 Venue **为什么适合**。

| 传统 Venue 匹配 | Super Scholar |
|---|---|
| 关键词 → Venue 列表 | 研究 → 证据化 Profile → Venue 证据 |
| 单一目录 / 排名 | OpenAlex + Semantic Scholar + CCF/CCFDDL + DBLP + Crossref |
| 黑盒分数 | 可检查的证据组成 |
| 缺失数据容易被默认处理 | Unknown 明确保留为 **Unknown** |
| 粗粒度领域匹配 | 面向问题 / 方法 / 实验 / 贡献的匹配 |

> [!IMPORTANT]
> **Research Match 不是录用概率。** Super Scholar 依据当前可获得证据评估研究与 Venue 的匹配程度，并明确展示缺失或降级的数据源。

---

## Super Scholar 能做什么

<table>
<tr>
<td width="50%" valign="top">

### 🧠 理解研究
从 PDF、DOCX、LaTeX、代码、表格、实验结果与图片中构建结构化 Research Profile。

</td>
<td width="50%" valign="top">

### 🔎 证据绑定
研究理解中的关键结论能够回溯到原始材料，而不是把模型生成内容直接当作事实。

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🎯 推荐 Venue
从多个真实学术与 CS 数据源中检索并排序相关会议与期刊。

</td>
<td width="50%" valign="top">

### ⚖️ 投稿前比较
使用 Required / Preferred 条件比较匹配度、元数据、Deadline、地点与证据覆盖。

</td>
</tr>
</table>

### 可靠性原则

- **Local-first**：研究材料先本地解析，再选择性调用外部 AI。
- **Evidence-grounded**：Research Profile 中的事实与上传材料保持可追溯关系。
- **Multi-source**：不把任何单一学术 API 当成推荐真值。
- **Unknown 不造假**：`Unknown ≠ 0`，`Unknown ≠ Pass`。
- **受控 Provider 调用**：调用数量和重试行为受明确约束。
- **凭据加密保存**：配置的 API Key 在本地加密持久化。

---

## 快速开始

### 环境要求

- Python **3.11+**
- Node.js **20+**
- npm
- Git

克隆仓库：

```bash
git clone https://github.com/__REPO_SLUG__.git
cd Super-Scholar
```

### 1. 后端

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

后端地址：

- `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/docs`

### 2. 前端

新开一个终端：

```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

浏览器打开 **http://localhost:3000**。

### 3. 一键开发启动

依赖安装完成后：

```powershell
.\run-dev.ps1
```

---

## 工作流程

```mermaid
flowchart LR
    A["研究材料"] --> B["本地解析"]
    B --> C["证据化<br/>Research Profile"]
    C --> D["投稿偏好"]

    D --> E["候选 Venue 检索"]
    E --> OA["OpenAlex"]
    E --> SS["Semantic Scholar"]
    E --> CCF["CCF / CCFDDL"]
    E --> DB["DBLP"]
    E --> CR["Crossref"]

    OA --> R["证据排序"]
    SS --> R
    CCF --> R
    DB --> R
    CR --> R
    C --> R

    R --> V["推荐结果"]
    V --> X["横向比较"]
    X --> S["选择目标 Venue"]
```

### Research Profile

系统当前关注的研究信号包括：

`research problem` · `core idea` · `CS areas` · `topics` · `methods` · `datasets` · `models` · `metrics` · `experiments` · `contributions`

### 投稿偏好

- **Required**：硬条件；不满足或在要求可验证时无法验证，可以直接排除候选。
- **Preferred**：排序偏好；Unknown 保持中性，不会伪装成已满足。

---

## 推荐证据

| 数据源 | 在 Super Scholar 中的作用 |
|---|---|
| **OpenAlex** | 语义论文、发表 Venue 证据、Source identity、Source topics |
| **Semantic Scholar** | 独立的相似论文与发表 Venue 证据 |
| **CCF** | CS 排名与领域元数据 |
| **CCFDDL** | 会议届次、Deadline、日期、地点 |
| **DBLP** | CS Venue 规范化、别名、缩写 |
| **Crossref** | 期刊 / ISSN / Publisher identity |
| **论文 References** | 从真实参考文献中提取社区 / Venue prior |

缺失的证据项会从当前可用证据分母中移除，而不是直接当成 0。

---

## Candidate Venue → OpenAlex Source

OpenAlex semantic Works 检索与候选 Venue Source 解析是两个独立阶段。

```text
期刊：ISSN → OpenAlex Source

会议：
Venue name + acronym + aliases
            ↓
      Source search
            ↓
    严格身份校验
            ↓
      可信匹配才绑定
```

因此，“OpenAlex Works Ready”并不意味着所有候选 Venue 都已经成功获得 Source topics。

---

## 数据源健康状态

Super Scholar 区分：

`Ready` · `Limited` · `Degraded` · `Error` · `Disabled` · `N/A`

例如：

```text
OpenAlex Works               Ready
OpenAlex paper Sources       Ready
OpenAlex candidate Sources   Limited
Semantic Scholar             Rate limited
DBLP                         Ready
CCFDDL                       Ready
```

这样不会因为某一个请求成功，就把整个推荐证据链显示成完全健康。

---

## AI Provider

支持：

- **OpenAI**
- **DeepSeek**
- **Custom OpenAI-compatible**

每个 Provider 独立保存：

`Base URL` · `model` · `protocol` · `output mode` · `reasoning` · `streaming` · `vision/files` · `transport profile` · `encrypted API key`

Provider 之间切换不会覆盖另一套已保存配置。

---

## 当前范围与 Roadmap

当前重点为 **计算机科学投稿 Venue 推荐**：

- [x] 多格式研究材料接入
- [x] Evidence-grounded Research Profile
- [x] 投稿偏好
- [x] 会议 / 期刊候选检索
- [x] 多数据源证据排序
- [x] Venue 对比与选择
- [x] 学术数据源健康诊断
- [x] 独立 AI Provider 配置
- [ ] Venue 相关论文深度检索
- [ ] Venue 写作风格 / 历史论文分析
- [ ] RAG 辅助论文修改
- [ ] 公开 Evaluation Benchmark
- [ ] 打包部署 / Hosted Demo

---

## 文档

- **[数据源与证据规则](docs/DATA_SOURCES.md)**
- **[Changelog](CHANGELOG.md)**
- **[历史 Release Archive](docs/releases/)**
- **[English README](README.md)**

---

## 项目状态

Super Scholar 目前是持续开发中的 **research prototype**。项目优先保证证据可追溯、Unknown 可见和 Venue identity 可靠，而不是为了让结果“看起来完整”去填补无法验证的数据。

---

<p align="center">
  <img src=".github/assets/super-scholar-logo.svg" width="64" alt="Super Scholar logo" />
</p>

<p align="center">
  <strong>Super Scholar</strong><br/>
  <sub>From research understanding to evidence-grounded publication decisions.</sub>
</p>
'@

$zh = $zh.Replace("__REPO_SLUG__", $repoSlug)
Write-Utf8NoBom "README.zh-CN.md" $zh

# ------------------------------------------------------------
# Docs index
# ------------------------------------------------------------
Step "生成 docs 文档入口"

$docs = @'
# Super Scholar Documentation

This directory contains project documentation that is intentionally kept out of the GitHub landing page.

## Documentation map

- **[Data Sources & Provenance](DATA_SOURCES.md)**  
  Scholarly data-source roles, reliability rules, source-health semantics and evidence treatment.

- **[Release Archive](releases/)**  
  Detailed engineering notes from earlier development stages.

- **[Project Changelog](../CHANGELOG.md)**  
  Concise version history.

- **[English README](../README.md)**  
  Main GitHub project landing page.

- **[简体中文 README](../README.zh-CN.md)**  
  Chinese project overview and quick start.

## Documentation principle

The root README describes **what Super Scholar is now**.

Historical implementation details belong in the release archive so the repository landing page remains concise, product-oriented and useful to first-time visitors.
'@
Write-Utf8NoBom "docs/README.md" $docs

# ------------------------------------------------------------
# Stage / review / commit / push
# ------------------------------------------------------------
Step "暂存 README 与品牌资产"

& git add -- README.md README.zh-CN.md docs/README.md .github/assets/super-scholar-hero.svg .github/assets/super-scholar-logo.svg
if ($LASTEXITCODE -ne 0) {
    Fail "git add 失败。"
}

Write-Host ""
& git status --short
Write-Host ""

& git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Warn "没有检测到变化。README 可能已经是当前版本。"
    exit 0
}

Step "提交 GitHub 首页升级"

& git commit -m "docs: redesign GitHub landing page"
if ($LASTEXITCODE -ne 0) {
    Fail "git commit 失败。"
}

Step "推送到 origin/$branch"

& git push origin $branch
if ($LASTEXITCODE -ne 0) {
    Warn "本地 README 已完成并 commit，但 push 失败。"
    Write-Host ""
    Write-Host "修复网络 / GitHub 登录后运行："
    Write-Host "  git push origin $branch"
    Write-Host ""
    Write-Host "README 备份目录：$backupDir"
    exit 1
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkGray
Write-Host "✅ Super Scholar GitHub 首页升级完成并已推送。" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor DarkGray
Write-Host ""
Write-Host "仓库：$remoteUrl"
Write-Host "分支：$branch"
Write-Host "备份：$backupDir"
Write-Host ""
Write-Host "已生成：" -ForegroundColor Cyan
Write-Host "  README.md"
Write-Host "  README.zh-CN.md"
Write-Host "  docs/README.md"
Write-Host "  .github/assets/super-scholar-hero.svg"
Write-Host "  .github/assets/super-scholar-logo.svg"
Write-Host ""
Write-Host "刷新 GitHub 仓库首页即可查看新效果。" -ForegroundColor Green
