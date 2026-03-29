# 部署上线指南

本文说明如何把 **静态前端**（`web/`）与 **FastAPI 后端**（`server/`）部署到公网。**我无法代替你在云平台完成登录与点击部署**，请按下面步骤在你选的服务商控制台操作。

---

## 1. 架构说明

| 部分 | 内容 | 典型托管方式 |
|------|------|----------------|
| 前端 | `web/` 目录（HTML/CSS/JS/图片） | 静态托管：Vercel、Netlify、Cloudflare Pages、对象存储 + CDN |
| 后端 | `server/` + 仓库根目录 `macau_tower_demo_kb_v1.md` | PaaS：Render、Railway、Fly.io；或 VPS + Docker / systemd |
| 密钥 | `LONGCAT_API_KEY`（及可选 `LONGCAT_API_URL`、`LONGCAT_MODEL`） | **仅配置在后端环境变量**，不要写进前端仓库 |

后端已开启 `CORS allow_origins=["*"]`，前端域名与 API 域名不同也能调用（生产环境可改为白名单你的前端域名）。

---

## 2. 上线前必做：前端指向公网 API

本地默认请求 `http://127.0.0.1:8000`。上线后必须把 **`window.__AGENT_API__`** 设为你的 **HTTPS API 根地址**（无尾部斜杠）。

任选其一：

- 编辑 **`web/agent-config.js`**（已随仓库提供，并被 `index.html` 引用），写入：  
  `window.__AGENT_API__ = "https://你的-api-域名.com";`  
- 或在 **`web/index.html`** 里、**在** `<script src="app.js">` **之前**增加一行：

```html
<script>window.__AGENT_API__ = "https://你的-api-域名.com";</script>
```

若前后端 **同域**（例如 Nginx 把 `/api` 反代到 uvicorn），可设为同源根路径，让请求走相对地址：

```html
<script>window.__AGENT_API__ = "";</script>
```

此时浏览器会请求当前站点下的 `/api/chat`（需网关把 `/api` 转到后端）。

改完后重新构建/上传静态资源。

---

## 3. 部署后端（API）

### 3.1 环境变量（在平台「Environment」里配置）

| 变量 | 必填 | 说明 |
|------|------|------|
| `LONGCAT_API_KEY` | 是 | LongCat（或兼容 OpenAI Chat 的服务）密钥 |
| `LONGCAT_API_URL` | 否 | 默认 `https://api.longcat.chat/openai/v1/chat/completions` |
| `LONGCAT_MODEL` | 否 | 默认 `LongCat-Flash-Chat` |

### 3.2 部署要求

- **Python 3.10+**
- **工作目录**需能同时访问：
  - `server/main.py`、`server/rag.py` 等
  - 仓库根目录的 **`macau_tower_demo_kb_v1.md`**（`rag.py` 通过路径向上两级读取）
- **启动命令**（在 `server` 目录下，且保证知识库在上一级目录，与本地开发一致）：

```bash
cd server
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

PaaS 一般设置 **Root** 为仓库根、`Start command` 类似：

```bash
pip install -r server/requirements.txt && cd server && uvicorn main:app --host 0.0.0.0 --port $PORT
```

（若平台提供 `$PORT`，用平台变量替换 `8000`。）

### 3.3 使用 Docker（可选）

仓库根目录提供 **`Dockerfile`** 时，可在支持容器的平台「从 Dockerfile 部署」，并同样注入上述环境变量。

构建与本地试跑示例：

```bash
docker build -t macau-tower-api .
docker run -p 8000:8000 -e LONGCAT_API_KEY=你的密钥 macau-tower-api
```

健康检查：`GET http://localhost:8000/api/health` → `{"status":"ok"}`。

---

## 4. 部署前端（静态站）

1. 按 **第 2 节** 改好 `__AGENT_API__`（或同域反代）。
2. 将 **`web/` 下全部文件**（含 `assets/`）上传到静态托管的根目录或 `public`。
3. 若托管商要求「构建」，本项目无构建步骤，**发布目录选 `web`** 即可。

