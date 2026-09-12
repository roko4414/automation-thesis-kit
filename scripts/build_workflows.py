#!/usr/bin/env python3
"""
Build the five n8n workflows, once per industry pack.

One skeleton, many industries. The workflows are written with <<TOKENS>> where the
industry shows through — what a quote is called, what counts as an emergency, where the
service area stops — and `specialise()` swaps them for a pack's values.

That is not a code-tidiness choice, it is the transferability claim under test: if
moving to a new industry only needs a pack, the pattern generalises; if it needs surgery
on the workflows, it does not. Either answer is a real finding.

Written as a generator rather than by hand because the failure modes of hand-authored
n8n JSON are all bookkeeping: duplicate node names collapse connections silently,
a mistyped connection target is dropped without a warning, and positions drift.
Generating them means the node registry is the single source of truth for names.

typeVersions are pinned deliberately BELOW the newest available (see PINS). A
typeVersion the target n8n does not know either throws or silently mis-renders
parameters, and a student on an older install is the common case. Every pin here was
checked to exist in the node's version array.

Run:  python3 scripts/build_workflows.py && python3 scripts/validate-workflows.py workflows/*.json
"""
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDUSTRIES = ROOT / "industries"

# --- pinned type versions -------------------------------------------------
FORM_TRIGGER = ("n8n-nodes-base.formTrigger", 2.2)
SCHEDULE     = ("n8n-nodes-base.scheduleTrigger", 1.2)
WEBHOOK      = ("n8n-nodes-base.webhook", 2)
SET          = ("n8n-nodes-base.set", 3.4)
IF           = ("n8n-nodes-base.if", 2.2)     # filter version 2 — see FILTER_V
SWITCH       = ("n8n-nodes-base.switch", 3.2)
CODE         = ("n8n-nodes-base.code", 2)
MERGE        = ("n8n-nodes-base.merge", 3.2)
WAIT         = ("n8n-nodes-base.wait", 1.1)
NOOP         = ("n8n-nodes-base.noOp", 1)
STICKY       = ("n8n-nodes-base.stickyNote", 1)
SHEETS       = ("n8n-nodes-base.googleSheets", 4.5)
EMAIL        = ("n8n-nodes-base.emailSend", 2.1)
EXTRACTOR    = ("@n8n/n8n-nodes-langchain.informationExtractor", 1.2)
LLM_CHAIN    = ("@n8n/n8n-nodes-langchain.chainLlm", 1.7)
ANTHROPIC    = ("@n8n/n8n-nodes-langchain.lmChatAnthropic", 1.3)
OUT_PARSER   = ("@n8n/n8n-nodes-langchain.outputParserStructured", 1.2)

FILTER_V = 2  # must track IF typeVersion 2.2

MODEL = "claude-sonnet-4-5-20250929"

# Sticky colours: 1 yellow, 2 gold, 3 red, 4 green, 5 blue, 6 purple, 7 grey
C_INTRO, C_GATE, C_STEP, C_MEASURE = 5, 2, 7, 4


def nid():
    return str(uuid.uuid4())


class WF:
    """Collects nodes and connections, keeping names unique by construction."""

    def __init__(self, name, description):
        self.name = name
        self.description = description
        self.nodes = []
        self.conns = {}
        self._names = set()

    def node(self, name, type_version, params, pos, **extra):
        if name in self._names:
            raise ValueError(f"duplicate node name {name!r} in {self.name!r}")
        self._names.add(name)
        t, v = type_version
        n = {"parameters": params, "id": nid(), "name": name,
             "type": t, "typeVersion": v, "position": list(pos)}
        n.update(extra)
        self.nodes.append(n)
        return name

    def sticky(self, content, pos, width, height, color):
        # Sticky names never collide and are never wired.
        name = f"Note {len([n for n in self.nodes if n['type'] == STICKY[0]]) + 1}"
        return self.node(name, STICKY,
                         {"content": content, "width": width, "height": height, "color": color},
                         pos)

    def wire(self, src, dst, out=0, inp=0, ctype="main"):
        by = self.conns.setdefault(src, {}).setdefault(ctype, [])
        while len(by) <= out:
            by.append([])
        by[out].append({"node": dst, "type": ctype, "index": inp})

    def ai(self, sub, root, ctype):
        """Cluster sub-node connects UP into its root node."""
        self.wire(sub, root, ctype=ctype)

    def dump(self, filename, pack):
        doc = {
            "name": self.name,
            "nodes": self.nodes,
            "connections": self.conns,
            "pinData": {},
            "settings": {"executionOrder": "v1"},
            "meta": {"instanceId": ""},
        }
        doc = specialise(doc, tokens(pack))
        out = INDUSTRIES / pack["slug"] / "workflows"
        out.mkdir(parents=True, exist_ok=True)
        p = out / filename
        p.write_text(json.dumps(doc, indent=2) + "\n")
        return p


def anthropic_node(wf, name, pos, temperature=0, max_tokens=2048):
    """Anthropic chat sub-node. mode 'id' avoids depending on a live model list."""
    return wf.node(name, ANTHROPIC, {
        "model": {"__rl": True, "mode": "id", "value": MODEL},
        "options": {"temperature": temperature, "maxTokensToSample": max_tokens},
    }, pos)


def if_params(left, operator, right=None, right_type="string"):
    cond = {"id": nid(), "operator": operator, "leftValue": left, "rightValue": right if right is not None else ""}
    return {
        "conditions": {
            "options": {"version": FILTER_V, "leftValue": "", "caseSensitive": True,
                        "typeValidation": "loose"},
            "combinator": "and",
            "conditions": [cond],
        },
        "looseTypeValidation": True,
        "options": {},
    }


def op_equals(t="string"):
    return {"type": t, "operation": "equals"}


def op_true():
    return {"type": "boolean", "operation": "true", "singleValue": True}


def set_params(pairs):
    return {
        "mode": "manual",
        "options": {},
        "assignments": {"assignments": [
            {"id": nid(), "name": k, "type": ty, "value": v} for k, ty, v in pairs
        ]},
    }


def sheets_append(doc_placeholder, tab, columns):
    schema = [{"id": c, "displayName": c, "required": False, "defaultMatch": False,
               "display": True, "type": "string", "canBeUsedToMatch": True} for c in columns]
    return {
        "operation": "append",
        "documentId": {"__rl": True, "mode": "id", "value": doc_placeholder},
        "sheetName": {"__rl": True, "mode": "name", "value": tab},
        "columns": {
            "mappingMode": "defineBelow",
            "value": {c: f"={{{{ $json.{c} }}}}" for c in columns},
            "schema": schema,
            "matchingColumns": [],
            "attemptToConvertTypes": False,
            "convertFieldsToString": True,
        },
        "options": {},
    }


SHEET_ID = "REPLACE_WITH_YOUR_SPREADSHEET_ID"


def load_packs():
    packs = []
    for d in sorted(INDUSTRIES.iterdir()):
        f = d / "pack.json"
        if f.exists():
            packs.append(json.loads(f.read_text()))
    if not packs:
        raise SystemExit("no industry packs found under industries/*/pack.json")
    return packs


