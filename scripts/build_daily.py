#!/usr/bin/env python3
"""Build the AI Digest daily pages from markdown editions.

  editions/<YYYY-MM-DD>.md   ->   docs/daily/<YYYY-MM-DD>.html
                                  docs/daily/index.html
                                  (and three generated regions of the landing page)

The chrome is NOT defined here. It is copied from the newest built cyber daily and
re-coloured to the AI brand hue — see templates/chrome/style.css, emitted to
docs/assets/chrome.css. Only the parts are the AI Daily's own. Nothing in this file
should invent a colour, a font or a component: if a badge needs changing, change the
chrome, not the page.
"""
import os, re, sys, glob, datetime, html as _html, collections

ROOT = os.path.expanduser("~/Desktop/AI Site")
SRC = os.path.join(ROOT, "editions")
OUT = os.path.join(ROOT, "docs", "daily")
CHROME = os.path.join(ROOT, "templates", "chrome")
# the page shell carries @@THEME_SCRIPT@@ and @@PAGE_SCRIPT@@; substitute the copied
# chrome scripts here so no edition can ship an unrendered token
TPL = (open(os.path.join(ROOT, "templates", "daily.html"), encoding="utf-8").read()
       .replace("@@THEME_SCRIPT@@", open(os.path.join(CHROME, "theme.js"), encoding="utf-8").read())
       .replace("@@PAGE_SCRIPT@@", open(os.path.join(CHROME, "page.js"), encoding="utf-8").read()))

# ── theme identity: icon + bar class. Theme colour is identity only; the semantic
#    colour scale on this page is Impact and nothing else.
_ICON = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
         'stroke-linecap="round" stroke-linejoin="round">%s</svg>')
# label -> (icon path, theme key). The key drives the theme identity class (the
# section icon and the card's left rule) and the analytics bar. It is NOT a colour
# decision made here: the palette lives in the chrome, outside the severity hues.
THEME_META = {
    "Frontier capability": ("<path d=\"M12 3l2.3 5.7L20 10l-4.9 3.4L16.4 20 12 16.7 7.6 20 "
                            "l1.3-6.6L4 10l6-.3z\"/>", "frontier"),
    "Frontier models & capability claims": ("<path d=\"M12 3l2.3 5.7L20 10l-4.9 3.4L16.4 20 "
                                            "12 16.7 7.6 20l1.3-6.6L4 10l6-.3z\"/>", "frontier"),
    "Regulation & obligation": ("<path d=\"M12 3v18M5 7h14M7 7l-3 6a3 3 0 0 0 6 0zM17 7l-3 6a3 3 0 "
                               "0 6 0zM9 20h6\"/>", "reg"),
    "Research & evidence": ("<path d=\"M9 3h6M10 3v6.5L5.5 18a2 2 0 0 0 1.8 3h9.4a2 2 0 0 0 "
                            "1.8-3L14 9.5V3\"/><path d=\"M7.5 15h9\"/>", "res"),
    "AI security & agentic risk": ("<path d=\"M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z\"/>"
                                   "<path d=\"M9.5 12l1.8 1.8L15 10\"/>", "sec"),
    "Infrastructure & compute": ("<rect x=\"3\" y=\"4\" width=\"18\" height=\"6\" rx=\"1.5\"/>"
                                 "<rect x=\"3\" y=\"14\" width=\"18\" height=\"6\" rx=\"1.5\"/>"
                                 "<path d=\"M7 7h.01M7 17h.01\"/>", "inf"),
    "Market & geopolitics": ("<circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M3 12h18M12 3c2.7 2.6 4 "
                             "5.6 4 9s-1.3 6.4-4 9c-2.7-2.6-4-5.6-4-9s1.3-6.4 4-9z\"/>", "mkt"),
    "Market, geopolitics & adoption": ("<circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M3 12h18M12 "
                                       "3c2.7 2.6 4 5.6 4 9s-1.3 6.4-4 9c-2.7-2.6-4-5.6-4-9s1.3"
                                       "-6.4 4-9z\"/>", "mkt"),
}

EXEC_ICON = _ICON % ('<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>'
                     '<path d="M14 3v6h6"/><path d="M9 13h6M9 17h4"/>')
