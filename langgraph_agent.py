#!/usr/bin/env python3
"""
jobfindAi Agent — LangGraph prototype
=====================================
A stateful, checkpointed job-application pipeline built on LangGraph:

    collect -> score -> claim_audit -> tailor -> cover -> queue
                                                    -> human_review (interrupt)
                                                    -> apply (DRY-RUN stub)
                                                    -> report
    Any hard-gate gap or failed audit routes to: park

Design rules (non-negotiable, mirrored from the production agent):
  * Verified facts ONLY. The tailor may reorder/emphasise real experience;
    it may never invent skills, employers, dates, or metrics.
  * CANNOT_CLAIM terms are gap flags only. A deterministic claim audit runs
    AFTER any generated text; a single violation parks the job.
  * Sponsorship questions are answered "No" and sponsorship/OPT is never
    mentioned in application materials (owner's standing rule, 2026-11-12).
  * No Easy Apply. Real submission happens on official employer portals.
  * This prototype NEVER submits anything: the apply node is a dry-run stub
    behind a human-review interrupt (LangGraph checkpoint + interrupt),
    which is exactly where CAPTCHA / SSN / sign-in steps would pause.

Run the demo (no API key needed — scoring/tailoring are deterministic;
an LLM can be dropped into the tailor node later):

    pip install -r requirements.txt
    python langgraph_agent.py --company "Acme Corp" \
        --title "Data Quality Analyst" --jd-file sample_jd.txt

If langgraph is not installed, the script runs the same nodes sequentially
in fallback mode so the core logic can still be tested.
"""

from __future__ import annotations

import argparse
import operator
import re
import sys
from typing import Annotated, Any, Dict, List, Optional, TypedDict

# --------------------------------------------------------------------------
# Verified profile — the ONLY facts the tailor may use.
# --------------------------------------------------------------------------

VERIFIED_PROFILE: Dict[str, Any] = {
    "name": "Ajay Kumar Vasamsetti",
    "form_first_name": "Ajay Kumar",
    "form_last_name": "Vasamsetti",
    "location": "Hartford, CT",
    "links": {
        "linkedin": "linkedin.com/in/ajaytcm",
        "github": "github.com/ajaytcm",
        "portfolio": "https://ajaytcm.netlify.app",
    },
    "education": [
        "M.S. Technology Management, University of Bridgeport, 2023-2025, GPA 3.88",
        "B.Tech Aeronautical Engineering, Vel Tech, 2014-2018, CGPA 7.0, First Class",
    ],
    "certifications": [
        "Six Sigma Green Belt (LinkedIn Learning / PMI REP)",
        "Bloomberg Market Concepts",
        "CITI Social & Behavioral Research",
    ],
    "experience": [
        {
            "title": "Quality Analyst",
            "org": "NeuroNet Solutions Inc. (Remote)",
            "years": "2026-Present",
            "points": [
                "QA strategy and full testing lifecycle ownership",
                "Test environment management and defect tracking",
                "QA resource planning and quality reporting",
            ],
        },
        {
            "title": "Supply Chain Manager",
            "org": "SK Global Inc. / Hire360 for client cBizSoft (Remote)",
            "years": "2025-2026",
            "points": [
                "Led a 4-person customer service team",
                "Plex ERP workflows, vendor relationships, procurement and sourcing",
                "OTIF delivery tracking and SLA management",
            ],
        },
        {
            "title": "Process Executive",
            "org": "Randstad Digital, Chennai",
            "years": "2020-2023",
            "points": [
                "AI data quality control for client Nvidia",
                "Data validation, annotation QC, and error-pattern reporting",
            ],
        },
        {
            "title": "Process & Manufacturing Apprentice",
            "org": "Hindustan Aeronautics Limited, Bangalore",
            "years": "2019-2020",
            "points": [
                "Manufacturing quality environment in an aerospace plant",
                "Coordinated with design engineering and shop-floor teams",
            ],
        },
    ],
    "capstone": (
        "Low Speed Flying Demo of Hypersonic Transport Vehicle - team of 3, "
        "1:1000 scale-down of MBDA France concept, CATIA V5 modelling and "
        "ANSYS Fluent CFD at 50 m/s (lift/drag/moment, elevon efficiency)."
    ),
}