def tokens(pack):
    area = pack["service_area"]
    cap = lambda s: s[:1].upper() + s[1:]
    return {
        "<<LABEL>>": pack["label"],
        "<<BUSINESS>>": pack["business"],
        "<<REGION>>": pack["region"],
        "<<CUR>>": pack["currency"],
        "<<VAT>>": str(pack["vat_rate"]),
        "<<QUOTE>>": pack["quote_word"],
        "<<QUOTE_CAP>>": cap(pack["quote_word"]),
        "<<VISIT>>": pack["visit_word"],
        "<<VISIT_CAP>>": cap(pack["visit_word"]),
        "<<ENQUIRY>>": pack["enquiry_word"],
        "<<ENQUIRY_CAP>>": cap(pack["enquiry_word"]),
        "<<JOB>>": pack["job_word"],
        "<<JOB_CAP>>": cap(pack["job_word"]),
        "<<UNIT>>": pack["unit_of_work"],
        "<<AREA_IN>>": ", ".join(area["in"]),
        "<<AREA_OUT>>": ", ".join(area["out"]),
        "<<AREA_NOTE>>": area["note"],
        "<<EMERGENCY_DEF>>": pack["emergency_definition"],
        "<<THRESHOLD>>": str(pack["high_value_threshold_chf"]),
        "<<THRESHOLD_NOTE>>": pack["threshold_note"],
        "<<COMPLIANCE>>": pack["compliance_note"],
        "<<PRICING>>": pack["pricing_note"],
        "<<DIFFERENT>>": pack["what_makes_it_different"],
    }


def specialise(obj, tok):
    """Walk the built document and swap every <<TOKEN>> for this pack's value."""
    if isinstance(obj, str):
        for k, v in tok.items():
            if k in obj:
                obj = obj.replace(k, v)
        return obj
    if isinstance(obj, list):
        return [specialise(x, tok) for x in obj]
    if isinstance(obj, dict):
        # Keys matter too: `connections` is keyed by node name, so a key left
        # un-substituted points at a node that no longer exists under that name —
        # and n8n drops such an entry silently rather than complaining.
        return {specialise(k, tok): specialise(v, tok) for k, v in obj.items()}
    return obj


