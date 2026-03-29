import io
import json
import os
import time
from typing import Any

import httpx
import psycopg2
from dotenv import load_dotenv
from jose import jwt
from PIL import Image, ImageDraw

BASE = "http://127.0.0.1:8000"


class Verifier:
    def __init__(self) -> None:
        self.results: list[dict[str, Any]] = []
        self.failures: list[dict[str, str]] = []

    def record(self, name: str, ok: bool, detail: str = "") -> None:
        self.results.append({"check": name, "ok": ok, "detail": detail})
        if not ok:
            self.failures.append({"check": name, "detail": detail})

    def req(
        self,
        client: httpx.Client,
        method: str,
        path: str,
        token: str | None = None,
        expected: int | set[int] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        resp = client.request(method, BASE + path, headers=headers, **kwargs)
        if expected is not None:
            accepted = {expected} if isinstance(expected, int) else set(expected)
            if resp.status_code not in accepted:
                raise AssertionError(
                    f"{method} {path} -> {resp.status_code}, expected {sorted(accepted)}, body={resp.text}"
                )
        return resp

    @staticmethod
    def j(resp: httpx.Response) -> Any:
        return resp.json()

    @staticmethod
    def email(prefix: str) -> str:
        return f"{prefix}{time.time_ns()}@example.com"


def verify_api(v: Verifier) -> None:
    with httpx.Client(timeout=40) as client:
        # Health + auth contract
        health = v.j(v.req(client, "GET", "/", expected=200))
        v.record("health", health.get("ok") is True and health.get("service") == "reimbursement-api", json.dumps(health))

        password = "Pass@123"
        admin_a_email = v.email("admina")
        signup_a = v.j(
            v.req(
                client,
                "POST",
                "/auth/signup",
                expected=200,
                json={
                    "name": "Admin A",
                    "email": admin_a_email,
                    "password": password,
                    "country_code": "IN",
                },
            )
        )
        token_a = signup_a["token"]
        admin_a = signup_a["user"]

        v.record("signup contract", all(k in signup_a for k in ("token", "user", "company")), "signup keys")
        v.record("country->currency", signup_a["company"].get("currency_code") == "INR", json.dumps(signup_a["company"]))

        claims = jwt.get_unverified_claims(token_a)
        v.record("jwt payload keys", all(k in claims for k in ("user_id", "role", "company_id")), json.dumps(claims))

        me_a = v.j(v.req(client, "GET", "/auth/me", token=token_a, expected=200))
        v.record("auth/me role", me_a.get("role") == "admin", json.dumps(me_a))

        unauth = v.req(client, "GET", "/auth/me")
        v.record("unauth blocked", unauth.status_code in {401, 403}, f"status={unauth.status_code}")

        # Company A users
        manager_a = v.j(
            v.req(
                client,
                "POST",
                "/admin/users",
                token=token_a,
                expected=200,
                json={
                    "name": "Manager A",
                    "email": v.email("managera"),
                    "password": password,
                    "role": "manager",
                },
            )
        )
        finance_a = v.j(
            v.req(
                client,
                "POST",
                "/admin/users",
                token=token_a,
                expected=200,
                json={
                    "name": "Finance A",
                    "email": v.email("financea"),
                    "password": password,
                    "role": "manager",
                },
            )
        )
        employee_a = v.j(
            v.req(
                client,
                "POST",
                "/admin/users",
                token=token_a,
                expected=200,
                json={
                    "name": "Employee A",
                    "email": v.email("employeea"),
                    "password": password,
                    "role": "employee",
                    "manager_id": manager_a["id"],
                },
            )
        )

        token_manager_a = v.j(
            v.req(
                client,
                "POST",
                "/auth/login",
                expected=200,
                json={"email": manager_a["email"], "password": password},
            )
        )["token"]
        token_finance_a = v.j(
            v.req(
                client,
                "POST",
                "/auth/login",
                expected=200,
                json={"email": finance_a["email"], "password": password},
            )
        )["token"]
        token_employee_a = v.j(
            v.req(
                client,
                "POST",
                "/auth/login",
                expected=200,
                json={"email": employee_a["email"], "password": password},
            )
        )["token"]

        # Role guards
        v.record("employee blocked admin/users", v.req(client, "GET", "/admin/users", token=token_employee_a).status_code == 403)
        v.record("manager blocked admin/users", v.req(client, "GET", "/admin/users", token=token_manager_a).status_code == 403)
        v.record("manager blocked /expenses/all", v.req(client, "GET", "/expenses/all", token=token_manager_a).status_code == 403)

        # Patch manager assignment null and restore
        _ = v.j(
            v.req(
                client,
                "PATCH",
                f"/admin/users/{employee_a['id']}",
                token=token_a,
                expected=200,
                json={"manager_id": None},
            )
        )
        users_after_null = v.j(v.req(client, "GET", "/admin/users", token=token_a, expected=200))
        employee_now = next(user for user in users_after_null if user["id"] == employee_a["id"])
        v.record("manager assignment can be null", employee_now.get("manager_id") is None, json.dumps(employee_now))

        _ = v.j(
            v.req(
                client,
                "PATCH",
                f"/admin/users/{employee_a['id']}",
                token=token_a,
                expected=200,
                json={"manager_id": manager_a["id"]},
            )
        )

        # Rule 1: threshold 60, 3 approvers, 2 approvals resolve
        _ = v.j(
            v.req(
                client,
                "POST",
                "/admin/approval-rules",
                token=token_a,
                expected=200,
                json={
                    "name": "Threshold60",
                    "threshold": 60,
                    "is_hybrid": False,
                    "steps": [
                        {"approver_id": manager_a["id"], "order": 1},
                        {"approver_id": finance_a["id"], "order": 2},
                        {"approver_id": admin_a["id"], "order": 3},
                    ],
                },
            )
        )
        rules_now = v.j(v.req(client, "GET", "/admin/approval-rules", token=token_a, expected=200))
        v.record("approval-rules list contract", isinstance(rules_now, list) and len(rules_now) > 0, f"len={len(rules_now)}")

        exp1 = v.j(
            v.req(
                client,
                "POST",
                "/expenses",
                token=token_employee_a,
                expected=200,
                json={
                    "amount": 120,
                    "currency": "USD",
                    "category": "Travel",
                    "description": "Airport taxi",
                    "date": "2026-03-29",
                },
            )
        )
        exp1_id = exp1["id"]
        _ = v.j(
            v.req(
                client,
                "PATCH",
                f"/expenses/{exp1_id}/approve",
                token=token_manager_a,
                expected=200,
                json={"action": "approved", "comment": "ok"},
            )
        )
        _ = v.j(
            v.req(
                client,
                "PATCH",
                f"/expenses/{exp1_id}/approve",
                token=token_finance_a,
                expected=200,
                json={"action": "approved", "comment": "ok"},
            )
        )
        exp1_detail = v.j(v.req(client, "GET", f"/expenses/{exp1_id}", token=token_employee_a, expected=200))
        v.record("threshold 2/3 resolves", exp1_detail.get("status") == "approved", json.dumps({"status": exp1_detail.get("status")}))

        # Rule 2: hybrid specific approver auto-approves
        _ = v.j(
            v.req(
                client,
                "POST",
                "/admin/approval-rules",
                token=token_a,
                expected=200,
                json={
                    "name": "HybridSpecific",
                    "threshold": 90,
                    "specific_approver_id": finance_a["id"],
                    "is_hybrid": True,
                    "steps": [
                        {"approver_id": finance_a["id"], "order": 1},
                        {"approver_id": manager_a["id"], "order": 2},
                        {"approver_id": admin_a["id"], "order": 3},
                    ],
                },
            )
        )

        exp2 = v.j(
            v.req(
                client,
                "POST",
                "/expenses",
                token=token_employee_a,
                expected=200,
                json={
                    "amount": 50,
                    "currency": "INR",
                    "category": "Food",
                    "description": "Team lunch",
                    "date": "2026-03-29",
                },
            )
        )
        exp2_id = exp2["id"]
        _ = v.j(
            v.req(
                client,
                "PATCH",
                f"/expenses/{exp2_id}/approve",
                token=token_finance_a,
                expected=200,
                json={"action": "approved", "comment": "specific"},
            )
        )
        exp2_detail = v.j(v.req(client, "GET", f"/expenses/{exp2_id}", token=token_employee_a, expected=200))
        v.record("specific approver auto-approve", exp2_detail.get("status") == "approved", json.dumps({"status": exp2_detail.get("status")}))

        # Explicit rejection path
        _ = v.j(
            v.req(
                client,
                "POST",
                "/admin/approval-rules",
                token=token_a,
                expected=200,
                json={
                    "name": "RejectRule",
                    "is_hybrid": False,
                    "steps": [{"approver_id": manager_a["id"], "order": 1}],
                },
            )
        )
        exp_reject = v.j(
            v.req(
                client,
                "POST",
                "/expenses",
                token=token_employee_a,
                expected=200,
                json={
                    "amount": 40,
                    "currency": "INR",
                    "category": "Food",
                    "description": "Reject me",
                    "date": "2026-03-29",
                },
            )
        )
        _ = v.j(
            v.req(
                client,
                "PATCH",
                f"/expenses/{exp_reject['id']}/approve",
                token=token_manager_a,
                expected=200,
                json={"action": "rejected", "comment": "Not allowed"},
            )
        )
        exp_reject_detail = v.j(v.req(client, "GET", f"/expenses/{exp_reject['id']}", token=token_employee_a, expected=200))
        v.record("reject action updates status", exp_reject_detail.get("status") == "rejected", json.dumps({"status": exp_reject_detail.get("status")}))

        # Rule 3: manager-first
        _ = v.j(
            v.req(
                client,
                "POST",
                "/admin/approval-rules",
                token=token_a,
                expected=200,
                json={
                    "name": "ManagerFirst",
                    "is_hybrid": False,
                    "is_manager_first": True,
                    "steps": [{"approver_id": finance_a["id"], "order": 1}],
                },
            )
        )

        exp3 = v.j(
            v.req(
                client,
                "POST",
                "/expenses",
                token=token_employee_a,
                expected=200,
                json={
                    "amount": 75,
                    "currency": "INR",
                    "category": "Office",
                    "description": "Stationery",
                    "date": "2026-03-29",
                },
            )
        )
        exp3_id = exp3["id"]
        exp3_detail = v.j(v.req(client, "GET", f"/expenses/{exp3_id}", token=token_employee_a, expected=200))
        first_step = sorted(exp3_detail["approval_steps"], key=lambda row: row["step_order"])[0]
        v.record(
            "manager-first step 0",
            first_step["approver_id"] == manager_a["id"] and first_step["step_order"] == 0,
            json.dumps(first_step),
        )

        _ = v.j(
            v.req(
                client,
                "PATCH",
                f"/expenses/{exp3_id}/approve",
                token=token_manager_a,
                expected=200,
                json={"action": "approved", "comment": "mgr"},
            )
        )
        exp3_mid = v.j(v.req(client, "GET", f"/expenses/{exp3_id}", token=token_employee_a, expected=200))
        v.record("manager-first mid pending", exp3_mid.get("status") == "pending", json.dumps({"status": exp3_mid.get("status")}))

        _ = v.j(
            v.req(
                client,
                "PATCH",
                f"/expenses/{exp3_id}/approve",
                token=token_finance_a,
                expected=200,
                json={"action": "approved", "comment": "fin"},
            )
        )
        exp3_end = v.j(v.req(client, "GET", f"/expenses/{exp3_id}", token=token_employee_a, expected=200))
        v.record("manager-first final approved", exp3_end.get("status") == "approved", json.dumps({"status": exp3_end.get("status")}))

        # Rule 4: pending delete checks
        _ = v.j(
            v.req(
                client,
                "POST",
                "/admin/approval-rules",
                token=token_a,
                expected=200,
                json={
                    "name": "DeleteRule",
                    "is_hybrid": False,
                    "steps": [{"approver_id": manager_a["id"], "order": 1}],
                },
            )
        )

        exp4 = v.j(
            v.req(
                client,
                "POST",
                "/expenses",
                token=token_employee_a,
                expected=200,
                json={
                    "amount": 20,
                    "currency": "INR",
                    "category": "Other",
                    "description": "Pending deletable",
                    "date": "2026-03-29",
                },
            )
        )
        owner_del = v.req(client, "DELETE", f"/expenses/{exp4['id']}", token=token_employee_a)
        v.record("owner deletes pending", owner_del.status_code == 200, f"status={owner_del.status_code}")

        exp5 = v.j(
            v.req(
                client,
                "POST",
                "/expenses",
                token=token_employee_a,
                expected=200,
                json={
                    "amount": 30,
                    "currency": "INR",
                    "category": "Other",
                    "description": "Pending protected",
                    "date": "2026-03-29",
                },
            )
        )
        manager_queue = v.j(v.req(client, "GET", "/approvals/queue", token=token_manager_a, expected=200))
        queue_expense_ids = {item.get("expense_id") for item in manager_queue}
        v.record("manager approvals queue includes pending", exp5["id"] in queue_expense_ids, f"queue_len={len(manager_queue)}")
        employee_queue = v.j(v.req(client, "GET", "/approvals/queue", token=token_employee_a, expected=200))
        v.record("employee approvals queue empty", isinstance(employee_queue, list) and len(employee_queue) == 0, f"len={len(employee_queue)}")
        mgr_del = v.req(client, "DELETE", f"/expenses/{exp5['id']}", token=token_manager_a)
        v.record("manager cannot delete others", mgr_del.status_code == 403, f"status={mgr_del.status_code}")

        _ = v.j(
            v.req(
                client,
                "PATCH",
                f"/expenses/{exp5['id']}/approve",
                token=token_manager_a,
                expected=200,
                json={"action": "approved", "comment": "done"},
            )
        )
        owner_del_after = v.req(client, "DELETE", f"/expenses/{exp5['id']}", token=token_employee_a)
        v.record("owner cannot delete approved", owner_del_after.status_code == 400, f"status={owner_del_after.status_code}")

        # Rule 5 + admin override
        _ = v.j(
            v.req(
                client,
                "POST",
                "/admin/approval-rules",
                token=token_a,
                expected=200,
                json={
                    "name": "OverrideRule",
                    "is_hybrid": False,
                    "steps": [{"approver_id": manager_a["id"], "order": 1}],
                },
            )
        )

        exp6 = v.j(
            v.req(
                client,
                "POST",
                "/expenses",
                token=token_employee_a,
                expected=200,
                json={
                    "amount": 999,
                    "currency": "INR",
                    "category": "Travel",
                    "description": "Override test",
                    "date": "2026-03-29",
                },
            )
        )
        _ = v.j(
            v.req(
                client,
                "POST",
                f"/admin/expenses/{exp6['id']}/override",
                token=token_a,
                expected=200,
                json={"action": "rejected", "reason": "policy"},
            )
        )
        exp6_detail = v.j(v.req(client, "GET", f"/expenses/{exp6['id']}", token=token_employee_a, expected=200))
        v.record("override sets rejected", exp6_detail.get("status") == "rejected", json.dumps({"status": exp6_detail.get("status")}))
        v.record(
            "override audit entry",
            any(item.get("action") == "overridden" for item in exp6_detail.get("audit_logs", [])),
            "overridden in audit",
        )

        # list endpoints
        mine = v.j(v.req(client, "GET", "/expenses/mine", token=token_employee_a, expected=200))
        team = v.j(v.req(client, "GET", "/expenses/team", token=token_manager_a, expected=200))
        all_a = v.j(v.req(client, "GET", "/expenses/all", token=token_a, expected=200))
        v.record("/expenses/mine works", isinstance(mine, list) and len(mine) > 0, f"len={len(mine)}")
        v.record("/expenses/team works", isinstance(team, list) and len(team) > 0, f"len={len(team)}")
        v.record("/expenses/all works", isinstance(all_a, list) and len(all_a) > 0, f"len={len(all_a)}")
        analytics = v.j(v.req(client, "GET", "/admin/analytics", token=token_a, expected=200))
        v.record(
            "analytics contract",
            all(k in analytics for k in ("total_pending", "total_approved", "total_rejected", "by_category", "top_spenders")),
            json.dumps(analytics),
        )

        # Company B isolation
        admin_b_email = v.email("adminb")
        signup_b = v.j(
            v.req(
                client,
                "POST",
                "/auth/signup",
                expected=200,
                json={
                    "name": "Admin B",
                    "email": admin_b_email,
                    "password": password,
                    "country_code": "US",
                },
            )
        )
        token_b = signup_b["token"]
        employee_b = v.j(
            v.req(
                client,
                "POST",
                "/admin/users",
                token=token_b,
                expected=200,
                json={
                    "name": "Employee B",
                    "email": v.email("employeeb"),
                    "password": password,
                    "role": "employee",
                },
            )
        )
        _ = v.j(
            v.req(
                client,
                "POST",
                "/admin/approval-rules",
                token=token_b,
                expected=200,
                json={
                    "name": "RuleB",
                    "is_hybrid": False,
                    "steps": [{"approver_id": signup_b["user"]["id"], "order": 1}],
                },
            )
        )
        token_employee_b = v.j(
            v.req(
                client,
                "POST",
                "/auth/login",
                expected=200,
                json={"email": employee_b["email"], "password": password},
            )
        )["token"]
        exp_b = v.j(
            v.req(
                client,
                "POST",
                "/expenses",
                token=token_employee_b,
                expected=200,
                json={
                    "amount": 10,
                    "currency": "USD",
                    "category": "Food",
                    "description": "Company B expense",
                    "date": "2026-03-29",
                },
            )
        )

        all_a_after = v.j(v.req(client, "GET", "/expenses/all", token=token_a, expected=200))
        all_b_after = v.j(v.req(client, "GET", "/expenses/all", token=token_b, expected=200))
        ids_a = {row["id"] for row in all_a_after}
        ids_b = {row["id"] for row in all_b_after}
        v.record(
            "company isolation list",
            exp_b["id"] not in ids_a and exp_b["id"] in ids_b,
            json.dumps({"in_a": exp_b["id"] in ids_a, "in_b": exp_b["id"] in ids_b}),
        )
        cross = v.req(client, "GET", f"/expenses/{exp_b['id']}", token=token_a)
        v.record("cross-company detail blocked", cross.status_code == 403, f"status={cross.status_code}")

        # Currency contract
        countries = v.j(v.req(client, "GET", "/currency/countries", expected=200))
        conv = v.j(v.req(client, "GET", "/currency/convert?from=USD&to=INR&amount=100", expected=200))
        v.record(
            "currency countries contract",
            isinstance(countries, list) and len(countries) > 0 and all(k in countries[0] for k in ("name", "currency_code", "symbol")),
            f"count={len(countries)}",
        )
        v.record("currency convert contract", all(k in conv for k in ("converted_amount", "rate")), json.dumps(conv))

        # OCR contract: image + pdf + invalid
        image = Image.new("RGB", (800, 240), "white")
        draw = ImageDraw.Draw(image)
        draw.text((20, 20), "Demo Store\nTotal: $123.45\n2026-03-29", fill="black")

        image_buf = io.BytesIO()
        image.save(image_buf, format="PNG")
        ocr_image = v.j(
            v.req(
                client,
                "POST",
                "/ocr/scan",
                expected=200,
                files={"file": ("receipt.png", image_buf.getvalue(), "image/png")},
            )
        )
        v.record(
            "ocr image contract",
            all(
                k in ocr_image
                for k in ("amount", "date", "description", "vendor", "currency", "expense_type", "expense_lines")
            ),
            json.dumps(ocr_image),
        )

        pdf_buf = io.BytesIO()
        image.save(pdf_buf, format="PDF")
        ocr_pdf = v.j(
            v.req(
                client,
                "POST",
                "/ocr/scan",
                expected=200,
                files={"file": ("receipt.pdf", pdf_buf.getvalue(), "application/pdf")},
            )
        )
        v.record(
            "ocr pdf contract",
            all(
                k in ocr_pdf
                for k in ("amount", "date", "description", "vendor", "currency", "expense_type", "expense_lines")
            ),
            json.dumps(ocr_pdf),
        )

        invalid = v.req(client, "POST", "/ocr/scan", files={"file": ("bad.txt", b"hello", "text/plain")})
        v.record("ocr invalid file rejected", invalid.status_code == 400, f"status={invalid.status_code}")


def verify_schema(v: Verifier) -> None:
    load_dotenv(".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        v.record("DATABASE_URL present", False, "Missing DATABASE_URL in .env")
        return

    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    required_columns = {
        "companies": {"id", "name", "country_code", "currency_code", "created_at"},
        "users": {"id", "company_id", "name", "email", "password_hash", "role", "manager_id", "created_at"},
        "expenses": {
            "id",
            "employee_id",
            "amount",
            "currency",
            "amount_in_base",
            "category",
            "description",
            "date",
            "receipt_url",
            "status",
            "current_step_order",
            "created_at",
        },
        "expense_audit_log": {"id", "expense_id", "actor_id", "action", "comment", "created_at"},
        "approval_rules": {"id", "company_id", "name", "threshold_pct", "is_hybrid", "is_manager_first"},
        "approval_steps": {"id", "expense_id", "rule_id", "approver_id", "step_order", "status", "comment", "acted_at"},
        "approval_rule_steps": {"id", "rule_id", "approver_id", "step_order"},
    }

    cur.execute(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = ANY(%s)
        """,
        (list(required_columns.keys()),),
    )

    found: dict[str, set[str]] = {}
    for table_name, column_name in cur.fetchall():
        found.setdefault(table_name, set()).add(column_name)

    for table_name, needed in required_columns.items():
        present = found.get(table_name, set())
        missing = sorted(needed - present)
        v.record(f"schema columns {table_name}", len(missing) == 0, f"missing={missing}")

    approval_rule_columns = found.get("approval_rules", set())
    v.record(
        "schema specific approver column",
        ("specific_approver_id" in approval_rule_columns) or ("specific_approver" in approval_rule_columns),
        f"columns={sorted(approval_rule_columns)}",
    )

    cur.execute(
        """
        SELECT t.typname, array_agg(e.enumlabel ORDER BY e.enumsortorder)
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        GROUP BY t.typname
        """
    )
    enum_map = {name: set(labels) for name, labels in cur.fetchall()}

    v.record(
        "enum role values",
        any(values == {"admin", "manager", "employee"} for values in enum_map.values()),
        "role enum labels",
    )
    v.record(
        "enum expense status values",
        any(values == {"pending", "approved", "rejected"} for values in enum_map.values()),
        "expense status labels",
    )
    v.record(
        "enum audit action values",
        any(values == {"submitted", "approved", "rejected", "overridden"} for values in enum_map.values()),
        "audit action labels",
    )

    cur.close()
    conn.close()


def main() -> int:
    verifier = Verifier()

    try:
        verify_api(verifier)
        verify_schema(verifier)
    except Exception as exc:
        verifier.record("verification runtime", False, str(exc))

    summary = {
        "total_checks": len(verifier.results),
        "passed": len(verifier.results) - len(verifier.failures),
        "failed": len(verifier.failures),
        "failures": verifier.failures,
    }
    print(json.dumps(summary, indent=2))
    return 0 if not verifier.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
