# -*- coding: utf-8 -*-
"""安全检查当前 MODEL_* 配置与 OpenAI 兼容上游。不会输出密钥。"""

import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

provider = os.getenv("MODEL_PROVIDER", "SiliconFlow").strip() or "SiliconFlow"
url = os.getenv("MODEL_API_URL", "https://api.siliconflow.cn/v1/chat/completions").strip()
key = (os.getenv("MODEL_API_KEY", "").strip() or os.getenv("SILICONFLOW_API_KEY", "").strip())
model = os.getenv("MODEL_NAME", "Qwen/Qwen3-8B").strip()

if not key:
    print("错误：请先在 server/.env 中配置 MODEL_API_KEY", file=sys.stderr)
    raise SystemExit(2)

payload = {
    "model": model,
    "messages": [{"role": "user", "content": "请用一句话介绍澳门塔。"}],
    "max_tokens": 120,
    "temperature": 0.3,
    "enable_thinking": False,
}

try:
    response = httpx.post(
        url,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=60.0,
    )
except httpx.RequestError as exc:
    print(f"网络错误：{exc}", file=sys.stderr)
    raise SystemExit(3) from exc

print(f"Provider: {provider}")
print(f"Model: {model}")
print(f"HTTP: {response.status_code}")
if response.status_code != 200:
    print(response.text[:800], file=sys.stderr)
    raise SystemExit(4)

data = response.json()
content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
if not content:
    print("错误：响应中没有 assistant content", file=sys.stderr)
    raise SystemExit(5)

print("--- 模型回复 ---")
print(content)
print("--- 测试通过 ---")

