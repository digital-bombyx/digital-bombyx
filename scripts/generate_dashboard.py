#!/usr/bin/env python3
"""Build profile/dashboard.svg: one silk-moth themed card with live GitHub stats.

Run with GH_TOKEN (or GITHUB_TOKEN) set to fetch real data; without a token it
renders demo numbers so the layout can be checked locally:  py scripts/generate_dashboard.py
Standard library only.
"""
import base64
import datetime as dt
import json
import os
import random
import textwrap
import urllib.request
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "profile" / "dashboard.svg"
AVATAR = ROOT / "assets" / "avatar.jpg"

USER = os.environ.get("GH_USER", "digital-bombyx")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

# ── what the card says ──────────────────────────────────────────────────────
CONTACT = ("tg", "@db_mori")
ABOUT = [
    ("into", "privacy · cybersec · devops · automation"),
    ("os", "Windows 11 · CachyOS · debloated Android"),
]
# "source" is where stars come from (owner/repo); "role" adds a tag on the card
PROJECTS = [
    {"name": "Argus", "source": "Ray-lea/Argus", "role": "contributor", "lang": "Rust",
     "desc": "Fast, modern task manager for Windows, built with Rust and GPUI."},
    {"name": "OYO", "lang": "JavaScript",
     "desc": "Performance-focused YouTube userscript: less clutter, less CPU, full control."},
    {"name": "SSHagement", "lang": "Svelte",
     "desc": "Offline-first SSH client for Windows. No cloud, no accounts, no telemetry."},
    {"name": "Zapret2-RustGUI", "lang": "Rust",
     "desc": "Cozy Windows GUI for zapret2: one-click DPI bypass, strategy tests, tray."},
]
LANG_EXCLUDE = {"HTML", "CSS", "Batchfile", "Inno Setup", "NSIS"}

# ── palette (taken from the avatar) ─────────────────────────────────────────
BG, PANEL, LINE = "#171A10", "#1F2317", "#363D27"
CREAM, DIM = "#F3E3C3", "#A99E82"
SAGE, BUD, LEAF = "#9DB07F", "#C9E0A0", "#6E8B3D"
BROWN, AMBER = "#8B5A2B", "#D9A25B"
LANG_COLORS = [AMBER, SAGE, BROWN, BUD, LEAF, "#E8C9A0", "#5C6B48"]
HEAT = ["#262B1C", "#3F5228", LEAF, SAGE, BUD]

W, PAD = 840, 28
FONT = "'JetBrains Mono','Cascadia Code','Fira Code',Consolas,monospace"