ANALYTICS_ICON = _ICON % '<path d="M4 20V10M10 20V4M16 20v-8M21 20H3"/>'
LEGEND_ICON = _ICON % ('<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.7 2.6 4 5.6 4 9'
                       's-1.3 6.4-4 9c-2.7-2.6-4-5.6-4-9s1.3-6.4 4-9z"/>')

# ── axis rendering. Impact is the only axis that carries colour; the other three are
#    monochrome pills. The vocabulary is the edition's own — an out-of-vocabulary
#    value is a validation failure in publish_daily.py, never a silent default here.
AXIS_ORDER = [("Impact", "Impact", "i"), ("Obligation", "Oblig.", "o"),
              ("Evidence", "Evidence", "e"), ("Capability", "Cap.", "d")]
VER_CLASS = {"Verified": ("v-verified", "b-v", "✓"),
             "Reported": ("v-reported", "b-r", "~"),
             "Unverified": ("v-unverified", "b-u", "?")}
MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
DAYNAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def inline(s):
    """Minimal markdown -> HTML for running text. Code first, then links, then bold, then italic."""
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s, flags=re.S)
    s = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", s)
    return s.strip()


def front_matter(text):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm, m.group(2)


def parse_edition(path):
    """-> (front matter, exec blocks, themes). exec blocks are ('p'|'au', text)."""
    fm, body = front_matter(open(path, encoding="utf-8").read())
    exec_blocks, themes, theme, story = [], [], None, None
    mode, buf = "exec", []

    def flush_para():
        if buf:
            txt = " ".join(buf).strip()
            if txt:
                exec_blocks.append(("p", txt))
            buf.clear()

    for ln in body.splitlines():
        if ln.startswith("## "):
            flush_para()
            if story:
                theme["stories"].append(story); story = None
            if theme:
                themes.append(theme)
            theme = {"label": ln[3:].strip(), "stories": []}
            mode = "exec"
        elif ln.startswith("### "):
            flush_para()
            if story:
                theme["stories"].append(story)
            story = {"headline": re.sub(r"^\d+\.\s*", "", ln[4:].strip()), "fields": []}
            mode = "story"
        elif mode == "story" and re.match(r"^-\s+\*\*", ln.strip()):
            mm = re.match(r"^-\s+\*\*(.+?):\*\*\s*(.*)$", ln.strip())
            if mm:
                story["fields"].append((mm.group(1).strip(), mm.group(2).strip()))
        elif ln.strip() == ":::au":
            flush_para(); buf.clear(); mode = "au"
        elif ln.strip() == ":::":
            txt = " ".join(buf).strip()
            if txt:
                exec_blocks.append(("au", txt))
            buf.clear(); mode = "exec"
        elif ln.strip() == "# Executive Summary":
            pass
        elif ln.strip():
            buf.append(ln.strip())
        else:
            flush_para()
    flush_para()
    if story:
        theme["stories"].append(story)
    if theme:
        themes.append(theme)
    return fm, exec_blocks, themes


def split_reliability(v):
    """'Tier 2/4 \\u2014 High (long rationale)' -> ('2/4', 'High', 'rationale')."""
    m = re.match(r"^(Tier\s*\d\s*/\s*\d)\s*[\u2014\u2013-]\s*([^(]+?)\s*(?:\((.*)\)\s*)?$", v.strip())
    if not m:
        return v.strip(), "", ""
    return m.group(1).replace(" ", "").replace("Tier", ""), m.group(2).strip(), (m.group(3) or "").strip()


def short_qualifier(rationale, limit=52):
    if not rationale:
        return ""
    first = re.split(r"[;.]", rationale)[0].strip()
    if len(first) > limit:
        first = first[:limit - 1].rsplit(" ", 1)[0] + "\u2026"
    return first


def slug(v):
    return re.sub(r"[^a-z0-9]+", "-", v.lower()).strip("-")


def axis_pill(axis, label, prefix, value):
    if not value:
        return ""
    return (f'<span class="axis {prefix}-{slug(value)}"><span class="lb">{label}</span>'
            f'{_html.escape(value)}</span>')


def source_link(fields):
    d = dict(fields)
    src = d.get("Source", "")
    mm = re.match(r"\[(.+?)\]\((.+?)\)", src)
    if mm:
        return (f'<a class="source src" href="{mm.group(2)}" target="_blank" '
                f'rel="noopener">{_html.escape(mm.group(1))}</a>')
    return f'<span class="src">{_html.escape(src)}</span>' if src else ""


