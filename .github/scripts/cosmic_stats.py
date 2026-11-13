"""Render a cosmos-themed GitHub telemetry card (stats + top languages) as SVG.

Usage: GITHUB_TOKEN=... python cosmic_stats.py <username> <output.svg>
       python cosmic_stats.py --mock <output.svg>   # render with sample data
Stdlib only, so it runs on a bare GitHub Actions runner.
"""
import json
import os
import random
import sys
import urllib.request
from collections import Counter
from html import escape

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar { totalContributions }
    }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

SKIP_LANGS = {"Jupyter Notebook", "HTML", "CSS", "Dockerfile", "Shell", "PowerShell", "PLpgSQL"}


def fetch(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if "errors" in data:
        raise SystemExit(f"GraphQL error: {data['errors']}")
    u = data["data"]["user"]
    repos = u["repositories"]["nodes"]
    langs, colors = Counter(), {}
    for r in repos:
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            if name in SKIP_LANGS:
                continue
            langs[name] += e["size"]
            colors[name] = e["node"]["color"] or "#c77dff"
    cc = u["contributionsCollection"]
    return {
        "contributions": cc["contributionCalendar"]["totalContributions"],
        "commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "prs": u["pullRequests"]["totalCount"],
        "issues": u["issues"]["totalCount"],
        "repos": u["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "followers": u["followers"]["totalCount"],
        "langs": [(n, s, colors[n]) for n, s in langs.most_common(6)],
    }


def mock():
    return {
        "contributions": 742, "commits": 612, "prs": 38, "issues": 12,
        "repos": 34, "stars": 21, "followers": 40,
        "langs": [("TypeScript", 600, "#3178c6"), ("Python", 250, "#3572A5"),
                  ("JavaScript", 90, "#f1e05a"), ("C++", 30, "#f34b7d")],
    }


def render(s):
    W, H = 840, 240
    rnd = random.Random(42)  # deterministic starfield -> no diff noise
    stars = []
    for i in range(70):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        r = rnd.choice([0.5, 0.7, 0.9, 1.2])
        dur = rnd.uniform(2, 6)
        delay = rnd.uniform(0, 5)
        stars.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#fff" class="tw" '
            f'style="animation-duration:{dur:.1f}s;animation-delay:{delay:.1f}s"/>'
        )

    rows = [
        ("✦", "Contributions (last year)", s["contributions"]),
        ("☄", "Commits (last year)", s["commits"]),
        ("⇄", "Pull requests", s["prs"]),
        ("◎", "Issues", s["issues"]),
        ("🪐", "Public repos", s["repos"]),
        ("★", "Stars earned", s["stars"]),
    ]
    stat_svg = []
    for i, (icon, label, val) in enumerate(rows):
        y = 82 + i * 25
        stat_svg.append(
            f'<g>'
            f'<text x="36" y="{y}" class="icon">{icon}</text>'
            f'<text x="60" y="{y}" class="label">{escape(label)}</text>'
            f'<text x="370" y="{y}" class="val" text-anchor="end">{val:,}</text></g>'
        )

    total = sum(sz for _, sz, _ in s["langs"]) or 1
    bar, legend, x = [], [], 0.0
    bar_w = 360
    for i, (name, size, color) in enumerate(s["langs"]):
        w = bar_w * size / total
        bar.append(f'<rect x="{440 + x:.2f}" y="78" width="{w:.2f}" height="10" fill="{color}"/>')
        x += w
        col, row = i % 2, i // 2
        lx, ly = 440 + col * 185, 120 + row * 30
        legend.append(
            f'<g>'
            f'<circle cx="{lx + 6}" cy="{ly - 4}" r="5" fill="{color}"/>'
            f'<text x="{lx + 18}" y="{ly}" class="label">{escape(name)} '
            f'<tspan class="pct">{100 * size / total:.1f}%</tspan></text></g>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub telemetry">
<defs>
  <radialGradient id="neb1" cx="85%" cy="20%" r="60%"><stop offset="0" stop-color="#5a189a" stop-opacity=".55"/><stop offset="1" stop-color="#5a189a" stop-opacity="0"/></radialGradient>
  <radialGradient id="neb2" cx="10%" cy="100%" r="55%"><stop offset="0" stop-color="#3c096c" stop-opacity=".6"/><stop offset="1" stop-color="#3c096c" stop-opacity="0"/></radialGradient>
  <clipPath id="card"><rect width="{W}" height="{H}" rx="14"/></clipPath>
  <clipPath id="barclip"><rect x="440" y="78" width="{bar_w}" height="10" rx="5"/></clipPath>
</defs>
<style>
  .title {{ font: 700 19px 'Segoe UI', Ubuntu, sans-serif; fill: #e0aaff; letter-spacing: .5px }}
  .label {{ font: 400 14px 'Segoe UI', Ubuntu, sans-serif; fill: #c9d1d9 }}
  .val   {{ font: 700 14px 'Segoe UI', Ubuntu, sans-serif; fill: #ffd166 }}
  .icon  {{ font: 14px 'Segoe UI Symbol', 'Segoe UI', sans-serif; fill: #c77dff }}
  .pct   {{ fill: #8b949e; font-size: 12px }}
  .tw    {{ animation: tw ease-in-out infinite alternate; opacity: .2 }}
  @keyframes tw {{ to {{ opacity: .95 }} }}
</style>
<g clip-path="url(#card)">
  <rect width="{W}" height="{H}" fill="#0d1117"/>
  <rect width="{W}" height="{H}" fill="url(#neb1)"/>
  <rect width="{W}" height="{H}" fill="url(#neb2)"/>
  {''.join(stars)}
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="#3c096c"/>
<text x="36" y="44" class="title">📡 Telemetry</text>
<text x="440" y="44" class="title">🌠 Most-used languages</text>
<line x1="405" y1="64" x2="405" y2="215" stroke="#3c096c" stroke-dasharray="2 5"/>
{''.join(stat_svg)}
<g clip-path="url(#barclip)"><rect x="440" y="78" width="{bar_w}" height="10" fill="#21262d"/>{''.join(bar)}</g>
{''.join(legend)}
</svg>
'''


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    who, out = sys.argv[1], sys.argv[2]
    data = mock() if who == "--mock" else fetch(who, os.environ["GITHUB_TOKEN"])
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(data))
    print(f"wrote {out}: {json.dumps({k: v for k, v in data.items() if k != 'langs'})}")


if __name__ == "__main__":
    main()
