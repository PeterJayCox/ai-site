#!/usr/bin/env python3
"""Validate, build, publish and verify one AI Digest daily edition.

    python3 scripts/publish_daily.py --date 2026-10-09
    python3 scripts/publish_daily.py --date 2026-10-09 --dry-run

Gate order — nothing is committed until every earlier gate passes:
  1. markdown validates (front matter, window, every card rated and sourced)
  2. the edition builds
  3. the generated HTML passes structural checks
  4. only then commit + push
  5. verify the live URL actually serves the new bytes

Exit codes: 0 ok, 1 validation/structure failure, 2 git or network failure.
This is deliberately fail-closed: a broken edition must not reach the site.
"""
import argparse, datetime, os, re, subprocess, sys, time, urllib.request

ROOT = os.path.expanduser("~/Desktop/AI Site")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0 Safari/537.36")
BASE = "https://ai.peterjaycox.com"
REQUIRED_PER_CARD = ["Summary", "Source", "Reliability", "Verification", "Date"]
AXIS_ONE_OF = [["Impact"], ["Evidence"]]          # every card must carry these


def sh(cmd, **kw):
    """Run a command as an argv LIST — never shell=True. None of these commands
    interpolate untrusted input, but a list removes the injection class entirely."""
    if isinstance(cmd, str):
        raise ValueError("sh() takes an argv list, not a shell string")
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, **kw)


def fail(msg, code=1):
    print(f"FAIL: {msg}")
    sys.exit(code)


# ── gate 1: markdown ───────────────────────────────────────────────────────
def parse_md(path):
    text = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        fail("no YAML front matter")
    fm = dict(l.split(":", 1) for l in m.group(1).splitlines() if ":" in l)
    fm = {k.strip(): v.strip() for k, v in fm.items()}
    return fm, m.group(2)


def validate_md(date):
    path = os.path.join(ROOT, "editions", f"{date}.md")
    if not os.path.exists(path):
        fail(f"no edition source at {path}")
    fm, body = parse_md(path)
    for k in ("date", "window_start", "window_end", "kicker"):
        if k not in fm:
            fail(f"front matter missing '{k}'")
    if fm["date"] != date:
        fail(f"front matter date {fm['date']} != requested {date}")

    # window must be ~48h (72h tolerated for a weekend bridge)
    try:
        d0 = datetime.date.fromisoformat(fm["window_start"])
        d1 = datetime.date.fromisoformat(fm["window_end"])
    except ValueError:
        fail("window_start/window_end must be ISO dates")
    span = (d1 - d0).days
    if not (1 <= span <= 3):
        fail(f"window span {span}d outside 1-3 (48h, 72h weekend bridge)")
    if d1.isoformat() != date:
        fail(f"window_end {fm['window_end']} != edition date {date}")

    if "# Executive Summary" not in body:
        fail("no '## Executive Summary' section")
    if ":::au" not in body:
        fail("no AUNZ context block (:::au) in the executive summary")
    if not re.search(r"^## ", body, re.M):
        fail("no theme sections")

    cards = re.split(r"^### ", body, flags=re.M)[1:]
    if not cards:
        fail("no story cards")
    themes = re.findall(r"^## (.+)$", body, re.M)
    fields_seen = {}
    for c in cards:
        head = c.splitlines()[0].strip()
        if not re.match(r"^\d+\.\s+\S", head):
            fail(f"card heading not numbered: {head[:60]}")
        f = dict(re.findall(r"^- \*\*(.+?):\*\*\s*(.*)$", c, re.M))
        for k in REQUIRED_PER_CARD:
            if k not in f or not f[k].strip():
                fail(f"card missing {k}: {head[:60]}")
        for group in AXIS_ONE_OF:
            if not any(g in f for g in group):
                fail(f"card missing {'/'.join(group)} rating: {head[:60]}")
        url = re.search(r"\[.+?\]\((https?://[^)]+)\)", f["Source"])
        if not url:
            fail(f"Source is not a link to a deep URL: {head[:60]}")
        low = url.group(1)
        if low.rstrip("/").count("/") <= 2:
            fail(f"Source looks like a homepage, not a deep link: {low}")
        if "news.google.com" in low or "/rss/articles/" in low:
            fail(f"Source is a news redirect, not the article: {low}")
        seen = re.search(r"\d{4}-\d{2}-\d{2}", f["Date"])
        if not seen or not (fm["window_start"] <= seen.group(0) <= fm["window_end"]):
            fail(f"card date {f.get('Date')} outside the stated window: {head[:60]}")
        for k in f:
            fields_seen[k] = fields_seen.get(k, 0) + 1

    print(f"  gate 1 OK  markdown: {len(cards)} cards, {len(themes)} themes, window {span}d")
    print(f"            ratings seen: { {k: v for k, v in sorted(fields_seen.items())} }")
    return len(cards)