# ── data ────────────────────────────────────────────────────────────────────
QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        name description isFork stargazerCount
        primaryLanguage { name }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } }
      }
    }
    contributionsCollection {
      totalCommitContributions totalPullRequestContributions
      totalIssueContributions restrictedContributionsCount
      contributionCalendar { totalContributions weeks { contributionDays { contributionCount date } } }
    }
  }
}"""


def project_query():
    parts = []
    for i, p in enumerate(PROJECTS):
        owner, name = p.get("source", f"{USER}/{p['name']}").split("/")
        parts.append(f'p{i}: repository(owner: "{owner}", name: "{name}") '
                     "{ stargazerCount primaryLanguage { name } }")
    return QUERY.rstrip()[:-1] + "\n  " + "\n  ".join(parts) + "\n}"


def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": project_query(), "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": "profile-dashboard"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    projects = [payload["data"].get(f"p{i}") or {} for i in range(len(PROJECTS))]
    u = payload["data"]["user"]
    cc = u["contributionsCollection"]
    repos = u["repositories"]["nodes"]
    langs = {}
    for repo in repos:
        if repo["isFork"]:
            continue
        for e in repo["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    days = [(d["date"], d["contributionCount"])
            for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    return {
        "stars": sum(r["stargazerCount"] for r in repos),
        "repos": u["repositories"]["totalCount"],
        "followers": u["followers"]["totalCount"],
        "commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "prs": cc["totalPullRequestContributions"],
        "issues": cc["totalIssueContributions"],
        "total": cc["contributionCalendar"]["totalContributions"],
        "langs": langs,
        "days": days,
        "projects": projects,
    }


def demo():
    rnd = random.Random(7)
    today = dt.date.today()
    start = today - dt.timedelta(days=today.weekday() + 1 + 52 * 7)
    days = []
    d = start
    while d <= today:
        busy = rnd.random() < 0.55
        days.append((d.isoformat(), rnd.choice([1, 2, 3, 4, 6, 9, 14]) if busy else 0))
        d += dt.timedelta(days=1)
    return {
        "stars": 42, "repos": 11, "followers": 17, "commits": 612, "prs": 9, "issues": 14,
        "total": sum(c for _, c in days),
        "langs": {"Python": 420000, "Rust": 310000, "PowerShell": 150000, "C++": 90000,
                  "TypeScript": 60000, "Svelte": 40000, "JavaScript": 20000},
        "days": days,
        "projects": [{"stargazerCount": s} for s in (1200, 12, 2, 1)],
    }


def streaks(days):
    longest = run = 0
    for _, c in days:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current = 0
    rev = list(reversed(days))
    if rev and rev[0][1] == 0:  # today may still be empty
        rev = rev[1:]
    for _, c in rev:
        if not c:
            break
        current += 1
    return current, longest


# ── svg helpers ─────────────────────────────────────────────────────────────
def t(x, y, s, size=13, fill=CREAM, weight="normal", anchor="start", extra=""):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'text-anchor="{anchor}" {extra}>{escape(str(s))}</text>')


def icon(kind, x, y, color=AMBER, scale=1.0):
    """16×16 line/solid icons drawn in SVG, so they look the same everywhere."""
    s = f'stroke="{color}" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round"'
    f = f'fill="{color}"'
    body = {
        "star": f'<path {f} d="M8 1.3l2 4.2 4.6.6-3.4 3.2.9 4.6L8 11.6l-4.1 2.3.9-4.6L1.4 6.1 6 5.5z"/>',
        "repo": f'<path {s} d="M3.5 13.5V3a1.5 1.5 0 0 1 1.5-1.5h7.5v10H5a1.5 1.5 0 0 0-1.5 1.5 1.5 1.5 0 0 0 1.5 1.5h7.5"/>',
        "heart": f'<path {f} d="M8 14.2S1.6 10.4 1.6 6A3.3 3.3 0 0 1 8 4.4 3.3 3.3 0 0 1 14.4 6C14.4 10.4 8 14.2 8 14.2z"/>',
        "commit": f'<circle cx="8" cy="8" r="3" {s}/><path {s} d="M1 8h4M11 8h4"/>',
        "pr": (f'<circle cx="4" cy="3.5" r="1.8" {s}/><circle cx="4" cy="12.5" r="1.8" {s}/>'
               f'<circle cx="12" cy="12.5" r="1.8" {s}/><path {s} d="M4 5.3v5.4M12 10.7V6a2 2 0 0 0-2-2H7.5M9 2.5 7.5 4 9 5.5"/>'),
        "issue": f'<circle cx="8" cy="8" r="6.2" {s}/><circle cx="8" cy="8" r="1.6" {f}/>',
        "flame": f'<path {f} d="M8.4 1c.4 2.6 4.1 4.3 4.1 8.2A4.5 4.5 0 0 1 3.5 9.6c0-1.9 1-3.1 2-3.9.1 1.5.8 2.4 1.7 2.7C6.6 5.9 7.3 3.3 8.4 1z"/>',
        "trophy": f'<path {s} d="M4.5 2h7v3.5a3.5 3.5 0 0 1-7 0zM4.5 3.5H2.2a2.3 2.3 0 0 0 2.6 3M11.5 3.5h2.3a2.3 2.3 0 0 1-2.6 3M8 9v3M5 14.5h6"/>',
        "tg": f'<path {f} d="M15.2 1.6.9 7.2c-.7.3-.7 1.2 0 1.4l3.6 1.1 1.4 4.3c.2.6.9.7 1.3.3l2-1.9 3.6 2.7c.5.4 1.2.1 1.3-.5l2.3-11.9c.1-.8-.6-1.4-1.2-1.1zM6 9.4l6.6-4.9-5.4 5.6-.3 2.5z"/>',
        "moth": (f'<path d="M7.4 7.2C5 3.2 1.4 2.6.8 4.6c-.6 2 1.8 4 6.2 3.8z" fill="{CREAM}"/>'
                 f'<path d="M8.6 7.2c2.4-4 6-4.6 6.6-2.6.6 2-1.8 4-6.2 3.8z" fill="{CREAM}"/>'
                 f'<path d="M7.2 8.6c-3.4.4-4.8 3-3.4 4.2 1.2 1 3-.6 3.6-3.4z" fill="{AMBER}"/>'
                 f'<path d="M8.8 8.6c3.4.4 4.8 3 3.4 4.2-1.2 1-3-.6-3.6-3.4z" fill="{AMBER}"/>'
                 f'<rect x="7.1" y="5.6" width="1.8" height="7" rx=".9" fill="{BROWN}"/>'
                 f'<path d="M7.6 5.8C7 3.6 5.6 2.2 4.4 1.8M8.4 5.8C9 3.6 10.4 2.2 11.6 1.8" stroke="{BROWN}" '
                 f'stroke-width="1" fill="none" stroke-linecap="round"/>'),
    }[kind]
    return f'<g transform="translate({x:.1f} {y:.1f}) scale({scale})">{body}</g>'


def heading(y, label):
    w = len(label) * 7.8 + 30
    return (f'<g class="f" style="animation-delay:{0.2 + y / 2500:.2f}s">'
            f'{t(PAD, y, "[ " + label + " ]", 13, AMBER, "bold")}'
            f'<line x1="{PAD + w}" y1="{y - 4}" x2="{W - PAD}" y2="{y - 4}" stroke="{LINE}" stroke-dasharray="2 5"/>'
            f'</g>')


def fade(delay):
    return f'class="f" style="animation-delay:{delay:.2f}s"'


def build(data):
    o = []
    y = 0

    # title bar
    o.append(f'<rect x="1" y="1" width="{W - 2}" height="42" rx="17" fill="{PANEL}"/>'
             f'<rect x="1" y="30" width="{W - 2}" height="13" fill="{PANEL}"/>'
             f'<line x1="1" y1="43" x2="{W - 1}" y2="43" stroke="{LINE}"/>')
    for i, c in enumerate((AMBER, BUD, SAGE)):
        o.append(f'<circle cx="{26 + i * 20}" cy="22" r="6" fill="{c}"/>')
    o.append(t(W / 2, 27, f"{USER}@silk: ~/profile", 13, DIM, anchor="middle"))
    o.append(f'<circle cx="{W - 112}" cy="22" r="4" fill="{SAGE}"><animate attributeName="opacity" '
             f'values="1;.25;1" dur="2s" repeatCount="indefinite"/></circle>')
    o.append(t(W - 100, 26, "spinning", 12, SAGE))

    # header: avatar + whoami
    cx, cy, r = 150, 178, 96
    o.append(f'<circle cx="{cx}" cy="{cy}" r="{r + 14}" fill="none" stroke="{SAGE}" stroke-width="1.5" '
             f'stroke-dasharray="3 9" opacity=".7"><animateTransform attributeName="transform" type="rotate" '
             f'from="0 {cx} {cy}" to="360 {cx} {cy}" dur="60s" repeatCount="indefinite"/></circle>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="{r + 4}" fill="none" stroke="{BROWN}" stroke-width="3"/>')
    if AVATAR.exists():
        b64 = base64.b64encode(AVATAR.read_bytes()).decode()
        o.append(f'<image href="data:image/jpeg;base64,{b64}" x="{cx - r}" y="{cy - r}" '
                 f'width="{2 * r}" height="{2 * r}" clip-path="url(#ava)"/>')
    else:
        o.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{SAGE}"/>')

    x0, ny = 300, 160  # ny: baseline of the big name
    o.append(t(x0, ny - 42, f"$ whoami", 14, SAGE))
    name_w = len(USER) * 20.5
    steps = ";".join(f"{name_w * i / len(USER):.1f}" for i in range(len(USER) + 1))
    o.append(f'<clipPath id="type"><rect x="{x0}" y="{ny - 38}" height="48" width="0">'
             f'<animate attributeName="width" values="{steps}" dur="1.3s" begin="0.3s" '
             f'calcMode="discrete" fill="freeze"/></rect></clipPath>')
    o.append(f'<g clip-path="url(#type)">{t(x0, ny, USER, 34, CREAM, "bold")}</g>')
    o.append(f'<rect x="{x0 + name_w + 4}" y="{ny - 28}" width="14" height="32" fill="{AMBER}">'
             f'<animate attributeName="opacity" values="1;0;1" dur="1s" repeatCount="indefinite"/></rect>')
    o.append(f'<g {fade(1.4)}>{icon("tg", x0, ny + 13, AMBER)}'
             f'{t(x0 + 22, ny + 28, CONTACT[1], 15, AMBER, "bold")}</g>')
    for i, (k, v) in enumerate(ABOUT):
        yy = ny + 70 + i * 26
        o.append(f'<g {fade(1.7 + i * 0.25)}>{t(x0, yy, k.ljust(6), 13, SAGE, "bold", extra="xml:space=\"preserve\"")}'
                 f'{t(x0 + 64, yy, v, 13, CREAM)}</g>')
    y = 312

    # projects
    o.append(heading(y, "SPUN SOLO & TOGETHER"))
    y += 18
    cw, ch, gap = (W - 2 * PAD - 16) / 2, 92, 16
    for i, p in enumerate(PROJECTS):
        info = data["projects"][i] if i < len(data["projects"]) else {}
        name, desc = p["name"], p["desc"]
        lang = p.get("lang") or (info.get("primaryLanguage") or {}).get("name") or ""
        stars = info.get("stargazerCount")
        px = PAD + (i % 2) * (cw + gap)
        py = y + (i // 2) * (ch + 14)
        lines = textwrap.wrap(desc, 50)[:2]
        if len(textwrap.wrap(desc, 50)) > 2:
            lines[-1] = lines[-1][:47].rstrip() + "…"
        g = [f'<rect x="{px}" y="{py}" width="{cw:.1f}" height="{ch}" rx="10" fill="{PANEL}" stroke="{LINE}"/>',
             f'<rect x="{px}" y="{py + 14}" width="3" height="22" rx="1.5" fill="{AMBER}"/>',
             t(px + 16, py + 30, name, 15, CREAM, "bold")]
        if p.get("role"):
            rx, rw = px + 24 + len(name) * 9.1, len(p["role"]) * 6.6 + 16
            g.append(f'<rect x="{rx:.1f}" y="{py + 16}" width="{rw:.1f}" height="19" rx="9.5" '
                     f'fill="{SAGE}" fill-opacity=".15" stroke="{SAGE}" stroke-opacity=".5"/>'
                     + t(rx + rw / 2, py + 29.5, p["role"], 11, SAGE, anchor="middle"))
        if stars is not None:
            sv = f"{stars / 1000:.1f}k" if stars >= 1000 else str(stars)
            g.append(t(px + cw - 14, py + 30, sv, 13, AMBER, "bold", anchor="end"))
            g.append(icon("star", px + cw - 32 - len(sv) * 7.8, py + 19, AMBER))
        for j, ln in enumerate(lines):
            g.append(t(px + 16, py + 52 + j * 17, ln, 12, DIM))
        g.append(f'<circle cx="{px + cw - 14 - len(lang) * 7 - 10:.1f}" cy="{py + ch - 14}" r="4" fill="{SAGE}"/>')
        g.append(t(px + cw - 14, py + ch - 10, lang, 11, SAGE, anchor="end"))
        o.append(f'<g {fade(2.3 + i * 0.12)}>{"".join(g)}</g>')
    y += -(-len(PROJECTS) // 2) * (ch + 14) + 30

    # metrics
    o.append(heading(y, "METRICS · LAST 12 MONTHS"))
    y += 18
    cur, longest = streaks(data["days"])
    stats = [("star", "stars", data["stars"]), ("repo", "public repos", data["repos"]),
             ("heart", "followers", data["followers"]), ("commit", "commits", data["commits"]),
             ("pr", "pull requests", data["prs"]), ("issue", "issues", data["issues"]),
             ("flame", "current streak", f"{cur}d"), ("trophy", "best streak", f"{longest}d")]
    ph = 168
    o.append(f'<g {fade(3.2)}><rect x="{PAD}" y="{y}" width="{cw:.1f}" height="{ph}" rx="10" '
             f'fill="{PANEL}" stroke="{LINE}"/>')
    for i, (ic, label, val) in enumerate(stats):
        sx = PAD + 18 + (i // 4) * (cw / 2)
        sy = y + 38 + (i % 4) * 33
        o.append(icon(ic, sx, sy - 12, AMBER))
        o.append(t(sx + 24, sy, label, 12, DIM))
        o.append(t(sx + cw / 2 - 34, sy, val, 13, CREAM, "bold", "end"))
    o.append("</g>")

    lx = PAD + cw + gap
    langs = sorted(((k, v) for k, v in data["langs"].items() if k not in LANG_EXCLUDE),
                   key=lambda kv: -kv[1])
    total = sum(v for _, v in langs) or 1
    top = langs[:6]
    rest = total - sum(v for _, v in top)
    if rest > 0:
        top.append(("other", rest))
    o.append(f'<g {fade(3.4)}><rect x="{lx:.1f}" y="{y}" width="{cw:.1f}" height="{ph}" rx="10" '
             f'fill="{PANEL}" stroke="{LINE}"/>')
    o.append(t(lx + 18, y + 30, "languages", 12, DIM))
    bx, bw = lx + 18, cw - 36
    o.append(f'<clipPath id="bar"><rect x="{bx:.1f}" y="{y + 42}" width="{bw:.1f}" height="10" rx="5"/></clipPath>'
             f'<g clip-path="url(#bar)">')
    acc = 0.0
    for i, (name, v) in enumerate(top):
        seg = bw * v / total
        o.append(f'<rect x="{bx + acc:.1f}" y="{y + 42}" width="{seg + 0.5:.1f}" height="10" '
                 f'fill="{LANG_COLORS[i % len(LANG_COLORS)]}"/>')
        acc += seg
    o.append("</g>")
    for i, (name, v) in enumerate(top):
        lx2 = bx + (i % 2) * (bw / 2 + 8)
        ly = y + 78 + (i // 2) * 21
        o.append(f'<circle cx="{lx2 + 5:.1f}" cy="{ly - 4}" r="5" fill="{LANG_COLORS[i % len(LANG_COLORS)]}"/>')
        o.append(t(lx2 + 16, ly, name, 12, CREAM))
        o.append(t(lx2 + bw / 2 - 8, ly, f"{100 * v / total:.1f}%", 12, DIM, anchor="end"))
    o.append("</g>")
    y += ph + 40

    # contribution calendar
    o.append(heading(y, f"SILK SPUN · {data['total']} CONTRIBUTIONS"))
    y += 30
    days = data["days"]
    first = dt.date.fromisoformat(days[0][0])
    offset = (first.weekday() + 1) % 7  # GitHub weeks start on Sunday
    cells = len(days) + offset
    weeks = -(-cells // 7)
    step = 13.6
    gx = (W - weeks * step) / 2
    peak = max((c for _, c in days), default=1) or 1
    last_month = None
    for idx, (date, c) in enumerate(days):
        k = idx + offset
        wk, wd = divmod(k, 7)
        d = dt.date.fromisoformat(date)
        if wd == 0 and d.month != last_month and d.day <= 7:
            o.append(t(gx + wk * step, y - 6, d.strftime("%b"), 10, DIM))
            last_month = d.month
        lvl = 0 if c == 0 else min(4, 1 + int(3 * c / peak + 0.35))
        o.append(f'<rect x="{gx + wk * step:.1f}" y="{y + wd * step:.1f}" width="10.5" height="10.5" rx="2.5" '
                 f'fill="{HEAT[lvl]}" class="f" style="animation-delay:{3.6 + wk * 0.025:.2f}s">'
                 f'<title>{date}: {c}</title></rect>')
    y += 7 * step + 22
    lg = W - PAD - 5 * 14 - 34
    o.append(t(lg - 8, y + 9, "less", 10, DIM, anchor="end"))
    for i, c in enumerate(HEAT):
        o.append(f'<rect x="{lg + i * 14}" y="{y}" width="10.5" height="10.5" rx="2.5" fill="{c}"/>')
    o.append(t(lg + 5 * 14 + 4, y + 9, "more", 10, DIM))
    o.append(icon("moth", PAD, y - 4, scale=1.25))
    o.append(t(PAD + 28, y + 9, "quiet code, fluffy results", 11, SAGE))
    y += 34

    # footer
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    o.append(f'<line x1="{PAD}" y1="{y}" x2="{W - PAD}" y2="{y}" stroke="{LINE}"/>')
    o.append(t(PAD, y + 22, f"last spun {stamp}", 11, DIM))
    o.append(t(W - PAD, y + 22, "auto-updated by GitHub Actions", 11, DIM, anchor="end"))
    H = y + 38

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">
<title>{escape(USER)} — profile dashboard</title>
<defs>
  <clipPath id="ava"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>
  <pattern id="silk" width="24" height="24" patternUnits="userSpaceOnUse">
    <circle cx="2" cy="2" r="1" fill="{SAGE}" opacity=".09"/>
  </pattern>
  <radialGradient id="glow" cx="18%" cy="14%" r="45%">
    <stop offset="0" stop-color="{SAGE}" stop-opacity=".16"/><stop offset="1" stop-color="{SAGE}" stop-opacity="0"/>
  </radialGradient>
</defs>
<style>
  .f {{ opacity: 0; animation: in .5s ease-out forwards; }}
  @keyframes in {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: none; }} }}
  @media (prefers-reduced-motion: reduce) {{ .f {{ animation: none; opacity: 1; }} }}
</style>
<rect width="{W}" height="{H}" rx="18" fill="{BG}"/>
<rect width="{W}" height="{H}" rx="18" fill="url(#silk)"/>
<rect width="{W}" height="{H}" rx="18" fill="url(#glow)"/>
{chr(10).join(o)}
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="17" fill="none" stroke="{SAGE}" stroke-opacity=".55" stroke-width="1.5"/>
</svg>
"""


def main():
    data = fetch() if TOKEN else demo()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(data), encoding="utf-8")
    print(f"wrote {OUT} ({'live' if TOKEN else 'demo'} data)")


if __name__ == "__main__":
    main()