# Claimable skills -> weight for scoring. Excel is claimed ONLY as
# "Proficient: Pivot Tables, VLOOKUP, Formulas" (never Advanced/Macros).
CLAIMABLE_SKILLS: Dict[str, float] = {
    "sql": 1.5,
    "excel": 1.5,
    "power bi": 1.2,
    "data validation": 1.2,
    "data quality": 1.5,
    "quality assurance": 1.2,
    "defect tracking": 1.0,
    "dmaic": 1.0,
    "8d": 1.0,
    "5 whys": 0.8,
    "root cause": 1.0,
    "kaizen": 0.8,
    "5s": 0.6,
    "plex": 0.8,
    "erp": 0.8,
    "otif": 0.8,
    "sla": 0.6,
    "catia": 0.8,
    "ansys": 0.8,
    "cfd": 0.6,
    "testing lifecycle": 1.0,
    "test cases": 0.8,
    "procurement": 0.8,
    "vendor": 0.6,
    "inventory": 0.6,
    "six sigma": 1.0,
}

# Hard gates: if a JD *requires* one of these, the job is parked, never filed.
CANNOT_CLAIM: List[str] = [
    "python", "sap", "ppap", "pfmea", "fmea", "apqp", "gage r&r",
    "minitab", "selenium", "tosca", "qtest", "spc", "agile",
    "tableau", "vba", "xlookup", "autocad", "unigraphics",
]

STRONG_FIT_THRESHOLD = 7.0  # >= this (and no hard gate) -> auto-pack + queue

# --------------------------------------------------------------------------
# Core logic — pure Python, no third-party imports, unit-testable.
# --------------------------------------------------------------------------


def _contains(text: str, term: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text) is not None


def score_jd(jd_text: str) -> Dict[str, Any]:
    """Score a JD against the verified profile. Deterministic, explainable."""
    text = jd_text.lower()
    matched = {k: w for k, w in CLAIMABLE_SKILLS.items() if _contains(text, k)}
    gaps = [t for t in CANNOT_CLAIM if _contains(text, t)]
    raw = sum(matched.values())
    score = round(min(10.0, raw), 1)  # weights tuned so a strong QA/DQ JD ~8-10
    return {"score": score, "matched": sorted(matched), "gaps": gaps}


def claim_audit(text: str) -> List[str]:
    """Return every cannot-claim term present in generated text. Must be []."""
    low = text.lower()
    return [t for t in CANNOT_CLAIM if _contains(low, t)]


def build_resume(state: "AgentState") -> str:
    """Deterministic tailored resume: JD-matched verified points first."""
    p = VERIFIED_PROFILE
    matched = set(state.get("matched", []))
    lines = [
        p["name"],
        f"{p['location']} | {p['links']['linkedin']} | "
        f"{p['links']['github']} | {p['links']['portfolio']}",
        "",
        state["title"].upper(),
        "",
        "SUMMARY",
        "Quality and data-quality professional with experience across the QA "
        "testing lifecycle, AI data quality control, and supply-chain quality "
        "operations. Six Sigma Green Belt.",
        "",
        "PROFESSIONAL EXPERIENCE",
    ]
    for job in p["experience"]:
        lines.append(f"{job['title']} - {job['org']} ({job['years']})")
        points = sorted(
            job["points"],
            key=lambda pt: -sum(1 for m in matched if m in pt.lower()),
        )
        lines += [f"  - {pt}" for pt in points]
    lines += ["", "EDUCATION"] + [f"  - {e}" for e in p["education"]]
    lines += ["", "CERTIFICATIONS"] + [f"  - {c}" for c in p["certifications"]]
    lines += ["", "PROJECTS", f"  - {p['capstone']}"]
    return "\n".join(lines)


