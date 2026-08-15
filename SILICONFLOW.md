# 硅基流动接入

澳门塔 Agent 后端使用 OpenAI 兼容的 `chat/completions` 格式，可直接接入硅基流动。

## 1. 配置密钥

打开 `server/.env`，使用以下配置：

```env
MODEL_PROVIDER=SiliconFlow
MODEL_API_URL=https://api.siliconflow.cn/v1/chat/completions
MODEL_API_KEY=在硅基流动控制台创建的密钥
MODEL_NAME=Qwen/Qwen3-8B
MODEL_ENABLE_THINKING=false
```

不要把真实密钥写入 `.env.example`、前端代码或 Git。`server/.env` 已被项目的 `.gitignore` 排除。

## 2. 启动后端

在 `server` 目录运行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

## 3. 验证

健康检查：

```text
http://127.0.0.1:8000/api/health
```

上游直连检查：

```powershell
.\.venv\Scripts\python.exe test_model_upstream.py
```

`Qwen/Qwen3-8B` 适合低成本中文目的地问答。若更换模型，只需更新 `MODEL_NAME`，并以硅基流动模型中心当前名称为准。

