#!/usr/bin/env python3
"""
Validate hand-authored n8n workflow JSON before importing it.

Checks the failure modes that make an import fail loudly, and — more importantly —
the ones that make it fail SILENTLY: duplicate node names collapse their connections,
dangling connection targets are dropped without warning, malformed connection entries
vanish, and a bad position stacks every node at the origin.

Rules derived from n8n's import path (importWorkflowData / sanitizeConnections /
addImportedNodesToWorkflow). See docs/n8n-json-reference.md for sources.

Usage:  python3 scripts/validate-workflows.py workflows/*.json
Exit:   0 all clean, 1 any error. Warnings alone do not fail.
"""
import json
import sys
from pathlib import Path

# typeVersions this kit is pinned to. Deliberately one minor below the newest in
# several cases: a typeVersion the target n8n does not know throws
# NodeVersionNotFoundError, and a student on an older install is the common case.
PINNED = {
    "n8n-nodes-base.webhook": 2,
    "n8n-nodes-base.scheduleTrigger": 1.2,
    "n8n-nodes-base.set": 3.4,
    "n8n-nodes-base.if": 2.2,
    "n8n-nodes-base.switch": 3.2,
    "n8n-nodes-base.code": 2,
    "n8n-nodes-base.merge": 3.2,
    "n8n-nodes-base.wait": 1.1,
    "n8n-nodes-base.httpRequest": 4.2,
    "n8n-nodes-base.respondToWebhook": 1.4,
    "n8n-nodes-base.stickyNote": 1,
    "n8n-nodes-base.noOp": 1,
    "n8n-nodes-base.formTrigger": 2.2,
    "n8n-nodes-base.googleSheets": 4.5,
    "n8n-nodes-base.emailSend": 2.1,
    "@n8n/n8n-nodes-langchain.informationExtractor": 1.2,
    "@n8n/n8n-nodes-langchain.chainLlm": 1.7,
    "@n8n/n8n-nodes-langchain.lmChatAnthropic": 1.3,
    "@n8n/n8n-nodes-langchain.outputParserStructured": 1.2,
}

# Cluster sub-nodes connect UP into their root node, on a non-main connection type.
# A sub-node with no such connection is inert: the root silently runs without it.
SUBNODE_OUTPUT = {
    "@n8n/n8n-nodes-langchain.lmChatAnthropic": "ai_languageModel",
    "@n8n/n8n-nodes-langchain.outputParserStructured": "ai_outputParser",
}
VALID_AI_TYPES = {
    "ai_agent", "ai_chain", "ai_document", "ai_embedding", "ai_languageModel",
    "ai_memory", "ai_outputParser", "ai_retriever", "ai_reranker",
    "ai_textSplitter", "ai_tool", "ai_vectorStore",
}

# IF/Switch carry a filter-version inside conditions.options.version that is tied to
# the node's typeVersion. A mismatch does not error — it changes operator semantics.
FILTER_VERSION_FOR_IF = {2.0: 1, 2.1: 1, 2.2: 2, 2.3: 3}


class Report:
    def __init__(self, path):
        self.path = path
        self.errors = []
        self.warnings = []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)


def check_conditions_version(node, rep):
    """IF and Switch embed a filter version that must track typeVersion."""
    t, tv = node.get("type"), node.get("typeVersion")
    params = node.get("parameters", {})
    name = node.get("name", "?")

    blocks = []
    if t == "n8n-nodes-base.if":
        blocks = [params.get("conditions", {})]
    elif t == "n8n-nodes-base.switch":
        blocks = [r.get("conditions", {}) for r in params.get("rules", {}).get("values", [])]

    for blk in blocks:
        if not blk:
            continue
        got = blk.get("options", {}).get("version")
        if got is None:
            rep.warn(f"{name}: conditions.options.version not set — n8n will guess")
            continue
        if t == "n8n-nodes-base.if":
            want = FILTER_VERSION_FOR_IF.get(tv)
            if want and got != want:
                rep.error(
                    f"{name}: typeVersion {tv} expects conditions.options.version "
                    f"{want}, found {got} — operator semantics will differ silently"
                )
        for cond in blk.get("conditions", []):
            for k in ("id", "operator", "leftValue"):
                if k not in cond:
                    rep.error(f"{name}: condition missing '{k}'")


