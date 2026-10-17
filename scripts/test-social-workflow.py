#!/usr/bin/env python3
"""Regression tests for campaign artifact gates, not model-behavior evaluations."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("social_workflow", ROOT / "scripts/check-social-workflow.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "examples/social-media-starter/campaign.json").read_text())

    def ready(self):
        data = copy.deepcopy(self.data)
        review = data["tasks"][3]
        review.update(status="verified", qa="PASS", qa_revision=review["revision"], evidence=["final-media-review-v2"])
        pub = data["publication"]
        pub["status"] = "ready"
        pub["approval"] = {k: pub[k] for k in ("revision", "account", "action", "scheduled_at", "timezone", "spend_cap")}
        pub["approval"]["user_evidence"] = "user-message-42"
        return data

    def test_authored_draft_is_consistent(self):
        self.assertEqual([], MODULE.validate(self.data))

    def test_reviewed_approved_package_is_ready(self):
        self.assertEqual([], MODULE.validate(self.ready()))

    def test_platform_adaptation_cannot_replace_brand_review(self):
        data = self.ready()
        data["publication"]["review_task"] = "adapt"
        self.assertTrue(MODULE.validate(data))

    def test_publish_action_cannot_be_reported_as_scheduled(self):
        data = self.ready()
        pub = data["publication"]
        pub.update(status="scheduled", action="publish")
        pub["approval"]["action"] = "publish"
        pub["receipt"] = dict(revision=pub["revision"], account=pub["account"], action="publish", platform_id="post-1", executed_at="2026-11-02T12:00:00+03:00", evidence="receipt-1", outcome="scheduled")
        self.assertTrue(MODULE.validate(data))

    def test_receipt_is_required_and_must_match(self):
        data = self.ready()
        pub = data["publication"]
        pub["status"] = "scheduled"
        self.assertTrue(MODULE.validate(data))
        pub["receipt"] = dict(revision=pub["revision"], account=pub["account"], action=pub["action"], platform_id="post-1", executed_at="2026-11-02T12:00:00+03:00", evidence="platform-response-1", outcome="scheduled")
        self.assertEqual([], MODULE.validate(data))
        for key in ("revision", "account", "action", "outcome", "platform_id", "executed_at", "evidence"):
            with self.subTest(key=key):
                changed = copy.deepcopy(data)
                changed["publication"]["receipt"][key] = ""
                self.assertTrue(MODULE.validate(changed))

    def test_approval_is_bound_to_every_action_field(self):
        for key, value in dict(revision="v3", account="other", action="publish", scheduled_at="2026-11-03T18:30:00+03:00", timezone="UTC", spend_cap=500).items():
            with self.subTest(key=key):
                data = self.ready()
                data["publication"][key] = value
                self.assertTrue(MODULE.validate(data))

    def test_missing_approval_or_user_evidence(self):
        for approval in (None, {}):
            data = self.ready()
            data["publication"]["approval"] = approval
            self.assertTrue(MODULE.validate(data))
        data = self.ready()
        del data["publication"]["approval"]["user_evidence"]
        self.assertTrue(MODULE.validate(data))

    def test_scheduling_is_not_publication(self):
        data = self.ready()
        data["publication"].update(status="published", receipt=dict(revision="intro-carousel-v2", account="@mavi-studio-demo", action="schedule", platform_id="post-1", executed_at="2026-11-02T12:00:00+03:00", evidence="receipt", outcome="scheduled"))
        self.assertTrue(MODULE.validate(data))

    def test_invalid_schedule_and_budget(self):
        for key, value in (("scheduled_at", "2026-11-02T18:30:00"), ("scheduled_at", "2026-11-02T18:30:00+00:00"), ("timezone", "Invalid/Zone"), ("spend_cap", -1), ("spend_cap", True), ("spend_cap", float("nan")), ("spend_cap", float("inf"))):
            with self.subTest(key=key, value=value):
                data = self.ready()
                data["publication"][key] = value
                data["publication"]["approval"][key] = value
                self.assertTrue(MODULE.validate(data))

    def test_required_blocker_prevents_completion(self):
        self.data["status"] = "complete"
        self.assertTrue(MODULE.validate(self.data))

    def test_independent_work_can_continue(self):
        # Analytics measurement plan is independent of the blocked final-media review.
        self.data["tasks"][4]["status"] = "in_progress"
        self.assertEqual([], MODULE.validate(self.data))

    def test_downstream_cannot_pass_unverified_input(self):
        self.data["tasks"][0]["status"] = "pending"
        self.assertTrue(MODULE.validate(self.data))

    def test_changed_verified_dependency_invalidates_downstream(self):
        self.data["tasks"][0].update(revision="strategy-v2", qa_revision="strategy-v2")
        self.assertTrue(MODULE.validate(self.data))

    def test_changed_brief_invalidates_prior_work(self):
        self.data["brief_revision"] = "brief-v2"
        self.assertTrue(MODULE.validate(self.data))

    def test_unavailable_evidence_is_not_a_pass(self):
        for qa in ("UNTESTED", "FAIL", "NOT_RUN"):
            data = self.ready()
            data["tasks"][3]["qa"] = qa
            self.assertTrue(MODULE.validate(data))

    def test_stale_or_missing_qa_evidence(self):
        for key, value in (("qa_revision", "old"), ("evidence", []), ("revision", "")):
            data = self.ready()
            data["tasks"][3][key] = value
            self.assertTrue(MODULE.validate(data))

    def test_third_failure_blocks_without_fourth_attempt(self):
        task = self.data["tasks"][3]
        task.update(attempts=3, qa="FAIL", status="in_progress")
        self.assertTrue(MODULE.validate(self.data))
        task["status"] = "blocked"
        self.assertEqual([], MODULE.validate(self.data))
        task["attempts"] = 4
        self.assertTrue(MODULE.validate(self.data))

    def test_attempt_zero_and_boolean_are_not_submissions(self):
        for attempts in (0, True, -1):
            data = self.ready()
            data["tasks"][3]["attempts"] = attempts
            self.assertTrue(MODULE.validate(data))

    def test_unknown_duplicate_and_cyclic_dependencies(self):
        mutations = [lambda d: d["tasks"][0]["dependencies"].append("missing"), lambda d: d["tasks"].append(copy.deepcopy(d["tasks"][0])), lambda d: d["tasks"][0]["dependencies"].append("adapt")]
        for mutation in mutations:
            data = copy.deepcopy(self.data)
            mutation(data)
            self.assertTrue(MODULE.validate(data))

    def test_malformed_top_level_and_tasks(self):
        for value in (None, [], {}, {"tasks": [None]}, {"tasks": [{"id": []}]}):
            self.assertTrue(MODULE.validate(value))

    def test_cli_reports_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid.json"
            path.write_text("{")
            result = subprocess.run([sys.executable, str(ROOT / "scripts/check-social-workflow.py"), str(path)], capture_output=True, text=True)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("Invalid snapshot", result.stderr)

    def test_malformed_publication_review_id(self):
        data = self.ready()
        data["publication"]["review_task"] = []
        self.assertTrue(MODULE.validate(data))

    def test_roster_installs_exactly_the_five_specialists(self):
        runbooks = json.loads((ROOT / "strategy/runbooks.json").read_text())["runbooks"]
        roster = next(r for r in runbooks if r["slug"] == "social-media-starter")
        agents = [a for group in roster["roster"] for a in group["agents"]]
        expected = {"marketing-social-media-strategist", "marketing-content-creator", "marketing-instagram-curator", "design-brand-guardian", "support-analytics-reporter"}
        self.assertEqual(expected, set(agents))
        self.assertEqual(5, len(agents))
        with tempfile.TemporaryDirectory() as tmp:
            team = Path(tmp) / "team.txt"
            team.write_text("\n".join(agents) + "\n")
            destination = Path(tmp) / "installed team"
            result = subprocess.run(["bash", str(ROOT / "scripts/install.sh"), "--tool", "claude-code", "--agents-file", str(team), "--path", str(destination), "--no-interactive"], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(expected, {p.stem for p in destination.glob("*.md")})


if __name__ == "__main__":
    unittest.main()
