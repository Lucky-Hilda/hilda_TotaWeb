# -*- coding: utf-8 -*-
"""
澳门塔 Agent API：会话状态 + 确定性工具 + RAG + OpenAI 兼容模型接口。

密钥只从 server/.env 或进程环境变量读取，不要写入前端、示例文件或版本库。
Agent 状态由前端随请求携带，因此不依赖数据库，也适合无状态部署。
"""

import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, AsyncIterator, Dict, List, Literal, Optional, Tuple

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
MAX_REPAIR_ATTEMPTS = 1

app = FastAPI(title="Macau Tower Agent API", version="0.3.0")

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


class TripConstraints(BaseModel):
    date: Optional[str] = None
    start_time: Optional[str] = None
    duration: Optional[str] = None
    companions: List[str] = Field(default_factory=list)
    preferences: List[str] = Field(default_factory=list)
    pace: Optional[str] = None
    avoid: List[str] = Field(default_factory=list)


class AgentState(BaseModel):
    constraints: TripConstraints = Field(default_factory=TripConstraints)
    current_plan: Optional[RoutePresentation] = None
    revision: int = 0
    last_action: Literal["chat", "planned", "revised"] = "chat"


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., description="OpenAI 格式的对话历史")
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1000
    response_mode: Literal["auto", "route"] = Field(
        default="auto",
        description="route 时要求模型返回可直接渲染的路线数据",
    )
    state: Optional[AgentState] = None


class UpstreamError(RuntimeError):
    pass


def _model_dump(value: BaseModel) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value.dict()


def _model_validate(model: Any, value: Any) -> Any:
    if hasattr(model, "model_validate"):
        return model.model_validate(value)
    return model.parse_obj(value)