def validate(path):
    rep = Report(path)
    try:
        data = json.loads(Path(path).read_text())
    except json.JSONDecodeError as e:
        rep.error(f"invalid JSON: {e}")
        return rep

    # --- envelope -------------------------------------------------------
    for key in ("nodes", "connections"):
        if key not in data:
            rep.error(f"missing required top-level key '{key}' — import aborts entirely")
    if rep.errors:
        return rep

    nodes = data["nodes"]
    conns = data["connections"]
    if not isinstance(nodes, list):
        rep.error("'nodes' must be an array")
        return rep
    if not isinstance(conns, dict):
        rep.error("'connections' must be an object")
        return rep

    if data.get("settings", {}).get("executionOrder") != "v1":
        rep.warn("settings.executionOrder is not 'v1' — set it explicitly")

    # --- nodes ----------------------------------------------------------
    names, seen = [], set()
    for i, n in enumerate(nodes):
        label = n.get("name", f"<node {i}>")

        if "type" not in n:
            rep.error(f"{label}: no 'type' — node is dropped on import")
            continue
        if "name" not in n:
            rep.error(f"node {i} ({n['type']}): no 'name' — connections cannot reference it")
            continue

        if n["name"] in seen:
            rep.error(
                f"duplicate node name '{n['name']}' — connections referencing it "
                f"collapse onto one node, silently"
            )
        seen.add(n["name"])
        names.append(n["name"])

        if "typeVersion" not in n:
            rep.error(f"{label}: no 'typeVersion'")
        else:
            pin = PINNED.get(n["type"])
            if pin is not None and n["typeVersion"] != pin:
                rep.warn(
                    f"{label}: typeVersion {n['typeVersion']} differs from this kit's "
                    f"pin of {pin} for {n['type']}"
                )

        pos = n.get("position")
        if not (isinstance(pos, list) and len(pos) >= 2
                and all(isinstance(v, (int, float)) and v == v for v in pos[:2])):
            rep.error(f"{label}: bad 'position' {pos!r} — node will stack at [0,0]")

        if "parameters" not in n:
            rep.warn(f"{label}: no 'parameters' key (use {{}} if none)")

        if "credentials" in n:
            rep.error(
                f"{label}: contains a 'credentials' block — strip it. Credential ids are "
                f"instance-specific and exported JSON can leak credential names"
            )

        if n["type"] == "n8n-nodes-base.stickyNote":
            p = n.get("parameters", {})
            for k in ("width", "height", "color"):
                if k not in p:
                    rep.error(f"{label}: sticky note missing required parameter '{k}'")
            c = p.get("color")
            if isinstance(c, int) and not 1 <= c <= 7:
                rep.error(f"{label}: sticky colour {c} out of range 1-7")

        if n["type"] == "n8n-nodes-base.webhook":
            p = n.get("parameters", {})
            if p.get("path") and p["path"] == n.get("webhookId"):
                rep.error(f"{label}: parameters.path equals webhookId — importer overwrites path")
            if not p.get("path"):
                rep.error(f"{label}: webhook has no 'path'")

        if n["type"] == "n8n-nodes-base.set" and n.get("typeVersion", 0) >= 3.3:
            if "fields" in n.get("parameters", {}):
                rep.error(f"{label}: Set >=3.3 uses 'assignments', not 'fields' — this sets nothing")

        check_conditions_version(n, rep)

    nameset = set(names)

    # --- connections ----------------------------------------------------
    wired = set()
    for src, bytype in conns.items():
        if src not in nameset:
            rep.error(f"connections: source '{src}' is not a node — whole entry dropped silently")
            continue
        if not isinstance(bytype, dict):
            rep.error(f"connections['{src}'] must be an object keyed by connection type")
            continue
        for ctype, outputs in bytype.items():
            if not isinstance(outputs, list):
                rep.error(f"connections['{src}']['{ctype}'] must be an array of outputs")
                continue
            for oi, output in enumerate(outputs):
                if output is None:
                    continue
                if not isinstance(output, list):
                    rep.error(f"connections['{src}']['{ctype}'][{oi}] must be an array or null")
                    continue
                for entry in output:
                    if not isinstance(entry, dict):
                        rep.error(f"connections['{src}'] output {oi}: entry is not an object")
                        continue
                    if not isinstance(entry.get("node"), str):
                        rep.error(f"connections['{src}'] output {oi}: 'node' missing or not a string")
                        continue
                    if not isinstance(entry.get("type"), str):
                        rep.error(f"connections['{src}']->{entry['node']}: 'type' missing/not a string — entry dropped")
                    if not isinstance(entry.get("index"), int) or isinstance(entry.get("index"), bool):
                        rep.error(
                            f"connections['{src}']->{entry['node']}: 'index' must be a number, "
                            f"found {entry.get('index')!r} — entry dropped silently"
                        )
                    if entry["node"] not in nameset:
                        rep.error(
                            f"connections['{src}'] output {oi}: target '{entry['node']}' "
                            f"is not a node — wire dropped silently"
                        )
                    else:
                        wired.add(entry["node"])
                        wired.add(src)

    # --- AI cluster wiring ----------------------------------------------
    for ctype in {c for by in conns.values() for c in by}:
        if ctype != "main" and ctype not in VALID_AI_TYPES:
            rep.error(f"unknown connection type '{ctype}' — check camelCase; it will be dropped")

    for n in nodes:
        want = SUBNODE_OUTPUT.get(n.get("type"))
        if not want:
            continue
        got = conns.get(n.get("name"), {})
        if want not in got or not any(got[want]):
            rep.error(
                f"{n.get('name')}: sub-node has no '{want}' connection to a root node — "
                f"it will sit on the canvas doing nothing"
            )

    for n in nodes:
        if n.get("type") in ("@n8n/n8n-nodes-langchain.chainLlm", "@n8n/n8n-nodes-langchain.agent"):
            has_parser = any(
                "ai_outputParser" in by and any(
                    e["node"] == n["name"] for out in by["ai_outputParser"] for e in (out or [])
                )
                for by in conns.values()
            )
            if has_parser and not n.get("parameters", {}).get("hasOutputParser"):
                rep.error(
                    f"{n['name']}: an output parser is wired in but hasOutputParser is not true "
                    f"— the input socket never exists and the parser is ignored"
                )

    # --- reachability ---------------------------------------------------
    TRIGGERS = ("trigger", "webhook", "formTrigger", "executeWorkflowTrigger")
    for n in nodes:
        t = n.get("type", "")
        if t == "n8n-nodes-base.stickyNote":
            continue
        if n.get("type") in SUBNODE_OUTPUT:
            continue
        if n.get("name") not in wired and len(nodes) > 1:
            if not any(k.lower() in t.lower() for k in TRIGGERS):
                rep.warn(f"{n.get('name')}: not referenced by any connection — orphaned on the canvas")

    return rep


def main(argv):
    paths = argv[1:]
    if not paths:
        print("usage: validate-workflows.py <file.json> [...]")
        return 2

    total_e = total_w = 0
    for p in paths:
        rep = validate(p)
        total_e += len(rep.errors)
        total_w += len(rep.warnings)
        status = "FAIL" if rep.errors else ("warn" if rep.warnings else "ok")
        print(f"\n{status:>4}  {p}")
        for e in rep.errors:
            print(f"      ERROR  {e}")
        for w in rep.warnings:
            print(f"      warn   {w}")

    print(f"\n{len(paths)} file(s), {total_e} error(s), {total_w} warning(s)")
    return 1 if total_e else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
