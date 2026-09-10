# Automation Boundary Thesis Kit

A scoping and method kit for a master's thesis on workflow automation in job-based
service businesses — trade contractors doing quoting, scheduling, job delivery and
invoicing.

**Read it here → https://roko4414.github.io/automation-thesis-kit/**

## What it covers

- **Method** — process discovery by subject-following, cost quantification with
  measured / estimated / assumed labelling, and a variance × consequence ×
  data-availability model for deciding where automation stops and human judgement starts.
- **System** — five connected workflows forming a quote-to-cash pipeline, built on n8n
  with an LLM inside the nodes and a form-and-review-queue wrapper on top.
- **Measurement** — baseline protocol, primary and secondary outcomes, the confounds
  that otherwise sink a small-n results chapter, and rules for reporting honestly.
- **Twelve weeks** — sequencing, scope limits, failure modes and supervisor checkpoints.

The research question the whole thing exists to answer:

> In a high-variance, low-data-maturity small business, where should the boundary
> between automated and human decision sit, and what evidence justifies placing it there?

## Scope

This is a starting scaffold, not a finished build. It contains no client or
third-party engagement material; the reference business is a composite of publicly
observable characteristics of the sector.

`index.html` is a single self-contained file with no build step. The `source-notes/`
directory holds the same content as markdown.
