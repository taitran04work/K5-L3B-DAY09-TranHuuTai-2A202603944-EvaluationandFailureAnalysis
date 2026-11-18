"""Shape C — orchestrator plus read-only investigators.

1. Orchestrator đọc claim view (allowlist) để biết có order_id hay không.
2. Dựng handoff bằng `make_handoff`: facts rỗng (không mang parent context),
   allowed_tools chỉ gồm tool đọc. `make_handoff` tự sanitize và từ chối write tool.
3. `run_readonly_investigators` chạy các tool đọc; investigator không có quyền ghi.
4. Orchestrator lấy quote từ investigator (tính từ order row, không từ ticket)
   rồi tự gọi `durability.issue_refund` với quote đầy đủ.
5. Trace ghi handoff đã sanitize + order view allowlist, không ghi parent context.

Model calls: 1 lần lập kế hoạch (orchestrator), 1 lần tổng hợp (investigator),
1 lần soạn trả lời.
"""

from __future__ import annotations

import sqlite3

from lab8 import durability
from lab8.db import connect
from lab8.handoff import make_handoff
from lab8.mock_llm import complete
from lab8.runtime import run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import get_claim_view, tool_cost
from lab8.trace import Trace

SHAPE = "orchestrator"
INVESTIGATOR_TOOLS = ["lookup_order", "lookup_policy", "lookup_refund_history", "compute_compensation"]


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

    # Orchestrator: đọc claim view, lập kế hoạch.
    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    trace.add("claim", {"claim_id": claim_id, "found": claim["found"], "order_id": claim.get("order_id")})
    if not claim["found"]:
        return done("failed", reason="unknown_claim")
    complete(budget, seed=seed, purpose="plan", prompt=f"{claim_id}|has_order={bool(claim['order_id'])}")
    if not claim["order_id"]:
        complete(budget, seed=seed, purpose="draft", prompt="needs_info")
        return done("needs_info", reason="missing_order_id")

    # Handoff qua allowlist. facts rỗng: investigator tự đọc từ DB qua tool đọc.
    handoff = make_handoff(
        request_id=f"REQ-{claim_id}",
        claim_id=claim_id,
        task="quote_refund_entitlement",
        facts={},
        allowed_tools=INVESTIGATOR_TOOLS,
    )
    trace.add("handoff", safe_dump(handoff))

    investigated = run_readonly_investigators(conn, budget, handoff, principal_id=claim["principal_id"])
    tools = investigated["tools"]
    order_view = tools.get("lookup_order") or {}
    history = tools.get("lookup_refund_history") or {}
    complete(budget, seed=seed, purpose="investigate", prompt=f"{claim_id}|visible={order_view.get('visible')}")
    trace.add(
        "investigator",
        {
            "lookup_order": safe_dump(order_view),
            "policy_count": len((tools.get("lookup_policy") or {}).get("policies") or []),
            "refund_history": {k: history.get(k) for k in ("visible", "refund_count", "refunded_vnd")},
        },
    )
    if not order_view.get("visible"):
        complete(budget, seed=seed, purpose="draft", prompt="escalated")
        return done("escalated", reason=order_view.get("reason"))

    quote = tools.get("compute_compensation") or {"amount_vnd": 0, "reason": "no_quote"}
    trace.add("quote", safe_dump(quote))
    proposal = int(quote["amount_vnd"])
    if proposal <= 0:
        complete(budget, seed=seed, purpose="draft", prompt="denied")
        return done("denied", 0, quote.get("reason"))

    # Chỉ orchestrator ghi, qua host. Quote đầy đủ; không bắt InjectedCrash.
    trace.add("host_call", {"tool": "issue_refund", "proposed_vnd": proposal})
    outcome = durability.issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    trace.add("host_result", {"ok": outcome["ok"], "reason": outcome["reason"], "conflict": outcome["conflict"]})
    complete(budget, seed=seed, purpose="draft", prompt=f"proposal={proposal}")
    if not outcome["ok"]:
        return done("failed" if outcome["conflict"] else "denied", proposal, outcome["reason"])
    return done("resolved", proposal)