def meta_strip(fields):
    """Source, then one pill per axis, the tier, the gate and the date — one line,
    hairline-separated, colour used once. The class hooks (src / date / b-tier /
    b-v|b-r|b-u / i-*) are what the publish gate reads; do not rename them without
    changing the gate in the same commit."""
    d = dict(fields)
    out = [source_link(fields)]
    for axis, label, prefix in AXIS_ORDER:
        out.append(axis_pill(axis, label, prefix, d.get(axis, "")))
    if d.get("Reliability"):
        grade, level, rationale = split_reliability(d["Reliability"])
        shown = f"Tier {grade} &middot; {level}" if level else f"Tier {grade}"
        qual = short_qualifier(rationale)
        out.append(f'<span class="reliability b-tier" title="{_html.escape(d["Reliability"], quote=True)}">'
                   f'<span class="tier-{grade[0]}">&#9679;</span> {shown}'
                   + (f'<span class="q">{_html.escape(qual)}</span>' if qual else "") + "</span>")
    if d.get("Verification"):
        v = d["Verification"]
        cls, gate, glyph = VER_CLASS.get(v, ("v-unverified", "b-u", "?"))
        out.append(f'<span class="verification {cls} {gate}"><span class="dot"></span> {v}</span>')
    if d.get("Shared"):
        out.append(f'<span class="crossref"><span class="dot"></span> &#8596; '
                   f'{_html.escape(d["Shared"])}</span>')
    if d.get("Date"):
        out.append(f'<span class="date">{_html.escape(d["Date"])}</span>')
    return "".join(out)


