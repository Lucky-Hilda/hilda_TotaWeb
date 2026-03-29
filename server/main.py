# -*- coding: utf-8 -*-
"""
澳门塔 Agent API：RAG（BM25 召回） + LongCat OpenAI 兼容接口。
密钥请通过环境变量 LONGCAT_API_KEY 提供，勿写入代码库。
"""

import os
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException  
from fastapi.middleware.cors import CORSMiddleware 
from pydantic import BaseModel, Field

import rag

load_dotenv()

LONGCAT_URL = os.getenv(
    "LONGCAT_API_URL",
    "https://api.longcat.chat/openai/v1/chat/completions",
)
LONGCAT_MODEL = os.getenv("LONGCAT_MODEL", "LongCat-Flash-Chat")
LONGCAT_API_KEY = os.getenv("LONGCAT_API_KEY", "").strip()

app = FastAPI(title="Macau Tower Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., description="OpenAI 格式的对话历史")
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1000


def _build_system_prompt(kb_context: str) -> str:
    return f"""你是「澳门塔目的地 Agent」塔塔（Tota），人设为科技感旅游管家：专业但不生硬、表达有画面感、会主动给出场景化建议。

【知识库检索片段（请优先依据以下内容回答；勿编造实时票价、当日开放时间、活动排期等；若用户追问实时信息，请明确建议查阅澳门塔官网或现场公告）】
{kb_context}

【回答要求】
1. 以中文为主（若用户用英文提问则用英文回复）。
2. 紧扣用户问题，简洁有层次；可适当分段。
3. 涉及「值不值得去」「适合谁」「什么时段」等，结合知识库做场景化建议。
4. 知识库未覆盖的内容，可合理推理，但不要编造具体数字与实时政策。"""


def _last_user_text(messages: List[ChatMessage]) -> str:
    for m in reversed(messages):
        if m.role == "user":
            return m.content.strip()
    return ""


@app.get("/api/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(req: ChatRequest) -> Dict[str, Any]:
    if not LONGCAT_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="未配置 LONGCAT_API_KEY，请在 server/.env 中设置",
        )

    msgs = list(req.messages)
    if not msgs:
        raise HTTPException(status_code=400, detail="messages 不能为空")

    last_user = _last_user_text(msgs)
    if not last_user:
        raise HTTPException(status_code=400, detail="缺少 user 消息")

    kb_context, sources = rag.retrieve_for_query(last_user, top_k=5)
    system_content = _build_system_prompt(kb_context)

    outbound: List[dict[str, str]] = [{"role": "system", "content": system_content}]
    for m in msgs:
        if m.role == "system":
            continue
        outbound.append({"role": m.role, "content": m.content})

    payload = {
        "model": LONGCAT_MODEL,
        "messages": outbound,
        "max_tokens": req.max_tokens or 1000,
        "temperature": req.temperature if req.temperature is not None else 0.7,
    }

    headers = {
        "Authorization": f"Bearer {LONGCAT_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(LONGCAT_URL, headers=headers, json=payload)
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"上游请求失败: {e!s}") from e

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"LongCat 返回异常 HTTP {resp.status_code}: {resp.text[:500]}",
        )

    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise HTTPException(
            status_code=502,
            detail=f"解析 LongCat 响应失败: {resp.text[:500]}",
        ) from e

    return {
        "message": {"role": "assistant", "content": content},
        "sources": sources,
        "model": LONGCAT_MODEL,
    }
