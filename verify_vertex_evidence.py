from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "automatom-vertex-live-evidence-2026-08-22"
run = json.loads((ROOT / "run-us.json").read_text())
approved = json.loads((ROOT / "approve-us.json").read_text())
run_result = json.loads(run["result"])
approved_result = json.loads(approved["result"])
assert run["status"] == "done"
assert run_result["agentMode"] == "gemini"
assert run_result["status"] == "awaiting_approval"
assert run_result["notificationStatus"] == "pending_approval"
assert run_result["sent"] is False
assert approved["status"] == "done"
assert approved_result["agentMode"] == "gemini"
assert approved_result["status"] == "approved"
assert approved_result["notificationStatus"] == "approved_for_send"
assert approved_result["sent"] is False
print({
    "runUid": run["runUid"],
    "agentMode": approved_result["agentMode"],
    "statusBeforeApproval": run_result["status"],
    "statusAfterApproval": approved_result["status"],
    "notificationStatusAfterApproval": approved_result["notificationStatus"],
    "sent": approved_result["sent"],
})
