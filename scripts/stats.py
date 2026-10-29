#!/usr/bin/env python3
"""Render assets/stats.svg and assets/langs.svg in the rice palette.

Runs in GitHub Actions (GITHUB_TOKEN) or locally (`gh auth token`).
"""
import datetime as dt
import json
import os
import subprocess
import urllib.request
from pathlib import Path

USER = "332mindset"
OUT = Path(__file__).resolve().parent.parent / "assets"

BG, FG, DIM, MUTED = "#18181b", "#e6e6ea", "#8b8b91", "#2a2a30"
RED, LAV = "#e0444c", "#b4c3ff"
FONT = "JetBrains Mono,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

# kept in the same monochrome/red/lavender family instead of linguist colors
LANG_COLORS = [RED, LAV, "#e6e6ea", "#f2a2a6", "#7f8ccc", "#8b8b91", "#55555c"]
SKIP_LANGS = {"HTML", "CSS"}  # markup inflates landing-page repos


def token():
    return os.environ.get("GITHUB_TOKEN") or subprocess.check_output(
        ["gh", "auth", "token"], text=True).strip()


def api(path, body=None):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"bearer {token()}",
                 "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch():
    q = """query($u:String!){user(login:$u){
      followers{totalCount}
      repositories(ownerAffiliations:OWNER,isFork:false,privacy:PUBLIC,first:100){
        totalCount nodes{stargazerCount
          languages(first:12,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}}}}
      contributionsCollection{contributionCalendar{totalContributions
        weeks{contributionDays{date contributionCount}}}}}}"""
    return api("/graphql", {"query": q, "variables": {"u": USER}})["data"]["user"]


def streaks(days):
    today = dt.date.today().isoformat()
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] else 0
        longest = max(longest, run)
    current = 0
    for d in reversed(days):
        if d["date"] == today and not d["contributionCount"]:
            continue  # today isn't over yet
        if not d["contributionCount"]:
            break
        current += 1
    return current, longest


def frame(w, h, title, body):
    dots = "".join(f'<circle cx="{24 + i * 16}" cy="22" r="5" fill="{c}"/>'
                   for i, c in enumerate((RED, LAV, MUTED)))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{FONT}">
<style>.f{{animation:in .6s ease-out both}}@keyframes in{{from{{opacity:0}}}}</style>
<rect width="{w}" height="{h}" rx="14" fill="{BG}"/>
<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="13.5" fill="none" stroke="{LAV}" stroke-opacity=".18"/>
{dots}<text x="{w / 2}" y="26" text-anchor="middle" fill="{DIM}" font-size="12">{title}</text>
<line x1="0" y1="44" x2="{w}" y2="44" stroke="{MUTED}"/>
{body}
</svg>
'''


def stats_svg(u):
    cal = u["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    cur, best = streaks(days)
    stars = sum(r["stargazerCount"] for r in u["repositories"]["nodes"])
    rows = [("contributions", cal["totalContributions"], "past year"),
            ("current streak", cur, "days"), ("longest streak", best, "days"),
            ("public repos", u["repositories"]["totalCount"], ""),
            ("stars earned", stars, ""), ("followers", u["followers"]["totalCount"], "")]
    body = [f'<text x="24" y="74" fill="{RED}" font-size="13">❯</text>'
            f'<text x="40" y="74" fill="{FG}" font-size="13">gh stats {USER}</text>']
    for i, (k, v, unit) in enumerate(rows):
        y = 104 + i * 26
        body.append(f'<g class="f" style="animation-delay:{.15 * i:.2f}s">'
                    f'<text x="24" y="{y}" fill="{LAV}" font-size="13">{k}</text>'
                    f'<text x="200" y="{y}" fill="{FG}" font-size="13" font-weight="700">{v}</text>'
                    f'<text x="250" y="{y}" fill="{DIM}" font-size="12">{unit}</text></g>')
    # last ~6 months as a mini heatmap
    weeks = cal["weeks"][-23:]
    peak = max((d["contributionCount"] for w in weeks for d in w["contributionDays"]), default=0) or 1
    cells = []
    for wi, w in enumerate(weeks):
        for d in w["contributionDays"]:
            wd = dt.date.fromisoformat(d["date"]).weekday()
            n = d["contributionCount"]
            op = 0 if not n else .3 + .7 * n / peak
            fill = f'fill="{RED}" fill-opacity="{op:.2f}"' if n else f'fill="{MUTED}"'
            cells.append(f'<rect x="{356 + wi * 13}" y="{98 + ((wd + 1) % 7) * 13}" width="10" height="10" rx="2" {fill}/>')
    body.append(f'<g class="f" style="animation-delay:.9s">{"".join(cells)}'
                f'<text x="356" y="210" fill="{DIM}" font-size="11">last 6 months</text></g>')
    return frame(680, 260, "~ stats", "\n".join(body))


def langs_svg(u):
    totals = {}
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            if name not in SKIP_LANGS:
                totals[name] = totals.get(name, 0) + e["size"]
    top = sorted(totals.items(), key=lambda kv: -kv[1])[:6]
    whole = sum(v for _, v in top) or 1
    body, x = [f'<clipPath id="bar"><rect x="24" y="66" width="632" height="10" rx="5"/></clipPath><g clip-path="url(#bar)">'], 24.0
    for i, (_, v) in enumerate(top):
        w = 632 * v / whole
        body.append(f'<rect x="{x:.1f}" y="66" width="{w:.1f}" height="10" fill="{LANG_COLORS[i]}"/>')
        x += w
    body.append('</g>')
    for i, (name, v) in enumerate(top):
        col, row = i % 2, i // 2
        bx, y = 24 + col * 330, 112 + row * 34
        pct = 100 * v / whole
        body.append(f'<g class="f" style="animation-delay:{.12 * i:.2f}s">'
                    f'<circle cx="{bx + 5}" cy="{y - 4}" r="5" fill="{LANG_COLORS[i]}"/>'
                    f'<text x="{bx + 18}" y="{y}" fill="{FG}" font-size="13">{name}</text>'
                    f'<text x="{bx + 300}" y="{y}" text-anchor="end" fill="{DIM}" font-size="13">{pct:.1f}%</text>'
                    f'<rect x="{bx + 18}" y="{y + 8}" width="282" height="3" rx="1.5" fill="{MUTED}"/>'
                    f'<rect x="{bx + 18}" y="{y + 8}" width="{282 * pct / 100:.1f}" height="3" rx="1.5" fill="{LANG_COLORS[i]}"/></g>')
    return frame(680, 216, "~ languages", "\n".join(body))


if __name__ == "__main__":
    user = fetch()
    (OUT / "stats.svg").write_text(stats_svg(user))
    (OUT / "langs.svg").write_text(langs_svg(user))