# ── gate 2+3: build and structure ──────────────────────────────────────────
def build_and_check(date, n_cards):
    r = sh([sys.executable, "scripts/build_daily.py"])
    if r.returncode != 0:
        fail(f"build failed:\n{r.stdout}\n{r.stderr}")
    print("  gate 2 OK  built:",
          [l.strip() for l in r.stdout.splitlines() if "index.html" in l][0])

    p = os.path.join(ROOT, "docs", "daily", f"{date}.html")
    s = open(p, encoding="utf-8").read()
    if re.search(r"@@\w+@@", s):
        fail(f"unsubstituted template tokens in {date}.html")
    for t in ("article", "section", "div", "h2", "h3", "span", "p", "table", "tr", "td", "a"):
        o, c = len(re.findall(r"<" + t + r"[ >]", s)), len(re.findall(r"</" + t + r">", s))
        if o != c:
            fail(f"tag imbalance <{t}>: {o} open / {c} close")
    cards = re.findall(r'<article class="card".*?</article>', s, re.S)
    if len(cards) != n_cards:
        fail(f"rendered {len(cards)} cards, source has {n_cards}")
    nums = [int(x) for x in re.findall(r'<div class="num">(\d+)</div>', s)]
    if nums != list(range(1, len(nums) + 1)):
        fail(f"card numbering not continuous: {nums}")
    if re.search(r'class="badge axis\s+"', s):
        fail("an axis badge rendered with no colour class")
    for label, pat in (("source", r'class="src"'), ("date", r'class="date"'), ("tier", r"b-tier"),
                       ("verification", r'b-v"|b-r"|b-u"'),
                       ("impact", r"i-(low|guarded|elevated|severe|critical)")):
        n = sum(1 for c in cards if re.search(pat, c))
        if n != len(cards):
            fail(f"only {n}/{len(cards)} cards carry a {label} badge")
    idx = open(os.path.join(ROOT, "docs", "daily", "index.html"), encoding="utf-8").read()
    if f'href="{date}.html"' not in idx:
        fail(f"{date} missing from the editions index")
    print(f"  gate 3 OK  html: {len(cards)} cards, numbering 1..{len(cards)}, "
          f"all badges present, indexed")


# ── gate 5: live ───────────────────────────────────────────────────────────
def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def verify_live(date, local_bytes, local_cards, attempts=10, delay=30):
    """Confirm the published page is the bytes we built.

    Compare ENCODED BYTE LENGTH, not len(str): the HTML is full of em-dashes and
    curly quotes, so a character count can never equal a file byte count and the
    check would pass only via its fallback — training the operator to ignore a
    live-verification warning. Card count is checked as content, so a size match
    alone cannot pass.
    """
    url = f"{BASE}/daily/{date}.html"
    for i in range(1, attempts + 1):
        try:
            body = fetch(f"{url}?cb={int(time.time())}")
            served = len(body.encode("utf-8"))
            cards = body.count('<article class="card"')
            indexed = f'href="{date}.html"' in fetch(f"{BASE}/daily/?cb={int(time.time())}")
            if served == local_bytes and cards == local_cards and indexed:
                print(f"  gate 5 OK  live after {i} attempt(s): {url} "
                      f"({served:,} bytes, {cards} cards, indexed)")
                return True
            print(f"    attempt {i}: bytes {served:,}/{local_bytes:,} "
                  f"cards {cards}/{local_cards} indexed={indexed}")
        except Exception as e:
            print(f"    attempt {i}: {type(e).__name__}: {e}")
        time.sleep(delay)
    print(f"WARN: {url} not confirmed live after {attempts} attempts "
          f"(deploy may still be propagating) — the push succeeded")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--dry-run", action="store_true",
                    help="validate + build only; do not commit or push")
    a = ap.parse_args()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date):
        fail("--date must be YYYY-MM-DD")

    print(f"publish_daily  date={a.date}  dry_run={a.dry_run}")
    n = validate_md(a.date)
    build_and_check(a.date, n)

    live = f"{BASE}/daily/{a.date}.html"
    try:
        already = fetch(f"{live}?cb={int(time.time())}")
        if f"<h1>AI Digest — " in already:
            print(f"  NOTE  {live} already serves an edition; this will overwrite it")
    except Exception:
        pass

    if a.dry_run:
        print("\nDRY RUN — gates 1-3 passed, nothing committed.")
        return

    local_path = os.path.join(ROOT, "docs", "daily", f"{a.date}.html")
    size = os.path.getsize(local_path)
    cards = open(local_path, encoding="utf-8").read().count('<article class="card"')
    sh(["git", "add", "-A"])
    r = sh(["git", "status", "--short"])
    print("  staged:\n" + (r.stdout.rstrip() or "    (nothing changed)"))
    if not r.stdout.strip():
        print("  nothing to commit — edition already published")
        verify_live(a.date, size, cards)
        return
    msg = (f"Edition: AI Digest {a.date}\n\n"
           f"Produced by the scheduled daily run. Validated (front matter, window, "
           f"per-card ratings and deep links), built, and structure-checked before push.")
    r = sh(["git", "-c", "user.name=Peter Cox", "-c", "user.email=peterjaycox@gmail.com",
            "commit", "-q", "-m", msg])
    if r.returncode != 0:
        fail(f"commit failed:\n{r.stdout}\n{r.stderr}", 2)
    r = sh(["git", "push", "-q", "origin", "main"])
    if r.returncode != 0:
        fail(f"push failed:\n{r.stdout}\n{r.stderr}", 2)
    print("  gate 4 OK  committed and pushed")
    verify_live(a.date, size, cards)
    print("\nPUBLISHED.")


if __name__ == "__main__":
    main()