def build_edition(path, prev_next_html):
    fm, exec_blocks, themes = parse_edition(path)
    d = datetime.date.fromisoformat(fm["date"])
    n_stories = sum(len(t["stories"]) for t in themes)
    urls, src_names = [], collections.Counter()
    ev = collections.Counter()
    gate = collections.Counter()
    impacts = collections.Counter()

    for t in themes:
        for s in t["stories"]:
            f = dict(s["fields"])
            mm = re.match(r"\[(.+?)\]\((.+?)\)", f.get("Source", ""))
            if mm:
                if mm.group(2) not in urls:
                    urls.append(mm.group(2))
                src_names[re.split(r"\s+[—–-]\s+", mm.group(1))[0].strip()] += 1
            if f.get("Evidence"):
                ev[f["Evidence"]] += 1
            if f.get("Verification"):
                gate[f["Verification"]] += 1
            if f.get("Impact"):
                impacts[f["Impact"]] += 1

    def pretty(iso):
        y, m, dd = (int(x) for x in iso.split("-"))
        return dd, MONTHS[m - 1], y

    ws, we = fm.get("window_start"), fm.get("window_end")
    if ws and we and ws != we:
        d1, m1, y1 = pretty(ws); d2, m2, y2 = pretty(we)
        win = (f"{d1}&ndash;{d2} {m2} {y2}" if m1 == m2 and y1 == y2
               else f"{d1} {m1} &ndash; {d2} {m2} {y2}")
        hours = (datetime.date.fromisoformat(we) - datetime.date.fromisoformat(ws)).days * 24
    else:
        win, hours = f"{d.day} {MONTHS[d.month-1]} {d.year}", 24

    title = f"AI Digest — {d.day} {MONTHS[d.month - 1]} {d.year}"
    desc = (f"{n_stories} stories across {len(themes)} themes in the {win} window, with an "
            f"Australian and New Zealand read.")
    kicker = f"// ai digest &middot; {hours}-hour window &middot; {win}"

    chips = (f'<span class="chip chip-accent">{n_stories} stories</span>'
             f'<span class="chip">{len(themes)} themes</span>'
             f'<span class="chip">{len(urls)} sources</span>'
             f'<span class="chip">{hours}-hour window</span>'
             f'<span class="chip chip-guard"><i></i>AU/NZ watchlist active</span>')

    # ── executive summary
    ex = [f'<section id="exec" class="exec-summary">',
          f'<h2><span class="icon">{EXEC_ICON}</span> Executive Summary '
          f'<span class="count">{n_stories} stories</span></h2>']
    for kind, txt in exec_blocks:
        if kind == "au":
            ex.append(f'<div class="au-context-box"><p>{inline(txt)}</p></div>')
        else:
            ex.append(f"<p>{inline(txt)}</p>")
    ex.append("</section>")

    # ── themes, cards numbered and the TOC built in the same pass
    n = 0
    th = []
    toc = [f'<a href="#exec" data-section="exec"><span class="sicon">{EXEC_ICON}</span>'
           f'<span class="tlabel">Executive summary</span></a>']
    for i, t in enumerate(themes, 1):
        icon, key = THEME_META.get(t["label"], (THEME_META["Market & geopolitics"][0], "mkt"))
        cnt = len(t["stories"])
        tid = f"theme-{i}"
        toc.append(f'<a href="#{tid}" data-section="{tid}"><span class="sicon">{_ICON % icon}</span>'
                   f'<span class="tlabel">{_html.escape(t["label"])}</span>'
                   f'<span class="tcount">{cnt}</span></a>')
        th.append(f'<section id="{tid}" class="section t-{key}">')
        th.append(f'<h2><span class="icon">{_ICON % icon}</span> {_html.escape(t["label"])} '
                  f'<span class="count">{cnt} {"story" if cnt == 1 else "stories"}</span></h2>')
        th.append('<div class="story-grid">')
        for s in t["stories"]:
            n += 1
            f = dict(s["fields"])
            th.append(f'<article class="story-card t-{key} num-{n}" id="story-{n}">'
                      f'<div class="card-accent"></div>'
                      f'<div class="story-number">{n}</div>'
                      f'<h3>{inline(s["headline"])}</h3>'
                      f'<p class="summary">{inline(f.get("Summary", ""))}</p>'
                      f'<div class="meta">{meta_strip(s["fields"])}</div></article>')
            import html as _h
            ttl = _h.unescape(re.sub(r"<[^>]+>", "", inline(s["headline"])))
            toc.append(f'<a class="tsub" href="#story-{n}" data-story="story-{n}" '
                       f'title="{_h.escape(ttl, quote=True)}"><span class="tsub-n">{n}</span>'
                       f'<span class="tsub-label">{_h.escape(ttl)}</span></a>')
        th.append("</div></section>")
    toc.append(f'<a href="#analytics" data-section="analytics"><span class="sicon">{ANALYTICS_ICON}</span>'
               f'<span class="tlabel">Coverage</span></a>')
    toc.append(f'<a href="#legend" data-section="legend"><span class="sicon">{LEGEND_ICON}</span>'
               f'<span class="tlabel">Key to this page</span></a>')

    # ── analytics — computed from the cards in the same pass, never authored
    counts = [(t["label"], len(t["stories"])) for t in themes]
    mx = max([c for _, c in counts] + [1])
    rows = []
    for label, c in counts:
        _, key = THEME_META.get(label, ("", "mkt"))
        rows.append(f'<div class="bar-row t-{key}"><span class="bar-label">{_html.escape(label)}</span>'
                    f'<div class="bar-track"><div class="bar-fill" style="width:{c/mx*100:.1f}%">'
                    f'</div></div><span class="bar-val">{c}</span></div>')
    evmax = max(list(ev.values()) + [1]) if ev else 1
    ev_rows = []
    for name, c in ev.most_common():
        ev_rows.append(f'<div class="bar-row mono"><span class="bar-label">{_html.escape(name)}</span>'
                       f'<div class="bar-track"><div class="bar-fill" '
                       f'style="width:{c/evmax*100:.1f}%"></div></div>'
                       f'<span class="bar-val">{c}</span></div>')
    gmax = max(list(gate.values()) + [1]) if gate else 1
    gate_rows = []
    for name in ("Verified", "Reported", "Unverified"):
        c = gate.get(name, 0)
        gate_rows.append(f'<div class="bar-row mono"><span class="bar-label">{name}</span>'
                         f'<div class="bar-track"><div class="bar-fill" '
                         f'style="width:{c/gmax*100:.1f}%"></div></div>'
                         f'<span class="bar-val">{c}</span></div>')
    tax_rows = []
    for label, c in counts:
        tax_rows.append(f'<tr><td>{_html.escape(label)}</td><td>{c}</td></tr>')

    an = [f'<section id="analytics" class="section">',
          f'<h2><span class="icon">{ANALYTICS_ICON}</span> Coverage this edition '
          f'<span class="count">{n_stories} stories &middot; {len(themes)} themes &middot; '
          f'{len(urls)} sources</span></h2>',
          '<div class="bar-chart"><h3>Where the window\'s stories landed</h3>',
          *rows, "</div>",
          '<div class="bar-chart"><h3>Evidence class — what kind of claim each story carries</h3>',
          *ev_rows,
          '<p class="empty-note">A vendor&rsquo;s claim about its own product is recorded here as a '
          'claim, never as a measurement — the axis is orthogonal to verification, so a story can be '
          'Verified (they did say it) and a Vendor claim (the capability is unreplicated) at once.</p>',
          "</div>",
          '<div class="bar-chart"><h3>Verification gate</h3>', *gate_rows, "</div>",
          '<table class="data-table"><thead><tr><th>Theme (taxonomy)</th><th>Stories</th></tr></thead>'
          "<tbody>", *tax_rows, "</tbody></table>",
          "</section>"]
    if not gate.get("Unverified"):
        an.append("")

    # ── footer: measured source diversity, prev/next, provenance
    src_line = (f"AI Digest generated {d.isoformat()}." + (
        " Sources: " + ", ".join(f"{_html.escape(k)} ({v})" for k, v in src_names.most_common())
        + "." if src_names else ""))
    top = src_names.most_common(1)
    if top and n_stories:
        share = top[0][1] / n_stories
        src_line += (f" Largest single source: {_html.escape(top[0][0])} — "
                     f"{top[0][1]}/{n_stories} ({share:.0%})." +
                     (" Within the 40% threshold." if share <= 0.40
                      else " ABOVE the 40% threshold."))
    footer = (f'<footer class="footer"><nav class="ednav">{prev_next_html}</nav>'
              f'<div class="source-line">{src_line}</div>'
              f'<div class="note">Window: {hours} hours to {d.day} {MONTHS[d.month-1]} {d.year}. '
              f'Stories are grouped by layer of the stack, not by industry sector; a theme with no '
              f'qualifying item is listed in the coverage table above and rendered as no section at '
              f'all. Colour on this page means impact severity and nothing else.</div>'
              f'<div class="links"><a href="/daily/">All editions</a>'
              f'<a href="/about/">About the AI Digest</a>'
              f'<a href="https://peterjaycox.com">Hub</a></div></footer>')

    page = (TPL.replace("@@TITLE@@", _html.escape(title))
               .replace("@@DESCRIPTION@@", _html.escape(desc, quote=True))
               .replace("@@KICKER@@", kicker)
               .replace("@@HERO_DATE@@", f"{DAYNAMES[d.weekday()]}<span class=\"sep\">&middot;</span>"
                                         f"{d.day} {MONTHS[d.month-1]} {d.year}")
               .replace("@@CHIPS@@", chips)
               .replace("@@TOC@@", "\n".join(toc))
               .replace("@@EXEC@@", "\n".join(ex))
               .replace("@@THEMES@@", "\n".join(th))
               .replace("@@ANALYTICS@@", "\n".join(an))
               .replace("@@LEGEND@@", legend_section())
               .replace("@@FOOTER@@", footer))
    return d, page, n_stories, len(themes), desc


