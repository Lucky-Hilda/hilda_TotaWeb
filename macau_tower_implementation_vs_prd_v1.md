# Macau Tower Destination Agent — 实现说明与 PRD 对照

**版本**：V1（对照 PRD：`macau_tower_destination_agent_prd_v1.md`）  
**范围**：当前仓库内 **网页前端**（`web/`）与 **Agent API**（`server/`）已实现能力说明。

---

## 1. 总览

| 维度 | PRD 预期 | 当前实现 |
|------|----------|----------|
| 产品形态 | 沉浸式网页 + 对话式 Agent | 已实现：单页纵向模块 + 对话区 |
| 推荐与问答 | 意图识别 + 知识召回 + 结构化路线卡 | **双轨**：远程为 LLM+RAG 文本回复；本地/兜底为规则意图 + 路线卡/FAQ |
| 内容底座 | 数字资产库 + 知识库可运营 | **演示级**：静态资源目录 + 单文件 Markdown 知识库（BM25），无后台管理 |
| 数据 | 完整埋点与统计 | **演示级**：前端内存埋点 + `console.debug`，无上报服务端 |

---

## 2. PRD 第 7 章功能清单对照

| 模块 | PRD 功能点 | 优先级 | 当前实现情况 |
|------|------------|--------|----------------|
| 首页展示 | 沉浸式首屏 | P0 | **已实现**：实景背景、粒子、Tota 立绘、主副标题、CTA（开始探索 / 和澳门塔聊聊）、底部「试试这样问」芯片；整页纵向 scroll-snap |
| 首页展示 | 澳门塔亮点卡片 | P0 | **已实现**：`#highlights` 四张亮点卡片（文案在 `app.js` I18N + 渲染） |
| Agent 交互 | 快捷问题入口 | P0 | **已实现**：首屏芯片 + 对话区内同款芯片；首屏点击会先滚到对话区再发送 |
| Agent 交互 | 自由对话框 | P0 | **已实现**：输入框 + 发送；历史最多 20 条参与远程请求 |
| Agent 交互 | 用户意图识别 | P0 | **部分符合 PRD**：**仅本地链路**有关键词打分意图（`detectIntent`）；**远程成功时**由大模型直接生成回复，**未**按 PRD 输出独立 JSON 意图节点 |
| 推荐能力 | 个性化玩法推荐 | P0 | **双轨**：本地/兜底用 `buildPlans` + 标签（情侣/家庭/半天/夜景等）；远程由 RAG+LLM 自然语言推荐，**非** PRD 所述结构化 JSON 计划接口 |
| 推荐能力 | 路线卡生成 | P0 | **已实现（本地/兜底路径）**：横向滑动路线卡，含时段、亮点、理由、CTA；**远程路径**一般为纯文本气泡，不自动出卡片 |
| 知识服务 | FAQ 问答 | P0 | **双轨**：本地关键词匹配固定 FAQ 文案；远程用知识库片段 + system 约束回答 |
| 导览体验 | 场景化导览内容 | P1 | **已实现（简化）**：横向导览卡片（黄昏/夜景/拍照/餐饮等），**静态文案**，非资产库动态拉取 |
| 内容生成 | 数字纪念卡生成 | P1 | **部分实现**：弹层内「纪念卡」样式预览 + 文案；**无**独立海报图生成、无下载图片；「重新生成」为模板文案轮换 |
| 内容生成 | 分享文案生成 | P1 | **部分实现**：与纪念卡共用一段文案；支持「复制分享文案」 |
| 转化承接 | 门票/活动详情跳转 | P0 | **已实现**：官网链接（路线卡内、转化区等）；**无**活动/餐饮多链接矩阵 |
| 用户留存 | 收藏路线卡 | P1 | **未实现** |
| 多语言 | 中英双语支持 | P1 | **已实现**：EN/中切换，I18N 驱动文案与快捷问题 |
| 数据层 | 行为埋点采集 | P0 | **演示级**：`analytics` 对象推入内存数组；**未**对接分析平台 |
| 底座层 | 数字资产库管理 | P0 | **未实现（管理端）**：仅 `web/assets` 静态引用 |
| 底座层 | 知识库管理 | P0 | **未实现（管理端）**：`macau_tower_demo_kb_v1.md` + 服务启动时 BM25 索引 |

