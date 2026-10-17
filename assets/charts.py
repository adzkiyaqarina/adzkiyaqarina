"""Draws the year-in-grooves card in the profile README (grooves-light.svg and grooves-dark.svg) from
the last year of GitHub contributions:

  - the record: each day a dot along the spiral groove, oldest at the rim and today by the label,
    bigger and brighter when busier
  - the numbers: contributions, longest streak and best month
  - contributions per week, as equalizer bars, and by day of the week

Runs every day in .github/workflows/charts.yml, with the standard library only. The lettering comes
from glyphs.json (made by build.py).

  GITHUB_TOKEN=… python3 assets/charts.py [output folder]
"""
import datetime
import json
import math
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
GLYPHS = json.loads((HERE / 'glyphs.json').read_text())
USER = os.environ.get('GITHUB_USER', 'adzkiyaqarina')
W, H = 1200, 640
CX, CY, R = 902, 296, 226
R_OUT, R_IN, TURNS = 212, 94, 6.5

QUERY = '''query($login: String!) { user(login: $login) { contributionsCollection { contributionCalendar {
  totalContributions weeks { contributionDays { date weekday contributionCount contributionLevel } } } } } }'''

LEVELS = {'NONE': 0, 'FIRST_QUARTILE': 1, 'SECOND_QUARTILE': 2, 'THIRD_QUARTILE': 3, 'FOURTH_QUARTILE': 4}
DOTS = [('rgba(255,255,255,0.22)', 1.4), ('#b8d0da', 2.4), ('#dce9ee', 3.1), ('#f6efe2', 3.8), ('#f0c08e', 4.6)]
THEMES = {
    'light': dict(bg='#dfe9ec', glow='#eef3f4', border='rgba(59,90,105,0.18)', ink='#221a15', soft='#4b5f68', faint='#6f8590', line='rgba(59,90,105,0.16)',
                  shadow='rgba(34,52,61,0.28)', top='#7fa3b3', bottom='#3b5a69', peak='#b5703f', stub='rgba(59,90,105,0.25)', track='rgba(59,90,105,0.10)'),
    'dark': dict(bg='#1b2c35', glow='#26404c', border='rgba(143,182,198,0.18)', ink='#f1ebe0', soft='#b9cbd2', faint='#8aa3ae', line='rgba(143,182,198,0.16)',
                 shadow='rgba(0,0,0,0.5)', top='#b4d0db', bottom='#5f8797', peak='#c98552', stub='rgba(143,182,198,0.3)', track='rgba(143,182,198,0.10)'),
}


def num(n):
    text = f'{n:.1f}'
    return text[:-2] if text.endswith('.0') else text


def fetch():
    body = json.dumps({'query': QUERY, 'variables': {'login': USER}}).encode()
    headers = {'Authorization': f'bearer {os.environ["GITHUB_TOKEN"]}', 'User-Agent': 'profile-charts'}
    with urllib.request.urlopen(urllib.request.Request('https://api.github.com/graphql', data=body, headers=headers), timeout=30) as response:
        calendar = json.loads(response.read())['data']['user']['contributionsCollection']['contributionCalendar']
    days = sorted((d for week in calendar['weeks'] for d in week['contributionDays']), key=lambda d: d['date'])
    return calendar['totalContributions'], calendar['weeks'], days


def set_text(table, text, size, x, y, fill, tracking=0.0, anchor='start'):
    glyphs = GLYPHS[table]
    scale = size / 100
    width = sum(glyphs.get(ch, {'adv': 50})['adv'] * scale for ch in text) + tracking * size * (len(text) - 1)
    if anchor == 'middle':
        x -= width / 2
    elif anchor == 'end':
        x -= width
    out = []
    for ch in text:
        glyph = glyphs.get(ch, {'d': '', 'adv': 50})
        if glyph['d']:
            out.append(f'<path transform="translate({num(x)} {num(y)}) scale({scale:g})" d="{glyph["d"]}"/>')
        x += glyph['adv'] * scale + tracking * size
    return f'<g fill="{fill}">{"".join(out)}</g>', x


