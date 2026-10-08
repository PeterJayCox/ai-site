#!/usr/bin/env python3
"""Build the AI Digest daily pages from markdown editions.

  editions/<YYYY-MM-DD>.md   ->   docs/daily/<YYYY-MM-DD>.html
                                  docs/daily/index.html

Counts are computed from the parsed edition, never hand-written.
"""
import os, re, sys, glob, datetime, html as _html

ROOT = os.path.expanduser("~/Desktop/AI Site")
SRC = os.path.join(ROOT, "editions")
OUT = os.path.join(ROOT, "docs", "daily")
TPL = open(os.path.join(ROOT, "templates", "daily.html"), encoding="utf-8").read()

THEME_COLOUR = {
    "Frontier capability": "var(--ai)",
    "Frontier models & capability claims": "var(--ai)",
    "Regulation & obligation": "var(--amber)",
    "Research & evidence": "var(--teal)",
    "AI security & agentic risk": "var(--red)",
    "Infrastructure & compute": "var(--green)",
    "Market, geopolitics & adoption": "var(--blue)",
    "Market & geopolitics": "var(--blue)",
}
# Which colour class a badge VALUE gets. Presentation lives here, not in the
# content: re-styling an axis never means editing an edition.
CLASS_MAP = {
    "Impact": {"low": "i-low", "guarded": "i-guarded", "elevated": "i-elevated",
               "severe": "i-severe", "critical": "i-critical"},
    "Obligation": {"mandated": "o-mandated", "commenced": "o-commenced",
                   "proposed": "o-proposed", "signalled": "o-signalled"},
    "Evidence": {"corroborated": "b-corrob", "confirmed": "b-confirmed",
                 "probable": "b-probable", "other": "b-other",
                 "vendor claim": "b-claim", "independently evaluated": "b-eval",
                 "unreplicated preprint": "b-preprint", "rumoured": "b-rumour"},
    "Capability": {"frontier": "d-frontier", "material": "d-material",
                   "incremental": "d-incremental"},
}
VER_CLASS = {"Verified": "b-v", "Reported": "b-r", "Unverified": "b-u"}
AXIS_ORDER = ["Impact", "Obligation", "Evidence", "Capability"]
MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]


def inline(s):
    """Minimal markdown -> HTML for running text. Bold before italic."""
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
    fm, body = front_matter(open(path, encoding="utf-8").read())
    lines = body.splitlines()
    exec_blocks, themes, theme, story = [], [], None, None
    mode = "exec"          # exec | story
    buf = []

    def flush_para():
        if buf:
            txt = " ".join(buf).strip()
            if txt:
                exec_blocks.append(("p", txt))
            buf.clear()

    for ln in lines:
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
            head = re.sub(r"^\d+\.\s*", "", ln[4:].strip())
            story = {"headline": head, "fields": []}
            mode = "story"
        elif mode == "story" and re.match(r"^-\s+\*\*", ln.strip()):
            mm = re.match(r"^-\s+\*\*(.+?):\*\*\s*(.*)$", ln.strip())
            if mm:
                story["fields"].append((mm.group(1).strip(), mm.group(2).strip()))
        elif ln.strip() == ":::au":
            flush_para()
            buf.clear()
            mode = "au"
        elif ln.strip() == ":::":
            txt = " ".join(buf).strip()
            if txt:
                exec_blocks.append(("au", txt))
            buf.clear()
            mode = "exec"
        elif ln.strip() == "# Executive Summary":
            pass
        else:
            if ln.strip():
                buf.append(ln.strip())
            else:
                flush_para()
    flush_para()
    if story:
        theme["stories"].append(story)
    if theme:
        themes.append(theme)
    return fm, exec_blocks, themes


