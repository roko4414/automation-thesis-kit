# System architecture — quote-to-cash for a job-based trade business

## Reference business

An owner-operated trade contractor (electrical, HVAC, landscaping or joinery), 3–12
staff, 20–80 jobs a month, quotes between a few hundred and a few tens of thousands.
Characteristics that drive the design, all observable in the sector generally:

- The owner is also the estimator, so quoting competes with billable work and happens
  at night.
- Enquiries arrive by phone, web form, email and text, and are not in one place.
- Quote-to-decision lag is long and follow-up is inconsistent — this is where revenue
  leaks, not in win rate on quotes actually chased.
- Invoicing lags job completion because the person who finished the job is not the
  person who invoices.
- Existing systems are a calendar, a spreadsheet, an accounting package, and memory.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Orchestration | **n8n** | Named in the brief. Visual graph is legible in a thesis appendix — you can screenshot a workflow and a reader understands it, which is not true of code. |
| Intelligence | **Claude via HTTP Request / Anthropic node** | Extraction, classification and drafting inside n8n nodes. Keeps the spine visible while the judgement lives in prompts you can version and quote in the appendix. |
| Wrapper | **Wippli** | Named in the brief. Input form, output visualisation, and the productisation argument. |
| Store | **Postgres or Airtable** | You need a job record with state. n8n is orchestration, not a database — do not keep state in the workflow. |

If you use an agent framework (Mastra or similar) for step 3, keep n8n as the caller.
The brief will be graded against n8n; an agent invoked *from* n8n satisfies it, an
agent that replaces n8n does not.

## The five workflows

### W1 — Enquiry intake and triage
**Trigger:** web form submit, inbound email, or call transcript dropped to a folder.
**Does:** normalises any source into one job record. Extracts customer, location, job
type, described scope, stated urgency. Classifies in/out of service area and job type.
Flags incomplete enquiries with the specific missing field.
**Boundary:** fully automated. Low consequence — a misfiled enquiry surfaces in the
review queue — and the input, though unstructured, is short.
**Instrument:** source, timestamp, extraction confidence, fields missing.

### W2 — Site-visit scheduling
**Trigger:** job record reaches `qualified`.
**Does:** reads crew calendar, proposes 2–3 slots clustered by geography to cut travel,
sends options, writes the confirmed slot back to the calendar.
**Boundary:** automated proposal, human confirm for jobs over a value threshold.
**Instrument:** proposal-to-confirmation lag, travel minutes per job before and after
clustering. The travel number is your most quotable single result — it is unambiguous
and it is money.

### W3 — Quote drafting
**Trigger:** site visit marked complete, with notes or voice memo attached.
**Does:** transcribes if needed, extracts scope into line items, prices against the
rate card, retrieves the three most similar historical jobs as a sanity check, drafts
the quote document with an explicit assumptions section.
**Boundary:** **draft-and-review, always.** High variance and high consequence — a
wrong price is money out of the owner's pocket and is not trivially reversible once
sent. The system assembles; the owner approves.
**This is the centre of the thesis.** Everything interesting is here: what the model
gets right, what it gets wrong, how long review takes versus writing from scratch,
and whether review time falls as the owner calibrates trust. Instrument it heavily —
draft-to-approved edit distance, review duration, field-level override rate.

### W4 — Quote follow-up
**Trigger:** quote sent.
**Does:** condition-based sequence — nudge at day 3, 7, 14, stop on any reply, accept,
decline or expiry. Escalates to the owner rather than sending a fourth message.
**Boundary:** fully automated with a hard stop on human reply.
**Instrument:** touches per quote before and after, response rate by touch number,
win rate against baseline. Guard the confound in `03-measurement-design.md` before you
claim a win-rate effect.

### W5 — Completion to cash
**Trigger:** job marked complete.
**Does:** assembles the invoice from the approved quote plus variations, routes
variations for approval, issues, then nudges on overdue at a set cadence.
**Boundary:** automated issue where the invoice matches the approved quote exactly;
human approval wherever a variation changes the total.
**Instrument:** completion-to-invoice lag, invoice-to-payment lag.

## Why five and not one

Two reasons, and both belong in the thesis.

**Individually each is unremarkable; connected they change the unit of work.** The
job record persists across all five and accumulates state. That is the difference
between task automation and process automation, and it is a claim you can defend.

**It lets you show a compounding lead-time effect.** Each workflow removes a wait,
and the interesting result is total quote-to-cash elapsed time, which no single
workflow could move. Report both the per-step labour savings and the end-to-end lead
time; they tell different stories and the second is the better one.

## The Wippli layer

Roger's word is "productisation," and it is the part most students under-read. Treat
it as three separate claims:

1. **Input form** — the intake surface, so the system does not depend on the owner
   configuring n8n. Non-trivial: the form's field design determines W1's extraction
   quality, so form design is an engineering decision, not decoration.
2. **Output visualisation** — the review queue where the owner approves drafted quotes
   and variations. This is where your human-in-the-loop boundary becomes a literal
   screen. Screenshot it for the thesis; it is the clearest possible evidence of the
   design argument.
3. **Productisation** — the argument that the thing is transferable to a second
   business without rebuilding. Test the claim rather than asserting it: what is
   configuration (rate card, service area, crew, thresholds) versus what is code? If
   a second business needs workflow surgery, say so — a negative finding on
   transferability is a real result and examiners reward it.

## Human gates — the summary table

| Workflow | Gate | Rationale |
|---|---|---|
| W1 Intake | None | Low consequence, reversible |
| W2 Scheduling | Above value threshold | Consequence scales with job value |
| W3 Quote | **Always** | High variance, high consequence, irreversible once sent |
| W4 Follow-up | Stop on human reply | Automation must never talk over a live conversation |
| W5 Invoice | On any variation | Amount changed from what the customer agreed |

Justify each of these against the Stage 3 scores. If your observed business gives a
different score on an axis, move the gate and explain why — a boundary that moved
because of evidence is the strongest thing you can put in a results chapter.