def fixed(d, x, y, fill):
    return f'<path transform="translate({num(x)} {num(y)})" fill="{fill}" d="{d}"/>'


def record(days):
    n = len(days)
    points, dots = [], []
    for i, day in enumerate(days):
        t = i / max(n - 1, 1)
        angle = -math.pi / 2 + t * TURNS * 2 * math.pi
        r = R_OUT - (R_OUT - R_IN) * t
        x, y = CX + r * math.cos(angle), CY + r * math.sin(angle)
        points.append(f'{num(x)},{num(y)}')
        color, size = DOTS[LEVELS.get(day['contributionLevel'], 0)]
        dots.append(f'<circle cx="{num(x)}" cy="{num(y)}" r="{size}" fill="{color}"/>')
    first = datetime.date.fromisoformat(days[0]['date'])
    last = datetime.date.fromisoformat(days[-1]['date'])
    span = f'{first.strftime("%b").upper()} {first.year} – {last.strftime("%b").upper()} {last.year}'
    label, _ = set_text('mono', span, 8.6, CX, CY + 30, '#3b5a69', 0.1, 'middle')
    rings = ''.join(f'<circle cx="{CX}" cy="{CY}" r="{r}" fill="none" stroke="rgba(18,34,42,0.16)" stroke-width="0.8"/>' for r in range(84, R - 4, 6))
    return f'''<g class="spin"><circle cx="{CX}" cy="{CY}" r="{R}" fill="url(#vinyl)"/>{rings}
      <polyline points="{" ".join(points)}" fill="none" stroke="rgba(255,255,255,0.10)" stroke-width="1"/>{"".join(dots)}
      <circle cx="{CX}" cy="{CY}" r="{R}" fill="url(#sheen)"/>
      <circle cx="{CX}" cy="{CY}" r="74" fill="#f1e8d6"/><circle cx="{CX}" cy="{CY}" r="74" fill="none" stroke="rgba(18,34,42,0.25)" stroke-width="5"/>
      <circle cx="{CX}" cy="{CY}" r="64" fill="none" stroke="rgba(59,90,105,0.35)"/>
      {fixed(GLYPHS["mark"], CX, CY - 8, "#3b5a69")}{label}<circle cx="{CX}" cy="{CY}" r="5" fill="#1b2a31"/></g>'''


def tonearm():
    # The needle rests on today's groove, by the label.
    angle = math.radians(-24)
    hx, hy = CX + (R_IN + 2) * math.cos(angle), CY + (R_IN + 2) * math.sin(angle)
    px, py = 1146, 106
    deg = math.degrees(math.atan2(hy - py, hx - px)) + 90
    return f'''<line x1="{px}" y1="{py}" x2="{num(hx)}" y2="{num(hy)}" stroke="#d9cfbd" stroke-width="7" stroke-linecap="round"/>
      <line x1="{px}" y1="{py}" x2="{num(hx)}" y2="{num(hy)}" stroke="rgba(255,255,255,0.35)" stroke-width="2" stroke-linecap="round"/>
      <rect x="{num(hx - 12)}" y="{num(hy - 8)}" width="24" height="16" rx="3" fill="#cfc4b0" transform="rotate({num(deg)} {num(hx)} {num(hy)})"/>
      <circle cx="{px}" cy="{py}" r="26" fill="#e7dfd1"/><circle cx="{px}" cy="{py}" r="26" fill="none" stroke="rgba(34,26,21,0.12)"/>
      <circle cx="{px}" cy="{py}" r="11" fill="#1e1612"/>'''