# =====================================================================
# W1 — Enquiry intake and triage
# =====================================================================
def build_w1(pack):
    wf = WF("W1 · <<ENQUIRY_CAP>> intake and triage — <<LABEL>>",
            "Any inbound <<ENQUIRY>> becomes one structured record, or is refused with a reason.")

    wf.sticky(
        "## W1 — <<ENQUIRY_CAP>> intake · <<LABEL>>\n\n"
        "**Boundary decision: fully automated.**\n"
        "Variance low-ish, consequence low (a misfiling surfaces in the queue), "
        "input short. Scored 2/1/2 on variance / consequence / data-availability.\n\n"
        "**Except one case.** An emergency must leave the automated path immediately. "
        "That branch is the red note below — if it ever stops working, that is not a bug "
        "report, it is a finding for your results chapter.\n\n"
        "### Before you run this\n"
        "1. Open **Extract enquiry fields** and pick your Anthropic credential.\n"
        "2. Open the three **Google Sheets** nodes and set the document ID.\n"
        "3. Replace `REPLACE_WITH_YOUR_SPREADSHEET_ID` throughout.\n\n"
        "### Test it\n"
        "Paste each record from this pack's `enquiries.json` into the form. Every file has a "
        "record that must be refused, one that must escalate, and one out-of-area case — "
        "each says so in its `notes_for_testing`.\n\n"
        "### What is different about this industry\n<<DIFFERENT>>",
        (-820, -420), 520, 560, C_INTRO)

    trg = wf.node("Enquiry form", FORM_TRIGGER, {
        "authentication": "none",
        "formTitle": "Request a <<QUOTE>>",
        "formDescription": "Tell us what you need and we will reply within one business day.",
        "formFields": {"values": [
            {"fieldLabel": "Your name", "fieldName": "customer_name", "fieldType": "text", "requiredField": True},
            {"fieldLabel": "Email", "fieldName": "email", "fieldType": "email", "requiredField": True},
            {"fieldLabel": "Phone", "fieldName": "phone", "fieldType": "text", "requiredField": False},
            {"fieldLabel": "Where the work is", "fieldName": "address", "fieldType": "text", "requiredField": False},
            {"fieldLabel": "What do you need?", "fieldName": "raw", "fieldType": "textarea", "requiredField": True},
        ]},
        "responseMode": "onReceived",
        "options": {"path": "enquiry", "buttonLabel": "Send enquiry"},
    }, (-260, -180), webhookId=nid())

    norm = wf.node("Normalise inbound", CODE, {"jsCode": '''
// One shape for every channel. The form is only one door — email, SMS and phone
// transcripts arrive via other triggers and are normalised to exactly this object,
// so everything downstream reads the same fields regardless of where it came from.
//
// `raw` is never overwritten anywhere in the pipeline. Extraction can then be re-run
// and compared later, which is what makes the prompt-version comparison possible.
const now = new Date().toISOString();

return items.map((item, i) => {
  const f = item.json;
  return {
    json: {
      job_id: `JOB-${new Date().getFullYear()}-${String(Date.now()).slice(-4)}${i}`,
      state: 'new',
      created_at: now,
      channel: f.channel ?? 'web-form',
      raw: f.raw ?? '',
      form_customer_name: f.customer_name ?? null,
      form_email: f.email ?? null,
      form_phone: f.phone ?? null,
      form_address: f.address ?? null,
      events: [],
    },
  };
});
'''.strip()}, (-40, -180))

    ext = wf.node("Extract enquiry fields", EXTRACTOR, {
        "text": "={{ $json.raw }}",
        "schemaType": "manual",
        "inputSchema": json.dumps({
            "type": "object",
            "properties": {
                "customer_name": {"type": ["string", "null"]},
                "email": {"type": ["string", "null"]},
                "phone": {"type": ["string", "null"]},
                "locality": {"type": ["string", "null"]},
                "language": {"type": "string", "enum": ["de", "en", "fr", "it", "unknown"]},
                "job_type": {"type": ["string", "null"]},
                "described_scope": {"type": ["string", "null"]},
                "urgency": {"type": "string",
                            "enum": ["emergency", "urgent", "scheduled", "no_rush", "unknown"]},
                "deadline": {"type": ["string", "null"]},
                "in_service_area": {"type": ["boolean", "null"]},
                "is_repeat_customer": {"type": "boolean"},
                "missing_fields": {"type": "array", "items": {"type": "string"}},
                "extraction_confidence": {"type": "number"},
                "disqualify_reason": {"type": ["string", "null"]},
            },
            "required": ["language", "urgency", "missing_fields", "extraction_confidence"],
        }, indent=2),
        "options": {"systemPromptTemplate": (
            "You extract structured data from <<ENQUIRY>> messages sent to <<BUSINESS>> in "
            "<<REGION>>. They arrive in German or English and are often incomplete.\n\n"
            "Never invent a value. If a field is not present, return null and name it in "
            "missing_fields. A plausible guess is worse than a null: a null gets asked about, "
            "a guess gets acted on.\n\n"
            "Keep described_scope in the language it was written in and set language accordingly.\n\n"
            "urgency is about consequence, not tone. A calm message can describe an emergency and "
            "an angry one can describe something trivial. For this business, treat as an "
            "emergency: <<EMERGENCY_DEF>>\n\n"
            "Service area — <<AREA_NOTE>>\n"
            "In: <<AREA_IN>>. Out: <<AREA_OUT>>. If a locality is stated but you do not "
            "recognise it, return null rather than guessing — a wrong false loses real work.\n\n"
            "extraction_confidence is your honest estimate that a human reading the same text "
            "would extract the same fields. Do not inflate it.\n\n"
            "If no actionable <<UNIT>> is described at all, set job_type null and give a "
            "disqualify_reason."
        )},
    }, (220, -180))

    model = anthropic_node(wf, "Claude — extraction", (240, 40), temperature=0)
    wf.ai(model, ext, "ai_languageModel")

    score = wf.node("Merge and score", CODE, {"jsCode": '''
// Form fields beat model extraction. If the customer typed their name into a labelled
// box, that is ground truth; the model's reading of free text is not.
const src = $('Normalise inbound').first().json;
const ex  = $json.output ?? $json;

const merged = {
  ...src,
  customer_name: src.form_customer_name || ex.customer_name || null,
  email:         src.form_email         || ex.email         || null,
  phone:         src.form_phone         || ex.phone         || null,
  address:       src.form_address       || null,
  locality:      ex.locality ?? null,
  language:      ex.language ?? 'unknown',
  job_type:      ex.job_type ?? null,
  described_scope: ex.described_scope ?? null,
  urgency:       ex.urgency ?? 'unknown',
  deadline:      ex.deadline ?? null,
  in_service_area: ex.in_service_area ?? null,
  is_repeat_customer: ex.is_repeat_customer ?? false,
  missing_fields: ex.missing_fields ?? [],
  extraction_confidence: ex.extraction_confidence ?? 0,
  disqualify_reason: ex.disqualify_reason ?? null,
};

// Contactability is decided here, not by the model. A job with no way to reach the
// customer cannot be quoted no matter how well described it is.
const contactable = Boolean(merged.email || merged.phone);
if (!contactable && !merged.disqualify_reason) {
  merged.disqualify_reason = 'no contact detail supplied';
}

merged.is_emergency = merged.urgency === 'emergency';

// Low confidence is not a disqualification — it is a routing signal. These go to a
// human to read rather than being refused or auto-progressed.
merged.needs_human_read =
  merged.extraction_confidence < 0.6 || merged.missing_fields.length > 2;

if (merged.disqualify_reason)            merged.route = 'disqualified';
else if (merged.in_service_area === false) merged.route = 'out_of_area';
else                                       merged.route = 'qualified';

merged.state = merged.route === 'qualified' ? 'qualified' : 'disqualified';
return [{ json: merged }];
'''.strip()}, (480, -180))

    emg = wf.node("Emergency?", IF,
                  if_params("={{ $json.is_emergency }}", op_true()), (700, -180))

    wf.sticky(
        "## The escalation branch\n\n"
        "This is the only unconditional exit from the automated path in W1.\n\n"
        "<<EMERGENCY_DEF>>\n\n"
        "None of that belongs in a pricing pipeline. If your triage ever routes one into the "
        "normal flow, **report it** — an automation that handles an emergency as routine admin "
        "is exactly the kind of boundary failure this thesis is about.",
        (940, -480), 380, 240, C_GATE)

    alert = wf.node("Alert owner immediately", EMAIL, {
        "operation": "send",
        "fromEmail": "workflow@example.ch",
        "toEmail": "owner@example.ch",
        "subject": "=URGENT — {{ $json.customer_name || 'unknown contact' }} — call now",
        "emailFormat": "html",
        "html": "=<p><strong>Possible emergency. Automated handling stopped.</strong></p>"
                "<p><strong>Contact:</strong> {{ $json.phone || $json.email || 'NONE SUPPLIED' }}</p>"
                "<p><strong>They wrote:</strong></p><blockquote>{{ $json.raw }}</blockquote>"
                "<p>Record {{ $json.job_id }} received {{ $json.created_at }}.</p>",
        "options": {},
    }, (960, -280))

    route = wf.node("Route", SWITCH, {
        "rules": {"values": [
            {"outputKey": "qualified", "renameOutput": True,
             "conditions": {"options": {"version": FILTER_V, "leftValue": "", "caseSensitive": True,
                                        "typeValidation": "loose"},
                            "combinator": "and",
                            "conditions": [{"id": nid(), "operator": op_equals(),
                                            "leftValue": "={{ $json.route }}", "rightValue": "qualified"}]}},
            {"outputKey": "out_of_area", "renameOutput": True,
             "conditions": {"options": {"version": FILTER_V, "leftValue": "", "caseSensitive": True,
                                        "typeValidation": "loose"},
                            "combinator": "and",
                            "conditions": [{"id": nid(), "operator": op_equals(),
                                            "leftValue": "={{ $json.route }}", "rightValue": "out_of_area"}]}},
        ]},
        "options": {"fallbackOutput": "extra", "renameFallbackOutput": "disqualified"},
    }, (960, -60))

    save = wf.node("Save job record", SHEETS, sheets_append(
        SHEET_ID, "jobs",
        ["job_id", "state", "created_at", "channel", "customer_name", "email", "phone",
         "address", "locality", "language", "job_type", "described_scope", "urgency",
         "deadline", "in_service_area", "extraction_confidence", "needs_human_read", "raw"],
    ), (1240, -220))

    decline = wf.node("Decline — out of area", EMAIL, {
        "operation": "send",
        "fromEmail": "workflow@example.ch",
        "toEmail": "={{ $json.email }}",
        "subject": "About your enquiry",
        "emailFormat": "html",
        "html": "=<p>Hallo {{ $json.customer_name || '' }},</p>"
                "<p>Thanks for getting in touch. {{ $json.locality }} is outside the area we cover, "
                "so we are not able to take this on — we did not want to leave you waiting "
                "on a reply.</p><p>Best of luck with it.</p>",
        "options": {},
    }, (1240, 40))

    park = wf.node("Park for review", SHEETS, sheets_append(
        SHEET_ID, "unqualified",
        ["job_id", "created_at", "channel", "disqualify_reason", "extraction_confidence", "raw"],
    ), (1240, 220))

    wf.sticky(
        "## Refusals are data\n\n"
        "Nothing is thrown away. Everything the triage refuses is written to the "
        "`unqualified` tab with the reason.\n\n"
        "Two reasons this matters for the thesis:\n\n"
        "1. **False refusals are invisible otherwise.** A real job wrongly refused looks "
        "exactly like no enquiry at all. Reviewing this tab weekly is how you find them.\n"
        "2. Refusal rate over time, with reasons, is a genuine result — and it is the "
        "number the business owner will care about most.",
        (1180, 420), 420, 250, C_MEASURE)

    log = wf.node("Log event", SHEETS, sheets_append(
        SHEET_ID, "events",
        ["at", "workflow", "node", "status", "job_id", "human_intervened", "note"],
    ), (1520, -220))

    logprep = wf.node("Build event", CODE, {"jsCode": '''
// Instrumentation is built BEFORE the automation, not after. Without this table there
// is no baseline, no before/after, and no results chapter — only a feature description.
return [{
  json: {
    at: new Date().toISOString(),
    workflow: 'W1-intake',
    node: 'triage-complete',
    status: 'ok',
    job_id: $json.job_id ?? null,
    human_intervened: false,
    note: `route=${$json.route} confidence=${$json.extraction_confidence} lang=${$json.language}`,
  },
}];
'''.strip()}, (1400, -220))

    wf.wire(trg, norm)
    wf.wire(norm, ext)
    wf.wire(ext, score)
    wf.wire(score, emg)
    wf.wire(emg, alert, out=0)      # true  → escalate, path ends
    wf.wire(emg, route, out=1)      # false → normal routing
    wf.wire(route, save, out=0)
    wf.wire(route, decline, out=1)
    wf.wire(route, park, out=2)
    wf.wire(save, logprep)
    wf.wire(logprep, log)

    return wf.dump("01-enquiry-intake.json", pack)


