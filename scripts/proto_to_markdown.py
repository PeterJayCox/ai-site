#!/usr/bin/env python3
"""One-off: convert the approved prototype edition (HTML parts) into the daily
edition's durable markdown source. Faithful by construction — parsed, not retyped."""
import os, re, html, sys

PARTS = os.path.expanduser("~/Desktop/Hermes/AI Daily/prototype/parts")
OUT = os.path.expanduser("~/Desktop/AI Site/editions/2026-10-06.md")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

def rd(p):
    return open(os.path.join(PARTS, p), encoding="utf-8").read()

def inline(s):
    """HTML inline markup -> markdown. Keeps emphasis, drops the rest."""
    s = re.sub(r"<(strong|b)>(.*?)</\1>", r"**\2**", s, flags=re.S)
    s = re.sub(r"<(em|i)>(.*?)</\1>", r"*\2*", s, flags=re.S)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()

# ── executive summary ──────────────────────────────────────────────────────
ex = rd("exec.html")
body = ex[ex.find("</h2>") + 5:]
exec_md = []
for m in re.finditer(r"(?s)<p>(.*?)</p>|<div class=\"au-context-box\">(.*?)</div>", body):
    if m.group(1):
        exec_md.append(inline(m.group(1)))
    elif m.group(2):
        exec_md.append(":::au\n" + inline(m.group(2)) + "\n:::")

# ── theme sections ─────────────────────────────────────────────────────────
THEMES = ["t1-regulation.html", "t2-research.html", "t3-security.html",
          "t4-infrastructure.html", "t5-market.html"]
CARD = re.compile(r'<div class="story-card num-(\d+)" id="(story-\d+)">(.*?)</div></div>', re.S)

sections = []
for fn in THEMES:
    blob = rd(fn)
    label = inline(re.search(r"</span>(.*?)<span class=\"count\">", blob, re.S).group(1))
    label = re.sub(r"^[^\w]+", "", label).strip()          # drop the leading emoji
    cards = []
    for m in CARD.finditer(blob):
        c = m.group(3)
        head = inline(re.search(r"<h3>(.*?)</h3>", c, re.S).group(1))
        summ = inline(re.search(r'<p class="summary">(.*?)</p>', c, re.S).group(1))
        src  = re.search(r'<a class="source" href="([^"]+)"[^>]*>(.*?)</a>', c, re.S)
        tier = re.search(r'<span class="tier-(\d)">', c)
        ver  = re.search(r'class="verification v-(\w+)"', c)
        ev   = re.search(r'class="breach (b-\w+)"', c)
        xref = "crossref" in c
        date = re.search(r'<span class="date">([\d-]+)</span>', c)
        TIERNAME = {"1": "Very High", "2": "High", "3": "Moderate", "4": "Low"}
        EV = {"b-claim": "Vendor claim", "b-preprint": "Unreplicated preprint",
              "b-eval": "Independently evaluated", "b-rumour": "Rumoured"}
        t = tier.group(1) if tier else "3"
        cards.append(dict(
            headline=head, summary=summ,
            source=inline(src.group(2)) if src else "",
            url=src.group(1) if src else "",
            reliability=f"Tier {t}/4 — {TIERNAME.get(t,'Moderate')}",
            verification={"verified": "Verified", "reported": "Reported",
                          "unverified": "Unverified"}.get(ver.group(1) if ver else "", "Unverified"),
            evidence=EV.get(ev.group(1) if ev else "", "Corroborated"),
            shared=xref, date=date.group(1) if date else "2026-10-06"))
    sections.append((label, cards))

# ── emit ───────────────────────────────────────────────────────────────────
L = []
L += ["---",
      "date: 2026-10-06",
      "window_start: 2026-10-04",
      "window_end: 2026-10-06",
      "kicker: 48-hour window &middot; 4&ndash;6 October 2026",
      "---", "", "# Executive Summary", ""]
for p in exec_md:
    L += [p, ""]
for label, cards in sections:
    L += [f"## {label}", ""]
    for i, c in enumerate(cards, 1):
        L += [f"### {i}. {c['headline']}", "",
              f"- **Summary:** {c['summary']}",
              f"- **Source:** [{c['source']}]({c['url']})",
              f"- **Reliability:** {c['reliability']}",
              f"- **Verification:** {c['verification']}",
              f"- **Evidence:** {c['evidence']}"]
        if c["shared"]:
            L += ["- **Shared:** Cyber Digest"]
        L += [f"- **Date:** {c['date']}", ""]

open(OUT, "w", encoding="utf-8").write("\n".join(L).rstrip() + "\n")
n = sum(len(c) for _, c in sections)
print(f"wrote {OUT}")
print(f"  themes: {len(sections)}  stories: {n}  bytes: {os.path.getsize(OUT)}")
for label, cards in sections:
    print(f"    {len(cards):>2}  {label}")
