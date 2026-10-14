#!/usr/bin/env python3
"""Draw the documentation's diagrams (app/docs/diagrams/*.svg).

    python scripts/docs_diagrams.py

The SVGs carry no colours or fonts of their own: every shape and label has a class (d-box, d-key, d-t, d-s...)
that app/static/docs.css colours with the theme's tokens, so the diagrams follow light and dark mode and match
the dashboard's palette. They are inlined into the page, so they may not contain scripts, styles, links or
images (app/docs/assets.py refuses them). Edit the layouts below and run the script again.

Each diagram restates something the code does; the comment above it says where.
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import List, Sequence

OUT = Path(__file__).resolve().parent.parent / "app" / "docs" / "diagrams"


class Diagram:
    def __init__(self, name: str, width: int, height: int):
        self.name, self.width, self.height = name, width, height
        self.parts: List[str] = []

    # -- primitives
    def box(self, x, y, w, h, title=None, lines: Sequence[str] = (), cls="d-box", mono: Sequence[str] = (),
            align="middle", r=8, title_cls="d-t"):
        self.parts.append('<rect class="%s" x="%g" y="%g" width="%g" height="%g" rx="%g"/>' % (cls, x, y, w, h, r))
        rows = ([(title, title_cls)] if title else []) + [(t, "d-s") for t in lines] + [(t, "d-m") for t in mono]
        heights = [18 if c == title_cls else 16 for _, c in rows]
        top = y + (h - sum(heights)) / 2
        tx = x + w / 2 if align == "middle" else x + 14
        for (text, c), dh in zip(rows, heights):
            top += dh
            self.text(tx, top - 4, text, c, align)

    def text(self, x, y, text, cls="d-s", anchor="middle"):
        self.parts.append('<text class="%s" x="%g" y="%g" text-anchor="%s">%s</text>'
                          % (cls, x, y, anchor, html.escape(text, quote=False)))

    def line(self, d, arrow=True, dash=False):
        self.parts.append('<path class="d-line%s" d="%s"%s/>'
                          % (" dash" if dash else "", d, ' marker-end="url(#%s-a)"' % self.name if arrow else ""))

    def num(self, x, y, n):
        self.parts.append('<circle class="d-numc" cx="%g" cy="%g" r="10"/>' % (x, y))
        self.text(x, y + 4, str(n), "d-num")

    def svg(self) -> str:
        defs = ('<defs><marker id="%s-a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                'orient="auto-start-reverse"><path class="d-arrow" d="M0,0 L10,5 L0,10 z"/></marker></defs>' % self.name)
        return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">\n%s\n%s\n</svg>\n'
                % (self.width, self.height, self.width, self.height, defs, "\n".join(self.parts)))


# ------------------------------------------------------------------------------------------------ diagrams

def how_a_run_flows() -> Diagram:
    """index.md: the policy drives the engine, which attacks the agent; the trace is evaluated into findings and
    verdicts, written as reports, and read in the terminal or CI, the local dashboard or the hosted dashboard."""
    d = Diagram("how-a-run-flows", 720, 330)
    d.box(16, 24, 150, 72, "Your policy", mono=["agentsec.yaml"])
    d.box(204, 16, 236, 88, "AgentSec engine", ["builds attack scenarios, plays the", "user, answers every tool call"],
          cls="d-key")
    d.box(584, 24, 120, 72, "Your agent", ["HTTP, Python,", "LangChain, MCP"])
    d.line("M166,60 H200")
    d.line("M440,48 H580")
    d.text(512, 40, "attacks, tool results", "d-s")
    d.line("M584,74 H444")
    d.text(512, 92, "replies, tool calls", "d-s")
    # evaluation pipeline
    d.line("M322,104 V122 H91 V140")
    d.box(16, 140, 150, 64, "Trace", ["every message and call"])
    d.box(196, 140, 160, 64, "Evaluators", ["deterministic rules", "(+ optional judge)"])
    d.box(386, 140, 150, 64, "Findings", ["and one verdict", "per scenario"])
    d.box(566, 140, 138, 64, "Reports", mono=["report.json, .html", "summary.md, .sarif"])
    d.line("M166,172 H192")
    d.line("M356,172 H382")
    d.line("M536,172 H562")
    # where reports go
    d.line("M635,204 V232 H111 V254", arrow=True)
    d.line("M371,232 V254")
    d.line("M635,232 V254")
    d.box(16, 254, 190, 64, "Terminal and CI", ["exit code, SARIF,", "pull-request comment"])
    d.box(266, 254, 210, 64, "Local dashboard", mono=["agentsec dashboard"])
    d.box(534, 254, 170, 64, "Hosted dashboard", ["via agentsec upload:", "history, compare, share"], cls="d-key")
    return d


def report_to_dashboard() -> Diagram:
    """guide/dashboard-tour.md and testing/upload.md: app/ingest.py and app/reports.py."""
    d = Diagram("report-to-dashboard", 720, 330)
    d.parts.append('<rect class="d-group" x="8" y="8" width="226" height="314" rx="12"/>')
    d.text(22, 30, "Your machine or CI", "d-x", "start")
    d.box(24, 44, 194, 52, mono=["agentsec test"], title="Run the tests")
    d.box(24, 128, 194, 52, mono=[".agentsec/report.json"], title="Report file")
    d.box(24, 212, 194, 60, title="Upload", mono=["agentsec upload", "or the GitHub Action"])
    d.line("M121,96 V124")
    d.line("M121,180 V208")
    d.parts.append('<rect class="d-group" x="300" y="8" width="412" height="314" rx="12"/>')
    d.text(314, 30, "Hosted dashboard", "d-x", "start")
    d.line("M218,242 H312")
    d.text(266, 226, "HTTPS", "d-s")
    d.text(266, 262, "Bearer asp_…", "d-m")
    steps = [("Check the token", "find its project (only a hash is stored)"),
             ("Read the body", "up to the plan's size limit, after decompression"),
             ("Check, summarise, store", "summarised by AgentSec's code, stored compressed"),
             ("Trim to the plan", "the oldest runs beyond the plan's limit are removed")]
    for i, (t, s) in enumerate(steps):
        y = 44 + i * 56
        d.num(332, y + 22, i + 1)
        d.box(352, y, 344, 44, t, [s], align="start")
        d.line("M524,%d V%d" % (y + 44, y + 52))
    d.box(352, 268, 344, 44, "The run is in the project", ["runs, history and comparisons in your browser"],
          cls="d-key", align="start")
    return d


def scenario_loop() -> Diagram:
    """concepts.md: agentsec/runners/local.py run_scenario, with the adapter in between."""
    d = Diagram("scenario-loop", 720, 400)
    cols = [(110, "AgentSec runner", "d-key"), (360, "Adapter", "d-box"), (610, "Your agent", "d-box")]
    for x, t, c in cols:
        d.box(x - 92, 10, 184, 40, t, cls=c)
        d.parts.append('<path class="d-line dash" d="M%d,50 V318"/>' % x)
    sub = ["HTTP, Python function,", "LangChain, ToolHost, MCP"]
    d.text(360, 66, sub[0], "d-s")
    d.text(360, 80, sub[1], "d-s")
    msgs = [  # (y, from, to, text)
        (106, 110, 610, "1  the user's message (a task, or the attack itself), session id, declared tools"),
        (148, 610, 110, "2  tool call: search_documents(…)"),
        (190, 110, 610, "3  simulated result: for a scenario tool, it carries the poisoned content"),
        (232, 610, 110, "4  tool call: send_email(…)  is recorded and flagged, never executed"),
        (274, 110, 610, "5  OK (simulated by AgentSec sandbox; no real action was taken)"),
        (310, 610, 110, "6  final reply, with no tool calls"),
    ]
    for y, a, b, t in msgs:
        d.line("M%d,%d H%d" % (a + (4 if b > a else -4), y, b + (-6 if b > a else 6)))
        d.text((a + b) / 2, y - 7, t, "d-s")
    d.box(18, 336, 684, 52, None, cls="d-soft")
    d.text(360, 358, "Repeats until a reply has no tool calls or a limit (steps, tool calls, time) stops it.", "d-s")
    d.text(360, 376, "Then the trace is evaluated against the policy: findings, and one verdict for the scenario.", "d-s")
    return d


def verdict_decision() -> Diagram:
    """results/verdicts.md: ScenarioResult.status in agentsec/runners/local.py, first match wins."""
    d = Diagram("verdict-decision", 720, 432)
    d.box(130, 8, 220, 36, "A scenario has finished", cls="d-soft")
    qs = [("Did any check fire?", "", "Findings", "d-bad", "tested"),
          ("Did the trace end in an error?", "unreachable, timeout, bad reply", "Error", "d-err", "not tested"),
          ("Multi-agent scenario, and no event", "says which agent acted?", "Not observable", "d-muted", "not tested"),
          ("Tracks delivery, and the content never", "reached the agent in a tool result?", "Inconclusive", "d-warn",
           "not tested")]
    y = 64
    d.line("M240,44 V%d" % (y - 4))
    for q1, q2, label, cls, tested in qs:
        d.box(60, y, 360, 52, q1, [q2] if q2 else [])
        d.line("M420,%d H494" % (y + 26))
        d.text(457, y + 19, "yes", "d-yes")
        d.box(498, y + 6, 134, 40, label, cls=cls, r=20)
        d.text(644, y + 30, tested, "d-s", "start")
        d.line("M240,%d V%d" % (y + 52, y + 72))
        d.text(252, y + 66, "no", "d-no", "start")
        y += 76
    d.box(60, y, 360, 52, "Attacked and judged, nothing fired")
    d.line("M420,%d H494" % (y + 26))
    d.box(498, y + 6, 134, 40, "Passed", cls="d-ok", r=20)
    d.text(644, y + 30, "tested", "d-s", "start")
    return d


def investigate() -> Diagram:
    """results/interpreting.md: what to open in the dashboard for each verdict, and how to confirm a fix."""
    d = Diagram("investigate", 720, 440)
    d.box(250, 8, 220, 48, "Open the run", ["read the verdict and What this run measured"], cls="d-soft")
    lanes = [
        (16, "Findings", "d-bad", [("Findings tab", "start with the worst severity"),
                                   ("Read the finding", "what the agent did, the policy"),
                                   ("Open the full trace", "the evidence is highlighted"),
                                   ("Fix the agent", "allowlist, guard, prompt")]),
        (252, "Inconclusive", "d-warn", [("Scenarios tab", "filter: Inconclusive"),
                                         ("Why inconclusive", "the payload never arrived"),
                                         ("Check the trace", "which tools did it call?"),
                                         ("Change task or tools", "retrieval_tools, wiring")]),
        (488, "Error", "d-err", [("Error box on the run", "the message per scenario"),
                                 ("Fix the setup", "agent running? endpoint, port?"),
                                 ("", ""), ("", "")]),
    ]
    d.line("M360,56 V70 H124 V84", arrow=True)
    d.line("M360,70 V84")
    d.line("M360,70 H596 V84")
    for x, title, cls, steps in lanes:
        d.box(x, 86, 216, 36, title, cls=cls, r=18)
        y = 136
        prev = 122
        for t, s in steps:
            if not t:
                continue
            d.line("M%d,%d V%d" % (x + 108, prev, y - 3))
            d.box(x, y, 216, 44, t, [s] if s else [])
            prev = y + 44
            y += 60
    d.box(16, 384, 688, 48, None, cls="d-key")
    d.text(360, 404, "Run again and confirm", "d-t")
    d.text(360, 422, "agentsec replay report.json (does each finding still reproduce?), then Compare runs", "d-s")
    for x in (124, 360):
        d.line("M%d,%d V380" % (x, 136 + 60 * 3 + 44))
    d.line("M596,%d V380" % (136 + 60 + 44))
    return d


def delivery_and_goals() -> Diagram:
    """results/attack-goals-and-exposure.md: payload_delivery and AttackGoalEvaluator (agentsec/evaluators/goals.py)."""
    d = Diagram("delivery-and-goals", 720, 300)
    d.text(16, 22, "A trace, in order", "d-x", "start")
    d.parts.append('<path class="d-line" d="M16,74 H704"/>')
    events = [(70, "#0 task", "user message", "d-box"), (190, "tool result", "no payload", "d-box"),
              (310, "tool result", "no payload", "d-box"), (440, "tool result", "contains the exposure text", "d-warn"),
              (600, "tool call", "matches the goal", "d-bad")]
    for x, t, s, c in events:
        w = 150 if c != "d-box" else 100
        d.box(x - w / 2, 48, w, 52, t, [s], cls=c)
    d.num(440, 122, 1)
    d.text(456, 126, "Payload delivered", "d-t", "start")
    d.num(600, 156, 2)
    d.text(578, 160, "Attack goal reached", "d-t", "end")
    d.line("M440,100 V110", arrow=False)
    d.line("M600,100 V144", arrow=False)
    d.box(16, 184, 336, 104, "When 1 and 2 happen", ["finding attack_goal_achieved; its evidence", "is the delivering result and the call.",
                                                      "The scenario was tested."], cls="d-soft")
    d.box(368, 184, 336, 104, "When 1 never happens", ["nothing was measured: the scenario is", "inconclusive and its goals are “not tested”,",
                                                       "never counted as passed or fixed."], cls="d-soft")
    return d


ALL = [how_a_run_flows, report_to_dashboard, scenario_loop, verdict_decision, investigate, delivery_and_goals]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for make in ALL:
        d = make()
        (OUT / (d.name + ".svg")).write_text(d.svg(), encoding="utf-8")
        print("wrote", OUT / (d.name + ".svg"))


if __name__ == "__main__":
    main()