### PRD 第 8 章详细功能摘要

| PRD 章节 | 实现要点 |
|----------|----------|
| 8.1 沉浸式首屏 | 与 PRD 低保真高度一致；Explore/开始探索滚到亮点区（含 snap 与首屏过渡处理） |
| 8.2 快捷问题 + 自由对话 | 低置信补问在**本地** `processReply` 中实现；远程路径无单独「置信度回问」API |
| 8.3 个性化推荐 | 主推荐 + 备选在**本地** `buildPlans` 中实现；卡片无「收藏」按钮 |
| 8.4 导览 | 无视频；弱网降级未单独做策略 |
| 8.5 纪念内容 | 无一键分享 SDK、无下载海报；违规校验未单独实现 |

### PRD 第 9 章提示词 / 节点设计

| PRD 节点 | 当前实现 |
|----------|----------|
| 意图识别 JSON | **未**按 PRD 独立调用模型输出 JSON；本地用 `detectIntent` 模拟 |
| 推荐结构化 JSON | **未**由模型输出；本地硬编码结构 |
| FAQ Prompt | 远程侧合并进 **单一 system prompt**（人设 + RAG 片段 + 边界） |
| 纪念文案 Prompt | **未**单独节点；本地 `generateMemorialText`，远程不自动触发生成 |

### PRD 第 11 章非功能

- **性能**：未做系统化压测；API 超时 120s。  
- **安全**：system 中约束不编造实时票价/开放时间；**无**单独输入过滤与敏感词服务。  
- **可维护性**：知识库为文件编辑；Prompt 在 `server/main.py` 内联字符串。

---

## 3. 当前 Agent 链路

以下描述**实际代码路径**，便于与 PRD 第 6 章「Agent 主流程」对照。

### 3.1 用户动作入口

1. 用户在 **`#agent`** 对话区输入或点击快捷问题（含首屏「试试这样问」：先 `scrollToAgentChat` 再 `sendUserMessage`）。  
2. **`sendUserMessage`**（`web/app.js`）：去空白 → 渲染用户气泡 → `chatHistory.push({ role: "user" })` → 展示 typing。

### 3.2 分支 A：关闭远程（`window.__USE_REMOTE_AGENT__ === false`）

1. 约 350ms 后关闭 typing。  
2. 对**当前用户句**执行 **`processReply(text)`**（纯前端规则链）。  
3. **`appendPureLocalReply`** 渲染：文本气泡或路线卡 DOM；更新 `chatHistory` 中 assistant 摘要。  
4. **不涉及**后端与 LongCat。

**`processReply` 内部顺序（与 PRD「理解层→决策层」粗略对应）**：

1. **`detectIntent`**：关键词打分 → `intent`（seed / faq / recommend / guide / memento / ambiguous 等）、`user_tags`、`need_followup`、`confidence`（启发式）。  
2. **`faqAnswer`**：命中票价/时间/交通/家庭/雨天等 → 直接固定 FAQ 文本返回。  
3. 若 **`need_followup`** → 返回补问文案（`followupLowConfidence`）。  
4. `intent === "faq"` → 通用 FAQ 文案。  
5. 种草 **`seed`** 或「值得去吗」类句式 → **`seedingAnswer`**。  
6. **`memento`** → **`buildPlans` 取首条** → **`generateMemorialText`** 模板纪念文案。  
7. 默认 → **`buildPlans`** 生成 1～2 套方案 → **`routeCardsHtml`** 结构化路线卡。  

**输出层**：对话气泡、横向路线卡、埋点 `intent_detected` / `recommendation_shown` 等。

### 3.3 分支 B：开启远程（默认，`USE_REMOTE_AGENT !== false`）

1. **POST** `{API_BASE}/api/chat`（默认 `http://127.0.0.1:8000`），Body：  
   - `messages`: `chatHistory.slice(-20)`（OpenAI 格式，**不含**前端计算的 intent JSON）  
   - `max_tokens: 1000`, `temperature: 0.7`  
