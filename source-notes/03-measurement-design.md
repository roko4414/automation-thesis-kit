# Measurement design

Design this before you build. If you build first you will have no baseline, and the
results chapter becomes a description of features.

## Baseline

Four weeks minimum of the process running unchanged, instrumented. If you cannot
instrument the current process, timestamp what already exists — enquiry emails,
calendar entries, quote PDFs, invoice dates in the accounting package. Most of the
lead-time series can be reconstructed from artefacts nobody thought of as data.

Capture per job instance:
- Enquiry received → qualified
- Qualified → site visit
- Site visit → quote sent
- Quote sent → decision
- Job complete → invoice issued
- Invoice issued → paid
- Owner time spent per stage (self-reported diary; label it estimated)
- Number of follow-up touches
- Outcome: won / lost / no decision

Twenty to thirty instances gives you something to talk about. Be upfront that it does
not give you statistical power — see Honesty below.

## Primary outcome

**End-to-end quote-to-cash elapsed time.** One number, moved by the system as a whole,
robust to the noise in any single step. This is your headline.

## Secondary outcomes

- Owner hours per job on administrative steps
- Quote turnaround (site visit → quote sent) — likely your largest single effect
- Follow-up touches actually delivered versus intended
- Invoice lag
- Win rate — **report with the confound flagged**, see below

## Instrumentation

Every n8n workflow writes a structured event to the job record: workflow, node, in,
out, duration, error, human-intervened. Build this as a reusable sub-workflow called
from every other one, on day one.

For W3, capture additionally:
- The drafted quote and the approved quote, both stored
- Edit distance between them, per line item
- Review duration (queue open → approve)
- Which fields the owner overrode

That last one is the richest data in the project. It tells you where model judgement
is trusted and where it is not, and it lets you show whether the boundary should move
over time. If you have one good chart in the whole thesis, make it override rate by
field over weeks.

## Confounds you must handle

**Hawthorne.** The owner knows they are measured and will chase quotes harder. Do not
pretend otherwise — declare it, and lean on metrics the owner cannot easily improve by
trying (system-timestamped lags) over ones they can (touches delivered).

**Seasonality.** Trades are seasonal and weather-dependent. Four weeks of baseline
against four weeks of treatment in different months is not a clean comparison. Report
job mix in both windows and say so explicitly.

**Selection.** If the system runs only on new enquiries while complex jobs stay
manual, your sample is the easy half. Either route everything through it or report
the split.

**Win rate is contaminated by market conditions** and you cannot control for them with
n=25. Report it, attribute nothing, and say why.

## Honesty rules

These are not ethics boilerplate; they are what protects the thesis at a defence.

- n is small. It is a case study, not an experiment. Frame it as one in the methods
  chapter and no examiner can attack it as a failed experiment.
- Distinguish measured / estimated / assumed on every figure, in every table.
- Report what the system got wrong. A results chapter with only wins reads as
  advocacy, and an examiner who finds a failure you did not report has found your
  weakest moment.
- If an effect is inside the noise, say it is inside the noise.
- Any extrapolation ("if applied across the sector…") is labelled as extrapolation and
  kept out of the abstract entirely.

## Qualitative strand

Numbers from one business will not carry the thesis alone. Add:
- A structured interview with the owner before and after — same questions both times,
  so you can quote the shift.
- Your own build log: what you expected, what broke, what you changed and why. This is
  primary data for the discussion chapter and it is free if you keep it as you go.
  Write it weekly; it cannot be reconstructed at the end.
