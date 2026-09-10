# Methodology — from observed process to justified automation

This is the methods chapter. Five stages. The value of the thesis is that each stage
produces an artefact the next stage consumes, so the final build is traceable back to
an observation rather than to an opinion.

## Stage 1 — Process discovery by subject-following

Do not map the org chart. Map the **job**: pick the unit of work the business sells
(one quote, one installation, one service call) and follow single instances of it end
to end, from first contact to cash received.

Method:
- Observe 5–8 complete instances. Fewer and you are describing anecdote; more and you
  are past the point of new information for a process this size.
- Record every step as: actor, trigger, tool touched, output, wait time, rework flag.
- Record what happens when it goes wrong, separately. The exception path is usually
  where the cost is, and it is almost always missing from how the owner describes
  their own process.
- Ask the owner to describe the process *before* you observe it, and keep that
  description. The gap between described and observed process is a finding in its own
  right, and a genuinely publishable one.

Output: a process model (BPMN is the defensible choice — it is a standard, so your
examiner is not evaluating your notation). One diagram per happy path, annotated
exception branches.

## Stage 2 — Quantify the current cost

For each step: `time per instance × instances per period × loaded hourly rate`.

Rules you must hold to, because this is where theses lose credibility:
- **Measured, estimated and assumed are three different labels.** Label every figure
  with which it is. A stopwatch reading is measured. An owner saying "about twenty
  minutes" is estimated. A loaded rate derived from an award wage plus on-costs is
  assumed, and you state the assumption.
- Never present an estimate as a measurement, in text, in a table, or in a chart.
- Wait time is not cost, but it is not nothing either. Track it in a separate column
  and discuss it as a lead-time effect rather than folding it into labour cost.
- Include rework explicitly. A step done twice 30% of the time costs 1.3×.

Output: a costed process table. This is the baseline your results chapter compares to.

## Stage 3 — Place the automation boundary

The core intellectual move of the thesis, and the part most student projects skip by
automating whatever is technically easiest.

Score each step on three axes:

| Axis | Low | High |
|---|---|---|
| **Variance** — how much do instances differ? | Same every time | Every one is a judgement call |
| **Consequence of error** — what does a wrong output cost? | Trivially corrected | Money, safety or reputation |
| **Data availability** — is the input already structured and reachable? | Sitting in an API | In someone's head |

The mapping:
- Low variance, low consequence, high availability → **fully automate**.
- High variance, low consequence → **automate with a draft-and-review gate**. The
  system proposes, the human disposes.
- Any high consequence → **human decides, automation only assembles the evidence**.
- Low data availability → **do not automate yet**; the prior project is capturing the
  data. Saying this in a thesis is a finding, not a failure.

Output: an annotated process model where every step carries a boundary decision and
the three scores that justify it. Your examiner can now disagree with a *score* rather
than with your whole design — which is exactly the position you want to be in at a
defence.

## Stage 4 — Build

Covered in `02-system-architecture.md`. Two methodological points belong here:

- **Build the instrumentation before the automation.** If logging goes in afterwards
  you have no baseline and no results chapter. This is the single most common way
  these projects fail.
- **Version the prompts and the workflows.** Export n8n workflow JSON into git at every
  meaningful change. An LLM-containing system whose prompts were edited in a web UI and
  never recorded is not reproducible, and reproducibility is a grading criterion.

## Stage 5 — Measurement

Covered in `03-measurement-design.md`.

## What makes this a thesis rather than a project write-up

The contribution is not "I built an automation." It is a defensible answer to:

> In a high-variance, low-data-maturity small business, where should the boundary
> between automated and human decision sit, and what evidence justifies placing it
> there?

Everything above is the apparatus for answering that. State the question in the
introduction and answer it in the conclusion with your own boundary decisions as
evidence. If a boundary you placed turned out wrong during the build, that is your
most valuable result — write it up rather than hiding it.

## Literature to anchor against

You need theory scaffolding; these are the standard hooks, and your library will have
better recent work:
- BPM lifecycle (Dumas et al., *Fundamentals of Business Process Management*) — gives
  you the discovery/analysis/redesign/implementation/monitoring frame this method sits in.
- Robotic Process Automation literature on task selection criteria — your variance /
  consequence / availability scoring is a contribution *against* this baseline, so read
  enough of it to say what yours adds.
- Human-in-the-loop and automation-boundary work (Parasuraman & Sheridan's levels of
  automation is the classic citation) — this is where your core question actually lives.
- Technology adoption in SMEs — for the discussion chapter, on why the constraint is
  rarely the technology.