# =====================================================================
# W3 — Quote drafting  (the centre of the thesis)
# =====================================================================
def build_w3(pack):
    wf = WF("W3 · <<QUOTE_CAP>> drafting — <<LABEL>>",
            "<<VISIT_CAP>> notes become a priced draft. A human approves every one, always.")

    wf.sticky(
        "## W3 — <<QUOTE_CAP>> drafting · <<LABEL>>\n\n"
        "**Boundary decision: draft-and-review, unconditional.**\n"
        "Variance high (every <<UNIT>> differs), consequence high (a wrong price is money out "
        "of the owner's pocket), and a sent <<QUOTE>> cannot be withdrawn. Scored 5/5/3.\n\n"
        "The system assembles. The owner decides. There is no value threshold below which "
        "this gate is skipped — a cheap <<UNIT>> priced wrong still costs trust.\n\n"
        "### Why this workflow is the thesis\n"
        "Everything measurable and interesting is here: what the model gets right, what it "
        "gets wrong, how long review takes against writing from scratch, and whether review "
        "time falls as the owner learns where to trust it.\n\n"
        "If you instrument nothing else properly, instrument this.",
        (-880, -520), 540, 520, C_INTRO)

    trg = wf.node("<<VISIT_CAP>> complete", WEBHOOK, {
        "path": "visit-complete",
        "httpMethod": "POST",
        "responseMode": "lastNode",
        "options": {},
    }, (-300, -140), webhookId=nid())

    rate = wf.node("Load price list", SHEETS, {
        "documentId": {"__rl": True, "mode": "id", "value": SHEET_ID},
        "sheetName": {"__rl": True, "mode": "name", "value": "price_list"},
        "options": {},
    }, (-80, -280))

    hist = wf.node("Load past work", SHEETS, {
        "documentId": {"__rl": True, "mode": "id", "value": SHEET_ID},
        "sheetName": {"__rl": True, "mode": "name", "value": "historical_jobs"},
        "options": {},
    }, (-80, 0))

    ctx = wf.node("Build pricing context", CODE, {"jsCode": '''
// Retrieval is deliberately crude: keyword overlap on job_type and scope text.
//
// That is a choice worth defending in the thesis rather than apologising for. A vector
// store would retrieve better, but 25 historical jobs is not a retrieval problem — it is
// a lookup. Adding embeddings here would add a dependency, a cost line and a failure
// mode in exchange for nothing measurable at this scale. If your business has 5,000 past
// jobs, revisit it, and say so in the limitations.
const visit = $('<<VISIT_CAP>> complete').first().json.body ?? $('<<VISIT_CAP>> complete').first().json;
const rateCard = $('Load price list').all().map(i => i.json);
const past     = $('Load past work').all().map(i => i.json);

const stop = new Set(['the','and','for','with','new','all','job','from','into','out','per']);
const tokens = (s) => String(s ?? '').toLowerCase().match(/[a-zà-ÿ]{3,}/g)?.filter(t => !stop.has(t)) ?? [];

const wanted = new Set([...tokens(visit.job_type), ...tokens(visit.visit_notes)]);

const scored = past.map(j => {
  const have = new Set([...tokens(j.job_type), ...tokens(j.scope_text)]);
  let overlap = 0;
  for (const t of wanted) if (have.has(t)) overlap++;
  const typeMatch = (j.job_type ?? '') === (visit.job_type ?? '') ? 3 : 0;
  return { job: j, score: overlap + typeMatch };
}).filter(x => x.score > 0)
  .sort((a, b) => b.score - a.score)
  .slice(0, 3);

return [{
  json: {
    job_id: visit.job_id,
    visit_notes: visit.visit_notes ?? '',
    job_type: visit.job_type ?? null,
    locality: visit.locality ?? null,
    language: visit.language ?? 'de',
    rate_card_csv: [Object.keys(rateCard[0] ?? {}).join(',')]
      .concat(rateCard.map(r => Object.values(r).join(','))).join('\\n'),
    similar_jobs: scored.map(s => s.job),
    similar_scores: scored.map(s => s.score),
    retrieval_method: 'keyword-overlap-v1',
  },
}];
'''.strip()}, (180, -140))

    chain = wf.node("Draft the quote", LLM_CHAIN, {
        "promptType": "define",
        "text": "=Draft a <<QUOTE>> from this <<VISIT>>.\n\n"
                "JOB TYPE: {{ $json.job_type }}\n"
                "LOCALITY: {{ $json.locality }}\n\n"
                "NOTES FROM THE <<VISIT>>:\n{{ $json.visit_notes }}\n\n"
                "PRICE LIST (csv):\n{{ $json.rate_card_csv }}\n\n"
                "THREE MOST SIMILAR COMPLETED <<JOB>>S:\n{{ JSON.stringify($json.similar_jobs, null, 2) }}",
        "messages": {"messageValues": [{"message": (
            "You draft <<QUOTE>>s for <<BUSINESS>> in <<REGION>>. Your output is REVIEWED AND "
            "CORRECTED by a person before anything is sent. Draft accordingly: it is far "
            "better to flag uncertainty than to look confident.\n\n"
            "RULES\n"
            "1. Every line item must use a code from the price list. If work is needed that "
            "has no code, put it in unpriced_items with a description. Never invent a code "
            "or a rate — that is the most expensive mistake available to you.\n"
            "2. Surface every assumption. Anything you inferred rather than read — cable "
            "runs, wall construction, access, spare ways in the board — goes in assumptions. "
            "The owner scans that list first to catch you being wrong.\n"
            "3. Use the similar past work as a sanity check, not a template. If your total differs "
            "from a comparable job by more than 30%, say so in flags and explain why. Do not "
            "quietly adjust to match.\n"
            "4. Optional scope stays optional: mark those lines optional true, never folded "
            "into the main total.\n"
            "5. No discounts. Pricing strategy is the owner's decision, not yours.\n"
            "6. State exclusions. There are always things a customer assumes are included and "
            "that are not. Name them.\n\n"
            "HOW PRICING WORKS HERE\n<<PRICING>>\n\n"
            "COMPLIANCE\n<<COMPLIANCE>> Do not omit it.\n\n"
            "VAT: <<VAT>>% of subtotal. Round line totals to 0.05 <<CUR>>, the total to 1 <<CUR>>."
        )}]},
        "hasOutputParser": True,
        "batching": {},
    }, (420, -140))

    model = anthropic_node(wf, "Claude — drafting", (400, 120), temperature=0, max_tokens=4096)
    wf.ai(model, chain, "ai_languageModel")

    parser = wf.node("Quote shape", OUT_PARSER, {
        "schemaType": "manual",
        "inputSchema": json.dumps({
            "type": "object",
            "properties": {
                "line_items": {"type": "array", "items": {"type": "object", "properties": {
                    "code": {"type": "string"}, "description": {"type": "string"},
                    "quantity": {"type": "number"}, "unit_rate_chf": {"type": "number"},
                    "line_total_chf": {"type": "number"}, "optional": {"type": "boolean"}},
                    "required": ["code", "description", "quantity", "unit_rate_chf", "line_total_chf"]}},
                "unpriced_items": {"type": "array", "items": {"type": "object", "properties": {
                    "description": {"type": "string"}, "why": {"type": "string"}}}},
                "assumptions": {"type": "array", "items": {"type": "string"}},
                "exclusions": {"type": "array", "items": {"type": "string"}},
                "flags": {"type": "array", "items": {"type": "string"}},
                "subtotal_chf": {"type": "number"},
                "vat_chf": {"type": "number"},
                "total_chf": {"type": "number"},
                "confidence": {"type": "number"},
            },
            "required": ["line_items", "assumptions", "exclusions", "subtotal_chf",
                         "vat_chf", "total_chf", "confidence"],
        }, indent=2),
    }, (620, 120))
    wf.ai(parser, chain, "ai_outputParser")

    check = wf.node("Check against rate card", CODE, {"jsCode": '''
// Deterministic checks the model does not get a vote on.
//
// An invented rate code is the failure mode that costs real money, so it is caught in
// code and counted — not left to the reviewer to spot. Every one of these findings is a
// row in your results chapter.
const draft = $json.output ?? $json;
const rateCard = $('Load price list').all().map(i => i.json);
const codes = new Set(rateCard.map(r => r.code));

const invented = [];
let recomputed = 0;

for (const li of draft.line_items ?? []) {
  if (!codes.has(li.code)) {
    invented.push(li.code);
    continue;
  }
  const card = rateCard.find(r => r.code === li.code);
  const expected = Number(card.rate_chf) * Number(li.quantity);
  // Flag arithmetic drift over 1 CHF. The model is not a calculator and should not be
  // trusted as one; this is cheaper than asking it to show its working.
  if (Math.abs(expected - Number(li.line_total_chf)) > 1 && !li.optional) {
    li.arithmetic_warning = `expected ${expected.toFixed(2)} from rate card`;
  }
  if (!li.optional) recomputed += expected;
}

const stated = Number(draft.subtotal_chf ?? 0);
const drift = Math.abs(recomputed - stated);

return [{
  json: {
    ...$('Build pricing context').first().json,
    drafted: draft,
    validation: {
      invented_codes: invented,
      invented_code_count: invented.length,
      subtotal_recomputed_chf: Number(recomputed.toFixed(2)),
      subtotal_drift_chf: Number(drift.toFixed(2)),
      // Any of these means the draft is unsafe to present without a warning banner.
      needs_attention: invented.length > 0 || drift > 5 || (draft.confidence ?? 0) < 0.5,
    },
    drafted_at: new Date().toISOString(),
    prompt_version: '1.0.0',
    model: 'claude-sonnet-4-5',
  },
}];
'''.strip()}, (860, -140))

    store = wf.node("Store draft", SHEETS, sheets_append(
        SHEET_ID, "quote_drafts",
        ["job_id", "drafted_at", "prompt_version", "model", "total_chf", "confidence",
         "invented_code_count", "subtotal_drift_chf", "needs_attention", "draft_json"],
    ), (1080, -300))

    prep = wf.node("Prepare review", CODE, {"jsCode": '''
const d = $json.drafted;
return [{
  json: {
    ...$json,
    total_chf: d.total_chf,
    confidence: d.confidence,
    invented_code_count: $json.validation.invented_code_count,
    subtotal_drift_chf: $json.validation.subtotal_drift_chf,
    needs_attention: $json.validation.needs_attention,
    draft_json: JSON.stringify(d),
    review_opened_at: new Date().toISOString(),
  },
}];
'''.strip()}, (1080, -140))

    wf.sticky(
        "## The gate\n\n"
        "**Wait — resume on webhook.** The workflow stops here until a human acts.\n\n"
        "The review link is `{{ $execution.resumeUrl }}`, and it must be sent from the node "
        "**before** the Wait. Once execution pauses here, nothing downstream runs until "
        "someone opens that link — so an email placed after the gate would never arrive to "
        "tell anyone the gate existed.\n\n"
        "In week 9 you replace this email with the Wippli review queue. The gate does not "
        "move; only its surface does. That is the point worth making in the write-up: the "
        "boundary is an architectural decision, the interface is an implementation detail.\n\n"
        "### Measure here\n"
        "`review_opened_at` to `review_approved_at` is review duration. Compare it against "
        "how long the owner took to write a quote from scratch during your baseline weeks. "
        "That single comparison is your headline number for this workflow.",
        (1300, -560), 460, 400, C_GATE)

    gate = wf.node("Await owner approval", WAIT, {
        "resume": "webhook",
        "httpMethod": "GET",
        "responseCode": 200,
        "responseMode": "onReceived",
        "options": {"webhookSuffix": "approve"},
    }, (1540, -140), webhookId=nid())

    notify = wf.node("Send review request", EMAIL, {
        "operation": "send",
        "fromEmail": "workflow@example.ch",
        "toEmail": "owner@example.ch",
        "subject": "=<<QUOTE_CAP>> draft ready — {{ $json.job_id }} — <<CUR>> {{ $json.total_chf }}",
        "emailFormat": "html",
        "html": "=<p>Draft for <strong>{{ $json.job_id }}</strong> "
                "({{ $json.job_type }}, {{ $json.locality }}).</p>"
                "<p><strong>Total: <<CUR>> {{ $json.total_chf }}</strong> · "
                "model confidence {{ $json.confidence }}</p>"
                "{{ $json.needs_attention ? '<p style=\\\"color:#b00\\\"><strong>Needs attention:</strong> '"
                " + $json.invented_code_count + ' unrecognised rate code(s), '"
                " + 'subtotal drift <<CUR>> ' + $json.subtotal_drift_chf + '</p>' : '' }}"
                "<h4>Assumptions the draft made</h4>"
                "<ul>{{ $json.drafted.assumptions.map(a => '<li>' + a + '</li>').join('') }}</ul>"
                "<h4>Excluded</h4>"
                "<ul>{{ $json.drafted.exclusions.map(a => '<li>' + a + '</li>').join('') }}</ul>"
                "<h4>Lines</h4><pre>{{ JSON.stringify($json.drafted.line_items, null, 2) }}</pre>"
                "<p><a href=\"{{ $execution.resumeUrl }}\">Approve as drafted</a> — "
                "or edit the sheet first, then approve.</p>",
        "options": {},
    }, (1320, -140))

    diff = wf.node("Diff draft against approved", CODE, {"jsCode": '''
// THE measurement. Everything else in this workflow exists so that this node has
// something honest to compare.
//
// The approved version is read back from the sheet because that is where the owner
// actually edits it. If she approves without touching anything, drafted === approved
// and the override list is empty — which is itself the finding you are looking for.
const before = $('Prepare review').first().json;
const drafted = before.drafted;

let approved = drafted;
try {
  approved = JSON.parse($json.approved_json ?? '{}');
  if (!approved.line_items) approved = drafted;
} catch (e) {
  approved = drafted;
}

const overridden = [];
if (Number(approved.total_chf) !== Number(drafted.total_chf)) overridden.push('total_chf');

const byCode = (arr) => Object.fromEntries((arr ?? []).map(li => [li.code, li]));
const dMap = byCode(drafted.line_items);
const aMap = byCode(approved.line_items);

for (const code of new Set([...Object.keys(dMap), ...Object.keys(aMap)])) {
  const d = dMap[code], a = aMap[code];
  if (!a) { overridden.push(`line_removed:${code}`); continue; }
  if (!d) { overridden.push(`line_added:${code}`);   continue; }
  if (Number(d.quantity)      !== Number(a.quantity))      overridden.push(`quantity:${code}`);
  if (Number(d.unit_rate_chf) !== Number(a.unit_rate_chf)) overridden.push(`rate:${code}`);
}

const openedAt = new Date(before.review_opened_at);
const now = new Date();

return [{
  json: {
    job_id: before.job_id,
    prompt_version: before.prompt_version,
    model: before.model,
    review_opened_at: before.review_opened_at,
    review_approved_at: now.toISOString(),
    review_duration_seconds: Math.round((now - openedAt) / 1000),
    drafted_total_chf: drafted.total_chf,
    approved_total_chf: approved.total_chf,
    delta_chf: Number((Number(approved.total_chf) - Number(drafted.total_chf)).toFixed(2)),
    line_count_drafted: (drafted.line_items ?? []).length,
    line_count_approved: (approved.line_items ?? []).length,
    fields_overridden: overridden,
    override_count: overridden.length,
    // Untouched means the owner trusted it as-is. Tracked weekly, the rise of this
    // number is calibration — and it is the chart that answers the research question.
    approved_untouched: overridden.length === 0,
    invented_code_count: before.invented_code_count,
  },
}];
'''.strip()}, (1760, -140))

    measure = wf.node("Record review outcome", SHEETS, sheets_append(
        SHEET_ID, "quote_reviews",
        ["job_id", "prompt_version", "model", "review_opened_at", "review_approved_at",
         "review_duration_seconds", "drafted_total_chf", "approved_total_chf", "delta_chf",
         "override_count", "approved_untouched", "invented_code_count"],
    ), (1980, -140))

    wf.sticky(
        "## What comes out of this table\n\n"
        "The `quote_reviews` tab is your results chapter.\n\n"
        "**Plot override rate by field, by week.** If the owner stops correcting material "
        "quantities by week 3 but never stops correcting labour hours, you have located the "
        "automation boundary empirically rather than argued for it.\n\n"
        "Also watch `delta_chf`. If drafts are consistently under-priced, the business loses "
        "money every time review is rushed — which is an argument for keeping the gate that "
        "does not depend on anyone's opinion about AI.",
        (1920, 100), 440, 300, C_MEASURE)

    wf.wire(trg, rate)
    wf.wire(trg, hist)
    wf.wire(rate, ctx)
    wf.wire(hist, ctx)
    wf.wire(ctx, chain)
    wf.wire(chain, check)
    wf.wire(check, store)
    wf.wire(check, prep)
    wf.wire(prep, notify)
    wf.wire(notify, gate)
    wf.wire(gate, diff)
    wf.wire(diff, measure)

    return wf.dump("03-quote-drafting.json", pack)