def build_cover_note(state: "AgentState") -> str:
    matched = ", ".join(state.get("matched", [])[:5]) or "data quality and QA"
    return (
        f"Dear {state['company']} hiring team,\n\n"
        f"I am applying for the {state['title']} role. My background covers "
        f"{matched}, across quality analysis at NeuroNet Solutions, AI data "
        f"quality control at Randstad Digital, and supply-chain quality "
        f"operations at SK Global/Hire360. I would welcome the chance to "
        f"discuss how that experience fits your team's needs.\n\n"
        f"Regards,\nAjay Kumar Vasamsetti\n"
        f"{VERIFIED_PROFILE['links']['portfolio']}"
    )


# --------------------------------------------------------------------------
# LangGraph state + nodes
# --------------------------------------------------------------------------


class AgentState(TypedDict, total=False):
    company: str
    title: str
    location: str
    jd_text: str
    score: float
    matched: List[str]
    gaps: List[str]
    resume: str
    cover_note: str
    audit_violations: List[str]
    status: str  # scored | pack_ready | queued | parked | ready_to_file
    park_reason: str
    agent_notes: Annotated[List[str], operator.add]


def node_collect(state: AgentState) -> AgentState:
    note = f"Collected: {state['title']} at {state['company']}"
    return {"status": "collected", "agent_notes": [note]}


def node_score(state: AgentState) -> AgentState:
    result = score_jd(state["jd_text"])
    return {
        "score": result["score"],
        "matched": result["matched"],
        "gaps": result["gaps"],
        "status": "scored",
        "agent_notes": [f"Scored {result['score']}/10; gaps: {result['gaps'] or 'none'}"],
    }


def route_after_score(state: AgentState) -> str:
    if state.get("gaps"):
        return "park"
    if state.get("score", 0) < STRONG_FIT_THRESHOLD:
        return "park"
    return "tailor"


def node_park(state: AgentState) -> AgentState:
    if state.get("gaps"):
        reason = f"Hard-gate gap(s) he cannot claim: {', '.join(state['gaps'])}"
    else:
        reason = f"Score {state.get('score')} below strong-fit threshold {STRONG_FIT_THRESHOLD}"
    return {"status": "parked", "park_reason": reason,
            "agent_notes": [f"Parked - {reason}"]}


def node_tailor(state: AgentState) -> AgentState:
    return {"resume": build_resume(state),
            "agent_notes": ["Tailored resume built from verified facts only"]}


def node_cover(state: AgentState) -> AgentState:
    return {"cover_note": build_cover_note(state),
            "agent_notes": ["Cover note drafted (no sponsorship/OPT wording)"]}


def node_claim_audit(state: AgentState) -> AgentState:
    violations = claim_audit(state.get("resume", "") + "\n" + state.get("cover_note", ""))
    return {"audit_violations": violations,
            "agent_notes": [f"Claim audit: {'CLEAN' if not violations else violations}"]}


def route_after_audit(state: AgentState) -> str:
    return "park_audit" if state.get("audit_violations") else "queue"


def node_park_audit(state: AgentState) -> AgentState:
    reason = f"Claim audit failed: {state.get('audit_violations')}"
    return {"status": "parked", "park_reason": reason,
            "agent_notes": [f"Parked - {reason}"]}


def node_queue(state: AgentState) -> AgentState:
    return {"status": "queued",
            "agent_notes": ["Queued for the next automated filing run"]}


def node_human_review(state: AgentState) -> AgentState:
    """Interrupt point: a human approves before any apply step.

    With LangGraph this node is where interrupt() pauses the graph; the
    checkpoint lets the run resume after CAPTCHA / SSN / sign-in handling.
    In this prototype the pause is represented by the graph topology and
    the dry-run apply stub below.
    """
    return {"agent_notes": ["Human review gate reached (interrupt point)"]}


