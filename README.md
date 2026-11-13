# jobfindAi Agent

A job-application pipeline agent: **Discover → Score → Tailor → Queue → Track**.

Paste a job posting and jobfindAi Agent scores it against a verified candidate profile, builds a claim-audited tailored resume and cover note, and queues it for application — with every gap flagged honestly instead of invented.

**Live demo:** https://jobfindai-agent.netlify.app

## What it does

- **Discover** — add postings one at a time or in bulk; each is tagged by ATS (Workday, Greenhouse, Lever, Ashby, Taleo, iCIMS, SuccessFactors, UKG, Breezy)
- **Score** — local fit score (0–10) against the verified profile, split into Required vs Preferred qualifications, with matched skills and gap flags shown separately and a "Strong fit" badge for top scores
- **Tailor** — one tap builds a tailored resume + cover note from verified facts only; skills the candidate cannot claim are hard-blocked from the resume and appear only as gap flags
- **Apply Queue** — Draft / Queued / Pack ready / Filed (with confirmation #) / Parked (with reason) / Rejected, plus follow-up-due flags at 7 and 14 days
- **Track & Insights** — pipeline counts, outcome tracking, and a "top gap skills" view across all scored postings
- Duplicate warning when a company + title is already in the tracker

## Honest by design

This public demo **prepares** applications — it does not submit them. Submissions happen on official employer portals. No seeded/sample jobs; the pipeline starts empty. This public version contains no private contact details.

## Tech

Single-file static web app (`index.html`) — no backend, no build step. Deployable to any static host (Netlify, GitHub Pages, Vercel).

## Part of a larger system

jobfindAi Agent is the public demo of a private, agent-run job search system: postings queued here are filed on official portals by scheduled agent runs, with confirmations written back into the tracker and a master ledger kept in sync.
