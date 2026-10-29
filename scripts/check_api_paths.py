#!/usr/bin/env python3
"""Check that every curl example against the Relyt One Open API uses an allowed method, path, query parameter and
JSON body field (scripts/openapi-allowlist.json).

  check_api_paths.py                 check the Markdown files against the allowlist
  check_api_paths.py --spec FILE     also check that every allowlisted call exists in that OpenAPI 3 spec
                                     (same method and path, query parameters and request-body properties)
"""
import json
import os
import re
import subprocess
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = json.load(open(os.path.join(ROOT, "scripts", "openapi-allowlist.json"), encoding="utf-8"))
BASE = ALLOW["base"]
BASE_VAR = "$RELYT_API"


def norm(path):
    """/projects/$PROJECT_ID or /projects/{id} -> /projects/{}"""
    segs = []
    for s in path.strip("/").split("/"):
        segs.append("{}" if s.startswith("$") or (s.startswith("{") and s.endswith("}")) else s)
    return "/" + "/".join(segs)


def allowed():
    out = {}
    for e in ALLOW["endpoints"]:
        out[(e["method"], norm(e["path"]))] = e
    return out


def code_blocks(text):
    blocks, cur = [], None
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            if cur is None:
                cur = []
            else:
                blocks.append("\n".join(cur))
                cur = None
        elif cur is not None:
            cur.append(line)
    return blocks


def commands(block):
    joined = re.sub(r"\\\n\s*", " ", block)
    for line in joined.split("\n"):
        line = line.strip()
        if line.startswith("curl "):
            yield line


def parse(cmd):
    m = re.search(r"-X\s+([A-Z]+)", cmd)
    data = re.search(r"\s(?:-d|--data(?:-raw)?)\s", cmd)
    method = m.group(1) if m else ("POST" if data else "GET")
    um = re.search(r"[\"']?((?:\$RELYT_API|\$\{RELYT_API\}|" + re.escape(BASE) + r")[^\"'\s]*)", cmd)
    if not um:
        return None
    url = um.group(1).replace("${RELYT_API}", BASE).replace(BASE_VAR, BASE)
    u = urllib.parse.urlparse(url)
    path = u.path[len(urllib.parse.urlparse(BASE).path):]
    query = sorted(urllib.parse.parse_qs(u.query, keep_blank_values=True))
    body = []
    if data:
        rest = cmd[data.end():]
        jm = re.match(r"'(\{.*?\})'", rest)
        if jm:
            body = sorted(json.loads(jm.group(1)))
        else:
            q = re.search(r"'\{([^']*)\}'", rest)  # jq -n '{name: ..., orgId: $org}'
            if q:
                body = sorted(set(re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*:", q.group(1))))
            else:
                body = ["<unparsed body>"]
    return method, path, query, body


def check_docs():
    files = subprocess.run(["git", "-C", ROOT, "ls-files", "-co", "--exclude-standard", "*.md"],
                           capture_output=True, text=True).stdout.split()
    table, errors, seen, n = allowed(), [], set(), 0
    for rel in files:
        text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        for block in code_blocks(text):
            for cmd in commands(block):
                if "RELYT_API" not in cmd and BASE not in cmd:
                    continue
                n += 1
                p = parse(cmd)
                if p is None:
                    errors.append(f"{rel}: cannot find the API URL in: {cmd[:120]}")
                    continue
                method, path, query, body = p
                key = (method, norm(path))
                e = table.get(key)
                if e is None:
                    errors.append(f"{rel}: {method} {path} is not an allowed Open API call")
                    continue
                seen.add(key)
                bad_q = set(query) - set(e.get("query", []))
                bad_b = set(body) - set(e.get("body", []))
                if bad_q:
                    errors.append(f"{rel}: {method} {path}: query parameters not allowed: {sorted(bad_q)}")
                if bad_b:
                    errors.append(f"{rel}: {method} {path}: body fields not allowed: {sorted(bad_b)}")
        # API paths mentioned outside curl, e.g. https://relytone.data.cloud/api/v1/foo
        for m in re.finditer(re.escape(BASE) + r"(/[A-Za-z0-9_/{}$.-]+)", text):
            path = m.group(1).rstrip(".")
            if not any(norm(path) == k[1] for k in table):
                errors.append(f"{rel}: mentions unknown Open API path {path}")
    if n == 0:
        errors.append("no curl examples found; the check would pass vacuously")
    unused = sorted(f"{m} {p}" for (m, p) in table if (m, p) not in seen)
    return errors, n, unused


def check_spec(spec_path):
    import yaml

    spec = yaml.safe_load(open(spec_path, encoding="utf-8"))
    errors = []
    servers = [s.get("url") for s in spec.get("servers", [])]
    if BASE not in servers:
        errors.append(f"spec servers {servers} do not include {BASE}")
    paths = {norm(p): (p, item) for p, item in spec.get("paths", {}).items()}
    for e in ALLOW["endpoints"] + ALLOW.get("excluded", []):
        k = norm(e["path"])
        if k not in paths or e["method"].lower() not in paths[k][1]:
            errors.append(f"spec has no {e['method']} {e['path']}")
            continue
        op = paths[k][1][e["method"].lower()]
        params = op.get("parameters", []) + paths[k][1].get("parameters", [])
        spec_q = {p["name"] for p in params if p.get("in") == "query"}
        for q in set(e.get("query", [])) - spec_q:
            errors.append(f"{e['method']} {e['path']}: query parameter {q} not in spec")
        props = (op.get("requestBody", {}).get("content", {}).get("application/json", {})
                 .get("schema", {}).get("properties", {}))
        for b in set(e.get("body", [])) - set(props):
            errors.append(f"{e['method']} {e['path']}: body field {b} not in spec")
        spec_path_params = re.findall(r"\{(\w+)\}", paths[k][0])
        if spec_path_params != re.findall(r"\{(\w+)\}", e["path"]):
            errors.append(f"{e['method']} {e['path']}: path parameters differ from spec {paths[k][0]}")
    spec_ops = {(m.upper(), k) for k, (_, item) in paths.items() for m in item if m in ("get", "post", "put", "patch", "delete")}
    listed = {(e["method"], norm(e["path"])) for e in ALLOW["endpoints"] + ALLOW.get("excluded", [])}
    for m, p in sorted(spec_ops - listed):
        errors.append(f"spec operation {m} {p} is neither allowed nor excluded in the allowlist")
    return errors


def main():
    errors, n, unused = check_docs()
    if "--spec" in sys.argv:
        errors += check_spec(sys.argv[sys.argv.index("--spec") + 1])
    for e in errors:
        print("ERROR", e)
    if unused:
        print("note: allowed calls without an example:", ", ".join(unused))
    print(f"check_api_paths: {n} curl examples, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
