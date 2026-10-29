#!/usr/bin/env python3
"""Hygiene scan for a public repository: no internal host names, private addresses, internal tracker ids,
credentials or non-English text, in the working tree and in the full git history.

Some patterns are assembled from pieces so this file does not match itself."""
import re
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = "".join
PATTERNS = {
    "internal company host": re.compile(J(["z", "byte"]), re.I),
    "private address 10/8": re.compile(r"\b10\.\d+\.\d+\.\d+\b"),
    "cluster-local service": re.compile(J([r"svc\.", r"cluster\.", "local"])),
    "internal git host": re.compile(J(["git", "lab"]), re.I),
    "internal repository": re.compile(J(["relyt-one", "-console"])),
    "internal tracker id": re.compile(r"\b(?:MA|LO|KD)-\d|" + J(["SE", "C-"])),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "AWS access key": re.compile(J(["AK", "IA"]) + r"[0-9A-Z]{16}"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    "npm token": re.compile(r"\bnpm_[A-Za-z0-9]{30,}"),
    "Postgres URL with password": re.compile(r"postgres(?:ql)?://[^:/\s\"'`@]+:(?!<|\$)[^@\s\"'`]+@"),
    "JWT": re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]*"),
    "non-English (CJK) text": re.compile("[\u3000-\u9fff\uff00-\uffef]"),
}


def scan(label, text, hits):
    for i, line in enumerate(text.splitlines(), 1):
        for name, rx in PATTERNS.items():
            if rx.search(line):
                hits.append(f"{label}:{i}: [{name}] {line.strip()[:140]}")


def git(*args):
    return subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True).stdout


def main():
    hits, n = [], 0
    for f in filter(None, git("ls-files", "-co", "--exclude-standard").split("\n")):
        try:
            text = open(os.path.join(ROOT, f), encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        n += 1
        scan(f, text, hits)
    history = git("log", "--all", "-p", "--format=COMMIT %H%n%B")
    hist_hits = []
    scan("history", "\n".join(l for l in history.splitlines() if not l.startswith(("+++", "---"))), hist_hits)
    identities = sorted(set(git("log", "--all", "--format=%an <%ae> | %cn <%ce>").split("\n")) - {""})
    print("commit identities (reported, not counted):", identities)
    print(f"scan: {n} files; working-tree hits: {len(hits)}; history hits: {len(hist_hits)}")
    for h in hits + hist_hits:
        print(h)
    return 1 if hits or hist_hits else 0


if __name__ == "__main__":
    sys.exit(main())