def legend_section():
    return """<section id="legend" class="section">
<h2><span class="icon">%s</span> Key to this page <span class="count">how to read it</span></h2>

<div class="legend-group">
<h3>Impact &mdash; the only coloured axis</h3>
<p>How far the risk, obligation or capability position moves. <strong>Impact is not harm</strong>:
half of what this digest carries &mdash; a model release, a research result, a funding round &mdash; is
not a harm at all. The band is driven by precedent, blast radius, reversibility, structural change
and sector criticality, not by a severity dictionary borrowed from cyber incidents.</p>
<p><span class="axis i-low"><span class="lb">Impact</span>Low</span>
<span class="axis i-guarded"><span class="lb">Impact</span>Guarded</span>
<span class="axis i-elevated"><span class="lb">Impact</span>Elevated</span>
<span class="axis i-severe"><span class="lb">Impact</span>Severe</span>
<span class="axis i-critical"><span class="lb">Impact</span>Critical</span></p>
</div>

<div class="legend-group">
<h3>Obligation &mdash; does it bind an AUNZ organisation?</h3>
<p>Rendered only when the band is not <em>None</em>; a pill reading &ldquo;Obligation: None&rdquo; on
every card is noise. <em>Proposed</em> means text exists; <em>Signalled</em> means a minister or a
government has said it will &mdash; a two-stage ministerial statement stays Signalled. Where an
obligation is claimed, the card names the instrument <em>and</em> its operative provision.</p>
</div>

<div class="legend-group">
<h3>Evidence &mdash; how established is the claim?</h3>
<p>Orthogonal to verification, and the reason this product exists separately from the cyber digest:
an AI capability claim usually cannot be verified at all. A vendor testifying about its own model is
<strong>Verified</strong> (they did say it) and simultaneously a <strong>Vendor claim</strong> (the
capability is unreplicated). Both badges render.</p>
<p><span class="axis e-confirmed"><span class="lb">Evidence</span>Confirmed</span>
<span class="axis e-corroborated"><span class="lb">Evidence</span>Corroborated</span>
<span class="axis e-vendor-claim"><span class="lb">Evidence</span>Vendor claim</span>
<span class="axis e-independently-evaluated"><span class="lb">Evidence</span>Independently evaluated</span>
<span class="axis e-unreplicated-preprint"><span class="lb">Evidence</span>Unreplicated preprint</span>
<span class="axis e-rumoured"><span class="lb">Evidence</span>Rumoured</span></p>
</div>

<div class="legend-group">
<h3>Capability delta &mdash; frontier themes only</h3>
<p><span class="axis d-frontier"><span class="lb">Cap.</span>Frontier step-change</span>
<span class="axis d-material"><span class="lb">Cap.</span>Material</span>
<span class="axis d-incremental"><span class="lb">Cap.</span>Incremental</span></p>
</div>

<div class="legend-group">
<h3>Source reliability and verification</h3>
<table class="data-table">
<thead><tr><th>Tier</th><th>Label</th><th>Description</th></tr></thead>
<tbody>
<tr><td><span class="tier-badge tier-1">1</span></td><td>Very High</td><td>Official, first-party or regulator &mdash; the instrument, the register entry, the vendor&rsquo;s own newsroom or research blog</td></tr>
<tr><td><span class="tier-badge tier-2">2</span></td><td>High</td><td>Established wire and specialist reporting, and independent evaluators</td></tr>
<tr><td><span class="tier-badge tier-3">3</span></td><td>Moderate</td><td>General technology and specialist AI media; market coverage relaying a company&rsquo;s own numbers</td></tr>
<tr><td><span class="tier-badge tier-4">4</span></td><td>Low</td><td>Social, forum and release-tracker sites &mdash; leads only, never cited</td></tr>
</tbody>
</table>
<p><span class="verification v-verified"><span class="dot"></span> Verified</span> established by first-party disclosure, a regulator, or two or more independent sources. <span class="verification v-reported"><span class="dot"></span> Reported</span> a single credible outlet, or a party&rsquo;s own account. <span class="verification v-unverified"><span class="dot"></span> Unverified</span> circulating without a source that meets the bar.</p>
</div>

<div class="legend-group">
<h3>Three rules that shape what appears</h3>
<p><strong>Freshness is a state-change test, not a date test.</strong> An item qualifies when
something moved &mdash; a model shipped, a rule commenced, a vulnerability was exploited, a subpoena
was served, a paper published. The window is 48 hours, 72 across a weekend bridge, and it is stated
on every edition. Anything older appears in the executive summary as context, never as an entry.</p>
<p><strong>An empty theme stays empty.</strong> Where a theme has no qualifying item it is listed in
the coverage table with the count it earned and rendered as no section at all &mdash; never as a
zero bar and never padded with stale material.</p>
<p><strong>Suppression.</strong> A story that ran in either of the previous two editions is not
repeated unless the day adds a fact, and the new fact must be what the entry is about.</p>
</div>
</section>""" % LEGEND_ICON