def badges(fields):
    d = {}
    for k, v in fields:
        d.setdefault(k, v)
    out = []
    src, url = d.get("Source", ""), ""
    mm = re.match(r"\[(.+?)\]\((.+?)\)", src)
    if mm:
        src, url = mm.group(1), mm.group(2)
    if src:
        out.append(f'<a class="src" href="{url}">{_html.escape(src)}</a>')
    # the rated axes, always in the same order, omitted when an edition has no rating
    for axis in AXIS_ORDER:
        if axis in d:
            cls = CLASS_MAP.get(axis, {}).get(d[axis].lower(), "")
            out.append(f'<span class="badge axis {cls}">{_html.escape(axis)}: '
                       f'{_html.escape(d[axis])}</span>')
    if "Reliability" in d:
        out.append(f'<span class="badge b-tier">{_html.escape(d["Reliability"])}</span>')
    if "Verification" in d:
        v = d["Verification"]
        out.append(f'<span class="badge {VER_CLASS.get(v,"b-u")}">{_html.escape(v)}</span>')
    if "Shared" in d:
        out.append(f'<span class="badge b-shared">&#8596; {_html.escape(d["Shared"])}</span>')
    if "Date" in d:
        out.append(f'<span class="date">{_html.escape(d["Date"])}</span>')
    return "".join(out)


def build_edition(path):
    fm, exec_blocks, themes = parse_edition(path)
    d = datetime.date.fromisoformat(fm["date"])
    n_stories = sum(len(t["stories"]) for t in themes)
    urls = set()
    for t in themes:
        for s in t["stories"]:
            for k, v in s["fields"]:
                if k == "Source":
                    mm = re.match(r"\[.+?\]\((.+?)\)", v)
                    if mm:
                        urls.add(mm.group(1))

    def pretty(iso):
        y, m, dd = (int(x) for x in iso.split("-"))
        return dd, MONTHS[m - 1], y

    ws, we = fm.get("window_start"), fm.get("window_end")
    if ws and we and ws != we:
        d1, m1, y1 = pretty(ws)
        d2, m2, y2 = pretty(we)
        win = (f"{d1}\u2013{d2} {m2} {y2}" if m1 == m2 and y1 == y2
               else f"{d1} {m1} \u2013 {d2} {m2} {y2}")
    else:
        win = f"{d.day} {MONTHS[d.month-1]} {d.year}"

    title = f"AI Digest — {d.day} {MONTHS[d.month - 1]} {d.year}"
    desc = (f"{n_stories} stories across {len(themes)} themes in the "
            f"{win} window, with an Australian and New Zealand read.")

    chips = [f'{n_stories} stories', f'{len(themes)} themes', f'{len(urls)} sources']
    chips_html = ("".join(f'<span class="chip{" acc" if i==0 else ""}">{c}</span>'
                          for i, c in enumerate(chips)))

    # executive summary
    ex = ['<section id="executive">',
          '<h2 class="sec"><span class="dot" style="background:var(--ai)"></span>Executive summary'
          f'<span class="cnt">{n_stories} stories</span></h2>']
    for kind, txt in exec_blocks:
        if kind == "au":
            ex.append(f'<div class="au"><p>{inline(txt)}</p></div>')
        else:
            ex.append(f'<p class="body">{inline(txt)}</p>')
    ex.append("</section>")

    # themes
    n = 0
    th = []
    for t in themes:
        col = THEME_COLOUR.get(t["label"], "var(--ai)")
        cnt = len(t["stories"])
        th.append('<section class="theme">')
        th.append(f'<h2 class="sec"><span class="dot" style="background:{col}"></span>'
                  f'{_html.escape(t["label"])}<span class="cnt">{cnt} '
                  f'{"story" if cnt == 1 else "stories"}</span></h2>')
        for s in t["stories"]:
            n += 1
            fields = dict(s["fields"])
            summ = inline(fields.get("Summary", ""))
            th.append(f'<article class="card" id="story-{n}">'
                      f'<div class="bar" style="background:{col}"></div>'
                      f'<div class="num">{n}</div>'
                      f'<h3>{inline(s["headline"])}</h3>'
                      f'<p class="sum">{summ}</p>'
                      f'<div class="meta">{badges(s["fields"])}</div></article>')
        th.append("</section>")

    # analytics (computed)
    counts = [(t["label"], len(t["stories"])) for t in themes]
    mx = max([c for _, c in counts] + [1])
    rows = []
    for label, c in counts:
        col = THEME_COLOUR.get(label, "var(--ai)")
        rows.append(f'<div class="row"><span>{_html.escape(label)}</span>'
                    f'<span class="track"><span class="fill" style="width:{c/mx*100:.0f}%;'
                    f'background:{col};display:block"></span></span>'
                    f'<span class="val">{c}</span></div>')
    an = ['<section class="analytics" id="analytics">',
          '<h2 class="sec"><span class="dot" style="background:var(--ai)"></span>'
          f'Coverage this edition<span class="cnt">{n_stories} stories</span></h2>',
          *rows, "</section>"]

    page = (TPL.replace("@@TITLE@@", title)
               .replace("@@DESCRIPTION@@", _html.escape(desc, quote=True))
               .replace("@@KICKER@@", fm.get("kicker", ""))
               .replace("@@CHIPS@@", chips_html)
               .replace("@@EXEC@@", "\n".join(ex))
               .replace("@@THEMES@@", "\n".join(th))
               .replace("@@ANALYTICS@@", "\n".join(an))
               .replace("@@DATE_LONG@@", f"{d.day} {MONTHS[d.month-1]} {d.year}"))
    return d, page, n_stories, len(themes), desc


