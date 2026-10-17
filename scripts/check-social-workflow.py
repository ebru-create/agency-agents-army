#!/usr/bin/env python3
"""Validate a recorded social campaign snapshot; no execution or authorization service."""
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def validate(data):
    """Return actionable errors for malformed or internally inconsistent snapshots."""
    errors = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    def nonempty(value):
        return isinstance(value, str) and bool(value.strip())

    def strings(value):
        return isinstance(value, list) and all(nonempty(v) for v in value)

    if not isinstance(data, dict):
        return ["campaign must be an object"]
    require(data.get("schema_version") == 1, "schema_version must be 1")
    for key in ("campaign_id", "brief_revision"):
        require(nonempty(data.get(key)), f"{key} must be nonempty")
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return errors + ["tasks must be a nonempty array"]
    by_id = {}
    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            errors.append(f"task {i} must be an object")
            continue
        tid = task.get("id")
        if not nonempty(tid):
            errors.append(f"task {i} needs an id")
            continue
        require(tid not in by_id, f"duplicate task: {tid}")
        by_id[tid] = task
    for tid, task in by_id.items():
        require(nonempty(task.get("owner")), f"{tid}: owner required")
        require(type(task.get("required")) is bool, f"{tid}: required must be boolean")
        state = task.get("status")
        require(state in ("pending", "in_progress", "ready_for_qa", "verified", "blocked"), f"{tid}: invalid status")
        attempts = task.get("attempts")
        valid_attempts = type(attempts) is int and 0 <= attempts <= 3
        require(valid_attempts, f"{tid}: attempts must be an integer from 0 to 3")
        deps = task.get("dependencies")
        if not strings(deps):
            errors.append(f"{tid}: dependencies must be a string array")
            deps = []
        for dep in deps:
            require(dep in by_id, f"{tid}: unknown dependency {dep}")
        if state in ("in_progress", "ready_for_qa", "verified"):
            require(all(by_id.get(dep, {}).get("status") == "verified" for dep in deps), f"{tid}: dependency is not verified")
            require(task.get("brief_revision") == data.get("brief_revision"), f"{tid}: stale brief revision")
            revisions = task.get("dependency_revisions")
            if not isinstance(revisions, dict):
                errors.append(f"{tid}: dependency_revisions must be an object")
            else:
                for dep in deps:
                    require(dep in revisions and revisions[dep] == by_id.get(dep, {}).get("revision"), f"{tid}: stale dependency revision for {dep}")
        qa = task.get("qa")
        require(qa in ("NOT_RUN", "PASS", "FAIL", "UNTESTED"), f"{tid}: invalid QA verdict")
        if state in ("ready_for_qa", "verified"):
            require(valid_attempts and attempts > 0, f"{tid}: submission needs an attempt")
            require(nonempty(task.get("revision")), f"{tid}: submission needs a revision")
        if state == "verified":
            require(qa == "PASS", f"{tid}: verified requires QA PASS")
            require(strings(task.get("evidence")) and bool(task.get("evidence")), f"{tid}: verified needs evidence")
            require(task.get("qa_revision") == task.get("revision"), f"{tid}: stale QA revision")
        if valid_attempts and attempts == 3 and qa == "FAIL":
            require(state == "blocked", f"{tid}: third failed submission must block")
        if state == "blocked":
            require(nonempty(task.get("blocker")), f"{tid}: blocker reason required")

    # DFS checks all dependencies, including pending work, without trusting input IDs.
    visiting, visited = set(), set()

    def visit(tid):
        if tid in visiting:
            errors.append(f"dependency cycle at {tid}")
            return
        if tid in visited:
            return
        visiting.add(tid)
        deps = by_id[tid].get("dependencies")
        if strings(deps):
            for dep in deps:
                if dep in by_id:
                    visit(dep)
        visiting.remove(tid)
        visited.add(tid)

    for tid in by_id:
        visit(tid)
    require(data.get("status") in ("in_progress", "blocked", "complete"), "invalid campaign status")
    if data.get("status") == "complete":
        require(all(t.get("status") == "verified" for t in by_id.values() if t.get("required") is True), "complete campaign has unverified required tasks")

    publication = data.get("publication")
    if not isinstance(publication, dict):
        return errors + ["publication must be an object"]
    state = publication.get("status")
    require(state in ("draft", "ready", "scheduled", "published"), "invalid publication status")
    if state != "draft":
        review_id = publication.get("review_task")
        review = by_id.get(review_id, {}) if nonempty(review_id) else {}
        require(review.get("status") == "verified" and review.get("revision") == publication.get("revision"), "publication requires verified review of exact revision")
        approval = publication.get("approval")
        if not isinstance(approval, dict):
            return errors + ["publication needs explicit approval record"]
        for key in ("revision", "account", "action", "scheduled_at", "timezone", "spend_cap"):
            require(key in approval and key in publication and approval[key] == publication[key], f"approval mismatch: {key}")
        for key in ("revision", "account", "scheduled_at", "timezone"):
            require(nonempty(publication.get(key)), f"publication needs {key}")
        require(nonempty(approval.get("user_evidence")), "approval needs user instruction evidence")
        require(publication.get("action") in ("publish", "schedule"), "publication action must be publish or schedule")
        cap = publication.get("spend_cap")
        require(type(cap) in (int, float) and 0 <= cap < float("inf"), "spend_cap must be finite and nonnegative")
        try:
            dt = datetime.fromisoformat(publication.get("scheduled_at", ""))
            zone = ZoneInfo(publication.get("timezone", ""))
            require(dt.utcoffset() is not None and dt.utcoffset() == dt.astimezone(zone).utcoffset(), "schedule needs an offset matching timezone")
        except (ValueError, TypeError, KeyError):
            errors.append("invalid schedule/timezone")
        if state in ("scheduled", "published"):
            receipt = publication.get("receipt")
            if not isinstance(receipt, dict):
                errors.append("executed publication needs a receipt")
            else:
                for key in ("revision", "account", "action"):
                    require(receipt.get(key) == publication.get(key), f"receipt mismatch: {key}")
                for key in ("platform_id", "executed_at", "evidence"):
                    require(nonempty(receipt.get(key)), f"receipt needs {key}")
                require(receipt.get("outcome") == state, "receipt must confirm recorded publication outcome")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    try:
        problems = validate(json.loads(args.snapshot.read_text()))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(1, f"Invalid snapshot: {exc}\n")
    if problems:
        parser.exit(1, "\n".join(f"ERROR: {p}" for p in problems) + "\n")
    print("PASS: recorded campaign state is internally consistent (external evidence not authenticated)")
