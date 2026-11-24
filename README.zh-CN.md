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
  <a href="https://github.com/fog-frog11/super-scholar/stargazers"><img src="https://img.shields.io/github/stars/fog-frog11/super-scholar?style=flat-square&color=7C6CF2" alt="GitHub stars"></a>
  <a href="https://github.com/fog-frog11/super-scholar/forks"><img src="https://img.shields.io/github/forks/fog-frog11/super-scholar?style=flat-square&color=5F8FEF" alt="GitHub forks"></a>
  <a href="https://github.com/fog-frog11/super-scholar/commits/main"><img src="https://img.shields.io/github/last-commit/fog-frog11/super-scholar?style=flat-square&color=41BFA8" alt="Last commit"></a>
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

## Docker 启动

在根目录运行 `docker compose up -d --build --wait`，然后打开 `http://127.0.0.1:3000`。首次启动会迁移空数据库。数据和上传材料由 Docker 卷持久保存，模型及学术数据源仍需自行配置。详细说明见 [Docker 部署与验收](DOCKER_DEPLOY.md)。

## 快速开始

### 环境要求

- Python **3.11+**
- Node.js **20+**
- npm
- Git

克隆仓库：

```bash
git clone https://github.com/fog-frog11/super-scholar.git
cd super-scholar
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
- [x] Docker 本机部署
- [ ] Hosted Demo

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

