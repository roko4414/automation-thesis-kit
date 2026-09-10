# Build plan

Twelve weeks, adjust to your submission date. The ordering is the load-bearing part:
access first, instrumentation before automation, the hard workflow in the middle with
room to recover.

| Wk | Focus | Done when |
|---|---|---|
| 1–2 | **Secure the business.** Outreach, access agreement, confidentiality terms. | Signed access, owner has agreed to a weekly 30 minutes. |
| 2–3 | **Observe.** 5–8 job instances end to end. Owner's described process captured *before* observing. | BPMN happy path + exception branches. |
| 3–4 | **Baseline.** Instrument, or reconstruct from artefacts. Costed process table. | 4 weeks of data underway, every figure labelled measured/estimated/assumed. |
| 4 | **Boundary decisions.** Score every step on variance / consequence / availability. | Annotated model, each gate justified. Send to Roger — this is the natural checkpoint. |
| 5 | **Foundations.** n8n up, job record schema, the shared logging sub-workflow. | An event from a dummy run lands in the store. |
| 5–6 | **W1 + W2.** Intake, triage, scheduling. | A real enquiry produces a real job record and a proposed slot. |
| 7–8 | **W3 quote drafting.** The hard one. Prompt iteration, rate card, similar-job retrieval. | Owner reviews a drafted quote and approves it with edits captured. |
| 9 | **W4 + W5.** Follow-up sequence, invoice, payment nudge. | One job traverses all five workflows. |
| 9–10 | **Wippli wrapper.** Input form, review queue, transferability test. | Owner uses it without you present. Screenshots captured. |
| 10–11 | **Treatment period.** System live, collecting. Weekly build log. | 4 weeks of comparable data. |
| 11–12 | **Analyse and write.** | Draft to Roger with two weeks of runway. |

## Where to stop

Scope creep kills these projects. Out of scope, and say so in the limitations section
rather than building them:

- Mobile app for field crew
- Two-way accounting-package sync — read-only is enough
- Payment processing
- Anything for a second business beyond *assessing* transferability
- Rebuilding the CRM

Four workflows working and measured beats six workflows half-built. If week 9 is
tight, cut W5 and say why.

## Failure modes

- **No business by week 3.** Switch to observe-only or constructed reference and say
  so in methods. Do not keep waiting into week 6.
- **No baseline captured.** Fatal to the results chapter. If week 4 arrives with no
  baseline, stop building and fix it.
- **W3 quality is poor.** This is a finding, not a failure. Report where model
  judgement was insufficient and what data would have been needed — that is a better
  contribution than a working quote generator.
- **Owner stops using it.** The most informative outcome in the whole project.
  Interview immediately, while the reason is fresh. Adoption failure in SME automation
  is a genuine research contribution and it is under-reported precisely because
  students bury it.

## What to send Roger, and when

- End of week 4: process model and boundary decisions. Confirms the framing before you
  build on it.
- End of week 8: the W3 review interface working. Confirms the productisation element
  he asked for.
- End of week 11: full draft.