# =====================================================================
# W2 — Site-visit scheduling
# =====================================================================
def build_w2(pack):
    wf = WF("W2 · <<VISIT_CAP>> booking — <<LABEL>>",
            "Qualified work gets slots clustered by locality, so travel stops being invisible.")

    wf.sticky(
        "## W2 — <<VISIT_CAP>> booking · <<LABEL>>\n\n"
        "**Boundary: automated proposal, human confirm above <<CUR>> <<THRESHOLD>>.**\n"
        "<<THRESHOLD_NOTE>> Scored 3/2/4.\n\n"
        "### The measurable thing here is travel\n"
        "Clustering by locality is the whole point. Travel minutes per <<UNIT>>, before "
        "and after, is unambiguous and it converts directly to money — the easiest result "
        "in the whole project to defend.\n\n"
        "Record the unclustered estimate too, or you have nothing to compare against. "
        "The **Cluster by locality** node writes both.",
        (-820, -360), 480, 380, C_INTRO)

    trg = wf.node("Every weekday 07:00", SCHEDULE, {
        "rule": {"interval": [{"field": "cronExpression", "expression": "0 7 * * 1-5"}]}
    }, (-280, -120))

    fetch = wf.node("Get work awaiting <<VISIT>>", SHEETS, {
        "documentId": {"__rl": True, "mode": "id", "value": SHEET_ID},
        "sheetName": {"__rl": True, "mode": "name", "value": "jobs"},
        "filtersUI": {"values": [{"lookupColumn": "state", "lookupValue": "qualified"}]},
        "combineFilters": "AND",
        "options": {},
    }, (-60, -120))

    cluster = wf.node("Cluster by locality", CODE, {"jsCode": '''
// Group the week's visits by locality so one trip covers several jobs.
//
// The travel model is a flat per-locality estimate, not a routing API. That is a
// deliberate limitation: a real distance matrix would give better numbers but the
// comparison here is between clustered and unclustered under the SAME model, so the
// saving is valid even though the absolute minutes are approximate. Say exactly this
// in your limitations section — it is a defensible simplification, not a shortcut.
const DEPOT = 'St. Gallen';
const MINUTES_FROM_DEPOT = {
  'St. Gallen': 8, 'Wittenbach': 12, 'Abtwil': 14, 'Gossau': 18,
  'Herisau': 22, 'Waldkirch': 20, 'Rorschach': 24,
};
const DEFAULT_MINUTES = 30;

const jobs = items.map(i => i.json).filter(j => j.job_id);
const HIGH_VALUE = <<THRESHOLD>>;

const byLocality = {};
for (const j of jobs) {
  const loc = j.locality || 'unknown';
  (byLocality[loc] ??= []).push(j);
}

const out = [];
let slotDay = 1;

for (const [loc, group] of Object.entries(byLocality)) {
  const legMinutes = MINUTES_FROM_DEPOT[loc] ?? DEFAULT_MINUTES;

  // Unclustered: every job is its own return trip from the depot.
  const unclustered = legMinutes * 2 * group.length;
  // Clustered: one trip out, one back, short hops between jobs in the same locality.
  const clustered = legMinutes * 2 + Math.max(0, group.length - 1) * 6;

  group.forEach((j, idx) => {
    const d = new Date();
    d.setDate(d.getDate() + slotDay);
    d.setHours(8 + idx * 2, 0, 0, 0);

    out.push({
      json: {
        job_id: j.job_id,
        customer_name: j.customer_name,
        email: j.email,
        locality: loc,
        cluster_size: group.length,
        clustered_with: group.filter(g => g.job_id !== j.job_id).map(g => g.job_id).join(' '),
        proposed_slot: d.toISOString(),
        travel_minutes_unclustered: Math.round(unclustered / group.length),
        travel_minutes_clustered: Math.round(clustered / group.length),
        travel_minutes_saved: Math.round((unclustered - clustered) / group.length),
        estimated_value_chf: Number(j.estimated_value_chf ?? 0),
        needs_owner_confirmation: Number(j.estimated_value_chf ?? 0) >= HIGH_VALUE,
      },
    });
  });
  slotDay++;
}

return out;
'''.strip()}, (180, -120))

    gate = wf.node("High value?", IF,
                   if_params("={{ $json.needs_owner_confirmation }}", op_true()), (420, -120))

    ask = wf.node("Ask owner to confirm", EMAIL, {
        "operation": "send", "fromEmail": "workflow@example.ch", "toEmail": "owner@example.ch",
        "subject": "=Confirm <<VISIT>> — {{ $json.job_id }} — est. <<CUR>> {{ $json.estimated_value_chf }}",
        "emailFormat": "html",
        "html": "=<p>Proposed: <strong>{{ $json.proposed_slot }}</strong> for "
                "{{ $json.customer_name }} in {{ $json.locality }}.</p>"
                "<p>Clustered with: {{ $json.clustered_with || 'nothing — single trip' }}</p>"
                "<p>Above the <<CUR>> <<THRESHOLD>> threshold, so this one is yours to confirm.</p>",
        "options": {},
    }, (660, -280))

    offer = wf.node("Offer slot to customer", EMAIL, {
        "operation": "send", "fromEmail": "workflow@example.ch", "toEmail": "={{ $json.email }}",
        "subject": "A time for your <<VISIT>>",
        "emailFormat": "html",
        "html": "=<p>Hallo {{ $json.customer_name }},</p>"
                "<p>We can do <strong>{{ $json.proposed_slot }}</strong>. "
                "Reply to this email if that does not suit and we will find another time.</p>",
        "options": {},
    }, (660, 40))

    rec = wf.node("Record travel figures", SHEETS, sheets_append(
        SHEET_ID, "scheduling",
        ["job_id", "locality", "cluster_size", "clustered_with", "proposed_slot",
         "travel_minutes_unclustered", "travel_minutes_clustered", "travel_minutes_saved",
         "needs_owner_confirmation"],
    ), (900, -120))

    wf.wire(trg, fetch)
    wf.wire(fetch, cluster)
    wf.wire(cluster, gate)
    wf.wire(gate, ask, out=0)
    wf.wire(gate, offer, out=1)
    wf.wire(ask, rec)
    wf.wire(offer, rec)
    return wf.dump("02-booking.json", pack)