**注意**：全站需 **HTTPS**，否则浏览器可能拦截对 HTTPS API 的请求（混合内容）。

---

## 5. 使用 GitHub 部署（可以）

### 5.1 GitHub 能做什么、不能做什么

| 能力 | 说明 |
|------|------|
| **代码托管** | 把整个仓库推到 GitHub，协作与版本管理。 |
| **GitHub Pages** | 只托管**静态文件**，适合发布 **`web/`**（HTML/CSS/JS）。 |
| **GitHub Actions** | 可在 push 时自动把 `web/` 部署到 Pages，或调用其它平台 API（需自行写 workflow）。 |
| **不能** | Pages **不能**直接运行 Python / FastAPI；**后端必须**放在 Render、Railway、Fly.io、VPS、Docker 等（见第 3 节）。 |

### 5.2 用本仓库自带的 Workflow 发布前端到 Pages

1. 在 GitHub **新建仓库**，把本项目 **push** 上去（`main` 或 `master` 分支）。  
2. **先**按第 3 节把 API 部署好，记下公网根地址，例如 `https://macau-api.onrender.com`（**无**尾部斜杠）。  
3. 打开仓库 **Settings → Secrets and variables → Actions**，新建 Secret：  
   - 名称：`PUBLIC_AGENT_API_URL`  
   - 值：你的 API 根地址（HTTPS）。  
4. 打开 **Settings → Pages**，**Build and deployment** 里 **Source** 选 **GitHub Actions**（不要选 Deploy from a branch）。  
5. 推送任意提交到 `main`/`master`，或到 **Actions** 里手动运行 **Deploy web to GitHub Pages**。  
6. 完成后 Pages 会给出站点地址（形如 `https://<用户名>.github.io/<仓库名>/`）。  

Workflow 文件：`.github/workflows/deploy-github-pages.yml`。若**未**配置 `PUBLIC_AGENT_API_URL`，部署仍成功，但页面会继续请求默认 `127.0.0.1:8000`，**公网无法对话**——务必配置 Secret 或自行改 `web/agent-config.js` 后推送。

### 5.3 后端与 GitHub 的关系

- **LongCat 密钥**只放在**后端**托管平台的环境变量里，**不要**放进 GitHub Secret 给前端用（前端不需要密钥）。  
- 若希望「推代码自动部署 API」，需在 **Render/Railway** 等绑定 GitHub 仓库，或使用自定义 Action 调用其部署 API——本仓库未内置通用「部署后端」workflow，避免与你的账号强绑定。

---

## 6. 推荐组合（示例，非广告）

| 场景 | 前端 | 后端 |
|------|------|------|
| 快速演示 | Vercel / Netlify 拖 `web` | Render / Railway 免费档跑 Python |
| **GitHub 生态** | **GitHub Pages**（本仓库 Actions）发布 `web/` | 同上，API 仍用 Render 等 |
| 同机简单 | 一台 VPS：Nginx 静态 + 反代 `/api` 到本机 8000 | 同上 uvicorn 或 Docker |
| 仅展示 UI、不耗 Key | 只部署 `web`，并设 `window.__USE_REMOTE_AGENT__ = false` | 可不部署后端（仅本地规则） |

---

## 7. 自检清单

- [ ] `GET https://你的API/api/health` 返回 `ok`
- [ ] 前端 `__AGENT_API__` 与浏览器控制台 **Network** 里 `api/chat` 的域名一致
- [ ] 生产环境 **勿**把 `.env`、密钥提交到 Git
- [ ] 更新知识库后需 **重新部署后端**（或重启进程）以加载 `macau_tower_demo_kb_v1.md`

---

## 8. 我无法代你完成的步骤

- 在各云平台注册账号、绑卡、选区域
- 在 GitHub 上创建仓库、开启 Pages、填写 Secret
- 填写你的域名 DNS、申请证书（多数静态托管自动 HTTPS）
- 替你执行 `git push` 或上传文件

按本文改配置并在目标平台创建服务即可完成上线；若你希望增加 **某一平台（如 Render）逐步截图级教程**，可说明平台名称再补充文档。
