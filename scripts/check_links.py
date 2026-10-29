#!/usr/bin/env python3
"""Check links in every Markdown file and llms.txt: relative links must resolve to an existing file (and, for
#anchors into Markdown files, to an existing heading); external links must be well-formed https URLs.
Pass --online to also request every external URL (not used in CI, to avoid flaky network failures)."""
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")
AUTOLINK = re.compile(r"<(https?://[^>\s]+)>")
FENCE = re.compile(r"^\s*```")
HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


def files():
    out = subprocess.run(["git", "-C", ROOT, "ls-files", "-co", "--exclude-standard"], capture_output=True, text=True)
    return [f for f in out.stdout.split("\n") if f.endswith(".md") or f == "llms.txt"]


def slug(heading):
    s = heading.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


def anchors(path):
    result, in_fence = set(), False
    for line in open(path, encoding="utf-8"):
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and line.startswith("#"):
            result.add(slug(line.lstrip("#")))
    return result


def links(path):
    in_fence = False
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for m in MD_LINK.finditer(line):
            yield n, m.group(1)
        for m in AUTOLINK.finditer(line):
            yield n, m.group(1)


def main():
    online = "--online" in sys.argv
    errors, external, count = [], set(), 0
    for rel in files():
        path = os.path.join(ROOT, rel)
        for n, target in links(path):
            count += 1
            where = f"{rel}:{n}"
            if re.match(r"^[a-z]+:", target):
                u = urllib.parse.urlparse(target)
                if u.scheme != "https" or not HOST_RE.match(u.hostname or "") or u.username or u.password:
                    errors.append(f"{where}: external link must be a plain https URL: {target}")
                else:
                    external.add(target)
                continue
            file_part, _, frag = target.partition("#")
            dest = os.path.normpath(os.path.join(os.path.dirname(path), file_part)) if file_part else path
            if not dest.startswith(ROOT):
                errors.append(f"{where}: link leaves the repository: {target}")
            elif not os.path.exists(dest):
                errors.append(f"{where}: missing target {target}")
            elif frag and dest.endswith(".md") and frag not in anchors(dest):
                errors.append(f"{where}: no heading #{frag} in {os.path.relpath(dest, ROOT)}")
    if online:
        for url in sorted(external):
            try:
                req = urllib.request.Request(url, method="GET", headers={"user-agent": "link-check"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    status = r.status
            except Exception as e:  # noqa: BLE001
                status = getattr(e, "code", str(e))
            print(f"{status} {url}")
    for e in errors:
        print("ERROR", e)
    print(f"check_links: {count} links ({len(external)} distinct external), {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