def node_apply_dry_run(state: AgentState) -> AgentState:
    """DRY-RUN ONLY. A production build would call the browser applier tool
    here (official portal only, no Easy Apply) and would still stop on
    CAPTCHA/SSN. This prototype never submits anything."""
    return {"status": "ready_to_file",
            "agent_notes": ["DRY-RUN: apply step stubbed - nothing submitted"]}


def node_report(state: AgentState) -> AgentState:
    return {"agent_notes": [f"Final status: {state.get('status')}"]}


def build_graph(checkpointer: Any = None):
    """Compile the LangGraph StateGraph. Requires the langgraph package."""
    from langgraph.graph import END, START, StateGraph

    g = StateGraph(AgentState)
    g.add_node("collect", node_collect)
    g.add_node("score", node_score)
    g.add_node("tailor", node_tailor)
    g.add_node("cover", node_cover)
    g.add_node("claim_audit", node_claim_audit)
    g.add_node("queue", node_queue)
    g.add_node("human_review", node_human_review)
    g.add_node("apply", node_apply_dry_run)
    g.add_node("park", node_park)
    g.add_node("park_audit", node_park_audit)
    g.add_node("report", node_report)

    g.add_edge(START, "collect")
    g.add_edge("collect", "score")
    g.add_conditional_edges("score", route_after_score,
                            {"tailor": "tailor", "park": "park"})
    g.add_edge("tailor", "cover")
    g.add_edge("cover", "claim_audit")
    g.add_conditional_edges("claim_audit", route_after_audit,
                            {"queue": "queue", "park_audit": "park_audit"})
    g.add_edge("queue", "human_review")
    g.add_edge("human_review", "apply")
    g.add_edge("apply", "report")
    g.add_edge("park", "report")
    g.add_edge("park_audit", "report")
    g.add_edge("report", END)
    return g.compile(checkpointer=checkpointer)


def run_fallback(state: AgentState) -> AgentState:
    """Sequential run of the same nodes when langgraph is unavailable."""

    def apply_node(node) -> None:
        result = dict(node(state))
        notes = result.pop("agent_notes", [])
        state.update(result)  # type: ignore[arg-type]
        state["agent_notes"] = state.get("agent_notes", []) + notes

    apply_node(node_collect)
    apply_node(node_score)
    if route_after_score(state) == "park":
        apply_node(node_park)
    else:
        for node in (node_tailor, node_cover, node_claim_audit):
            apply_node(node)
        if route_after_audit(state) == "park_audit":
            apply_node(node_park_audit)
        else:
            for node in (node_queue, node_human_review, node_apply_dry_run):
                apply_node(node)
    apply_node(node_report)
    return state


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="jobfindAi Agent - LangGraph prototype")
    ap.add_argument("--company", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--location", default="")
    ap.add_argument("--jd-file", required=True, help="Path to a file with the full JD text")
    args = ap.parse_args(argv)

    with open(args.jd_file, encoding="utf-8") as fh:
        jd_text = fh.read()

    initial: AgentState = {
        "company": args.company, "title": args.title,
        "location": args.location, "jd_text": jd_text, "agent_notes": [],
    }

    try:
        from langgraph.checkpoint.sqlite import SqliteSaver

        with SqliteSaver.from_conn_string("jobfindai_checkpoints.db") as saver:
            graph = build_graph(checkpointer=saver)
            config = {"configurable": {"thread_id": f"{args.company}-{args.title}"}}
            final = graph.invoke(initial, config=config)
        mode = "langgraph+sqlite-checkpointer"
    except ImportError:
        final = run_fallback(dict(initial))
        mode = "fallback (langgraph not installed)"

    print(f"Mode: {mode}")
    print(f"Score: {final.get('score')}  Matched: {final.get('matched')}")
    print(f"Gaps: {final.get('gaps')}  Status: {final.get('status')}")
    if final.get("park_reason"):
        print(f"Park reason: {final['park_reason']}")
    for n in final.get("agent_notes", []):
        print(f"  - {n}")
    if final.get("resume"):
        print("\n--- TAILORED RESUME ---\n" + final["resume"])
        print("\n--- COVER NOTE ---\n" + final.get("cover_note", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
