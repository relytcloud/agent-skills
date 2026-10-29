#!/usr/bin/env python3
"""Validate every skills/<name>/SKILL.md against the Agent Skills spec (https://agentskills.io/specification)
and the plugin manifests in .claude-plugin/. Exit 1 on any error."""
import json
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")  # 1-64 chars, lowercase, digits, single hyphens
ALLOWED_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
MAX_BODY_LINES = 500

errors = []


def err(where, msg):
    errors.append(f"{where}: {msg}")


def check_skill(dirname):
    path = os.path.join(ROOT, "skills", dirname, "SKILL.md")
    where = os.path.relpath(path, ROOT)
    if not os.path.isfile(path):
        err(where, "missing SKILL.md")
        return None
    text = open(path, encoding="utf-8").read()
    lines = text.split("\n")
    if lines[0] != "---":
        err(where, "frontmatter must start on the first line with ---")
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        err(where, "frontmatter is not closed with ---")
        return None
    try:
        fm = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as e:
        err(where, f"invalid YAML: {e}")
        return None
    if not isinstance(fm, dict):
        err(where, "frontmatter must be a mapping")
        return None
    extra = set(fm) - ALLOWED_KEYS
    if extra:
        err(where, f"keys outside the Agent Skills spec: {sorted(extra)}")
    name = fm.get("name")
    if not isinstance(name, str) or not 1 <= len(name) <= 64 or not NAME_RE.match(name):
        err(where, f"invalid name {name!r} (1-64 chars, a-z 0-9 and single hyphens, no leading/trailing hyphen)")
    elif name != dirname:
        err(where, f"name {name!r} must match the directory name {dirname!r}")
    desc = fm.get("description")
    if not isinstance(desc, str) or not 1 <= len(desc.strip()) <= 1024:
        err(where, "description must be a non-empty string of at most 1024 characters")
    comp = fm.get("compatibility")
    if comp is not None and (not isinstance(comp, str) or not 1 <= len(comp) <= 500):
        err(where, "compatibility must be 1-500 characters")
    meta = fm.get("metadata")
    if meta is not None and (
        not isinstance(meta, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in meta.items())
    ):
        err(where, "metadata must map strings to strings (quote numbers such as version)")
    body_lines = len(lines) - end - 1
    if body_lines > MAX_BODY_LINES:
        err(where, f"body has {body_lines} lines; keep SKILL.md under {MAX_BODY_LINES}")
    return name


def check_manifests():
    mp_path = os.path.join(ROOT, ".claude-plugin", "marketplace.json")
    pj_path = os.path.join(ROOT, ".claude-plugin", "plugin.json")
    try:
        mp = json.load(open(mp_path, encoding="utf-8"))
        pj = json.load(open(pj_path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        err(".claude-plugin", f"cannot read manifests: {e}")
        return
    for key in ("name", "owner", "plugins"):
        if key not in mp:
            err("marketplace.json", f"missing {key}")
    if mp.get("name") == "agent-skills":
        err("marketplace.json", "agent-skills is a reserved marketplace name")
    entries = {p.get("name"): p for p in mp.get("plugins", [])}
    if pj.get("name") not in entries:
        err("marketplace.json", f"no entry named like plugin.json name {pj.get('name')!r}")
    for p in entries.values():
        src = p.get("source")
        if isinstance(src, str) and (not src.startswith("./") or ".." in src):
            err("marketplace.json", f"relative source must start with ./ and not contain ..: {src!r}")


def main():
    skills_dir = os.path.join(ROOT, "skills")
    names = sorted(d for d in os.listdir(skills_dir) if os.path.isdir(os.path.join(skills_dir, d)))
    if not names:
        err("skills", "no skills found")
    for d in names:
        check_skill(d)
    check_manifests()
    for e in errors:
        print("ERROR", e)
    print(f"check_skills: {len(names)} skills, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