# =====================================================================
# W4 — Quote follow-up
# =====================================================================
def build_w4(pack):
    wf = WF("W4 · Follow-up — <<LABEL>>",
            "Three nudges, then stop. Never talks over a live conversation.")

    wf.sticky(
        "## W4 — Follow-up · <<LABEL>>\n\n"
        "**Boundary: automated, with a hard stop the moment a human replies.**\n"
        "Low consequence per message, but the failure mode is reputational and compounding, "
        "so the stop condition is absolute rather than probabilistic. Scored 2/3/5.\n\n"
        "### Three touches. Ever.\n"
        "Day 3, day 7, day 14, then it escalates to the owner and the sequence ends. "
        "A fourth automated message is not follow-up, it is harassment — and in a town this "
        "size the business cannot afford it.\n\n"
        "### Confound warning\n"
        "Win rate will move and you will want to claim it. Don't. At n≈25 you cannot "
        "separate the sequence from market conditions. Report **touches delivered vs "
        "intended** — that one is clean, and it is the thing the automation actually changed.",
        (-840, -380), 500, 440, C_INTRO)

    trg = wf.node("Daily 08:00", SCHEDULE, {
        "rule": {"interval": [{"field": "cronExpression", "expression": "0 8 * * *"}]}
    }, (-300, -100))

    fetch = wf.node("Get open <<QUOTE>>s", SHEETS, {
        "documentId": {"__rl": True, "mode": "id", "value": SHEET_ID},
        "sheetName": {"__rl": True, "mode": "name", "value": "quotes_sent"},
        "filtersUI": {"values": [{"lookupColumn": "decision", "lookupValue": ""}]},
        "combineFilters": "AND",
        "options": {},
    }, (-80, -100))

    due = wf.node("Which touch is due", CODE, {"jsCode": '''
const SCHEDULE_DAYS = { 1: 3, 2: 7, 3: 14 };
const MAX_TOUCHES = 3;
const now = Date.now();
const out = [];

for (const item of items) {
  const q = item.json;
  if (!q.job_id || !q.sent_at) continue;

  const daysSince = Math.floor((now - new Date(q.sent_at).getTime()) / 86400000);
  const sent = Number(q.touches_sent ?? 0);
  const next = sent + 1;

  // The absolute stop. Checked before anything else, and again in the IF node after
  // this one, because a duplicated guard is cheap and a message sent over the top of a
  // live conversation is not recoverable.
  const humanReplied = String(q.inbound_since_sent ?? '').trim().length > 0;

  if (humanReplied) {
    out.push({ json: { ...q, send: false, stopped_reason: 'human_reply', touch_number: next } });
    continue;
  }
  if (next > MAX_TOUCHES) {
    out.push({ json: { ...q, send: false, stopped_reason: 'escalated', touch_number: next } });
    continue;
  }
  if (daysSince < SCHEDULE_DAYS[next]) continue;  // not due yet, say nothing

  out.push({
    json: {
      ...q, send: true, touch_number: next, days_since_sent: daysSince,
      stance: next === 1 ? 'assume it was missed, no ask beyond did this arrive'
            : next === 2 ? 'offer to answer questions or adjust scope, name the total'
            : 'close it out, ask for a yes or a no, say the quote expires, thank them either way',
    },
  });
}
return out;
'''.strip()}, (160, -100))

    guard = wf.node("Safe to send?", IF,
                    if_params("={{ $json.send }}", op_true()), (400, -100))

    compose = wf.node("Compose the nudge", LLM_CHAIN, {
        "promptType": "define",
        "text": "=Write follow-up touch {{ $json.touch_number }}.\n\n"
                "Language: {{ $json.language }}\nCustomer: {{ $json.customer_name }}\n"
                "Job: {{ $json.described_scope }}\n<<QUOTE_CAP>> total: <<CUR>> {{ $json.total_chf }}\n"
                "Sent: {{ $json.sent_at }} ({{ $json.days_since_sent }} days ago)\n"
                "Stance for this touch: {{ $json.stance }}",
        "messages": {"messageValues": [{"message": (
            "You write short follow-up messages chasing an unanswered <<QUOTE>> for <<BUSINESS>> "
            "in <<REGION>>.\n\n"
            "Write in the customer's language. German uses Sie.\n\n"
            "No pressure tactics: no fake scarcity, no invented deadlines, no last chance. "
            "A small contractor's reputation in a town this size is the entire business.\n\n"
            "Make declining easy and explicit — every message offers a one-line way out. "
            "The goal is a decision, not a yes.\n\n"
            "Under 80 words. Plain text, no markdown. No subject line for touches 2 and 3; "
            "they thread onto the original."
        )}]},
        "batching": {},
    }, (640, -220))

    model = anthropic_node(wf, "Claude — follow-up", (620, 40), temperature=0.3, max_tokens=512)
    wf.ai(model, compose, "ai_languageModel")

    send = wf.node("Send follow-up", EMAIL, {
        "operation": "send", "fromEmail": "workflow@example.ch",
        "toEmail": "={{ $('Which touch is due').item.json.email }}",
        "subject": "=Re: your <<QUOTE>> — {{ $('Which touch is due').item.json.job_id }}",
        "emailFormat": "text",
        "text": "={{ $json.text }}",
        "options": {},
    }, (880, -220))

    stop = wf.node("Log the stop", SHEETS, sheets_append(
        SHEET_ID, "followups",
        ["job_id", "touch_number", "sent", "stopped_reason", "at"],
    ), (640, 200))

    logsent = wf.node("Log the touch", SHEETS, sheets_append(
        SHEET_ID, "followups",
        ["job_id", "touch_number", "sent", "stopped_reason", "at"],
    ), (1120, -220))

    wf.wire(trg, fetch)
    wf.wire(fetch, due)
    wf.wire(due, guard)
    wf.wire(guard, compose, out=0)
    wf.wire(guard, stop, out=1)
    wf.wire(compose, send)
    wf.wire(send, logsent)
    return wf.dump("04-follow-up.json", pack)


