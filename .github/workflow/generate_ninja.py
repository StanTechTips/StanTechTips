#!/usr/bin/env python3
"""
Ninja Contribution Graph SVG Generator
Generates an animated SVG: a ninja throws spinning shurikens along the GitHub contribution grid.
Run by GitHub Actions — outputs dist/github-ninja.svg and dist/github-ninja-dark.svg
"""

import os, sys, math, requests
from datetime import datetime

# ── Grid constants ─────────────────────────────────────────────────────────────
CELL   = 11        # cell size px
GAP    = 3         # gap between cells px
STEP   = CELL + GAP
LPAD   = 34        # left padding (day labels)
TPAD   = 24        # top padding (month labels)
RPAD   = 10
BPAD   = 14
DAYS   = 7
DUR    = 14        # total animation loop seconds

# ── GitHub GraphQL ─────────────────────────────────────────────────────────────
def fetch_contributions(username, token):
    query = """
    query($u: String!) {
      user(login: $u) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              firstDay
              contributionDays { date contributionCount }
            }
          }
        }
      }
    }
    """
    r = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": {"u": username}},
        headers={"Authorization": f"bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["data"]["user"]["contributionsCollection"]["contributionCalendar"]


# ── Helpers ────────────────────────────────────────────────────────────────────
def level_color(n, dark):
    if n == 0:
        return "#161b22" if dark else "#ebedf0"
    i = min(n // 3, 3)
    return (["#3d0061", "#6600a8", "#9B00FF", "#c84fff"] if dark
            else ["#9be9a8", "#40c463", "#30a14e", "#216e39"])[i]

def shuriken_pts(cx=0, cy=0, ro=5.5, ri=2.2, n=8):
    pts = []
    for i in range(n * 2):
        a = math.pi * i / n - math.pi / 2
        r = ro if i % 2 == 0 else ri
        pts.append(f"{cx + r*math.cos(a):.2f},{cy + r*math.sin(a):.2f}")
    return " ".join(pts)

def cell_center(wi, di):
    return LPAD + wi * STEP + CELL // 2, TPAD + di * STEP + CELL // 2


# ── SVG generator ─────────────────────────────────────────────────────────────
def make_svg(cal, username, dark=True):
    weeks   = cal["weeks"]
    W       = len(weeks)
    SVG_W   = LPAD + W * STEP + RPAD
    SVG_H   = TPAD + DAYS * STEP + BPAD
    BG      = "#0D0014" if dark else "#ffffff"
    TC      = "#9B00FF" if dark else "#24292f"
    ACCENT  = "#FF003C"

    # ── build cell list ────────────────────────────────────────────────────────
    cells = []
    for wi, wk in enumerate(weeks):
        for di, day in enumerate(wk["contributionDays"]):
            cx, cy = cell_center(wi, di)
            cells.append({
                "x": LPAD + wi * STEP, "y": TPAD + di * STEP,
                "cx": cx, "cy": cy,
                "n": day["contributionCount"],
                "color": level_color(day["contributionCount"], dark),
            })

    # ── snake path (col-by-col, alternating direction) ─────────────────────────
    path_pts = []
    for wi in range(W):
        col = [cell_center(wi, di) for di in range(DAYS)]
        if wi % 2 == 1:
            col = col[::-1]
        path_pts.extend(col)
    N = len(path_pts)

    motion_path = "M " + " L ".join(f"{x},{y}" for x, y in path_pts)

    # ── assemble SVG ───────────────────────────────────────────────────────────
    o = []
    a = o.append  # shorthand

    a(f'<svg viewBox="0 0 {SVG_W} {SVG_H}" xmlns="http://www.w3.org/2000/svg">')

    # defs: gradient + glow filter
    a('<defs>')
    a('<radialGradient id="bg-g" cx="50%" cy="50%" r="70%">')
    if dark:
        a('<stop offset="0%" stop-color="#1A0035"/>')
        a('<stop offset="100%" stop-color="#0D0014"/>')
    else:
        a('<stop offset="0%" stop-color="#f5f5ff"/>')
        a('<stop offset="100%" stop-color="#ffffff"/>')
    a('</radialGradient>')
    a('<filter id="glow" x="-40%" y="-40%" width="180%" height="180%">')
    a('<feGaussianBlur stdDeviation="2" result="b"/>')
    a('<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>')
    a('</filter>')
    a('<filter id="soft-glow" x="-20%" y="-20%" width="140%" height="140%">')
    a('<feGaussianBlur stdDeviation="1" result="b"/>')
    a('<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>')
    a('</filter>')
    a('</defs>')

    # background
    a(f'<rect width="{SVG_W}" height="{SVG_H}" fill="url(#bg-g)" rx="8"/>')

    # month labels
    seen = {}
    for wi, wk in enumerate(weeks):
        if wk["contributionDays"]:
            m = datetime.strptime(wk["contributionDays"][0]["date"], "%Y-%m-%d").strftime("%b")
            if m not in seen:
                seen[m] = wi
                a(f'<text x="{LPAD + wi*STEP}" y="{TPAD-7}" font-size="9" fill="{TC}" '
                  f'font-family="monospace" opacity="0.8">{m}</text>')

    # day labels
    for di, lbl in {1: "M", 3: "W", 5: "F"}.items():
        a(f'<text x="{LPAD-5}" y="{TPAD+di*STEP+CELL}" font-size="8" fill="{TC}" '
          f'text-anchor="end" font-family="monospace" opacity="0.55">{lbl}</text>')

    # contribution cells
    for i, c in enumerate(cells):
        a(f'<rect id="c{i}" x="{c["x"]}" y="{c["y"]}" width="{CELL}" height="{CELL}" '
          f'rx="2" fill="{c["color"]}"/>')

    # ── shurikens ─────────────────────────────────────────────────────────────
    # One throw every ~16 steps; shuriken travels 20 cells ahead
    interval = max(12, N // 22)
    fly_dur  = 0.65

    for ti, pi in enumerate(range(0, N - 20, interval)):
        sx, sy = path_pts[pi]
        ex, ey = path_pts[min(pi + 20, N - 1)]
        t0      = pi / N * DUR          # when to throw
        restart = DUR - fly_dur         # gap until next loop

        # key times for opacity: invisible → flash in → visible → fade out
        kts = f"0;{t0/DUR:.4f};{(t0+0.04)/DUR:.4f};{(t0+fly_dur*0.88)/DUR:.4f};{(t0+fly_dur)/DUR:.4f};1"

        a(f'<g id="s{ti}">')
        a(f'  <polygon points="{shuriken_pts()}" fill="#9B00FF" stroke="#FFD700" '
          f'stroke-width="0.5" filter="url(#glow)">')
        # opacity pulse
        a(f'    <animate attributeName="opacity" '
          f'values="0;0;1;1;0;0" keyTimes="{kts}" '
          f'dur="{DUR}s" repeatCount="indefinite"/>')
        # spin
        a(f'    <animateTransform attributeName="transform" type="rotate" '
          f'from="0" to="360" dur="0.32s" repeatCount="indefinite" additive="sum"/>')
        # fly — resets each DUR cycle via begin chain
        a(f'    <animateMotion from="{sx},{sy}" to="{ex},{ey}" '
          f'begin="{t0:.3f}s" dur="{fly_dur}s" fill="remove" '
          f'repeatCount="1"/>')
        a(f'  </polygon>')
        a(f'</g>')

    # ── impact flashes ─────────────────────────────────────────────────────────
    for ti, pi in enumerate(range(0, N - 20, interval)):
        ex, ey  = path_pts[min(pi + 20, N - 1)]
        t_hit   = (pi / N * DUR) + fly_dur
        kts2    = f"0;{t_hit/DUR:.4f};{(t_hit+0.06)/DUR:.4f};{(t_hit+0.18)/DUR:.4f};1"
        a(f'<circle cx="{ex}" cy="{ey}" r="0" fill="{ACCENT}" opacity="0" filter="url(#glow)">')
        a(f'  <animate attributeName="r" values="0;0;7;0;0" keyTimes="{kts2}" '
          f'dur="{DUR}s" repeatCount="indefinite"/>')
        a(f'  <animate attributeName="opacity" values="0;0;0.9;0;0" keyTimes="{kts2}" '
          f'dur="{DUR}s" repeatCount="indefinite"/>')
        a(f'</circle>')

    # ── ninja ─────────────────────────────────────────────────────────────────
    a(f'<g filter="url(#soft-glow)">')

    # shadow
    a(f'  <ellipse cx="0" cy="12" rx="7" ry="2.5" fill="#9B00FF" opacity="0.35">')
    a(f'    <animateMotion path="{motion_path}" dur="{DUR}s" repeatCount="indefinite"/>')
    a(f'  </ellipse>')

    # ninja body parts (all child of animateMotion group)
    a(f'  <g>')
    # cloak / cape
    a(f'    <polygon points="0,-7 -8,10 8,10" fill="#1a0030"/>')
    # body
    a(f'    <rect x="-4" y="-3" width="8" height="10" rx="1.5" fill="#0a0a14"/>')
    # belt sash
    a(f'    <rect x="-5" y="2.5" width="10" height="2.2" rx="0.8" fill="#9B00FF"/>')
    # head
    a(f'    <circle cx="0" cy="-10" r="5.2" fill="#0a0a14"/>')
    # headband
    a(f'    <rect x="-5.2" y="-12.2" width="10.4" height="2.4" rx="1.2" fill="{ACCENT}"/>')
    # headband knot
    a(f'    <rect x="4.5" y="-12.8" width="3" height="4" rx="0.8" fill="{ACCENT}" opacity="0.7"/>')
    # eyes
    a(f'    <rect x="-2.9" y="-11" width="2.2" height="1.1" rx="0.5" fill="white"/>')
    a(f'    <rect x="0.7" y="-11" width="2.2" height="1.1" rx="0.5" fill="white"/>')
    # left arm (throwing pose — extended forward)
    a(f'    <rect x="-9" y="-4" width="5" height="3" rx="1" fill="#0a0a14" transform="rotate(-20,-9,-4)"/>')
    # right arm (guard)
    a(f'    <rect x="4" y="-2" width="4" height="6" rx="1" fill="#0a0a14" transform="rotate(10,4,-2)"/>')
    # legs
    a(f'    <rect x="-4" y="7" width="3.2" height="6" rx="1" fill="#0a0a14"/>')
    a(f'    <rect x="0.8" y="7" width="3.2" height="6" rx="1" fill="#0a0a14"/>')
    # motion
    a(f'    <animateMotion path="{motion_path}" dur="{DUR}s" repeatCount="indefinite"/>')
    a(f'  </g>')
    a(f'</g>')

    # username watermark
    a(f'<text x="{SVG_W//2}" y="{SVG_H-2}" text-anchor="middle" font-size="8" '
      f'fill="{TC}" font-family="monospace" opacity="0.45">@{username}</text>')

    a('</svg>')
    return "\n".join(o)


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    username = os.environ.get("GITHUB_USER", "StanTechTips")
    token    = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("ERROR: GITHUB_TOKEN environment variable is required.", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching contributions for @{username} ...")
    cal = fetch_contributions(username, token)
    print(f"  Total contributions: {cal['totalContributions']}")

    os.makedirs("dist", exist_ok=True)

    svg_dark = make_svg(cal, username, dark=True)
    with open("dist/github-ninja-dark.svg", "w", encoding="utf-8") as f:
        f.write(svg_dark)
    print("  ✓ dist/github-ninja-dark.svg")

    svg_light = make_svg(cal, username, dark=False)
    with open("dist/github-ninja.svg", "w", encoding="utf-8") as f:
        f.write(svg_light)
    print("  ✓ dist/github-ninja.svg")

if __name__ == "__main__":
    main()