def main():
    os.makedirs(OUT, exist_ok=True)
    files = sorted(glob.glob(os.path.join(SRC, "*.md")), reverse=True)
    if not files:
        sys.exit("no editions found in " + SRC)
    built = []
    for f in files:
        d, page, ns, nt, desc = build_edition(f)
        dst = os.path.join(OUT, f"{d.isoformat()}.html")
        open(dst, "w", encoding="utf-8").write(page)
        built.append((d, ns, nt, os.path.getsize(dst)))
        print(f"  {d.isoformat()}.html  {ns} stories / {nt} themes  {os.path.getsize(dst):,} bytes")

    # index
    items = []
    for d, ns, nt, _ in built:
        items.append(f'<a class="edrow" href="{d.isoformat()}.html">'
                     f'<span class="eddate">{d.day} {MONTHS[d.month-1]} {d.year}</span>'
                     f'<span class="edmeta">{ns} stories &middot; {nt} themes</span>'
                     f'<span class="edar">&#8594;</span></a>')
    newest = built[0][0]
    idx = (INDEX_TPL.replace("@@ROWS@@", "\n".join(items))
                    .replace("@@N@@", f"{len(built)} edition" + ("" if len(built) == 1 else "s"))
                    .replace("@@NEWEST@@", f"{newest.day} {MONTHS[newest.month-1]} {newest.year}"))
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(idx)
    print(f"  index.html  {len(built)} edition(s)  {os.path.getsize(os.path.join(OUT,'index.html')):,} bytes")


