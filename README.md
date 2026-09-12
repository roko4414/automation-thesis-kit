# Automation Boundary Thesis Kit

A starting kit for a master's thesis on workflow automation.

**Start here → https://roko4414.github.io/automation-thesis-kit/**

## The idea

Almost every small business runs the same five steps: a message arrives, you book a time
to look at the work, you send a price, you chase it up, you finish and invoice.

This kit automates all five — except sending the price. That step is drafted by the
system and approved by a person, always.

That one rule is the thesis. Not "I built an automation", but: *here is exactly where I
let the computer decide, here is where I did not, and here is the evidence I was right.*

## Five kinds of business

The same five workflows, specialised for five industries. Each folder under
`industries/` holds the workflows, twelve realistic example messages, and a price list.

| Folder | Business | What is different about it |
|---|---|---|
| `trades` | Electrical contractor | The baseline. Scope is established by looking at the work, and geography is a hard limit. |
| `dental` | Private dental practice | Risk moves to the front — sorting symptoms is nearly clinical — while pricing becomes almost deterministic. The inverse of trades. |
| `wellness` | Physiotherapy practice | The strongest case for a human gate. Some messages carry clinical red flags, one of them written calmly enough to slip past a careless triage. |
| `advisory` | Tax and accounting firm | No visit at all, and a conflict-of-interest check must clear *before* anything is priced. |
| `studio` | Photo and video studio | Distance is a price input rather than a refusal, and price tracks image usage rights rather than hours worked. |

Only one is needed for a thesis. The other four exist so something can be said about
whether the pattern travels — which is itself a finding, either way.

## Layout

| | |
|---|---|
| `industries/<slug>/` | Five workflows, `enquiries.json`, `price-list.csv`, `pack.json` |
| `prompts/` | Versioned prompts for extraction, drafting and follow-up |
| `docs/` | How the workflow JSON works; the job-record schema |
| `scripts/` | The generator and the validator |
| `reference.html` | The detailed version of the site |

## Before importing anything

```bash
n8n --version
python3 scripts/validate-workflows.py industries/*/workflows/*.json
```

The validator checks the failure modes that let an n8n import *look* like it worked
while silently dropping connections. Details in `docs/n8n-json-reference.md`.

## How the industries work

One skeleton, many industries. The workflows are written with `<<TOKENS>>` where the
industry shows through, and each `pack.json` supplies the values.

```bash
python3 scripts/build_workflows.py      # rebuilds all 25 workflow files
```

Adding a sixth industry means writing a `pack.json` and rerunning that. If it ever needs
surgery on the workflows themselves, that is worth writing down — it is the
transferability claim failing, which is a real result.

## Status

Workflows are validated structurally: envelope, node shapes, unique names, connection
integrity, AI cluster wiring, pinned typeVersions. They have **not** been run against a
live n8n instance. Import one end to end before building on top of it.

No credentials ship in any file, deliberately.

## Scope

Contains no client or third-party material. The businesses are composites built from how
these trades generally work, not real companies. Prices and any regulatory detail are
illustrative and marked as such in the files.