HOME = os.path.join(ROOT, "docs", "index.html")
LATEST_START, LATEST_END = "<!-- LATEST:START -->", "<!-- LATEST:END -->"
KICKER_START, KICKER_END = "<!-- KICKER:START -->", "<!-- KICKER:END -->"
LEAD_START, LEAD_END = "<!-- LEAD:START -->", "<!-- LEAD:END -->"
HOME_ROWS = 4


def lead_card(page):
    m = re.search(r'<article class="story-card.*?</article>', page, re.S)
    return m.group(0) if m else ""


def edlink(d, kind, label):
    if d is None:
        return (f'<a class="edlink {kind} dis" aria-hidden="true" tabindex="-1">'
                f'<span class="dl">{label}</span><span class="dd">&nbsp;</span></a>')
    return (f'<a class="edlink {kind}" href="{d.isoformat()}.html">'
            f'<span class="dl">{label}</span>'
            f'<span class="dd">{d.day} {MONTHS[d.month-1]} {d.year}</span></a>')


def prev_next(older, newer):
    return edlink(older, "prev", "\u2190 Older") + edlink(newer, "next", "Newer \u2192")


def timeline(asc):
    mx = max([ns for _, ns, _, _ in asc] + [1])
    cols = []
    for d, ns, nt, _ in asc:
        h = 5 + round(ns / mx * 33)
        cols.append(f'<a class="tl" href="{d.isoformat()}.html" '
                    f'title="{d.day} {MONTHS[d.month-1]} {d.year} \u2014 {ns} '
                    f'{"story" if ns == 1 else "stories"}, {nt} themes">'
                    f'<span class="tlbar" style="height:{h}px"></span>'
                    f'<span class="tld">{d.day}</span></a>')
    return "".join(cols)