def _unique(items: List[str]) -> List[str]:
    result: List[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def _clock_minutes(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    match = re.search(r"([01]?\d|2[0-3])[:：]([0-5]\d)", value)
    if not match:
        return None
    return int(match.group(1)) * 60 + int(match.group(2))


def _clock_text(minutes: int) -> str:
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _duration_minutes(value: str) -> Optional[int]:
    if not value:
        return None
    hour = re.search(r"(\d+(?:\.\d+)?)\s*(?:个)?小时", value)
    minute = re.search(r"(\d+)\s*分钟", value)
    total = 0
    if hour:
        total += int(float(hour.group(1)) * 60)
    if "半小时" in value:
        total += 30
    elif minute:
        total += int(minute.group(1))
    if total:
        return total
    if "半天" in value or "半日" in value:
        return 240
    return None


def extract_trip_constraints(
    text: str,
    current: Optional[TripConstraints] = None,
    current_plan: Optional[RoutePresentation] = None,
) -> Tuple[TripConstraints, List[str]]:
    """Deterministic tool: merge explicit user constraints into session state."""
    base = _model_dump(current or TripConstraints())
    changes: List[str] = []

    date_match = re.search(r"(今天|明天|后天|周[一二三四五六日天]|星期[一二三四五六日天])", text)
    if date_match and base.get("date") != date_match.group(1):
        base["date"] = date_match.group(1)
        changes.append(f"日期：{date_match.group(1)}")

    time_match = re.search(
        r"(?<!\d)([01]?\d|2[0-3])(?:[:：]([0-5]\d)|点(?:(半)|([0-5]?\d)分?)?)",
        text,
    )
    if time_match:
        hour = int(time_match.group(1))
        minute = 30 if time_match.group(3) else int(time_match.group(2) or time_match.group(4) or 0)
        prefix = text[: time_match.start()]
        if re.search(r"下午|傍晚|晚上|夜里", prefix[-8:]) and hour < 12:
            hour += 12
        value = f"{hour:02d}:{minute:02d}"
        if base.get("start_time") != value:
            base["start_time"] = value
            changes.append(f"到达：{value}")
    else:
        relative = re.search(r"(晚|推迟|延后|早|提前)\s*(\d+|半)\s*(分钟|小时)", text)
        if relative:
            anchor = _clock_minutes(base.get("start_time"))
            if anchor is None and current_plan and current_plan.stops:
                anchor = _clock_minutes(current_plan.stops[0].time)
            if anchor is not None:
                amount = 30 if relative.group(2) == "半" else int(relative.group(2))
                if relative.group(3) == "小时":
                    amount *= 60
                if relative.group(1) in {"早", "提前"}:
                    amount *= -1
                value = _clock_text(anchor + amount)
                base["start_time"] = value
                changes.append(f"到达调整为：{value}")

    duration_match = re.search(r"(\d+(?:\.\d+)?\s*(?:个)?小时|半天|半日)", text)
    if duration_match and base.get("duration") != duration_match.group(1):
        base["duration"] = duration_match.group(1)
        changes.append(f"时长：{duration_match.group(1)}")

    companions = list(base.get("companions") or [])
    companion_rules = [
        (r"情侣|对象|约会|男朋友|女朋友", "情侣"),
        (r"家人|家庭|父母|孩子|小孩|老人", "家人"),
        (r"朋友|同事", "朋友"),
        (r"一个人|独自|独行", "独自"),
    ]
    people = re.search(r"(\d+|两|三|四|五|六)\s*(?:个)?人", text)
    if people:
        number = {"两": "2", "三": "3", "四": "4", "五": "5", "六": "6"}.get(
            people.group(1), people.group(1)
        )
        companions.append(f"{number}人")
    for pattern, label in companion_rules:
        if re.search(pattern, text):
            companions.append(label)
    companions = _unique(companions)
    if companions != base.get("companions", []):
        base["companions"] = companions
        changes.append("同行：" + "、".join(companions))

    preferences = list(base.get("preferences") or [])
    preference_rules = [
        (r"夜景|灯光|华灯", "夜景"),
        (r"拍照|摄影|出片|打卡", "拍照"),
        (r"日落|黄昏|夕阳", "黄昏"),
        (r"餐厅|吃饭|晚餐|美食", "餐饮"),
        (r"刺激|冒险|蹦极|笨猪跳|空中漫步", "冒险"),
    ]
    negative = bool(re.search(r"不要|避开|不想|不去|排除|取消", text))
    for pattern, label in preference_rules:
        match = re.search(pattern, text)
        if not match:
            continue
        local_prefix = text[max(0, match.start() - 8) : match.start()]
        is_locally_negative = bool(
            re.search(r"不要|避开|不想|不去|排除|取消", local_prefix)
        )
        if not is_locally_negative:
            preferences.append(label)
    preferences = _unique(preferences)
    if preferences != base.get("preferences", []):
        base["preferences"] = preferences
        changes.append("偏好：" + "、".join(preferences))

    pace = None
    if re.search(r"轻松|松弛|慢一点|别太赶|不赶", text):
        pace = "轻松"
    elif re.search(r"紧凑|多安排|尽量多|赶一点", text):
        pace = "紧凑"
    elif re.search(r"适中|正常节奏", text):
        pace = "适中"
    if pace and base.get("pace") != pace:
        base["pace"] = pace
        changes.append(f"节奏：{pace}")

    avoid = list(base.get("avoid") or [])
    if negative:
        avoid_rules = [
            (r"高空|刺激|冒险|蹦极|笨猪跳|空中漫步", "高空刺激"),
            (r"餐厅|吃饭|晚餐|餐饮", "餐饮"),
            (r"拍照|摄影|打卡", "拍照"),
            (r"排队|人多", "长时间排队"),
        ]
        for pattern, label in avoid_rules:
            for match in re.finditer(pattern, text):
                local_prefix = text[max(0, match.start() - 8) : match.start()]
                if re.search(r"不要|避开|不想|不去|排除|取消", local_prefix):
                    avoid.append(label)
                    if label in preferences:
                        preferences.remove(label)
                    break
    avoid = _unique(avoid)
    if avoid != base.get("avoid", []):
        base["avoid"] = avoid
        base["preferences"] = preferences
        changes.append("避开：" + "、".join(avoid))

    return _model_validate(TripConstraints, base), changes


def _is_revision_request(text: str, state: AgentState) -> bool:
    if not state.current_plan:
        return False
    return bool(
        re.search(
            r"改|调整|换|不要|避开|去掉|取消|保留|晚|早|提前|推迟|节奏|重新排|第二站|第三站",
            text,
        )
    )


def validate_route(
    route: Dict[str, Any],
    constraints: Optional[TripConstraints] = None,
) -> Dict[str, Any]:
    """Deterministic tool: schema, chronology, duplicates, duration and avoid-list."""
    validated = _model_validate(RoutePresentation, route)
    data = _model_dump(validated)
    constraints = constraints or TripConstraints()
    issues: List[str] = []
    checks: List[Dict[str, Any]] = []

    times = [_clock_minutes(stop["time"]) for stop in data["stops"]]
    chronological = all(
        current is not None and following is not None and following >= current
        for current, following in zip(times, times[1:])
    )
    checks.append({"code": "chronology", "label": "时间顺序", "passed": chronological})
    if not chronological:
        issues.append("stops 必须按时间先后排列，并使用 HH:MM 时间")

    titles = [stop["title"].strip() for stop in data["stops"]]
    unique_titles = len(set(titles)) == len(titles)
    checks.append({"code": "duplicates", "label": "站点不重复", "passed": unique_titles})
    if not unique_titles:
        issues.append("路线中存在重复站点，请合并或替换")

    start_expected = _clock_minutes(constraints.start_time)
    start_actual = times[0] if times else None
    start_ok = (
        start_expected is None
        or start_actual is None
        or abs(start_actual - start_expected) <= 20
    )
    checks.append({"code": "arrival", "label": "匹配到达时间", "passed": start_ok})
    if not start_ok:
        issues.append(f"首站应从用户到达时间 {constraints.start_time} 附近开始")

    limit = _duration_minutes(constraints.duration or "")
    used = sum(_duration_minutes(stop["duration"]) or 0 for stop in data["stops"])
    duration_ok = limit is None or used <= limit + 30
    checks.append({"code": "duration", "label": "符合可用时长", "passed": duration_ok})
    if not duration_ok:
        issues.append(f"各站停留合计 {used} 分钟，超过用户可用时长 {constraints.duration}")

    route_text = " ".join(
        f"{stop['title']} {stop['description']} {stop.get('tip', '')}"
        for stop in data["stops"]
    )
    forbidden_map = {
        "高空刺激": ["笨猪跳", "蹦极", "空中漫步", "高空项目", "冒险体验"],
        "餐饮": ["餐厅", "晚餐", "用餐", "餐饮"],
        "拍照": ["拍照", "摄影", "打卡"],
        "长时间排队": ["排队等候", "长时间排队"],
    }
    conflicts = [
        avoid
        for avoid in constraints.avoid
        if any(term in route_text for term in forbidden_map.get(avoid, [avoid]))
    ]
    avoid_ok = not conflicts
    checks.append({"code": "avoid", "label": "避开排除项目", "passed": avoid_ok})
    if conflicts:
        issues.append("路线仍包含用户要求避开的项目：" + "、".join(conflicts))

    return {
        "passed": not issues,
        "checks": checks,
        "issues": issues,
        "repair_attempts": 0,
    }


def repair_route_deterministically(
    route: Any,
    constraints: Optional[TripConstraints] = None,
) -> Dict[str, Any]:
    """Deterministic tool: repair common schedule conflicts without a second model call."""
    constraints = constraints or TripConstraints()
    source = _model_dump(route) if isinstance(route, BaseModel) else route
    data = json.loads(json.dumps(source, ensure_ascii=False))
    stops = data.get("stops") or []
    if not 3 <= len(stops) <= 6:
        raise ValueError("确定性修复需要 3–6 个完整站点")

    start = _clock_minutes(constraints.start_time)
    if start is None:
        start = _clock_minutes(stops[0].get("time")) or (16 * 60 + 30)

    durations = [max(10, _duration_minutes(stop.get("duration", "")) or 30) for stop in stops]
    limit = _duration_minutes(constraints.duration or "")
    if limit is not None and sum(durations) > limit + 30:
        budget = max(limit, len(stops) * 10)
        base = budget // len(stops)
        durations = [base for _ in stops]
        for index in range(budget - base * len(stops)):
            durations[index] += 1

    safe_replacements = {
        "高空刺激": (
            ["笨猪跳", "蹦极", "空中漫步", "高空项目", "冒险体验"],
            "室内观景与城市故事",
            "在室内观景层沿城市天际线慢慢浏览，补充澳门城市地标与历史信息。",
        ),
        "餐饮": (
            ["餐厅", "晚餐", "用餐", "餐饮"],
            "观景层自由活动",
            "保留一段不设固定消费项目的自由活动时间，按现场状态灵活休息。",
        ),
        "拍照": (
            ["拍照", "摄影", "打卡"],
            "城市天际线观察",
            "把注意力放在城市方位与景观层次，不设置专门的影像任务。",
        ),
        "长时间排队": (
            ["排队等候", "长时间排队"],
            "机动体验时段",
            "根据现场人流选择较顺畅的体验，遇到拥挤可直接切换到下一站。",
        ),
    }

    seen: Dict[str, int] = {}
    cursor = start
    for index, stop in enumerate(stops):
        stop_text = f"{stop.get('title', '')} {stop.get('description', '')} {stop.get('tip', '')}"
        for avoid in constraints.avoid:
            terms, safe_title, safe_description = safe_replacements.get(
                avoid,
                ([avoid], "观景层机动体验", "按已确认的排除条件选择安全、轻松的现场体验。"),
            )
            if any(term in stop_text for term in terms):
                stop["title"] = safe_title
                stop["description"] = safe_description
                stop["tip"] = "该站已按你的排除条件自动替换。"
                break

        title = (stop.get("title") or f"路线站点 {index + 1}").strip()
        seen[title] = seen.get(title, 0) + 1
        if seen[title] > 1:
            title = f"{title} · 补充体验 {seen[title]}"
        stop["title"] = title[:80]
        stop["time"] = _clock_text(cursor)
        stop["duration"] = f"{durations[index]}分钟"
        cursor += durations[index]

    total = sum(durations)
    data["recommended_time"] = f"{_clock_text(start)}–{_clock_text(start + total)}"
    data["duration"] = f"约{total}分钟"
    if constraints.pace:
        data["pace"] = constraints.pace
    data["summary"] = (
        (data.get("summary") or "已生成可执行路线").rstrip("。")
        + "；系统已按已确认条件重新校准时间与冲突项。"
    )[:300]
    repaired = _model_validate(RoutePresentation, data)
    return _model_dump(repaired)


def compare_routes(
    previous: Optional[RoutePresentation],
    current: RoutePresentation,
) -> Dict[str, Any]:
    """Deterministic tool: make route revisions visible without exposing reasoning."""
    if not previous:
        return {
            "type": "created",
            "summary": f"已生成 {len(current.stops)} 个可执行站点",
            "items": [],
        }

    old_stops = previous.stops
    new_stops = current.stops
    items: List[str] = []
    for index in range(max(len(old_stops), len(new_stops))):
        if index >= len(old_stops):
            items.append(f"新增：{new_stops[index].title}")
        elif index >= len(new_stops):
            items.append(f"移除：{old_stops[index].title}")
        else:
            old = old_stops[index]
            new = new_stops[index]
            if old.title != new.title:
                items.append(f"第{index + 1}站：{old.title} → {new.title}")
            elif old.time != new.time:
                items.append(f"{new.title}：{old.time} → {new.time}")
    if previous.pace != current.pace:
        items.append(f"节奏：{previous.pace} → {current.pace}")
    if not items:
        items.append("保留原有站点，仅优化了路线说明与提示")
    return {
        "type": "revised",
        "summary": f"已完成第 {max(1, len(items))} 项路线调整",
        "items": items[:5],
    }


def _extract_json_object(content: str) -> Dict[str, Any]:
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
    route = _model_validate(RoutePresentation, _extract_json_object(content))
    return _model_dump(route)


def _last_user_text(messages: List[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return message.content.strip()
    return ""


def _build_system_prompt(
    kb_context: str,
    response_mode: str = "auto",
    constraints: Optional[TripConstraints] = None,
    previous_plan: Optional[RoutePresentation] = None,
    action: str = "planned",
    repair_issues: Optional[List[str]] = None,
) -> str:
    state_json = json.dumps(
        _model_dump(constraints or TripConstraints()),
        ensure_ascii=False,
    )
    base_prompt = f"""你是「澳门塔目的地 Agent」塔塔（Tota）。你不是泛化攻略生成器，而是会维护旅行约束、检索本地知识并产出可执行路线的规划 Agent。

【已确认的旅行条件】
{state_json}

【知识库检索片段】
{kb_context}

【回答要求】
1. 以中文为主；若用户用英文提问则用英文回复。
2. 优先依据知识库，不编造实时票价、当日开放时间或活动排期。
3. 条件不足时只做必要假设，并在回答中明确说明。
4. 只输出给游客看的结果，不展示内部思维过程。"""

    if response_mode != "route":
        return base_prompt

    previous_json = (
        json.dumps(_model_dump(previous_plan), ensure_ascii=False)
        if previous_plan
        else "无"
    )
    revision_rule = (
        "这是局部改线任务。除用户明确要求修改的内容外，尽量保留原路线的站点、顺序和描述。"
        if action == "revised"
        else "这是首次路线规划任务。"
    )
    repair_rule = ""
    if repair_issues:
        repair_rule = (
            "\n【上次结果未通过约束检查】\n"
            + "\n".join(f"- {item}" for item in repair_issues)
            + "\n请只修复这些问题，保留已经满足要求的部分。"
        )

    return base_prompt + f"""

【路线任务】
{revision_rule}
上一版路线：{previous_json}
{repair_rule}

只返回一个合法 JSON 对象，不要使用 Markdown 代码块，不要添加 JSON 以外的文字。
严格使用以下结构：
{{
  "type": "route",
  "title": "路线名称",
  "summary": "一句话说明如何匹配用户条件",
  "recommended_time": "例如 17:00–20:00",
  "duration": "例如 约3小时",
  "pace": "轻松 / 适中 / 紧凑",
  "stops": [
    {{
      "time": "HH:MM",
      "duration": "例如 30分钟",
      "title": "站点名称",
      "description": "做什么以及为什么这样安排",
      "tip": "可操作提示；没有则为空字符串"
    }}
  ],
  "reminders": ["最多4条必要提醒"],
  "follow_up": "一个简短的继续调整问题"
}}
stops 必须按时间先后排列，共 3–6 站；不得包含 avoid 中的项目；首站时间和总时长必须符合已确认条件。"""


def _build_payload(
    req: ChatRequest,
    messages: List[ChatMessage],
    system_content: str,
    wants_route: bool,
    stream: bool,
) -> Dict[str, Any]:
    outbound: List[Dict[str, str]] = [{"role": "system", "content": system_content}]
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
    if stream:
        payload["stream"] = True
    if wants_route:
        payload["response_format"] = {"type": "json_object"}
    return payload


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {MODEL_API_KEY}",
        "Content-Type": "application/json",
    }


async def _stream_model(payload: Dict[str, Any]) -> AsyncIterator[str]:
    timeout = httpx.Timeout(120.0, connect=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            MODEL_API_URL,
            headers=_headers(),
            json=payload,
        ) as response:
            if response.status_code != 200:
                raw = await response.aread()
                detail = raw.decode("utf-8", errors="replace")[:500]
                raise UpstreamError(
                    f"{MODEL_PROVIDER} 返回异常 HTTP {response.status_code}: {detail}"
                )
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
                if isinstance(delta, str) and delta:
                    yield delta


async def _post_model(payload: Dict[str, Any]) -> str:
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                MODEL_API_URL,
                headers=_headers(),
                json=payload,
            )
    except httpx.RequestError as exc:
        raise UpstreamError(f"{MODEL_PROVIDER} 请求失败: {exc!s}") from exc
    if response.status_code != 200:
        raise UpstreamError(
            f"{MODEL_PROVIDER} 返回异常 HTTP {response.status_code}: {response.text[:500]}"
        )
    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise UpstreamError(f"解析 {MODEL_PROVIDER} 响应失败") from exc
    if not isinstance(content, str) or not content.strip():
        raise UpstreamError(f"{MODEL_PROVIDER} 返回了空回复")
    return content


def _trace(tool: str, label: str, detail: str) -> Dict[str, str]:
    return {"tool": tool, "label": label, "status": "complete", "detail": detail}


def _route_message(presentation: Dict[str, Any]) -> str:
    return (
        f"{presentation['title']}：{presentation['summary']} "
        f"建议时段 {presentation['recommended_time']}，{presentation['duration']}。"
    )


@app.get("/api/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "provider": MODEL_PROVIDER,
        "model": MODEL_NAME,
        "configured": bool(MODEL_API_KEY),
        "agent_version": "2.0",
        "capabilities": [
            "constraint_memory",
            "knowledge_retrieval",
            "route_validation",
            "automatic_repair",
            "partial_revision",
        ],
    }


@app.post("/api/chat")
async def chat(req: ChatRequest) -> Dict[str, Any]:
    if not MODEL_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="未配置 MODEL_API_KEY；请在 Render Environment 中填写硅基流动 API Key",
        )
    messages = list(req.messages)
    last_user = _last_user_text(messages)
    if not messages or not last_user:
        raise HTTPException(status_code=400, detail="messages 不能为空且必须包含 user 消息")

    state = req.state or AgentState()
    constraints, constraint_changes = extract_trip_constraints(
        last_user,
        state.constraints,
        state.current_plan,
    )
    is_revision = req.response_mode == "route" and _is_revision_request(last_user, state)
    action = "revised" if is_revision else "planned"
    kb_context, sources = rag.retrieve_for_query(last_user, top_k=5)
    prompt = _build_system_prompt(
        kb_context,
        req.response_mode,
        constraints,
        state.current_plan,
        action,
    )
    payload = _build_payload(
        req,
        messages,
        prompt,
        req.response_mode == "route",
        stream=False,
    )
    try:
        content = await _post_model(payload)
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    trace = [
        _trace(
            "extract_constraints",
            "识别旅行条件",
            "；".join(constraint_changes) if constraint_changes else "沿用当前会话条件",
        ),
        _trace("search_knowledge", "检索澳门塔知识", f"召回 {len(sources)} 条本地信息"),
    ]
    presentation: Optional[Dict[str, Any]] = None
    validation: Optional[Dict[str, Any]] = None
    changes: Optional[Dict[str, Any]] = None
    if req.response_mode == "route":
        try:
            presentation = _validated_route(content)
            validation = validate_route(presentation, constraints)
            if not validation["passed"]:
                presentation = repair_route_deterministically(presentation, constraints)
                validation = validate_route(presentation, constraints)
                validation["repair_attempts"] = 1
                validation["repair_mode"] = "deterministic"
                trace.append(
                    _trace(
                        "revise_route",
                        "自动修复路线",
                        "确定性工具已校准时间、重复站点与排除项",
                    )
                )
            if not validation["passed"]:
                raise ValueError("；".join(validation["issues"]))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=502,
                detail=f"{MODEL_PROVIDER} 路线未通过约束检查: {exc!s}",
            ) from exc
        route_model = _model_validate(RoutePresentation, presentation)
        changes = compare_routes(state.current_plan, route_model)
        state = AgentState(
            constraints=constraints,
            current_plan=route_model,
            revision=state.revision + (1 if is_revision else 0),
            last_action=action,
        )
        trace.append(_trace("check_route_constraints", "校验路线可执行性", "全部约束通过"))
        content = _route_message(presentation)
    else:
        state = AgentState(
            constraints=constraints,
            current_plan=state.current_plan,
            revision=state.revision,
            last_action="chat",
        )

    return {
        "message": {"role": "assistant", "content": content},
        "presentation": presentation,
        "sources": sources,
        "model": MODEL_NAME,
        "provider": MODEL_PROVIDER,
        "agent_state": _model_dump(state),
        "trace": trace,
        "validation": validation,
        "changes": changes,
    }


