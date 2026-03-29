# Macau Tower Destination Agent

澳门塔目的地演示站点：沉浸式首页、亮点导览、与 **Agent（智能对话）** 交互。完整体验 **LLM（大语言模型）+ RAG（检索增强生成）** 需要同时启动本地 API 服务并配置上游密钥。

---

## 重要文件索引

### Markdown 文档（建议优先阅读顺序）

| 文件 | 说明 |
|------|------|
| **`README.md`** | 本文件：运行方式、功能概览、目录说明。 |
| **`macau_tower_destination_agent_prd_v1.md`** | **PRD（产品需求文档）**：愿景、用户旅程、功能清单、Agent 流程、提示词与评估等非功能要求。 |
| **`macau_tower_implementation_vs_prd_v1.md`** | **实现对照说明**：当前网页/API 相对 PRD 的覆盖情况，以及 **Agent 链路**（前端本地规则 / 远程 RAG+LongCat / 失败兜底）的逐步说明。 |
| **`macau_tower_demo_kb_v1.md`** | **RAG 知识库正文**：按 `---` 分节；后端 `rag.py` 做 BM25 检索，将片段注入对话 system prompt。**改内容即可影响 Agent 回答依据（需在常识范围内，勿当实时票务数据）**。 |
| **`DEPLOY.md`** | **部署上线说明**：前后端拆分部署、`window.__AGENT_API__`、环境变量、Docker 与自检清单（需自行在云控制台操作）。 |

### 前端（`web/`）

| 文件 / 目录 | 说明 |
|-------------|------|
| **`web/index.html`** | 单页结构：首屏、亮点、Agent 对话、导览+纪念、模态框等。 |
| **`web/app.js`** | 前端逻辑：中英切换、快捷问题、对话与 **`sendUserMessage`**、本地意图/路线卡/FAQ、远程 `fetch /api/chat`、埋点、滚动与 snap 相关行为。 |
| **`web/agent-config.js`** | 可选：设置 `window.__AGENT_API__` 指向公网 API；GitHub Pages 部署可由 Actions 根据 Secret 覆盖。 |
| **`web/styles.css`** | 全局样式：深色主题、整页 scroll-snap、组件布局。 |
| **`web/assets/`** | 静态资源：如 `macauTowerBg.jpg`、`tota-agent.png`、`tota-chibi.png`、`mascot-tower.svg` 等。 |
| **`.github/workflows/deploy-github-pages.yml`** | 推送 `main`/`master` 时将 **`web/`** 部署到 **GitHub Pages**；详见 **`DEPLOY.md` 第 5 节**。 |

### 后端（`server/`）

| 文件 | 说明 |
|------|------|
| **`server/main.py`** | FastAPI 应用：`GET /api/health`、`POST /api/chat`（RAG 检索 + 调用 LongCat OpenAI 兼容接口）。 |
| **`server/rag.py`** | 读取仓库根目录 **`macau_tower_demo_kb_v1.md`**，建 BM25 索引，`retrieve_for_query` 供 `main.py` 使用。 |
| **`server/requirements.txt`** | Python 依赖。 |
| **`server/.env.example`** | 环境变量模板；复制为 **`server/.env`** 并填写密钥。 |
| **`server/.env`** | **本地密钥（勿提交版本库）**；含 `LONGCAT_API_KEY` 等。 |
| **`server/run.bat`** | Windows 下启动 uvicorn 的示例脚本（可能含本机 conda 环境名，通用用法见下文命令行）。 |
| **`server/test_longcat_upstream.py`** | 用于探测 LongCat 上游是否可用的测试脚本。 |
| **`server/.gitignore`** | 忽略 `.env` 等不应入库的文件。 |
| **`Dockerfile`**（仓库根目录） | 可选：构建仅含 API 的容器镜像（内含 `macau_tower_demo_kb_v1.md`），详见 **`DEPLOY.md`**。 |

上线步骤概要见 **`DEPLOY.md`**（无法代你完成云平台登录与点击部署）。

---

## 功能概览

| 能力 | 说明 |
|------|------|
| 首页与导览 | 首屏、亮点卡片、场景化导览、纪念文案弹窗等，打开页面即可浏览。 |
| **完整 Agent** | 对话走后端 `POST /api/chat`：从 `macau_tower_demo_kb_v1.md` **BM25 召回** 片段注入 system prompt，再调用 **LongCat** OpenAI 兼容接口生成回复。 |
| 本地规则兜底 | 未启动后端、接口报错或未配置密钥时，前端会用内置规则生成路线卡/FAQ 等（与「真 Agent」体验不同）。 |

