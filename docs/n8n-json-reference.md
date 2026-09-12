# Hand-authoring n8n workflow JSON

Everything here was read from n8n source at release tag `n8n@2.38.7` (11 September 2026)
and from live published templates. `docs.n8n.io` does **not** publish the workflow JSON
schema or any typeVersions, so the source is the authority. Sources are linked inline.

Written up because the thesis needs a reproducibility section, and "I clicked things in
the editor" is not one.

## Check this first

```bash
n8n --version
```

Every typeVersion below is pinned to a value that exists in older releases as well as
2.38.7. If your instance is newer, these still work. If it is much older, a typeVersion
it does not know will either throw `NodeVersionNotFoundError` or silently mis-render the
node's parameters — which is worse, because the workflow imports and then behaves oddly.

## The envelope

Only two keys are actually required. The importer's check is literally:

```js
if (!workflowData.hasOwnProperty('nodes') || !workflowData.hasOwnProperty('connections')) {
    toast.showError(... 'importWorkflowData.invalidStructure' ...);
    return {};
}
```
— [`useCanvasOperations.ts`](https://github.com/n8n-io/n8n/blob/master/packages/frontend/editor-ui/src/app/composables/useCanvasOperations.ts)

`"connections": {}` passes; omitting the key aborts the whole import. What this kit writes:

```json
{
  "name": "W1 · Enquiry intake and triage",
  "nodes": [],
  "connections": {},
  "pinData": {},
  "settings": { "executionOrder": "v1" },
  "meta": { "instanceId": "" }
}
```

`id`, `active`, `versionId`, `createdAt` are ignored on import — the editor overwrites them.

## Nodes

```json
{
  "parameters": {},
  "id": "uuid-v4",
  "name": "Unique within the file",
  "type": "n8n-nodes-base.set",
  "typeVersion": 3.4,
  "position": [220, -140]
}
```

`id` is **regenerated on every import** (`regenerateIds` defaults true), so its value
cannot break anything. Connections never reference it.

`name` is what connections reference, and it must be unique — see the failure list below.

## Connections

```
connections[SOURCE_NODE_NAME][connectionType][outputIndex] = [ { node, type, index }, … ]
```

- Outer array position = the **source's output index**. For IF: `0` is true, `1` is false.
- `index` inside each entry = the **destination's input index** (matters for Merge).
- Entries may be `null` for an unwired branch.
- Keys are node **names**, never ids.

```json
"connections": {
  "Emergency?": {
    "main": [
      [ { "node": "Alert owner immediately", "type": "main", "index": 0 } ],
      [ { "node": "Route", "type": "main", "index": 0 } ]
    ]
  }
}
```

### AI cluster nodes connect upward

This is the part that catches everyone. A chat model is not downstream of the chain — it
is a **source** whose target is the chain, on a non-`main` connection type:

```json
"Claude — drafting": {
  "ai_languageModel": [[{ "node": "Draft the quote", "type": "ai_languageModel", "index": 0 }]]
},
"Quote shape": {
  "ai_outputParser": [[{ "node": "Draft the quote", "type": "ai_outputParser", "index": 0 }]]
}
```

Connection type strings are camelCase after the underscore: `ai_languageModel`,
`ai_outputParser`, `ai_textSplitter`, `ai_vectorStore`, `ai_tool`, `ai_memory`,
`ai_agent`, `ai_chain`, `ai_document`, `ai_embedding`, `ai_retriever`, `ai_reranker`.
Write `ai_languagemodel` and the connection is dropped with no error.

## Pinned typeVersions used by this kit

| Node | `type` | Pinned |
|---|---|---|
| Form Trigger | `n8n-nodes-base.formTrigger` | 2.2 |
| Schedule Trigger | `n8n-nodes-base.scheduleTrigger` | 1.2 |
| Webhook | `n8n-nodes-base.webhook` | 2 |
| Edit Fields (Set) | `n8n-nodes-base.set` | 3.4 |
| IF | `n8n-nodes-base.if` | 2.2 |
| Switch | `n8n-nodes-base.switch` | 3.2 |
| Code | `n8n-nodes-base.code` | 2 |
| Merge | `n8n-nodes-base.merge` | 3.2 |
| Wait | `n8n-nodes-base.wait` | 1.1 |
| Sticky Note | `n8n-nodes-base.stickyNote` | 1 |
| Google Sheets | `n8n-nodes-base.googleSheets` | 4.5 |
| Send Email (SMTP) | `n8n-nodes-base.emailSend` | 2.1 |
| Information Extractor | `@n8n/n8n-nodes-langchain.informationExtractor` | 1.2 |
| Basic LLM Chain | `@n8n/n8n-nodes-langchain.chainLlm` | 1.7 |
| Anthropic Chat Model | `@n8n/n8n-nodes-langchain.lmChatAnthropic` | 1.3 |
| Structured Output Parser | `@n8n/n8n-nodes-langchain.outputParserStructured` | 1.2 |

Google Sheets 4.5 and 4.7 both instantiate the same `GoogleSheetsV2` class, so 4.5 is a
free compatibility win.

## Things that silently break

Loud failures are easy. These are the ones that let the import "succeed" and leave you
debugging a workflow that was never wired the way you wrote it.

| What | What happens |
|---|---|
| **Duplicate node names** | `nodeNameTable[oldName]` maps to the *last* rename only, so connections collapse onto one node. No warning. |
| **Connection target that isn't a node** | `sanitizeConnections()` drops it silently. One typo = one missing wire. |
| **`"index": "0"` as a string** | Entry fails `isValidConnectionEntry` and is dropped silently. |
| **Single-bracket connections** | `[{…}]` instead of `[[{…}]]` — dropped. |
| **Bad `position`** | Not an array, or NaN → `[0,0]`. Every affected node stacks at the origin. |
| **Missing `type`** | Node removed, rest imports. |
| **IF filter version mismatch** | `conditions.options.version` must track typeVersion (2.2→2, 2.3→3). Mismatched changes operator semantics rather than erroring. |
| **Set ≥3.3 using `fields`** | Must be `assignments`. Wrong key = a node that sets nothing. |
| **`hasOutputParser` not true** | The `ai_outputParser` socket never exists, so a wired parser is ignored. |
| **Missing `__rl: true`** | On a resourceLocator (model, documentId, sheetName) the value never resolves. |
| **Expression without `=`** | `"{{ $json.x }}"` is literal text. It must be `"={{ $json.x }}"`. |

`scripts/validate-workflows.py` checks every row in that table. Run it before every import:

```bash
python3 scripts/validate-workflows.py workflows/*.json
```

## Credentials

This kit ships **no** credentials block in any workflow. That is deliberate:

- Credential ids are instance-specific. On import, `removeUnknownCredentials()` strips
  any it does not recognise, then `autoSelectNodeCredentials()` binds the **most recently
  updated** credential of the right type and shows a toast. So a credential you named in
  the file may not be the one that ends up attached.
- Exported JSON carries credential **names and ids** (not secrets). n8n's own docs warn
  to anonymise before sharing.

Open each AI, Sheets and Email node after importing and confirm the credential rather
than trusting the toast.

## The model reference

```json
"model": { "__rl": true, "mode": "id", "value": "claude-sonnet-4-5-20250929" }
```

`mode: "id"` is used here rather than `mode: "list"` on purpose. The list is fetched live
from your Anthropic key, so a `list` value with a stale `cachedResultName` still sends
the underlying `value` — meaning a retired model id fails at *runtime*, not at import.
`id` makes the pin explicit and reviewable, which is what a reproducibility section needs.

**Pin the model for the duration of your study.** Changing it mid-way makes the before
and after incomparable, and you will not be able to tell a model change from a prompt
change. Record it in the job record — the schema already has a `model` field.

## Sticky notes as documentation

Every workflow in this kit is annotated with sticky notes carrying the boundary decision
and its scores. They cost nothing at runtime and they mean a screenshot of the canvas is
self-explanatory in an appendix.

```json
{
  "parameters": { "width": 520, "height": 560, "color": 5, "content": "## Markdown here" },
  "name": "Note 1",
  "type": "n8n-nodes-base.stickyNote",
  "typeVersion": 1,
  "position": [-820, -420]
}
```

`width`, `height` and `color` are **parameters**, not top-level keys, and all three are
required. Colours are integers 1–7: yellow, gold, red, green, blue, purple, grey. Stickies
need no entry in `connections`.

## Known gaps

Named rather than papered over, because a limitations section is easier to write when you
kept the list as you went.

- **No PDF generation node exists in n8n.** Verified across the whole node directory at
  2.38.7 — `ReadPdf` and Extract from File read PDFs, nothing writes one. Convert to File
  covers `csv, html, iCal, toJson, ods, rtf, toText, xls, xlsx, toBinary` and no PDF. The
  built-in route is Google Docs → Google Drive `file:download` with
  `options.googleFileConversion.conversion.docsToFormat: "application/pdf"`. Everything
  else means an external API.
- **The Postgres `select` operation has a real bug**: `returnAll`'s `displayOptions`
  references `resource: ['event'], operation: ['getAll']` — copy-paste residue from the
  Calendar node — so it never renders and `limit` (default 50) governs instead. Set
  `limit` explicitly if you switch storage to Postgres.
- **Unverified and worth five minutes each if you use them**: the Form node's
  `respondWith` value literals, Gmail's `readStatus` value literals, and whether Google
  Calendar renders `timeMin`/`timeMax` top-level or inside `options`.
- **Nobody has imported these files into a live n8n instance yet.** Everything is read
  from the import code path and validated structurally. Import one end to end before you
  build a week of work on top of it.