def home_blurb(path):
    m = re.search(r"\*\*Top stories\.\*\*\s*(.+)", open(path, encoding="utf-8").read())
    if not m:
        return ""
    txt = re.sub(r"\[(.+?)\]\([^)]+\)", r"\1", m.group(1))
    txt = txt.replace("**", "").replace("`", "")
    sent = re.split(r"(?<=[.!?])\s+", txt.strip())[0].strip()
    if len(sent) > 240:
        sent = sent[:237].rsplit(" ", 1)[0] + "\u2026"
    return sent


def update_homepage(built, newest_page=""):
    if not os.path.exists(HOME):
        print("  WARN homepage: docs/index.html missing — skipped")
        return
    page = open(HOME, encoding="utf-8").read()
    rows = []
    for i, (d, ns, nt, _) in enumerate(built[:HOME_ROWS]):
        label = (f"{d.day} {MONTHS[d.month - 1]} {d.year} &mdash; {ns} "
                 f"{'story' if ns == 1 else 'stories'}, {nt} {'theme' if nt == 1 else 'themes'}")
        link = f'<a href="/daily/{d.isoformat()}.html">{label}</a>'
        if i == 0:
            blurb = home_blurb(os.path.join(SRC, d.isoformat() + ".md"))
            rows.append(f'      <li><b>{link}</b><span class="blurb">{blurb}</span></li>')
        else:
            rows.append(f"      <li>{link}</li>")
    newest = built[0][0]
    regions = ((LATEST_START, LATEST_END, "\n" + "\n".join(rows) + "\n"),
               (KICKER_START, KICKER_END,
                f"Latest edition &middot; {newest.day} {MONTHS[newest.month - 1]} {newest.year}"),
               (LEAD_START, LEAD_END,
                "\n<div class=\"leadwrap\">" + lead_card(newest_page)
                + f'<a class="leadmore" href="/daily/{newest.isoformat()}.html">'
                  f'Read the full edition &rarr;</a></div>\n'))
    for start, end, body in regions:
        pat = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
        if not pat.search(page):
            print(f"  WARN homepage: {start} region not found — skipped")
            continue
        page = pat.sub(lambda m, b=body: start + b + end, page, count=1)
    open(HOME, "w", encoding="utf-8").write(page)
    print(f"  homepage  latest edition -> {newest.isoformat()}")