2. **后端** `server/main.py` **`POST /api/chat`**：  
   - 校验 **`LONGCAT_API_KEY`**，否则 503。  
   - 取**最后一条 user** 文本 **`last_user`**。  
   - **`rag.retrieve_for_query(last_user, top_k=5)`**（`server/rag.py`）：  
     - 读取 **`macau_tower_demo_kb_v1.md`**，按 `---` 分块；  
     - **jieba 分词 + BM25Okapi** 检索 Top5；  
     - 拼接为带标题片段的上下文字符串（总长约 `max_chars`）。  
   - 组装 **`system`**：**人设（塔塔 Tota）+ 检索片段 + 回答边界**（不编造实时票价、开放时间等）。  
   - 追加对话中除 `system` 外的 **`user` / `assistant`** 消息。  
   - **HTTP POST** 至 **LongCat** OpenAI 兼容 **`/v1/chat/completions`**，解析 `choices[0].message.content`。  
   - 返回 JSON：`message`, `sources`（前端当前未展示 sources）。  
3. **前端**成功：typing 关闭 → 内容转义换行 → Agent 气泡；`chatHistory.push(assistant 纯文本)`；**不执行** `processReply`。  
4. **与 PRD 差异**：PRD 中「意图识别 → 场景分类 → 分任务调知识/推荐」在远程路径上**合并为单次 RAG + 单轮 Chat**；**无**独立的意图 JSON API、**无**模型输出结构化路线卡。

### 3.4 分支 C：远程请求失败（网络、4xx/5xx、空内容等）

1. 关闭 typing → 展示 **`localFallbackHint`** 文案。  
2. 对**同一句用户输入**再跑一遍 **`processReply`**（与分支 A 相同规则链）。  
3. 将本地产生的第二段 UI（文本或路线卡）追加展示；`chatHistory` 的 assistant 为 **提示 + 本地摘要拼接**。  

即：**远程优先，失败则规则兜底**，保证可演示闭环。

### 3.5 会话状态与其它交互

- **`sessionContext`**：`intent`、`tags`、`lastPlan` 在**本地** `processReply` 路径更新；**远程成功轮次不更新**（与 PRD「全程画像」有差距）。  
- **路线卡按钮**：「查看详情」→ `scrollToSnapSection("guide")`；「生成纪念卡」→ `openMemento()`；「门票」→ 外链官网。  
- **埋点**：`page_view`、`cta_click`、`quick_question_click`、`intent_detected`、`agent_api_success` / `agent_api_error`、`recommendation_shown`、`memento_open`、`conversion_click` 等，均写入内存 **`analytics.events`**。

---

## 4. 数据与文件索引（便于联调）

| 用途 | 路径 |
|------|------|
| 前端逻辑与本地 Agent | `web/app.js` |
| 样式与整页模块 | `web/styles.css` |
| 页面结构 | `web/index.html` |
| FastAPI 与 LLM 调用 | `server/main.py` |
| BM25 RAG | `server/rag.py` |
| 演示知识库 | `macau_tower_demo_kb_v1.md` |
| 环境变量示例 | `server/.env.example` |

---

## 5. 小结

- **已较好覆盖 PRD MVP（P0）中的「沉浸首页、亮点、对话、快捷问题、部分 FAQ/推荐/转化、双语」**；**路线卡与强规则意图主要出现在本地与兜底路径**。  
- **远程路径**实现为 **「最后一句用户话 BM25 检索 + 单次 LongCat 对话」**，与 PRD 多节点 Prompt（意图 JSON、推荐 JSON、独立 FAQ/纪念节点）**架构不一致**，但能在知识库范围内提供人格化连续对话。  
- **P1 与底座**：导览与纪念为**简化版**；**收藏、资产库/知识库后台、完整埋点上报、海报生成**等 **PRD 未在当前仓库实现**。

如需下一版对齐 PRD 第 9 章，可考虑：独立意图分类请求、推荐结构化输出（或由模型 JSON + 前端解析卡片）、远程失败时的重试 UI、以及服务端埋点与 CMS。
