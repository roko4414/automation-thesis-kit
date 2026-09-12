# Prompts

Version these. The job record stores `prompt_version` against every drafted quote, and
without it your results are not reproducible — "the model got better in week 6" and
"I edited the prompt in week 6" are indistinguishable otherwise.

Convention used here: bump the version in the file header on every change, and tag the
repo. When you report a result, report the prompt version it was produced under.

| File | Used by | Purpose |
|---|---|---|
| `extract-enquiry.md` | W1 | Turn free-text enquiry into structured fields |
| `draft-quote.md` | W3 | Turn site-visit notes into priced line items |
| `followup-message.md` | W4 | Compose the nudge, in the customer's language |
