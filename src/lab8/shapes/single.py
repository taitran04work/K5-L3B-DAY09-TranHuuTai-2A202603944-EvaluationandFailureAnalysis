"""Shape B — one ReAct agent.

Vòng `lab8.runtime.run_react` (max_steps=8). `decide` là "model": mỗi bước tốn
một model call (MockLLM) và chỉ được chọn tool ĐỌC:

    get_claim_view -> lookup_order -> lookup_refund_history -> compute_compensation -> final

`decide` không bao giờ đọc số ngày trễ trong ticket: quote luôn lấy từ order row
qua `compute_compensation`. Sau vòng lặp, CODE của shape (không phải model) gọi
`durability.issue_refund` với quote đầy đủ. Host trừ phần đã hoàn của đơn.

refund_history chỉ để ghi vào trace (giải thích), không dùng để tự trừ tiền.

Trace không ghi ticket, principal_id, parent_secret hay order row thô.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8 import durability
from lab8.db import connect
from lab8.mock_llm import complete
from lab8.runtime import run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.trace import Trace

SHAPE = "single"
MAX_STEPS = 8


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _run(conn: sqlite3.Connection, claim_id: str, *, seed: int, crash_at: str | None) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id(SHAPE, claim_id, seed))
    memory: dict[str, Any] = {}  # scratchpad của agent, chỉ giữ output của tool allowlist

    def decide(seen: dict[str, Any]) -> dict[str, Any]:
        # Mỗi lần "suy nghĩ" là một model call. Prompt chỉ là tên tool vừa chạy,
        # không đưa ticket vào để tránh prompt injection kiểu "ignore policy".
        complete(budget, seed=seed, purpose="react", prompt=f"{claim_id}|{seen.get('last_tool')}")
        last, result = seen.get("last_tool"), seen.get("last_result")
        if last:
            memory[last] = result
            trace.add("observe", {"tool": last, "result": _trace_view(last, result)})

        if "get_claim_view" not in memory:
            return {"tool": "get_claim_view", "args": {"claim_id": claim_id}}
        claim = memory["get_claim_view"]
        if not claim.get("found"):
            return {"final": {"status": "failed", "error_reason": "unknown_claim"}}
        if not claim.get("order_id"):
            return {"final": {"status": "needs_info", "error_reason": "missing_order_id"}}

        scope = {"order_id": claim["order_id"], "principal_id": claim["principal_id"]}
        if "lookup_order" not in memory:
            return {"tool": "lookup_order", "args": scope}
        order_view = memory["lookup_order"]
        if not order_view.get("visible"):
            return {"final": {"status": "escalated", "error_reason": order_view.get("reason")}}

        if "lookup_refund_history" not in memory:
            return {"tool": "lookup_refund_history", "args": scope}
        if "compute_compensation" not in memory:
            return {"tool": "compute_compensation", "args": {"order": order_view["order"]}}

        quote = memory["compute_compensation"]
        return {"final": {"status": "quoted", "amount_vnd": int(quote["amount_vnd"]), "reason": quote["reason"]}}

    loop = run_react(conn, budget, observation={"claim": {"claim_id": claim_id}}, decide=decide, max_steps=MAX_STEPS)
    final = loop["final"]
    trace.add("react_stop", {"stopped": loop["stopped"], "final": safe_dump(final)})

    def done(status: str, proposal: int = 0, reason: str | None = None) -> RunResult:
        trace.add("decision", {"status": status, "proposal_amount": proposal, "reason": reason})
        return finish(
            conn,
            shape=SHAPE,
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )

    if final.get("status") != "quoted":
        return done(final.get("status", "failed"), 0, final.get("error_reason"))

    proposal = int(final["amount_vnd"])
    if proposal <= 0:
        return done("denied", 0, final.get("reason"))

    # Code của shape (không phải model) gọi host. Không bắt InjectedCrash.
    trace.add("host_call", {"tool": "issue_refund", "proposed_vnd": proposal})
    outcome = durability.issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    trace.add("host_result", {"ok": outcome["ok"], "reason": outcome["reason"], "conflict": outcome["conflict"]})
    complete(budget, seed=seed, purpose="draft", prompt=f"proposal={proposal}")
    if not outcome["ok"]:
        return done("failed" if outcome["conflict"] else "denied", proposal, outcome["reason"])
    return done("resolved", proposal)


def _trace_view(tool: str, result: Any) -> dict[str, Any]:
    """Chỉ ghi phần an toàn của kết quả tool vào trace."""
    if not isinstance(result, dict):
        return {}
    if tool == "get_claim_view":
        # Bỏ ticket (chữ của khách, có thể chứa PII) và principal_id.
        return {k: result.get(k) for k in ("found", "claim_id", "order_id")}
    if tool == "lookup_policy":
        return {"policy_count": len(result.get("policies") or [])}
    return safe_dump(result)
