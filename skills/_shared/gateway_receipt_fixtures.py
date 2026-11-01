#!/usr/bin/env python3
"""Synthetic gateway evidence tests, with no network or live project inputs."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import fixtures
import helpers
import schemas as S


def response(project="Synthetic", count=1, truncated=False):
    operation = {"tool": "urgency", "arguments": {"project": project}}
    return {
        "operation": operation, "project_ref": "synthetic-service",
        "view": "task_urgency", "observed_at": "2026-08-03T22:31:04.123456Z",
        "rows": [{"id": f"00000000-0000-4000-8000-{i:012d}", "urgency": "6.25",
                  "priority": 1, "project": project, "title": "Synthetic  title",
                  "flagged": False, "due": None, "review_on": None,
                  "status": "open", "updated_at": "2026-08-03T22:30:00.654321+00:00"}
                 for i in range(count)],
        "truncated": truncated, "outcome": "ok",
    }


def construct(result, operation=None, project="Synthetic", ref="synthetic-service"):
    return S.gateway_receipt(result, operation or result["operation"], ref, project)


def envelope(packet, project="Synthetic"):
    e = fixtures.base_envelope(project=project, mcp_receipts=[packet["receipt"]],
                              mutation_scope={"M2": [], "M3": [], "M4": []},
                              approval={"granted": False, "scope_string": None})
    e["capability_profile"]["external_detail"]["tasks_mcp"]["project_ref"] = "synthetic-service"
    e["returned_rows_by_capability"] = packet["returned_rows_by_capability"]
    return e


def run():
    problems = []
    def check(name, fn):
        try:
            fn()
        except Exception as exc:
            problems.append(f"{name}: {type(exc).__name__}: {exc}")
    def require(v):
        assert v
    def invalid(result, **kwargs):
        try:
            construct(result, **kwargs)
        except ValueError:
            return
        raise AssertionError("malformed evidence accepted")
    def mutate_result(name, mutate, **kwargs):
        r = response(); mutate(r)
        check(name, lambda: invalid(r, **kwargs))
    def valid_project():
        packet = construct(response())
        e = envelope(packet)
        require(S.validate_envelope(e, e["returned_rows_by_capability"])["valid"])
        require("[P1] Synthetic title" in helpers.render_task_mirror(
            packet["returned_rows_by_capability"]["tasks_mcp"], "2026-08-03"))
        require(packet["receipt"]["observed_at"] == response()["observed_at"])
    with fixtures.historical_clock():
        check("project-envelope-and-mirror", valid_project)
        for count, truncated in [(0, False), (8, False), (8, True)]:
            check(f"project-bound-{count}-{truncated}", lambda c=count,t=truncated: construct(response(count=c,truncated=t)))
        def portfolio():
            r = response(count=20, truncated=True)
            r["operation"] = {"tool":"urgency", "arguments":{"scope":"portfolio"}}
            r["rows"][0]["project"] = "Second"
            p = construct(r, project="portfolio")
            e = envelope(p, "portfolio")
            require(S.validate_envelope(e, e["returned_rows_by_capability"])["valid"])
        check("portfolio-explicit-mixed-projects", portfolio)
        check("independent-intended-operation", lambda: invalid(response(), operation={"tool":"urgency","arguments":{"project":"Other"}}))
        check("independent-intended-scope", lambda: invalid(response(), project="Other"))
        check("independent-service-ref", lambda: invalid(response(), ref="different-service"))
        for key, value in [("view","tasks"),("outcome","conflict"),("project_ref","other"),
                           ("observed_at","bad"),("truncated","false")]:
            kw = {"ref":"synthetic-service"} if key=="project_ref" else {}
            mutate_result(key, lambda r,k=key,v=value:r.__setitem__(k,v), **kw)
        mutate_result("foreign-row", lambda r:r["rows"][0].__setitem__("project","Other"))
        mutate_result("missing-row-column", lambda r:r["rows"][0].pop("updated_at"))
        mutate_result("private-extra-column", lambda r:r["rows"][0].__setitem__("details","not permitted"))
        mutate_result("duplicate-id", lambda r:r["rows"].append(copy.deepcopy(r["rows"][0])))
        mutate_result("wrong-tool", lambda r:r["operation"].__setitem__("tool","get_task"))
        mutate_result("extra-argument", lambda r:r["operation"]["arguments"].__setitem__("limit",8))
        mutate_result("missing-server-time", lambda r:r.pop("observed_at"))
        mutate_result("timezone-required", lambda r:r.__setitem__("observed_at","2026-08-03T22:30:00"))
        mutate_result("bad-row-date", lambda r:r["rows"][0].__setitem__("due","2026-02-30"))
        mutate_result("bool-priority", lambda r:r["rows"][0].__setitem__("priority",True))
        mutate_result("nonfinite-urgency", lambda r:r["rows"][0].__setitem__("urgency","NaN"))
        check("false-truncation", lambda: invalid(response(truncated=True)))
        check("project-overflow", lambda: invalid(response(count=9)))
        def fingerprint_literals():
            a = {"tool":"urgency","arguments":{"project":"Synthetic  Name"}}
            b = {"arguments":{"project":"Synthetic Name"},"tool":"urgency"}
            require(S.fingerprint_gateway_operation(a) != S.fingerprint_gateway_operation(b))
            require(S.fingerprint_gateway_operation(a) == S.fingerprint_gateway_operation(dict(reversed(list(a.items())))))
        check("literal-spaces-and-key-order", fingerprint_literals)
        def receipt_mutant(name, mutate):
            p=construct(response()); e=envelope(p); mutate(e)
            v=S.validate_envelope(e,e["returned_rows_by_capability"])
            require(not v["valid"])
            require("GATEWAY_RECEIPT" in {f["code"] for f in v["failures"]})
        mutants = {
            "transport-removed":lambda e:e["mcp_receipts"][0].pop("transport"),
            "transport-relabelled":lambda e:e["mcp_receipts"][0].__setitem__("transport","sql"),
            "result-removed":lambda e:e["mcp_receipts"][0].pop("gateway_result"),
            "fingerprint":lambda e:e["mcp_receipts"][0].__setitem__("operation_fingerprint","sha256:altered"),
            "time-diverges":lambda e:e["mcp_receipts"][0].__setitem__("observed_at","2026-08-03T22:32:00Z"),
            "truncation-diverges":lambda e:e["mcp_receipts"][0].__setitem__("truncated",True),
            "operation-diverges":lambda e:e["mcp_receipts"][0]["operation"]["arguments"].__setitem__("project","Other"),
            "exact-row-diverges":lambda e:e["returned_rows_by_capability"]["tasks_mcp"][0].__setitem__("title","Synthetic title"),
        }
        for name, mutant in mutants.items():
            check(name, lambda n=name,m=mutant:receipt_mutant(n,m))
        def time_case(instant, code):
            r=response();r["observed_at"]=instant;p=construct(r);e=envelope(p)
            require(code in {f["code"] for f in S.validate_envelope(e,e["returned_rows_by_capability"])["failures"]})
        check("stale-server-time",lambda:time_case("2026-08-03T21:00:00Z",S.STALE_RECEIPT))
        check("future-server-time",lambda:time_case("2026-08-04T00:00:00Z",S.FUTURE_RECEIPT))
        check("legacy-sql-unchanged",lambda:require(S.validate_envelope(fixtures.base_envelope(),{"tasks_mcp":fixtures.TASK_ROWS})["valid"]))
    def cli():
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp).resolve();r=response();(p/"operation.json").write_text(json.dumps(r["operation"]))
            command=[sys.executable,str(Path(__file__).with_name("runtime_cli.py")),"gateway-receipt","-",str(p/"operation.json"),"--project","Synthetic","--project-ref","synthetic-service"]
            done=subprocess.run(command,input=json.dumps(r),capture_output=True,text=True)
            require(done.returncode==0);data=json.loads(done.stdout)
            require(data["receipt"]["observed_at"]==r["observed_at"])
            require(data["returned_rows_by_capability"]["tasks_mcp"]==r["rows"])
            command[command.index(str(p/"operation.json"))]="-"
            done=subprocess.run(command,input=json.dumps(r),capture_output=True,text=True)
            require(done.returncode==2);require("EINPUT" in done.stdout)
    check("cli-stdin-and-single-input",cli)
    for issue in problems: print("FAIL",issue)
    print(f"Gateway receipt fixture failures: {len(problems)}")
    return problems


if __name__ == "__main__":
    sys.exit(bool(run()))