def numbers(t, total, days):
    longest = run = 0
    for day in days:
        run = run + 1 if day['contributionCount'] else 0
        longest = max(longest, run)
    months = {}
    for day in days:
        months[day['date'][:7]] = months.get(day['date'][:7], 0) + day['contributionCount']
    best = max(months, key=months.get)
    best_date = datetime.date.fromisoformat(best + '-01')
    cells = [('total', f'{total:,}', None), ('streak', f'{longest:,}', 'DAYS'), ('month', f'{months[best]:,}', f'{best_date.strftime("%b").upper()} {best_date.year}')]
    out = []
    for i, (key, value, unit) in enumerate(cells):
        x = 72 + i * 186
        out.append(fixed(GLYPHS['labels'][key], x, 232, t['faint']))
        figure, end = set_text('serif', value, 48, x - 2, 284, t['ink'])
        out.append(figure)
        if unit:
            out.append(set_text('mono', unit, 10.5, end + 8, 283, t['soft'], 0.14)[0])
    summary = dict(total=total, streak=longest, month=best_date.strftime('%B %Y'), month_total=months[best])
    return ''.join(out), summary


def weekly(t, weeks):
    totals = [sum(d['contributionCount'] for d in week['contributionDays']) for week in weeks]
    peak = max(totals) or 1
    left, right, base, top = 72, 620, 444, 362
    slot = (right - left) / len(totals)
    bw = max(4, min(7, slot - 3.5))
    shapes, labels, last_x = [], [], -100
    for i, (week, total) in enumerate(zip(weeks, totals)):
        x = left + i * slot + (slot - bw) / 2
        if total:
            bh = max(bw, total / peak * (base - top))
            fill = t['peak'] if total == peak else 'url(#bar)'
            shapes.append(f'<rect x="{num(x)}" y="{num(base - bh)}" width="{num(bw)}" height="{num(bh)}" rx="{num(bw / 2)}" fill="{fill}"/>')
        else:
            shapes.append(f'<circle cx="{num(x + bw / 2)}" cy="{base - 2}" r="1.8" fill="{t["stub"]}"/>')
        for day in week['contributionDays']:
            date = datetime.date.fromisoformat(day['date'])
            if date.day == 1 and x - last_x > 34:
                labels.append(set_text('mono', date.strftime('%b').upper(), 9.5, x + bw / 2, base + 26, t['faint'], 0.1, 'middle')[0])
                last_x = x
    return ''.join([
        fixed(GLYPHS['labels']['week'], 72, 340, t['faint']),
        f'<line x1="{left}" y1="{base + 8}" x2="{right}" y2="{base + 8}" stroke="{t["line"]}"/>',
        f'<g>{"".join(shapes)}</g>',
        f'<g clip-path="url(#bars)"><rect class="sweep" x="0" y="{top - 6}" width="90" height="{base - top + 12}" fill="url(#band)"/></g>',
        ''.join(labels),
    ]), ''.join(shapes)


def by_day(t, days):
    order, names = [1, 2, 3, 4, 5, 6, 0], ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
    totals = {k: 0 for k in order}
    for day in days:
        totals[day['weekday']] += day['contributionCount']
    most = max(totals.values()) or 1
    out = [fixed(GLYPHS['labels']['day'], 72, 522, t['faint'])]
    left, slot, base, tall, bw = 72, 78, 590, 44, 12
    for i, key in enumerate(order):
        value = totals[key]
        x = left + i * slot
        bh = max(4, value / most * tall)
        color = t['peak'] if value == most and value else 'url(#bar)'
        out.append(f'<rect x="{x}" y="{base - tall}" width="{bw}" height="{tall}" rx="{bw / 2}" fill="{t["track"]}"/>')
        out.append(f'<rect x="{x}" y="{num(base - bh)}" width="{bw}" height="{num(bh)}" rx="{num(min(bw, bh) / 2)}" fill="{color}"/>')
        out.append(set_text('mono', names[i], 10, x + bw + 8, base - 14, t['soft'], 0.12)[0])
        out.append(set_text('mono', f'{value:,}', 10, x + bw + 8, base, t['faint'], 0.04)[0])
    busiest = names[order.index(max(totals, key=totals.get))]
    return ''.join(out), busiest


