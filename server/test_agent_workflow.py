# -*- coding: utf-8 -*-
import asyncio
import copy
import json
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SERVER_DIR))

import main
from test_streaming import ROUTE, FakeStreamResponse, collect_events


class RepairingAsyncClient:
    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, method, url, **kwargs):
        type(self).calls += 1
        route = copy.deepcopy(ROUTE)
        if type(self).calls == 1:
            route["stops"][1]["title"] = route["stops"][0]["title"]
        content = json.dumps(route, ensure_ascii=False)
        lines = [
            "data: " + json.dumps(
                {"choices": [{"delta": {"content": content}}]},
                ensure_ascii=False,
            ),
            "data: [DONE]",
        ]
        return FakeStreamResponse(lines)


class AgentWorkflowTests(unittest.TestCase):
    def test_constraint_memory_merges_and_shifts_arrival(self):
        first, changes = main.extract_trip_constraints(
            "周六下午4点半，两个人，想看夜景和拍照，节奏轻松"
        )
        self.assertEqual(first.date, "周六")
        self.assertEqual(first.start_time, "16:30")
        self.assertIn("2人", first.companions)
        self.assertEqual(first.preferences, ["夜景", "拍照"])
        self.assertEqual(first.pace, "轻松")
        self.assertGreaterEqual(len(changes), 5)

        shifted, shifted_changes = main.extract_trip_constraints(
            "晚30分钟到，而且不要高空刺激项目",
            first,
        )
        self.assertEqual(shifted.start_time, "17:00")
        self.assertIn("高空刺激", shifted.avoid)
        self.assertNotIn("冒险", shifted.preferences)
        self.assertTrue(any("17:00" in item for item in shifted_changes))

    def test_route_validator_catches_real_constraint_conflicts(self):
        broken = copy.deepcopy(ROUTE)
        broken["stops"][1]["title"] = broken["stops"][0]["title"]
        broken["stops"][1]["description"] = "安排笨猪跳冒险体验"
        broken["stops"][2]["time"] = "16:00"
        result = main.validate_route(
            broken,
            main.TripConstraints(
                start_time="17:00",
                duration="2小时",
                avoid=["高空刺激"],
            ),
        )
        self.assertFalse(result["passed"])
        failed = {item["code"] for item in result["checks"] if not item["passed"]}
        self.assertTrue({"chronology", "duplicates", "duration", "avoid"}.issubset(failed))


    def test_invalid_candidate_is_repaired_once(self):
        original_client = main.httpx.AsyncClient
        original_retrieve = main.rag.retrieve_for_query
        original_key = main.MODEL_API_KEY
        RepairingAsyncClient.calls = 0
        main.httpx.AsyncClient = RepairingAsyncClient
        main.rag.retrieve_for_query = lambda query, top_k=5: ("澳门塔知识", [])
        main.MODEL_API_KEY = "test-key"
        try:
            request = main.ChatRequest(
                messages=[
                    main.ChatMessage(
                        role="user",
                        content="周六下午，帮我规划一条轻松夜景路线",
                    )
                ],
                response_mode="route",
            )
            response = asyncio.run(main.chat_stream(request))
            events = asyncio.run(collect_events(response))
        finally:
            main.httpx.AsyncClient = original_client
            main.rag.retrieve_for_query = original_retrieve
            main.MODEL_API_KEY = original_key

        stages = [item["stage"] for item in events if item["event"] == "status"]
        self.assertIn("repairing", stages)
        route_event = next(item for item in events if item["event"] == "route")
        self.assertTrue(route_event["validation"]["passed"])
        self.assertEqual(route_event["validation"]["repair_attempts"], 1)
        self.assertTrue(
            any(item["tool"] == "revise_route" for item in route_event["trace"])
        )

    def test_revision_diff_keeps_changes_visible(self):
        previous = main._model_validate(main.RoutePresentation, ROUTE)
        revised_data = copy.deepcopy(ROUTE)
        revised_data["stops"][0]["time"] = "17:30"
        revised_data["pace"] = "适中"
        revised = main._model_validate(main.RoutePresentation, revised_data)
        changes = main.compare_routes(previous, revised)
        self.assertEqual(changes["type"], "revised")
        self.assertTrue(any("17:00" in item and "17:30" in item for item in changes["items"]))
        self.assertTrue(any("节奏" in item for item in changes["items"]))


if __name__ == "__main__":
    unittest.main()