---

## 完整体验 Agent（推荐流程）

### 1. 环境准备

- **Python** 3.10+（建议；需能安装 `requirements.txt` 中的依赖）
- **LongCat API Key**：在 [LongCat](https://longcat.chat) 等平台申请，用于调用 OpenAI 兼容的 Chat Completions 接口

### 2. 配置密钥

在仓库中的 `server` 目录：

1. 复制 `server/.env.example` 为 `server/.env`
2. 编辑 `server/.env`，将 `LONGCAT_API_KEY` 改为你自己的密钥（**勿将 `.env` 提交到版本库**）

可选环境变量（有默认值，一般不必改）：

- `LONGCAT_API_URL`：默认 `https://api.longcat.chat/openai/v1/chat/completions`
- `LONGCAT_MODEL`：默认 `LongCat-Flash-Chat`

### 3. 安装依赖并启动 API

在 `server` 目录下执行：

```bash
cd server
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

启动成功后：

- 健康检查：<http://127.0.0.1:8000/api/health> 应返回 `{"status":"ok"}`
- 对话接口：`POST http://127.0.0.1:8000/api/chat`（由前端自动调用）

> **说明**：若你使用仓库里的 `server/run.bat`，其中包含本机专用的 `conda activate` 环境名，可能与你的机器不一致；直接用上面的 `venv + uvicorn` 更通用。

### 4. 打开前端页面

前端默认请求 **`http://127.0.0.1:8000`**（见 `web/app.js` 中的 `API_BASE`）。

为避免部分浏览器对 `file://` 访问本地接口的限制，建议用**静态 HTTP** 打开 `web` 目录，例如在**项目根目录**执行：

```bash
# Python 3
python -m http.server 8080 --directory web
```

浏览器访问：<http://127.0.0.1:8080/>

然后：点击 **「和澳门塔聊聊」** 或滚动到对话区，使用**快捷问题**或**自由输入**即可体验完整 Agent。

### 5. 自定义 API 地址（可选）

若后端不在本机 `8000` 端口，可在 `web/index.html` 中于引入 `app.js` **之前**设置：

```html
<script>window.__AGENT_API__ = "http://你的主机:端口";</script>
```

---

## 仅前端 / 关闭远程 Agent（无需密钥）

适合快速看界面与本地规则逻辑：

1. **不启动**后端，或启动但未配置 `LONGCAT_API_KEY`（接口会 503，前端会走兜底）。
2. 或在页面中关闭远程 Agent（在引入 `app.js` 之前）：

```html
<script>window.__USE_REMOTE_AGENT__ = false;</script>
```

此时对话完全由前端 `app.js` 内的规则与模板处理，**不会**调用 LongCat，也**没有** RAG 检索。

---

## 项目结构（树状速览）

更完整的说明见上文 **「重要文件索引」**。

```
macau_tower_destination_agent/
├── README.md
├── macau_tower_destination_agent_prd_v1.md    # PRD
├── macau_tower_implementation_vs_prd_v1.md    # 实现对照 + Agent 链路
├── macau_tower_demo_kb_v1.md                  # RAG 知识库（勿随意移动或删空）
├── DEPLOY.md、Dockerfile、.dockerignore       # 部署与容器（可选）
├── web/
│   ├── index.html、app.js、styles.css
│   └── assets/
└── server/
    ├── main.py、rag.py、requirements.txt
    ├── .env.example、.env（本地，勿提交）
    ├── run.bat、test_longcat_upstream.py
    └── .gitignore
```

---

## 常见问题

**对话一直像「模板/路线卡」，不像大模型在聊天？**  
多半是未成功连上 `/api/chat`（后端未启、端口不对、密钥未配或上游报错）。可打开浏览器开发者工具 → **Network（网络）** 查看 `api/chat` 是否 200。

**接口返回 503「未配置 LONGCAT_API_KEY」？**  
检查 `server/.env` 是否在 `server` 目录下、变量名是否正确、服务是否重启。

**知识库相关报错？**  
`rag.py` 默认读取仓库根目录的 `macau_tower_demo_kb_v1.md`，请保持该文件存在且内容按文档中的 `---` 分节，以便切分为检索块。

---

## 免责声明

演示站中的票价、开放时段等**不保证为实时数据**；出行请以澳门塔官方渠道为准。
