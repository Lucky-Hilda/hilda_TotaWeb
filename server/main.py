# -*- coding: utf-8 -*-
"""
澳门塔 Agent API：RAG（BM25 召回）+ OpenAI 兼容模型接口。

默认接入硅基流动。密钥只从 server/.env 或进程环境变量读取，
不要写入前端、示例文件或版本库。
"""

import json
import os
from typing import Any, AsyncIterator, Dict, List, Literal, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import rag

load_dotenv()

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "SiliconFlow").strip() or "SiliconFlow"
MODEL_API_URL = os.getenv(
    "MODEL_API_URL",
    "https://api.siliconflow.cn/v1/chat/completions",
).strip()
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen3-8B").strip()
MODEL_API_KEY = (
    os.getenv("MODEL_API_KEY", "").strip()
    or os.getenv("SILICONFLOW_API_KEY", "").strip()
)
MODEL_ENABLE_THINKING = os.getenv("MODEL_ENABLE_THINKING", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

app = FastAPI(title="Macau Tower Agent API", version="0.2.0")

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
    response_mode: Literal["auto", "route"] = Field(
        default="auto",
        description="route 时要求模型返回可直接渲染的路线数据",
    )


class RouteStop(BaseModel):
    time: str = Field(..., min_length=1, max_length=30)
    duration: str = Field(..., min_length=1, max_length=30)
    title: str = Field(..., min_length=1, max_length=80)
    description: str = Field(..., min_length=1, max_length=240)
    tip: str = Field(default="", max_length=160)


class RoutePresentation(BaseModel):
    type: Literal["route"]
    title: str = Field(..., min_length=1, max_length=100)
    summary: str = Field(..., min_length=1, max_length=300)
    recommended_time: str = Field(..., min_length=1, max_length=60)
    duration: str = Field(..., min_length=1, max_length=40)
    pace: str = Field(..., min_length=1, max_length=30)
    stops: List[RouteStop] = Field(..., min_length=3, max_length=6)
    reminders: List[str] = Field(default_factory=list, max_length=4)
    follow_up: str = Field(default="", max_length=160)


def _build_system_prompt(kb_context: str, response_mode: str = "auto") -> str:
    base_prompt = f"""你是「澳门塔目的地 Agent」塔塔（Tota），人设为科技感旅游管家：专业但不生硬、表达有画面感、会主动给出场景化建议。

【知识库检索片段（请优先依据以下内容回答；勿编造实时票价、当日开放时间、活动排期等；若用户追问实时信息，请明确建议查阅澳门塔官网或现场公告）】
{kb_context}

【回答要求】
1. 以中文为主（若用户用英文提问则用英文回复）。
2. 紧扣用户问题，简洁有层次；可适当分段。
3. 涉及「值不值得去」「适合谁」「什么时段」等，结合知识库做场景化建议。
4. 知识库未覆盖的内容，可合理推理，但不要编造具体数字与实时政策。
5. 只输出给游客看的最终答复，不展示内部推理过程。"""

    if response_mode != "route":
        return base_prompt

    return base_prompt + """

【路线展示模式】
用户正在要求规划路线。只返回一个合法 JSON 对象，不要使用 Markdown 代码块，不要添加 JSON 以外的文字。
严格使用以下结构和字段名：
{
  "type": "route",
  "title": "路线名称",
  "summary": "一句话说明路线如何匹配用户的时间、同行人与偏好；信息不足时明确写出合理假设",
  "recommended_time": "建议到访时段，例如 17:00–20:00",
  "duration": "总时长，例如 约3小时",
  "pace": "轻松 / 适中 / 紧凑",
  "stops": [
    {
      "time": "开始时间",
      "duration": "停留时长",
      "title": "这一站的名称",
      "description": "游客在这一站做什么，以及为什么这样安排",
      "tip": "可操作的小提示；没有则返回空字符串"
    }
  ],
  "reminders": ["最多4条必要提醒，不写虚构票价或未经确认的开放时间"],
  "follow_up": "一个能继续细化路线的简短问题"
}
stops 必须按时间先后排列，共 3–6 站；整条路线应能实际执行，避免同一事项重复出现。"""


def _extract_json_object(content: str) -> Dict[str, Any]:
    """提取 JSON 对象，并把路线结果交给 Pydantic 校验。"""
    raw = content.strip()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(raw[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("路线结果不是 JSON 对象")
    return value


def _validated_route(content: str) -> Dict[str, Any]:
    value = _extract_json_object(content)
    if hasattr(RoutePresentation, "model_validate"):
        route = RoutePresentation.model_validate(value)
        return route.model_dump()
    route = RoutePresentation.parse_obj(value)
    return route.dict()


def _last_user_text(messages: List[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return message.content.strip()
    return ""


@app.get("/api/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "provider": MODEL_PROVIDER,
        "model": MODEL_NAME,
        "configured": bool(MODEL_API_KEY),
    }


@app.post("/api/chat")
async def chat(req: ChatRequest) -> Dict[str, Any]:
    if not MODEL_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="未配置 MODEL_API_KEY；请在 server/.env 中填写硅基流动 API Key",
        )

    messages = list(req.messages)
    if not messages:
        raise HTTPException(status_code=400, detail="messages 不能为空")

    last_user = _last_user_text(messages)
    if not last_user:
        raise HTTPException(status_code=400, detail="缺少 user 消息")

    kb_context, sources = rag.retrieve_for_query(last_user, top_k=5)
    wants_route = req.response_mode == "route"
    system_content = _build_system_prompt(kb_context, req.response_mode)

    outbound: List[dict[str, str]] = [{"role": "system", "content": system_content}]
    for message in messages:
        if message.role != "system":
            outbound.append({"role": message.role, "content": message.content})

    payload: Dict[str, Any] = {
        "model": MODEL_NAME,
        "messages": outbound,
        "max_tokens": req.max_tokens or 1000,
        "temperature": req.temperature if req.temperature is not None else 0.7,
        "enable_thinking": MODEL_ENABLE_THINKING,
    }
    if wants_route:
        # 硅基流动 JSON mode 让路线输出更稳定；后端仍会再次做 schema 校验。
        payload["response_format"] = {"type": "json_object"}
    headers = {
        "Authorization": f"Bearer {MODEL_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(MODEL_API_URL, headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"{MODEL_PROVIDER} 请求失败: {exc!s}") from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"{MODEL_PROVIDER} 返回异常 HTTP {response.status_code}: {response.text[:500]}",
        )

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"解析 {MODEL_PROVIDER} 响应失败: {response.text[:500]}",
        ) from exc

    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=502, detail=f"{MODEL_PROVIDER} 返回了空回复")

    presentation: Optional[Dict[str, Any]] = None
    message_content = content
    if wants_route:
        try:
            presentation = _validated_route(content)
            message_content = (
                f"{presentation['title']}：{presentation['summary']} "
                f"建议时段 {presentation['recommended_time']}，{presentation['duration']}。"
            )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=502,
                detail=f"{MODEL_PROVIDER} 路线结构不完整，请重试: {exc!s}",
            ) from exc

    return {
        "message": {"role": "assistant", "content": message_content},
        "presentation": presentation,
        "sources": sources,
        "model": MODEL_NAME,
        "provider": MODEL_PROVIDER,
    }


def _stream_line(event: str, **data: Any) -> str:
    """Serialize one NDJSON event without exposing internal reasoning."""
    return json.dumps({"event": event, **data}, ensure_ascii=False) + "\n"


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    """Stream visible progress and text while keeping route JSON atomic."""
    if not MODEL_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="未配置 MODEL_API_KEY；请在 Render Environment 中填写硅基流动 API Key",
        )

    messages = list(req.messages)
    if not messages:
        raise HTTPException(status_code=400, detail="messages 不能为空")

    last_user = _last_user_text(messages)
    if not last_user:
        raise HTTPException(status_code=400, detail="缺少 user 消息")

    wants_route = req.response_mode == "route"

    async def event_stream() -> AsyncIterator[str]:
        try:
            yield _stream_line("status", stage="retrieving")
            kb_context, sources = rag.retrieve_for_query(last_user, top_k=5)

            system_content = _build_system_prompt(kb_context, req.response_mode)
            outbound: List[dict[str, str]] = [
                {"role": "system", "content": system_content}
            ]
            for message in messages:
                if message.role != "system":
                    outbound.append(
                        {"role": message.role, "content": message.content}
                    )

            payload: Dict[str, Any] = {
                "model": MODEL_NAME,
                "messages": outbound,
                "max_tokens": req.max_tokens or 1000,
                "temperature": (
                    req.temperature if req.temperature is not None else 0.7
                ),
                "enable_thinking": MODEL_ENABLE_THINKING,
                "stream": True,
            }
            if wants_route:
                payload["response_format"] = {"type": "json_object"}

            headers = {
                "Authorization": f"Bearer {MODEL_API_KEY}",
                "Content-Type": "application/json",
            }

            yield _stream_line("status", stage="planning")
            content_parts: List[str] = []
            chunk_count = 0

            timeout = httpx.Timeout(120.0, connect=30.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    MODEL_API_URL,
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        raw = await response.aread()
                        detail = raw.decode("utf-8", errors="replace")[:500]
                        yield _stream_line(
                            "error",
                            detail=(
                                f"{MODEL_PROVIDER} 返回异常 HTTP "
                                f"{response.status_code}: {detail}"
                            ),
                        )
                        return

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or line.startswith(":") or line.startswith("event:"):
                            continue
                        raw = line[5:].strip() if line.startswith("data:") else line
                        if raw == "[DONE]":
                            break
                        try:
                            data = json.loads(raw)
                            choice = data["choices"][0]
                            delta = choice.get("delta", {}).get("content")
                            if delta is None:
                                delta = choice.get("message", {}).get("content")
                        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                            continue
                        if not isinstance(delta, str) or not delta:
                            continue

                        content_parts.append(delta)
                        chunk_count += 1
                        if wants_route:
                            if chunk_count % 12 == 0:
                                yield _stream_line("heartbeat")
                        else:
                            yield _stream_line("delta", content=delta)

            content = "".join(content_parts)
            if not content.strip():
                yield _stream_line(
                    "error",
                    detail=f"{MODEL_PROVIDER} 返回了空回复",
                )
                return

            if wants_route:
                yield _stream_line("status", stage="validating")
                try:
                    presentation = _validated_route(content)
                except (json.JSONDecodeError, TypeError, ValueError) as exc:
                    yield _stream_line(
                        "error",
                        detail=f"{MODEL_PROVIDER} 路线结构不完整，请重试: {exc!s}",
                    )
                    return

                message_content = (
                    f"{presentation['title']}：{presentation['summary']} "
                    f"建议时段 {presentation['recommended_time']}，"
                    f"{presentation['duration']}。"
                )
                yield _stream_line(
                    "route",
                    message={"role": "assistant", "content": message_content},
                    presentation=presentation,
                    sources=sources,
                    model=MODEL_NAME,
                    provider=MODEL_PROVIDER,
                )
            else:
                yield _stream_line(
                    "message",
                    message={"role": "assistant", "content": content},
                    presentation=None,
                    sources=sources,
                    model=MODEL_NAME,
                    provider=MODEL_PROVIDER,
                )

            yield _stream_line("done")
        except httpx.RequestError as exc:
            yield _stream_line(
                "error",
                detail=f"{MODEL_PROVIDER} 请求失败: {exc!s}",
            )
        except Exception as exc:
            yield _stream_line(
                "error",
                detail=f"生成回复时发生异常: {exc!s}",
            )

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
