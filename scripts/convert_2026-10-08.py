#!/usr/bin/env python3
"""Convert the published 2026-10-08 edition into the durable markdown source.

Design: the markdown carries the RENDERED TEXT of every badge verbatim
("Impact: Elevated", "Tier 1/4 — Primary (vendor, partly corroborated)").
Presentation — which colour class a value gets — is the generator's job, so
re-styling never touches the content. Faithful by construction: parsed from the
published page, never retyped.
"""
import os, re, html, collections

SRC = os.path.expanduser("~/Desktop/AI Site/docs/daily/2026-10-08.html")
OUT = os.path.expanduser("~/Desktop/AI Site/editions/2026-10-08.md")
s = open(SRC, encoding="utf-8").read()
body = re.sub(r"<(script|style).*?</\1>", "", s, flags=re.S)


def text(x):
    """Inner text: keep emphasis as markdown, strip tags, collapse whitespace."""
    x = re.sub(r"<(strong|b)>(.*?)</\1>", r"**\2**", x, flags=re.S)
    x = re.sub(r"<(em|i)>(.*?)</\1>", r"*\2*", x, flags=re.S)
    x = re.sub(r"<[^>]+>", "", x)
    return re.sub(r"\s+", " ", html.unescape(x)).strip()


# ── executive summary ──────────────────────────────────────────────────────
exec_md = []
ex = re.search(r'<section id="exec".*?</section>', body, re.S)
if ex:
    for m in re.finditer(r"(?s)<p>(.*?)</p>|<div class=\"au-context-box\">(.*?)</div>", ex.group(0)):
        if m.group(1) and len(m.group(1).strip()) > 40:
            exec_md.append(("p", text(m.group(1))))
        elif m.group(2):
            exec_md.append(("au", text(m.group(2))))

# ── themes + stories ───────────────────────────────────────────────────────
CARD = re.compile(r'<div class="story-card num-(\d+)" id="story-\d+">(.*?)'
                  r'(?=<div class="story-card|<div class="story-grid"|</section>)', re.S)
# reliability / verification contain a nested <span> (the dot), so allow one level
BADGE = re.compile(r'<span class="(axis [a-z]-[a-z]+|reliability|verification v-[a-z]+)">'
                   r'((?:[^<]|<span[^>]*>[^<]*</span>)*?)</span>', re.S)

sections = []
for ch in re.split(r"(?=<section[^>]*>\s*<h2)", body):
    h2 = re.search(r"<h2[^>]*>(.*?)</h2>", ch, re.S)
    if not h2:
        continue
    lab = re.sub(r'<span class="[^"]*">.*?</span>', "", h2.group(1), flags=re.S)
    lab = re.sub(r"\s+\d+\s+stor(y|ies)\s*$", "", text(lab)).strip()
    if lab.lower().startswith(("executive", "analytics", "key to")):
        continue
    cards = []
    for m in CARD.finditer(ch):
        c = m.group(2)
        head = re.search(r"<h3>(.*?)</h3>", c, re.S)
        summ = re.search(r'<p class="summary">(.*?)</p>', c, re.S)
        src = re.search(r'<a class="source" href="([^"]+)"[^>]*>(.*?)</a>', c, re.S)
        f = [("Summary", text(summ.group(1)) if summ else "")]
        if src:
            f.append(("Source", f"[{text(src.group(2))}]({src.group(1)})"))
        for cls, txt in BADGE.findall(c):
            t = text(txt)
            if not t:
                continue
            if cls.startswith("verification"):
                f.append(("Verification", t))
            elif cls == "reliability":
                t = re.sub(r"^[^\w]*\s*", "", t)            # drop the leading dot glyph
                f.append(("Reliability", t))
            elif ":" in t:                                   # "Impact: Elevated"
                k, v = t.split(":", 1)
                f.append((k.strip(), v.strip()))
        if "crossref" in c or "shared" in c:
            f.append(("Shared", "Cyber Digest"))
        d = re.search(r'<span class="date">([\d-]+)</span>', c)
        if d:
            f.append(("Date", d.group(1)))
        cards.append((text(head.group(1)) if head else "", f))
    if cards:
        sections.append((lab, cards))

# ── emit ───────────────────────────────────────────────────────────────────
L = ["---", "date: 2026-10-08", "window_start: 2026-10-06", "window_end: 2026-10-08",
     "kicker: 48-hour window &middot; 6&ndash;8 October 2026", "---", "", "# Executive Summary", ""]
for kind, txt in exec_md:
    L += [f":::au\n{txt}\n:::" if kind == "au" else txt, ""]
for label, cards in sections:
    L += [f"## {label}", ""]
    for i, (head, fields) in enumerate(cards, 1):
        L += [f"### {i}. {head}", ""]
        for k, v in fields:
            L.append(f"- **{k}:** {v}")
        L.append("")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8").write("\n".join(L).rstrip() + "\n")
cnt = collections.Counter()
for _, cards in sections:
    for _, f in cards:
        for k, _ in f:
            cnt[k] += 1
print(f"wrote {OUT}  ({os.path.getsize(OUT):,} bytes)")
print(f"themes {len(sections)}  stories {sum(len(c) for _, c in sections)}")
print("fields:", dict(cnt))
for label, cards in sections:
    print(f"  {len(cards):>2}  {label}")
print()
print("sample reliability values:")
seen = set()
for _, cards in sections:
    for _, f in cards:
        for k, v in f:
            if k == "Reliability" and v not in seen:
                seen.add(v)
                print("   ", v)
