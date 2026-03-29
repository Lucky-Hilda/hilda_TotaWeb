# -*- coding: utf-8 -*-
"""
直连测试 LongCat OpenAI 兼容接口（不依赖 FastAPI）。
用法：在 server 目录下执行  python test_longcat_upstream.py
需已配置 server/.env 中的 LONGCAT_API_KEY，或设置环境变量。
"""

import json
import os
import ssl
import sys
from pathlib import Path

try:
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen
except ImportError:
    print("需要 Python 3", file=sys.stderr)
    sys.exit(1)


def load_env_file():
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def main():
    load_env_file()
    key = os.getenv("LONGCAT_API_KEY", "").strip()
    url = os.getenv(
        "LONGCAT_API_URL",
        "https://api.longcat.chat/openai/v1/chat/completions",
    )
    model = os.getenv("LONGCAT_MODEL", "LongCat-Flash-Chat")

    if not key:
        print("错误：未设置 LONGCAT_API_KEY（请在 server/.env 中配置）", file=sys.stderr)
        sys.exit(2)

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "你好，请用一句话介绍澳门塔。"}],
        "max_tokens": 200,
        "temperature": 0.7,
    }
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=body,
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    ctx = ssl.create_default_context()
    print("请求:", url)
    print("模型:", model)
    try:
        with urlopen(req, timeout=60, context=ctx) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
    except HTTPError as e:
        print("HTTP 错误:", e.code, e.reason, file=sys.stderr)
        print(e.read().decode("utf-8", errors="replace")[:800], file=sys.stderr)
        sys.exit(3)
    except URLError as e:
        print("网络错误:", e.reason, file=sys.stderr)
        sys.exit(4)

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        print("响应 JSON 异常:", json.dumps(data, ensure_ascii=False)[:1200])
        sys.exit(5)

    print("--- 模型回复 ---")
    print(content)
    print("--- 测试通过 ---")


if __name__ == "__main__":
    main()