INDEX_TPL = """<!DOCTYPE html>
<html lang="en-AU" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Digest — editions</title>
<meta name="description" content="Every AI Digest edition, newest first.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script>
@@THEME_SCRIPT@@
</script>
<link rel="stylesheet" href="/assets/chrome.css">
<link rel="stylesheet" href="/assets/digest.css">
</head>
<body>
<nav class="topnav"><div class="inner">
  <a class="brand" href="/"><span class="dot"></span>AI&nbsp;Digest<small>daily</small></a>
  <div class="navlinks">
    <a href="/daily/" class="active"><span class="t">Editions</span></a>
    <a href="/about/"><span class="t">About</span></a>
    <a href="https://peterjaycox.com"><span class="t">Hub</span></a>
    <a href="https://cyber.peterjaycox.com"><span class="t">Cyber</span></a>
    <a href="https://intel.peterjaycox.com"><span class="t">Intel</span></a>
  </div>
  <div class="theme-toggle" role="button" tabindex="0" aria-label="Appearance" onclick="window.__aiTheme.cycle(event)"><span class="tt-auto" aria-hidden="true">🌗</span><span class="tt-light" aria-hidden="true">☀️</span><span class="tt-dark" aria-hidden="true">🌙</span></div>
</div></nav>
<div class="wrap single">
<header class="hero" id="top">
<div class="hero-grid"></div>
<div class="kicker">@@N@@</div>
<div class="hero-date">Editions</div>
<h1>AI Digest</h1>
<p class="subtitle">Every edition, newest first. A daily read on artificial intelligence, with an Australian and New Zealand lens. Latest: @@NEWEST@@.</p>
<div class="ed-tl">@@TIMELINE@@</div>
<p class="ed-tlcap">Stories per edition, oldest to newest.</p>
</header>
<main id="main" class="main">
<div class="list">
@@ROWS@@
</div>
</main>
<footer class="footer"><div class="links"><a href="/about/">About the AI Digest</a><a href="https://peterjaycox.com">Hub</a></div></footer>
</div>
</body>
</html>
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    # the chrome is copied into docs/ by the build, so the published stylesheet can
    # never be a stale hand-edit of templates/chrome/style.css
    import shutil
    shutil.copy2(os.path.join(ROOT, "templates", "chrome", "style.css"),
                 os.path.join(ROOT, "docs", "assets", "chrome.css"))
    print(f"  chrome.css  {os.path.getsize(os.path.join(ROOT,'docs','assets','chrome.css')):,} bytes")
    files = sorted(glob.glob(os.path.join(SRC, "*.md")), reverse=True)
    if not files:
        sys.exit("no editions found in " + SRC)
    # pass 1: parse and render every edition, so each page can be given its neighbours
    prepared = [build_edition(f, "@@PREVNEXT@@") for f in files]
    dates = [d for d, *_ in prepared]

    built, newest_page = [], ""
    for i, (d, page, ns, nt, desc) in enumerate(prepared):
        older = dates[i + 1] if i + 1 < len(dates) else None
        newer = dates[i - 1] if i > 0 else None
        page = page.replace("@@PREVNEXT@@", prev_next(older, newer))
        dst = os.path.join(OUT, f"{d.isoformat()}.html")
        open(dst, "w", encoding="utf-8").write(page)
        if i == 0:
            newest_page = page
        built.append((d, ns, nt, os.path.getsize(dst)))
        print(f"  {d.isoformat()}.html  {ns} stories / {nt} themes  {os.path.getsize(dst):,} bytes")

    items = []
    for d, ns, nt, _ in built:
        items.append(f'<a class="edrow" href="{d.isoformat()}.html">'
                     f'<span class="eddate">{d.day} {MONTHS[d.month-1]} {d.year}</span>'
                     f'<span class="edmeta">{ns} stories &middot; {nt} themes</span>'
                     f'<span class="edar">&#8594;</span></a>')
    newest = built[0][0]
    idx = (INDEX_TPL.replace("@@ROWS@@", "\n".join(items))
                    .replace("@@TIMELINE@@", timeline(list(reversed(built))))
                    .replace("@@N@@", f"{len(built)} edition" + ("" if len(built) == 1 else "s"))
                    .replace("@@NEWEST@@", f"{newest.day} {MONTHS[newest.month-1]} {newest.year}")
                    .replace("@@THEME_SCRIPT@@",
                             open(os.path.join(ROOT, "templates", "chrome", "theme.js"),
                                  encoding="utf-8").read()))
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(idx)
    print(f"  index.html  {len(built)} edition(s)  {os.path.getsize(os.path.join(OUT,'index.html')):,} bytes")

    update_homepage(built, newest_page)


if __name__ == "__main__":
    main()
