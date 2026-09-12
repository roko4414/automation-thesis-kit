# Automation Boundary Thesis Kit

Five importable n8n workflows for a trade contractor's quote-to-cash process, the sample
data to run them, and the measurement design to write them up.

**Read it here → https://roko4414.github.io/automation-thesis-kit/**

For a master's thesis on workflow automation: build a live automation on n8n, wrap it so
someone else can use it, and make the thesis the documentation and justification of that
build.

## What's here

| | |
|---|---|
| `workflows/` | Five n8n workflows, importable. Annotated on the canvas with the boundary decision behind each gate. |
| `sample-data/` | 12 enquiries, a 25-line rate card, 25 completed jobs, and the job-record schema. |
| `prompts/` | Versioned prompts for extraction, quote drafting and follow-up. |
| `scripts/` | The generator that builds the workflows, and the validator that checks them. |
| `docs/` | How n8n workflow JSON works, and the eleven ways an import breaks silently. |

## Quick start

```bash
n8n --version                                        # check before anything else
python3 scripts/validate-workflows.py workflows/*.json
```

Then make a Google Sheet, replace `REPLACE_WITH_YOUR_SPREADSHEET_ID`, and import each
workflow through *Workflows → ⋯ → Import from File*. Full steps on the site.

## The question it exists to answer

> In a high-variance, low-data-maturity small business, where should the boundary between
> automated and human decision sit, and what evidence justifies placing it there?

Each workflow carries a variance / consequence / data-availability score and a gate
placement that follows from it. W3 (quote drafting) holds an unconditional human review
and writes what the reviewer changed — which is where the results chapter comes from.

## Status

Workflows are validated **structurally**: envelope, node shapes, unique names, connection
integrity, AI cluster wiring, pinned typeVersions. They have **not** been run against a
live n8n instance. Import one end to end before building on top of it.

No credentials ship in any file, deliberately — see `docs/n8n-json-reference.md`.

## Scope

Contains no client or third-party engagement material. The reference business is a
composite of publicly observable characteristics of small trade contractors.