def _stream_line(event: str, **data: Any) -> str:
    return json.dumps({"event": event, **data}, ensure_ascii=False) + "\n"


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    """Stream honest tool progress; route JSON remains atomic until validated."""
    if not MODEL_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="未配置 MODEL_API_KEY；请在 Render Environment 中填写硅基流动 API Key",
        )

    messages = list(req.messages)
    last_user = _last_user_text(messages)
    if not messages or not last_user:
        raise HTTPException(status_code=400, detail="messages 不能为空且必须包含 user 消息")
    wants_route = req.response_mode == "route"

    async def event_stream() -> AsyncIterator[str]:
        try:
            trace: List[Dict[str, str]] = []
            state = req.state or AgentState()

            yield _stream_line("status", stage="extracting")
            constraints, constraint_changes = extract_trip_constraints(
                last_user,
                state.constraints,
                state.current_plan,
            )
            trace.append(
                _trace(
                    "extract_constraints",
                    "识别旅行条件",
                    "；".join(constraint_changes) if constraint_changes else "沿用当前会话条件",
                )
            )
            yield _stream_line(
                "state",
                agent_state={
                    **_model_dump(state),
                    "constraints": _model_dump(constraints),
                },
            )

            yield _stream_line("status", stage="retrieving")
            search_query = last_user + "\n" + json.dumps(
                _model_dump(constraints),
                ensure_ascii=False,
            )
            kb_context, sources = rag.retrieve_for_query(search_query, top_k=5)
            trace.append(
                _trace(
                    "search_knowledge",
                    "检索澳门塔知识",
                    f"召回 {len(sources)} 条本地信息",
                )
            )

            is_revision = wants_route and _is_revision_request(last_user, state)
            action = "revised" if is_revision else "planned"
            stage = "revising" if is_revision else "planning"
            yield _stream_line("status", stage=stage)

            system_content = _build_system_prompt(
                kb_context,
                req.response_mode,
                constraints,
                state.current_plan,
                action,
            )
            payload = _build_payload(req, messages, system_content, wants_route, stream=True)
            content_parts: List[str] = []
            chunk_count = 0
            async for delta in _stream_model(payload):
                content_parts.append(delta)
                chunk_count += 1
                if wants_route:
                    if chunk_count % 12 == 0:
                        yield _stream_line("heartbeat")
                else:
                    yield _stream_line("delta", content=delta)

            content = "".join(content_parts)
            if not content.strip():
                yield _stream_line("error", detail=f"{MODEL_PROVIDER} 返回了空回复")
                return

            if wants_route:
                yield _stream_line("status", stage="validating")
                presentation: Optional[Dict[str, Any]] = None
                validation: Dict[str, Any]
                try:
                    presentation = _validated_route(content)
                    validation = validate_route(presentation, constraints)
                except Exception as exc:
                    validation = {
                        "passed": False,
                        "checks": [],
                        "issues": [f"路线 JSON 或字段结构不完整：{exc!s}"],
                        "repair_attempts": 0,
                    }

                repair_attempts = 0
                if not validation["passed"] and presentation is not None:
                    repair_attempts = 1
                    yield _stream_line("status", stage="repairing")
                    presentation = repair_route_deterministically(
                        presentation,
                        constraints,
                    )
                    validation = validate_route(presentation, constraints)
                    validation["repair_mode"] = "deterministic"
                    trace.append(
                        _trace(
                            "revise_route",
                            "自动修复路线",
                            "确定性工具已校准时间、重复站点与排除项",
                        )
                    )
                elif not validation["passed"] and MAX_REPAIR_ATTEMPTS:
                    repair_attempts = 1
                    yield _stream_line("status", stage="repairing")
                    repair_prompt = _build_system_prompt(
                        kb_context,
                        "route",
                        constraints,
                        state.current_plan,
                        action,
                        validation["issues"],
                    )
                    repair_messages = messages + [
                        ChatMessage(role="assistant", content=content)
                    ]
                    repair_payload = _build_payload(
                        req,
                        repair_messages,
                        repair_prompt,
                        True,
                        stream=True,
                    )
                    repaired_parts: List[str] = []
                    async for delta in _stream_model(repair_payload):
                        repaired_parts.append(delta)
                    repaired_content = "".join(repaired_parts)
                    try:
                        presentation = _validated_route(repaired_content)
                        validation = validate_route(presentation, constraints)
                        validation["repair_mode"] = "model"
                    except Exception as exc:
                        validation = {
                            "passed": False,
                            "checks": [],
                            "issues": [f"模型修复后结构仍不完整：{exc!s}"],
                            "repair_attempts": repair_attempts,
                        }

                    if not validation["passed"] and state.current_plan is not None:
                        presentation = repair_route_deterministically(
                            state.current_plan,
                            constraints,
                        )
                        validation = validate_route(presentation, constraints)
                        validation["repair_mode"] = "deterministic_fallback"
                    trace.append(
                        _trace(
                            "revise_route",
                            "自动修复路线",
                            "根据约束检查结果完成定向修复",
                        )
                    )

                validation["repair_attempts"] = repair_attempts
                if not validation["passed"] or presentation is None:
                    yield _stream_line(
                        "error",
                        detail="路线未通过可执行性检查：" + "；".join(validation["issues"]),
                    )
                    return

                route_model = _model_validate(RoutePresentation, presentation)
                changes = compare_routes(state.current_plan, route_model)
                next_state = AgentState(
                    constraints=constraints,
                    current_plan=route_model,
                    revision=state.revision + (1 if is_revision else 0),
                    last_action=action,
                )
                trace.append(
                    _trace(
                        "check_route_constraints",
                        "校验路线可执行性",
                        f"{sum(1 for item in validation['checks'] if item['passed'])} 项检查通过",
                    )
                )
                if is_revision:
                    trace.append(
                        _trace(
                            "compare_routes",
                            "比对路线改动",
                            changes["summary"],
                        )
                    )
                yield _stream_line(
                    "route",
                    message={"role": "assistant", "content": _route_message(presentation)},
                    presentation=presentation,
                    sources=sources,
                    model=MODEL_NAME,
                    provider=MODEL_PROVIDER,
                    agent_state=_model_dump(next_state),
                    trace=trace,
                    validation=validation,
                    changes=changes,
                )
            else:
                next_state = AgentState(
                    constraints=constraints,
                    current_plan=state.current_plan,
                    revision=state.revision,
                    last_action="chat",
                )
                yield _stream_line(
                    "message",
                    message={"role": "assistant", "content": content},
                    presentation=None,
                    sources=sources,
                    model=MODEL_NAME,
                    provider=MODEL_PROVIDER,
                    agent_state=_model_dump(next_state),
                    trace=trace,
                    validation=None,
                    changes=None,
                )

            yield _stream_line("done")
        except (httpx.RequestError, UpstreamError) as exc:
            yield _stream_line("error", detail=f"{MODEL_PROVIDER} 请求失败: {exc!s}")
        except Exception as exc:
            yield _stream_line("error", detail=f"生成回复时发生异常: {exc!s}")

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