INDEX_TPL = """<!DOCTYPE html>
<html lang="en-AU" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Digest — editions</title>
<meta name="description" content="Every AI Digest edition, newest first.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<script>
(function(){var d=document.documentElement;
function sys(){try{return (window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches)?'light':'dark';}catch(e){return 'dark';}}
function saved(){try{var s=localStorage.getItem('ai-theme2');return (s==='light'||s==='dark')?s:null;}catch(e){return null;}}
function mode(){return saved()||'auto';}
function save(m){try{if(m==='auto'){localStorage.removeItem('ai-theme2');}else{localStorage.setItem('ai-theme2',m);}}catch(e){}}
function apply(){var m=mode();d.setAttribute('data-theme',m==='auto'?sys():m);d.setAttribute('data-theme-mode',m);}
function cycle(ev){var m=mode();
if(ev&&ev.shiftKey){save('auto');}
else if(m==='auto'){save(sys()==='dark'?'light':'dark');}
else if(m===sys()){save('auto');}
else{save(m==='light'?'dark':'light');}
apply();}
try{localStorage.removeItem('ai-theme');}catch(e){}
window.__aiTheme={cycle:cycle,apply:apply};
apply();
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',apply);}
})();
</script>
<style>
:root{--bg:#F6F4EF;--surface:#FFFFFF;--text:#1D1B16;--muted:#6B665A;--border:#E4DFD3;--surface2:#EFEBE3;--surface-hover:#E6E1D6;--ai:#6E56CF}
[data-theme="dark"]{--bg:#191813;--surface:#211F19;--text:#ECE8DD;--muted:#A39C8D;--border:#3A372E;--surface2:#2A2821;--surface-hover:#322F27;--ai:#9B85F5}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',-apple-system,Segoe UI,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;transition:background .25s,color .25s}
.topbar{border-bottom:1px solid var(--border)}
.topbar .in{display:flex;align-items:center;justify-content:space-between;height:56px;max-width:760px;margin:0 auto;padding:0 28px}
.brand{display:flex;align-items:center;gap:9px;font-family:'Source Serif 4',serif;font-weight:600;font-size:16px;color:var(--text);text-decoration:none}
.brand .d{width:9px;height:9px;border-radius:50%;background:var(--ai);box-shadow:0 0 0 3px color-mix(in srgb,var(--ai) 22%,transparent)}
nav{display:flex;gap:16px;font-size:13.5px;align-items:center}
nav a{color:var(--muted);text-decoration:none}
nav a:hover{color:var(--text)}
.theme-toggle{display:flex;align-items:center;justify-content:center;margin-left:6px;width:32px;height:32px;border-radius:8px;background:var(--surface2);cursor:pointer;border:1px solid var(--border);user-select:none;font-size:15px}
.theme-toggle:hover{background:var(--surface-hover)}
.tt-auto,.tt-light{display:none}.tt-dark{display:inline}
html[data-theme-mode="auto"] .tt-dark{display:none}html[data-theme-mode="auto"] .tt-auto{display:inline}
html[data-theme-mode="light"] .tt-dark{display:none}html[data-theme-mode="light"] .tt-light{display:inline}
.wrap{max-width:760px;margin:0 auto;padding:0 28px}
header{padding:46px 0 24px}
.kick{display:inline-block;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--ai);border:1px solid color-mix(in srgb,var(--ai) 38%,transparent);background:color-mix(in srgb,var(--ai) 9%,transparent);border-radius:999px;padding:4px 11px;margin-bottom:14px}
h1{font-family:'Source Serif 4',serif;font-size:32px;font-weight:600;margin-bottom:8px}
p.sub{color:var(--muted);font-size:15px;max-width:560px}
.list{padding:10px 0 50px}
a.edrow{display:flex;align-items:center;gap:14px;text-decoration:none;color:var(--text);background:var(--surface);border:1px solid var(--border);border-radius:13px;padding:16px 18px;margin-bottom:10px;transition:border-color .18s,background .18s}
a.edrow:hover{border-color:color-mix(in srgb,var(--ai) 40%,transparent);background:var(--surface2)}
.eddate{font-family:'Source Serif 4',serif;font-size:17px;font-weight:600}
.edmeta{font-size:12.5px;color:var(--muted)}
.edar{margin-left:auto;color:var(--ai);font-size:17px}
footer{padding:8px 0 44px;color:var(--muted);font-size:12.5px;text-align:center}
footer a{color:var(--ai);text-decoration:none}
</style>
</head>
<body>
<div class="topbar"><div class="in">
  <a class="brand" href="/"><span class="d"></span>AI&nbsp;Digest</a>
  <nav><a href="https://peterjaycox.com">Hub</a><a href="https://cyber.peterjaycox.com">Cyber</a>
  <div class="theme-toggle" role="button" tabindex="0" aria-label="Appearance" onclick="window.__aiTheme.cycle(event)"><span class="tt-auto">🌗</span><span class="tt-light">☀️</span><span class="tt-dark">🌙</span></div></nav>
</div></div>
<div class="wrap">
<header>
  <div class="kick">@@N@@</div>
  <h1>AI Digest — editions</h1>
  <p class="sub">Newest first. A daily read on artificial intelligence, with an Australian and New Zealand lens. Latest edition: @@NEWEST@@.</p>
</header>
<div class="list">
@@ROWS@@
</div>
<footer><a href="/">About the AI Digest</a></footer>
</div>
</body>
</html>
"""

if __name__ == "__main__":
    main()
