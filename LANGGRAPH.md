# LangGraph prototype

`langgraph_agent.py` is a working prototype of the jobfindAi Agent pipeline
as a **LangGraph state graph** — the same loop the production agent runs,
expressed as inspectable, checkpointed code.

## The graph

```
collect → score → (hard-gate gap or weak fit) → park
              ↘ tailor → cover → claim_audit → (violation) → park
                                            ↘ queue → human_review ⏸ → apply (dry-run) → report
```

- **Score** is deterministic and explainable: weighted matches against the
  verified profile, with cannot-claim requirements returned as gap flags.
- **Claim audit** is a hard, non-LLM gate that runs *after* any generated
  text. One cannot-claim term in a resume or cover note parks the job.
- **Human review** is the interrupt point. LangGraph checkpoints the graph
  state at every step (SQLite checkpointer in this prototype), so a run
  paused for a CAPTCHA, an SSN prompt, or a portal sign-in resumes exactly
  where it stopped instead of restarting.
- **Apply is a dry-run stub.** This prototype never submits anything.
  Production filing happens on official employer portals through the
  agent's browser runs — no Easy Apply, confirmation required before a
  filing counts.

## Run it

```bash
pip install -r requirements.txt
python langgraph_agent.py --company "Acme Corp" \
  --title "Data Quality Analyst" --jd-file sample_jd.txt
```

No API key is needed: scoring and tailoring are deterministic functions of
the verified profile. An LLM can be added inside the tailor node later;
the claim audit still decides what may leave the system.

If `langgraph` is not installed, the script runs the identical nodes
sequentially in fallback mode, so the core logic stays testable anywhere.

## Rules baked in

- Verified facts only — no invented skills, employers, dates, or metrics.
- Cannot-claim list (Python, SAP, PPAP, Selenium, …) = gap flags only.
- Excel is claimed only as "Proficient: Pivot Tables, VLOOKUP, Formulas".
- Sponsorship answers and wording follow the owner's standing rule and
  never appear in generated application materials.
- Long-term memory (verified profile, preferences, ledger) maps to
  LangGraph's Store; per-run state maps to its checkpointers.
