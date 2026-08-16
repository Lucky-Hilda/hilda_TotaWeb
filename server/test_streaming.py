# -*- coding: utf-8 -*-
import asyncio
import json
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SERVER_DIR))

import main


ROUTE = {
    "type": "route",
    "title": "黄昏夜景路线",
    "summary": "按黄昏到夜景的光线变化安排。",
    "recommended_time": "17:00–20:00",
    "duration": "约3小时",
    "pace": "轻松",
    "stops": [
        {
            "time": "17:00",
            "duration": "30分钟",
            "title": "抵达澳门塔",
            "description": "先熟悉入口与观景层动线。",
            "tip": "",
        },
        {
            "time": "17:30",
            "duration": "60分钟",
            "title": "黄昏观景",
            "description": "在光线柔和时完成观景与拍照。",
            "tip": "靠窗位置更适合观察光线变化。",
        },
        {
            "time": "18:30",
            "duration": "90分钟",
            "title": "夜景收尾",
            "description": "等待城市灯光亮起后完成夜景体验。",
            "tip": "",
        },
    ],
    "reminders": ["开放安排以官方信息为准。"],
    "follow_up": "需要我调整成更适合拍照的节奏吗？",
}


class FakeStreamResponse:
    status_code = 200

    def __init__(self, lines):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def aiter_lines(self):
        for line in self._lines:
            await asyncio.sleep(0)
            yield line

    async def aread(self):
        return b""


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, method, url, **kwargs):
        payload = kwargs["json"]
        if "response_format" in payload:
            content = json.dumps(ROUTE, ensure_ascii=False)
            midpoint = len(content) // 2
            pieces = [content[:midpoint], content[midpoint:]]
        else:
            pieces = ["澳门塔适合", "在黄昏前抵达。"]

        lines = []
        for piece in pieces:
            chunk = {"choices": [{"delta": {"content": piece}}]}
            lines.append("data: " + json.dumps(chunk, ensure_ascii=False))
        lines.append("data: [DONE]")
        return FakeStreamResponse(lines)


async def collect_events(response):
    events = []
    async for chunk in response.body_iterator:
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8")
        for line in chunk.splitlines():
            if line.strip():
                events.append(json.loads(line))
    return events


class StreamingChatTests(unittest.TestCase):
    def setUp(self):
        self.original_client = main.httpx.AsyncClient
        self.original_retrieve = main.rag.retrieve_for_query
        self.original_key = main.MODEL_API_KEY
        main.httpx.AsyncClient = FakeAsyncClient
        main.rag.retrieve_for_query = lambda query, top_k=5: ("澳门塔知识", [])
        main.MODEL_API_KEY = "test-key"

    def tearDown(self):
        main.httpx.AsyncClient = self.original_client
        main.rag.retrieve_for_query = self.original_retrieve
        main.MODEL_API_KEY = self.original_key

    def test_text_reply_streams_deltas_before_message(self):
        request = main.ChatRequest(
            messages=[main.ChatMessage(role="user", content="澳门塔值得去吗？")],
            response_mode="auto",
        )
        response = asyncio.run(main.chat_stream(request))
        events = asyncio.run(collect_events(response))

        self.assertEqual(events[0], {"event": "status", "stage": "retrieving"})
        self.assertEqual(events[1], {"event": "status", "stage": "planning"})
        self.assertEqual(
            "".join(item["content"] for item in events if item["event"] == "delta"),
            "澳门塔适合在黄昏前抵达。",
        )
        self.assertEqual(
            next(item for item in events if item["event"] == "message")["message"]["content"],
            "澳门塔适合在黄昏前抵达。",
        )
        self.assertEqual(events[-1]["event"], "done")

    def test_route_stays_atomic_until_validated(self):
        request = main.ChatRequest(
            messages=[
                main.ChatMessage(
                    role="user",
                    content="周六下午，两个人，帮我规划一条夜景路线",
                )
            ],
            response_mode="route",
        )
        response = asyncio.run(main.chat_stream(request))
        events = asyncio.run(collect_events(response))

        self.assertFalse(any(item["event"] == "delta" for item in events))
        stages = [
            item["stage"] for item in events if item["event"] == "status"
        ]
        self.assertEqual(stages, ["retrieving", "planning", "validating"])
        route_event = next(item for item in events if item["event"] == "route")
        self.assertEqual(route_event["presentation"]["type"], "route")
        self.assertEqual(len(route_event["presentation"]["stops"]), 3)
        self.assertEqual(events[-1]["event"], "done")


if __name__ == "__main__":
    unittest.main()