def picture(theme, total, weeks, days):
    t = THEMES[theme]
    stats, summary = numbers(t, total, days)
    bars, bar_shapes = weekly(t, weeks)
    rhythm, busiest = by_day(t, days)
    legend = [fixed(GLYPHS['less'], CX - 74, H - 34, t['faint'])]
    x = CX - 26
    for color, size in DOTS:
        legend.append(f'<circle cx="{x}" cy="{H - 38}" r="{max(size, 2.4)}" fill="#3b5a69"/><circle cx="{x}" cy="{H - 38}" r="{size}" fill="{color}"/>')
        x += 18
    legend.append(fixed(GLYPHS['more'], x + 2, H - 34, t['faint']))
    desc = (f'{summary["total"]:,} contributions on GitHub in the last year, longest streak {summary["streak"]} days, '
            f'best month {summary["month"]} with {summary["month_total"]}. Most contributions land on {busiest}.')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
  <title id="t">A year in grooves</title><desc id="d">{desc}</desc>
  <style>.spin {{ transform-box: view-box; transform-origin: {CX}px {CY}px; animation: spin 40s linear infinite; }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    .sweep {{ animation: sweep 8s linear infinite; }} @keyframes sweep {{ from {{ transform: translateX(-100px); }} to {{ transform: translateX(640px); }} }}
    @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}</style>
  <defs><clipPath id="card"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="28"/></clipPath>
    <radialGradient id="glow" cx="160" cy="40" r="700" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="{t["glow"]}"/><stop offset="1" stop-color="{t["bg"]}"/></radialGradient>
    <radialGradient id="vinyl" cx="{CX}" cy="{CY}" r="{R}" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#557d8d"/><stop offset="0.35" stop-color="#5a8292"/><stop offset="0.72" stop-color="#45677a"/><stop offset="1" stop-color="#365464"/></radialGradient>
    <linearGradient id="sheen" x1="{CX - R}" y1="{CY - R}" x2="{CX + R}" y2="{CY + R}" gradientUnits="userSpaceOnUse"><stop offset="0.2" stop-color="#fff" stop-opacity="0"/><stop offset="0.35" stop-color="#fff" stop-opacity="0.06"/><stop offset="0.47" stop-color="#fff" stop-opacity="0"/><stop offset="0.72" stop-color="#fff" stop-opacity="0"/><stop offset="0.83" stop-color="#fff" stop-opacity="0.045"/><stop offset="0.94" stop-color="#fff" stop-opacity="0"/></linearGradient>
    <linearGradient id="bar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["top"]}"/><stop offset="1" stop-color="{t["bottom"]}"/></linearGradient>
    <linearGradient id="band" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="0.5" stop-color="#fff" stop-opacity="0.6"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
    <clipPath id="bars">{bar_shapes}</clipPath>
    <filter id="drop" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="14" stdDeviation="16" flood-color="{t["shadow"]}"/></filter></defs>
  <g clip-path="url(#card)"><rect width="{W}" height="{H}" fill="url(#glow)"/>
    {fixed(GLYPHS["title"], 0, 0, t["ink"])}{fixed(GLYPHS["subtitle1"], 0, 0, t["soft"])}{fixed(GLYPHS["subtitle2"], 0, 0, t["soft"])}
    {stats}{bars}{rhythm}
    <g filter="url(#drop)">{record(days)}</g>{tonearm()}{"".join(legend)}</g>
  <rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="28" fill="none" stroke="{t["border"]}" stroke-width="1.5"/>
</svg>
'''


if __name__ == '__main__':
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
    out.mkdir(parents=True, exist_ok=True)
    total, weeks, days = fetch()
    for theme in THEMES:
        (out / f'grooves-{theme}.svg').write_text(picture(theme, total, weeks, days))
    print(f'{total} contributions over {len(days)} days pressed')