# =====================================================================
# W5 — Completion to cash
# =====================================================================
def build_w5(pack):
    wf = WF("W5 · Completion to cash — <<LABEL>>",
            "Invoice issues itself only when it matches what was agreed.")

    wf.sticky(
        "## W5 — Completion to cash · <<LABEL>>\n\n"
        "**Boundary: automatic issue only when the invoice matches the approved quote "
        "exactly. Any variation goes to a human.**\n"
        "The test is not size, it is whether the amount differs from what was agreed. "
        "Scored 3/4/4.\n\n"
        "### Two lags, both worth measuring\n"
        "`completion → invoice` is the one automation moves, often dramatically — the "
        "person who finishes the job is not the person who invoices, and that handover is "
        "where days disappear.\n\n"
        "`invoice → paid` mostly is not yours to move. Report both and be honest about "
        "which one you affected.\n\n"
        "If roughly a quarter of your work carries a variation, the gate fires on one in four "
        "— and that rate is the number that tells you whether this workflow is worth its "
        "complexity.",
        (-860, -400), 500, 460, C_INTRO)

    trg = wf.node("<<JOB_CAP>> marked complete", WEBHOOK, {
        "path": "job-complete", "httpMethod": "POST",
        "responseMode": "lastNode", "options": {},
    }, (-320, -100), webhookId=nid())

    approved = wf.node("Load approved <<QUOTE>>", SHEETS, {
        "documentId": {"__rl": True, "mode": "id", "value": SHEET_ID},
        "sheetName": {"__rl": True, "mode": "name", "value": "quote_reviews"},
        "options": {},
    }, (-100, -100))

    compare = wf.node("Compare to what was agreed", CODE, {"jsCode": '''
const body = $('<<JOB_CAP>> marked complete').first().json.body ?? $('<<JOB_CAP>> marked complete').first().json;
const rows = $('Load approved <<QUOTE>>').all().map(i => i.json);
const quote = rows.find(r => r.job_id === body.job_id);

const variations = Array.isArray(body.variations) ? body.variations : [];
const variationTotal = variations.reduce((s, v) => s + Number(v.amount_chf ?? 0), 0);

const agreed = Number(quote?.approved_total_chf ?? 0);
const invoiceTotal = Number((agreed + variationTotal).toFixed(2));

const completedAt = body.completed_at ?? new Date().toISOString();

return [{
  json: {
    job_id: body.job_id,
    completed_at: completedAt,
    agreed_total_chf: agreed,
    variation_total_chf: Number(variationTotal.toFixed(2)),
    invoice_total_chf: invoiceTotal,
    variation_count: variations.length,
    variation_summary: variations.map(v => `${v.description} (CHF ${v.amount_chf})`).join('; '),
    // The single condition. Not job size, not a percentage — any difference at all from
    // what the customer agreed to means a human sends it.
    matches_agreed: variations.length === 0 && Math.abs(invoiceTotal - agreed) < 0.01,
    email: body.email ?? quote?.email ?? null,
    customer_name: body.customer_name ?? null,
  },
}];
'''.strip()}, (140, -100))

    gate = wf.node("Matches what was agreed?", IF,
                   if_params("={{ $json.matches_agreed }}", op_true()), (380, -100))

    issue = wf.node("Issue invoice", EMAIL, {
        "operation": "send", "fromEmail": "workflow@example.ch", "toEmail": "={{ $json.email }}",
        "subject": "=Invoice — {{ $json.job_id }} — <<CUR>> {{ $json.invoice_total_chf }}",
        "emailFormat": "html",
        "html": "=<p>Hallo {{ $json.customer_name }},</p>"
                "<p>The work is complete. Invoice total "
                "<strong><<CUR>> {{ $json.invoice_total_chf }}</strong>, as agreed.</p>"
                "<p>Payable within 30 days.</p>",
        "options": {},
    }, (620, -240))

    review = wf.node("Owner approves variation", EMAIL, {
        "operation": "send", "fromEmail": "workflow@example.ch", "toEmail": "owner@example.ch",
        "subject": "=Variation to approve — {{ $json.job_id }} — "
                   "<<CUR>> {{ $json.variation_total_chf }} over the <<QUOTE>>",
        "emailFormat": "html",
        "html": "=<p><strong>{{ $json.job_id }}</strong> finished at a different number "
                "from the one that was agreed.</p>"
                "<p>Agreed: <<CUR>> {{ $json.agreed_total_chf }}<br>"
                "Variations: <<CUR>> {{ $json.variation_total_chf }}<br>"
                "<strong>Invoice would be: <<CUR>> {{ $json.invoice_total_chf }}</strong></p>"
                "<p>{{ $json.variation_summary }}</p>"
                "<p>Nothing has been sent. Send it yourself once you are happy.</p>",
        "options": {},
    }, (620, 40))

    rec = wf.node("Record cash timings", SHEETS, sheets_append(
        SHEET_ID, "invoices",
        ["job_id", "completed_at", "invoiced_at", "agreed_total_chf", "variation_total_chf",
         "invoice_total_chf", "variation_count", "auto_issued"],
    ), (900, -100))

    stamp = wf.node("Stamp invoice time", CODE, {"jsCode": '''
// completion → invoice is the lag automation actually moves. Capture it at the moment
// the invoice goes, not at the end of the month from memory.
return [{ json: { ...$json, invoiced_at: new Date().toISOString(),
                  auto_issued: $json.matches_agreed === true } }];
'''.strip()}, (760, -100))

    wf.wire(trg, approved)
    wf.wire(approved, compare)
    wf.wire(compare, gate)
    wf.wire(gate, issue, out=0)
    wf.wire(gate, review, out=1)
    wf.wire(issue, stamp)
    wf.wire(review, stamp)
    wf.wire(stamp, rec)
    return wf.dump("05-completion-to-cash.json", pack)


if __name__ == "__main__":
    packs = load_packs()
    total = 0
    for pack in packs:
        made = [fn(pack) for fn in (build_w1, build_w2, build_w3, build_w4, build_w5)]
        total += len(made)
        print(f"{pack['slug']:<10} {pack['label']:<32} {len(made)} workflows")
    print(f"\n{total} workflow files across {len(packs)} industries")
