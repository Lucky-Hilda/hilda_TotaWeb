# -*- coding: utf-8 -*-
import copy
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SERVER_DIR))

import main
from test_streaming import ROUTE


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
