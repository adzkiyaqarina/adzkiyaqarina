"""Draws every picture in this profile README in the look of adzkiyaqarinas.com.

The content (projects, screenshots, skills, numbers) is read from the portfolio's own published
copy, https://adzkiyaqarinas.com/content/portfolio.json, so running this again picks up what has
changed on the site. Text is turned into outlines with the site's fonts (Cormorant Garamond,
Manrope, IBM Plex Mono), because an SVG shown through <img> on GitHub cannot load web fonts.

The year-in-grooves card (the GitHub contributions of the last year) is drawn every day by
assets/charts.py (see .github/workflows); this script only prepares the lettering they need
(assets/glyphs.json).

To run it:
  python3 -m venv .venv && .venv/bin/pip install fonttools uharfbuzz pillow
  mkdir -p assets/fonts && cd assets/fonts
  curl -sL -o Cormorant.ttf "https://github.com/google/fonts/raw/main/ofl/cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf"
  curl -sL -o CormorantItalic.ttf "https://github.com/google/fonts/raw/main/ofl/cormorantgaramond/CormorantGaramond-Italic%5Bwght%5D.ttf"
  curl -sL -o Manrope.ttf "https://github.com/google/fonts/raw/main/ofl/manrope/Manrope%5Bwght%5D.ttf"
  curl -sL -o PlexMono.ttf "https://github.com/google/fonts/raw/main/ofl/ibmplexmono/IBMPlexMono-Medium.ttf"
  cd ../.. && .venv/bin/python assets/build.py
"""
import base64
import io
import json
import math
import urllib.request
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image

HERE = Path(__file__).parent
FONTS = HERE / 'fonts'
SITE = 'https://adzkiyaqarinas.com'
STORAGE = 'https://slmipjfpdtdykbiszeni.supabase.co/storage/v1/object/public/media/'
W = 1200


# ---- Lettering --------------------------------------------------------------------------------

def num(n):
    text = f'{n:.1f}'
    return text[:-2] if text.endswith('.0') else text


class Face:
    def __init__(self, file, wght=None):
        tt = TTFont(FONTS / file)
        if wght is not None and 'fvar' in tt:
            tt = instantiateVariableFont(tt, {'wght': wght})
        buf = io.BytesIO()
        tt.save(buf)
        data = buf.getvalue()
        self.tt = TTFont(io.BytesIO(data))
        self.glyphs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.upem = self.tt['head'].unitsPerEm
        self.hb_font = hb.Font(hb.Face(hb.Blob(data)))

    def shape(self, text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb_font, buf, {'kern': True, 'liga': True})
        return [(self.order[i.codepoint], p.x_advance, p.x_offset, p.y_offset) for i, p in zip(buf.glyph_infos, buf.glyph_positions)]

    def width(self, text, size, tracking=0.0):
        s = size / self.upem
        run = self.shape(text)
        return sum(adv * s for _, adv, _, _ in run) + tracking * size * max(len(run) - 1, 0)

    def glyph_path(self, name, size, x, y):
        s = size / self.upem
        pen = SVGPathPen(self.glyphs, ntos=num)
        self.glyphs[name].draw(TransformPen(pen, (s, 0, 0, -s, x, y)))
        return pen.getCommands()

    def path(self, text, size, x, y, tracking=0.0, anchor='start'):
        s = size / self.upem
        if anchor == 'middle':
            x -= self.width(text, size, tracking) / 2
        elif anchor == 'end':
            x -= self.width(text, size, tracking)
        out = []
        for name, adv, xo, yo in self.shape(text):
            out.append(self.glyph_path(name, size, x + xo * s, y - yo * s))
            x += adv * s + tracking * size
        return ' '.join(c for c in out if c)

    def ring(self, text, size, cx, cy, r, start=-90.0):
        """Text running clockwise all the way around a circle, spaced to close the loop evenly."""
        s = size / self.upem
        run = self.shape(text)
        gap = (2 * math.pi * r - sum(adv * s for _, adv, _, _ in run)) / len(run)
        paths, angle = [], math.radians(start)
        for name, adv, _, _ in run:
            w = adv * s
            mid = angle + (w / 2) / r
            d = self.glyph_path(name, size, -w / 2, size * 0.35)
            if d:
                paths.append(f'<path transform="translate({num(cx + r * math.cos(mid))} {num(cy + r * math.sin(mid))}) rotate({num(math.degrees(mid) + 90)})" d="{d}"/>')
            angle += (w + gap) / r
        return ''.join(paths)

    def wrap(self, text, size, width):
        lines, line = [], ''
        for word in text.split():
            trial = f'{line} {word}'.strip()
            if line and self.width(trial, size) > width:
                lines.append(line)
                line = word
            else:
                line = trial
        return lines + ([line] if line else [])


SERIF = Face('Cormorant.ttf', 500)
SERIF_SEMI = Face('Cormorant.ttf', 600)
ITALIC = Face('CormorantItalic.ttf', 500)
ITALIC_SEMI = Face('CormorantItalic.ttf', 600)
SANS = Face('Manrope.ttf', 500)
SANS_LIGHT = Face('Manrope.ttf', 400)
SANS_BOLD = Face('Manrope.ttf', 600)
MONO = Face('PlexMono.ttf')


def text(face, s, size, x, y, fill, tracking=0.0, anchor='start', extra=''):
    return f'<path fill="{fill}"{extra} d="{face.path(s, size, x, y, tracking, anchor)}"/>'


def link_text(label, size, x, y, fill):
    """A link label with a drawn ↗ (the fonts have no arrow)."""
    end = x + SANS_BOLD.width(label, size) + 5
    k = size / 24 * 0.95
    arrow = (f'<path transform="translate({num(end)} {num(y - size * 0.86)}) scale({k:.3f})" fill="none" stroke="{fill}" stroke-width="2.4" '
             f'stroke-linecap="round" stroke-linejoin="round" d="M7 17 17 7M8 7h9v9"/>')
    return text(SANS_BOLD, label, size, x, y, fill) + arrow


def fit(face, s, size, width):
    """The largest size up to `size` at which the text fits in `width`."""
    natural = face.width(s, size)
    return size if natural <= width else size * width / natural


def para(face, s, size, x, y, width, leading, fill):
    lines = face.wrap(s, size, width)
    return ''.join(text(face, line, size, x, y + i * leading, fill) for i, line in enumerate(lines)), y + (len(lines) - 1) * leading


def doc(h, body, *, title, desc='', style='', defs='', w=W):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-labelledby="t d">'
        f'<title id="t">{title}</title><desc id="d">{desc or title}</desc>'
        f'<style>{style}</style><defs>{defs}</defs>{body}</svg>\n'
    )


# ---- Colours (the site's tokens) ---------------------------------------------------------------

C = dict(
    ivory='#faf6ef', bone='#f1ebe0', sand='#e6dccb', paper='#fffdf9', ink='#221a15', ink_soft='#5e5249', ink_faint='#8f8378',
    espresso='#2a1f19', espresso_deep='#1e1612', panel='#382a22', raised='#45352b', on_dark='#f1ebe0', on_dark_muted='#c4b5a4',
    blue='#4a6f80', blue_deep='#3b5a69', blue_soft='#7fa3b3', blue_bright='#8fb6c6', copper='#9a5a2e', copper_bright='#c98552',
    champagne='#d6cbb8', champagne_deep='#7d6e58',
)
# Per GitHub theme: the colours for things drawn straight on the page.
T = {
    'light': dict(ink=C['ink'], soft=C['ink_soft'], faint=C['ink_faint'], card=C['paper'], card_line='rgba(34,26,21,0.10)', chip=C['paper'],
                  accent=C['blue'], warm=C['copper'], rail='#8a7a68', shadow='rgba(34,26,21,0.22)', mat='#f3ecdf'),
    'dark': dict(ink=C['on_dark'], soft=C['on_dark_muted'], faint='#9a8b7c', card=C['panel'], card_line='rgba(241,235,224,0.12)', chip=C['panel'],
                 accent=C['blue_bright'], warm=C['copper_bright'], rail='#7a6a58', shadow='rgba(0,0,0,0.5)', mat='#efe6d6'),
}

NOTE_EIGHTH = '<ellipse cx="8" cy="18" rx="4.4" ry="3.3" transform="rotate(-22 8 18)"/><path d="M11.4 17.6V3h1.8c.4 2.6 2 3.8 3.6 5.2 1.7 1.5 2.6 3.4 1.7 6.3-.3-2.4-1.9-3.9-5.3-4.6v7.7z"/>'
NOTE_PAIR = '<ellipse cx="6" cy="19.4" rx="4" ry="3" transform="rotate(-22 6 19.4)"/><ellipse cx="16" cy="16.8" rx="4" ry="3" transform="rotate(-22 16 16.8)"/><path d="M8.6 19V5.6L20.2 3v13.4h-1.6V6.36l-8.4 1.88V19z"/>'
REDUCE = '@media (prefers-reduced-motion: reduce) { * { animation: none !important; } }'


# ---- Content from the site ---------------------------------------------------------------------

def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'profile-readme-build'}), timeout=30) as response:
        return response.read()


SNAPSHOT = json.loads(fetch(f'{SITE}/content/portfolio.json'))
ROWS = SNAPSHOT['rows']


def data_uri(url, width, fmt='JPEG', quality=78):
    image = Image.open(io.BytesIO(fetch(url)))
    if image.width > width:
        image = image.resize((width, round(image.height * width / image.width)), Image.LANCZOS)
    buf = io.BytesIO()
    if fmt == 'JPEG':
        image.convert('RGB').save(buf, 'JPEG', quality=quality, optimize=True, progressive=True)
        mime = 'image/jpeg'
    else:
        image.save(buf, 'WEBP', quality=quality, method=6)
        mime = 'image/webp'
    return f'data:{mime};base64,{base64.b64encode(buf.getvalue()).decode()}', image.size


def screenshot(project_id):
    images = sorted((i for i in ROWS['project_images'] if i['project_id'] == project_id), key=lambda i: i['sort_order'])
    if not images:
        return None
    return f'{SITE}/content/media/{images[0]["url"].replace(STORAGE, "")}'


PROJECTS = sorted(ROWS['projects'], key=lambda p: p.get('sort_order') or 0)


# ---- 1. Header ---------------------------------------------------------------------------------

def header(theme):
    t = {
        'light': dict(bg=C['ivory'], glow=C['bone'], border='rgba(34,26,21,0.10)', ink=C['ink'], soft=C['ink_soft'], pill=C['bone'],
                      pill_border='rgba(34,26,21,0.06)', dot='#b5703f', caret=C['blue'], shadow='rgba(34,26,21,0.18)', note_stroke=C['ivory']),
        'dark': dict(bg=C['espresso'], glow=C['panel'], border='rgba(241,235,224,0.12)', ink=C['on_dark'], soft=C['on_dark_muted'], pill=C['panel'],
                     pill_border='rgba(241,235,224,0.10)', dot=C['copper_bright'], caret=C['blue_bright'], shadow='rgba(0,0,0,0.45)', note_stroke=C['espresso']),
    }[theme]
    h, cx, cy, r = 440, 1015, 128, 262
    grooves = ''.join(
        f'<circle cx="{cx}" cy="{cy}" r="{rr}" fill="none" stroke="rgba(255,255,255,{0.035 if i % 3 else 0.06})"/>' for i, rr in enumerate(range(112, r - 6, 5))
    )
    record = f'''<g class="spin">
      <circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#vinyl)"/>{grooves}<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#sheen)"/>
      <circle cx="{cx}" cy="{cy}" r="100" fill="#9b5a2f"/><circle cx="{cx}" cy="{cy}" r="92" fill="none" stroke="rgba(250,240,225,0.45)" stroke-width="1.2"/>
      <g fill="#f5e9d8">{MONO.ring('ADZKIYA QARINA SALSABILA · IT ENTHUSIAST · ', 12.5, cx, cy, 74)}
      <path d="{ITALIC_SEMI.path('A.Q.S', 34, cx, cy - 14, anchor='middle')}"/><path fill-opacity="0.8" d="{MONO.path('33⅓ RPM', 10, cx, cy + 40, 0.12, 'middle')}"/></g>
      <circle cx="{cx}" cy="{cy}" r="6" fill="#1b1411"/></g>'''
    px, py, hx, hy = 1138, 392, 912, 214
    arm = f'''<line x1="{px}" y1="{py}" x2="{hx + 14}" y2="{hy + 12}" stroke="#d9cfbd" stroke-width="9" stroke-linecap="round"/>
      <line x1="{px}" y1="{py}" x2="{hx + 14}" y2="{hy + 12}" stroke="rgba(255,255,255,0.35)" stroke-width="2.5" stroke-linecap="round"/>
      <rect x="{hx - 16}" y="{hy - 10}" width="36" height="22" rx="4" fill="#cfc4b0" transform="rotate(38 {hx} {hy})"/>
      <rect x="{hx - 12}" y="{hy - 6}" width="10" height="8" rx="2" fill="#b5703f" transform="rotate(38 {hx} {hy})"/>
      <circle cx="{px}" cy="{py}" r="34" fill="#e7dfd1"/><circle cx="{px}" cy="{py}" r="34" fill="none" stroke="rgba(34,26,21,0.12)"/>
      <circle cx="{px}" cy="{py}" r="15" fill="#1e1612"/>'''
    notes = ''.join(
        f'<g class="note" style="--dx:{dx}px;animation-delay:{delay}s;transform-origin:{x}px {y}px"><g transform="translate({x - 21} {y - 21}) scale(1.75)" '
        f'fill="{color}" stroke="{t["note_stroke"]}" stroke-width="1.4" paint-order="stroke" stroke-linejoin="round">{shape}</g></g>'
        for x, y, dx, delay, shape, color in [
            (836, 232, -96, 0.0, NOTE_EIGHTH, C['blue']), (806, 160, -78, 1.5, NOTE_PAIR, C['copper']), (858, 300, -110, 3.0, NOTE_EIGHTH, C['blue']),
        ]
    )
    x0 = 72
    pill_text = 'Jakarta, Indonesia · Open to new opportunities'
    pill_w = SANS.width(pill_text, 17) + 58
    caret_x = x0 + 30 + MONO.width('IT Enthusiast', 28) + 4
    style = f'''.spin {{ transform-box: view-box; transform-origin: {cx}px {cy}px; animation: spin 14s linear infinite; }}
    .note {{ opacity: 0; transform-box: view-box; animation: rise 4.5s cubic-bezier(.3,.6,.4,1) infinite; }}
    .caret {{ animation: blink 1.1s steps(1) infinite; }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    @keyframes rise {{ 0% {{ opacity: 0; transform: translate(0,0) scale(.4) rotate(0deg); }} 12% {{ opacity: 1; }}
      45% {{ transform: translate(calc(var(--dx) * .45), -62px) scale(1) rotate(-10deg); }} 70% {{ opacity: .9; }}
      100% {{ opacity: 0; transform: translate(var(--dx), -150px) scale(.9) rotate(8deg); }} }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }} {REDUCE}'''
    defs = f'''<clipPath id="card"><rect x="1" y="1" width="{W - 2}" height="{h - 2}" rx="28"/></clipPath>
    <radialGradient id="vinyl" cx="{cx}" cy="{cy}" r="{r}" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#1c1513"/><stop offset="0.6" stop-color="#231b17"/><stop offset="1" stop-color="#15100e"/></radialGradient>
    <linearGradient id="sheen" x1="{cx - r}" y1="{cy - r}" x2="{cx + r}" y2="{cy + r}" gradientUnits="userSpaceOnUse"><stop offset="0.18" stop-color="#fff" stop-opacity="0"/><stop offset="0.34" stop-color="#fff" stop-opacity="0.07"/><stop offset="0.46" stop-color="#fff" stop-opacity="0"/><stop offset="0.7" stop-color="#fff" stop-opacity="0"/><stop offset="0.82" stop-color="#fff" stop-opacity="0.05"/><stop offset="0.94" stop-color="#fff" stop-opacity="0"/></linearGradient>
    <radialGradient id="glow" cx="160" cy="40" r="700" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="{t["glow"]}"/><stop offset="1" stop-color="{t["bg"]}"/></radialGradient>
    <filter id="drop" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="14" stdDeviation="16" flood-color="{t["shadow"]}"/></filter>'''
    body = f'''<g clip-path="url(#card)"><rect width="{W}" height="{h}" fill="url(#glow)"/><g filter="url(#drop)">{record}</g>{arm}{notes}
    <rect x="{x0}" y="78" width="{num(pill_w)}" height="40" rx="20" fill="{t["pill"]}" stroke="{t["pill_border"]}"/><circle cx="{x0 + 22}" cy="98" r="4.5" fill="{t["dot"]}"/>
    {text(SANS, pill_text, 17, x0 + 38, 106, t["soft"])}
    {text(SERIF, 'Adzkiya Qarina', 92, x0 - 4, 208, t["ink"], -0.01)}{text(ITALIC, 'Salsabila', 92, x0 - 2, 292, t["ink"], -0.01)}
    {text(MONO, '>', 28, x0, 352, t["caret"])}{text(MONO, 'IT Enthusiast', 28, x0 + 30, 352, t["ink"])}
    <rect class="caret" x="{num(caret_x)}" y="326" width="15" height="32" fill="{t["caret"]}"/>
    {text(SANS_LIGHT, 'Tech gets me going, real impact keeps me going.', 20, x0, 398, t["soft"])}</g>
    <rect x="1" y="1" width="{W - 2}" height="{h - 2}" rx="28" fill="none" stroke="{t["border"]}" stroke-width="1.5"/>'''
    return doc(h, body, title='Adzkiya Qarina Salsabila', desc='IT Enthusiast from Jakarta, Indonesia. Tech gets me going, real impact keeps me going.', style=style, defs=defs)


# ---- 2. Hi, I'm Qarina: a short intro and the tools on rotation, on a vinyl-blue panel ---------

INTRO = ('An Informatics graduate from Universitas Diponegoro who enjoys the whole journey of building software, '
         'from understanding the problem to shipping something people actually use.')
FOCUS = ['Business analysis', 'System design', 'Development', 'Testing', 'AI integration']
GROUPS = [
    ('LANGUAGES', ('Language',), C['blue_bright']),
    ('FRAMEWORKS', ('Framework',), C['copper_bright']),
    ('DATA & CLOUD', ('Database', 'Cloud'), C['champagne']),
    ('DEVOPS', ('DevOps', 'Tool'), '#b9d3dd'),
]


def chips(labels, x, y, width, size=14, dot=None, gap=8):
    """Pills that wrap onto new lines; returns the markup and the y below the last line."""
    out, cx, cy, h = [], x, y, size + 18
    for label in labels:
        w = SANS.width(label, size) + 30 + (14 if dot else 0)
        if cx > x and cx + w > x + width:
            cx, cy = x, cy + h + gap
        out.append(f'<rect x="{num(cx)}" y="{num(cy)}" width="{num(w)}" height="{h}" rx="{h / 2}" fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.16)"/>')
        tx = cx + 15
        if dot:
            out.append(f'<circle cx="{num(cx + 17)}" cy="{num(cy + h / 2)}" r="3.6" fill="{dot}"/>')
            tx += 14
        out.append(text(SANS, label, size, tx, cy + h / 2 + size * 0.36, C['on_dark']))
        cx += w + gap
    return ''.join(out), cy + h


def intro():
    cream, muted = C['on_dark'], 'rgba(241,235,224,0.78)'
    left = [
        '<g class="mini" style="transform-origin:84px 86px"><circle cx="84" cy="86" r="11" fill="#15100e"/><circle cx="84" cy="86" r="7.5" fill="none" stroke="rgba(255,255,255,0.14)"/>'
        '<circle cx="84" cy="86" r="4" fill="#f1e8d6"/><rect x="83" y="82" width="2" height="2" fill="#3b5a69"/></g>',
        text(MONO, 'NOW PLAYING', 12, 106, 91, muted, 0.2),
        text(SERIF, "Hi, I'm Qarina.", 56, 72, 162, cream),
    ]
    body_svg, end = para(SANS_LIGHT, INTRO, 18.5, 72, 210, 560, 31, muted)
    left.append(body_svg)
    left.append(text(MONO, 'INTERESTED IN', 11, 72, end + 54, muted, 0.18))
    focus_svg, left_end = chips(FOCUS, 72, end + 70, 580)
    left.append(focus_svg)
    # The tools, grouped, on the right.
    rx, rw = 712, 416
    right = [text(MONO, 'ON ROTATION', 12, rx, 91, muted, 0.2)]
    y = 126
    for name, categories, color in GROUPS:
        names = [s['name'] for s in sorted(ROWS['skills'], key=lambda s: s.get('sort_order') or 0) if (s.get('category') or 'Tool') in categories]
        if not names:
            continue
        right.append(text(MONO, name, 10.5, rx, y + 4, 'rgba(241,235,224,0.6)', 0.16))
        group_svg, y = chips(names, rx, y + 14, rw, 13.5, dot=color, gap=7)
        right.append(group_svg)
        y += 22
    h = int(max(left_end, y - 22) + 64)
    rings = ''.join(f'<circle cx="1210" cy="{h + 40}" r="{r}" fill="none" stroke="rgba(255,255,255,{0.05 if i % 4 else 0.08})"/>' for i, r in enumerate(range(150, 640, 12)))
    defs = (f'<clipPath id="card"><rect x="1" y="1" width="{W - 2}" height="{h - 2}" rx="28"/></clipPath>'
            '<linearGradient id="blue" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#46697a"/><stop offset="0.55" stop-color="#3b5a69"/><stop offset="1" stop-color="#2c4552"/></linearGradient>')
    style = '.mini { transform-box: view-box; animation: spin 2.4s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } } ' + REDUCE
    tools = ', '.join(s['name'] for s in ROWS['skills'])
    body = (f'<g clip-path="url(#card)"><rect width="{W}" height="{h}" fill="url(#blue)"/>{rings}{"".join(left)}{"".join(right)}</g>'
            f'<rect x="1" y="1" width="{W - 2}" height="{h - 2}" rx="28" fill="none" stroke="rgba(255,255,255,0.14)" stroke-width="1.5"/>')
    return doc(h, body, title="Hi, I'm Qarina", desc=f'{INTRO} Interested in {", ".join(FOCUS)}. On rotation: {tools}.', style=style, defs=defs)


# ---- 3. Selected projects, as record sleeves --------------------------------------------------

FEATURED = [
    dict(no='01', name='AgentBuff', tag='Agentic AI Platform', tech='React.js · Agentic AI · TypeScript', title_match='AgentBuff — Agentic',
         sleeve='#3b5a69', ink=C['on_dark'], soft='rgba(241,235,224,0.75)', rim='rgba(255,255,255,0.10)'),
    dict(no='02', name='WIKA Q-Nexus', tag='Tender and Procurement Platform', tech='React · TypeScript · Node.js', title_match='WIKA Q-Nexus',
         sleeve='#e4ecee', ink=C['ink'], soft=C['ink_soft'], rim='rgba(34,26,21,0.10)'),
    dict(no='03', name='WIKA HC Workspace', tag='EPCC Human Capital Platform', tech='Next.js · Prisma', title_match='WIKA HC Workspace',
         sleeve='#2a1f19', ink=C['on_dark'], soft='rgba(241,235,224,0.72)', rim='rgba(255,255,255,0.10)'),
]


def project_by_title(prefix):
    return next(p for p in PROJECTS if p['title'].startswith(prefix))


def heading(theme, title, note):
    t = T[theme]
    nw = MONO.width(note, 11.5, 0.16)
    body = (text(SERIF, title, 46, 72, 74, t['ink'])
            + f'<circle cx="{num(W - 72 - nw - 14)}" cy="66" r="4" fill="{t["accent"]}"/>' + text(MONO, note, 11.5, W - 72, 70, t['soft'], 0.16, 'end'))
    return doc(104, body, title=title, desc=note.capitalize())


def sleeve(theme, i, item):
    t = T[theme]
    h, sx, sy, s = 392, 20, 22, 272
    dx, dy, dr = sx + s - 8, sy + s / 2, 106
    project = project_by_title(item['title_match'])
    image, _ = data_uri(screenshot(project['id']), 520)
    grooves = ''.join(f'<circle cx="{num(dx)}" cy="{num(dy)}" r="{r}" fill="none" stroke="rgba(18,34,42,{0.3 if k % 3 else 0.45})" stroke-width="0.8"/>'
                      for k, r in enumerate(range(42, dr - 3, 4)))
    lw = MONO.width('LIVE', 10.5, 0.16)
    shot = f'x="{sx + 20}" y="{sy + 46}" width="{s - 40}" height="132"'
    defs = (f'<radialGradient id="vinyl" cx="{num(dx)}" cy="{num(dy)}" r="{dr}" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#557d8d"/>'
            '<stop offset="0.35" stop-color="#628a99"/><stop offset="0.72" stop-color="#48697a"/><stop offset="1" stop-color="#3a5767"/></radialGradient>'
            f'<linearGradient id="sheen" x1="{num(dx - dr)}" y1="{num(dy - dr)}" x2="{num(dx + dr)}" y2="{num(dy + dr)}" gradientUnits="userSpaceOnUse">'
            '<stop offset="0.25" stop-color="#fff" stop-opacity="0"/><stop offset="0.4" stop-color="#fff" stop-opacity="0.22"/><stop offset="0.52" stop-color="#fff" stop-opacity="0"/>'
            '<stop offset="0.75" stop-color="#fff" stop-opacity="0"/><stop offset="0.85" stop-color="#fff" stop-opacity="0.14"/><stop offset="0.95" stop-color="#fff" stop-opacity="0"/></linearGradient>'
            f'<clipPath id="shot"><rect {shot} rx="3"/></clipPath>'
            f'<filter id="drop" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="12" stdDeviation="12" flood-color="{t["shadow"]}"/></filter>')
    style = (f'.disc {{ transform-box: view-box; transform-origin: {num(dx)}px {num(dy)}px; animation: spin {7 + i}s linear infinite; }} '
             '@keyframes spin { to { transform: rotate(360deg); } } ' + REDUCE)
    disc = (f'<g class="disc"><circle cx="{num(dx)}" cy="{num(dy)}" r="{dr}" fill="url(#vinyl)"/>{grooves}'
            f'<circle cx="{num(dx)}" cy="{num(dy)}" r="{dr}" fill="url(#sheen)"/><circle cx="{num(dx)}" cy="{num(dy)}" r="34" fill="#f1e8d6"/>'
            f'<circle cx="{num(dx)}" cy="{num(dy)}" r="34" fill="none" stroke="rgba(18,34,42,0.25)" stroke-width="3"/>'
            + text(ITALIC_SEMI, f'A{i + 1}', 22, dx, dy - 8, C['blue_deep'], 0, 'middle')
            + f'<circle cx="{num(dx)}" cy="{num(dy)}" r="3" fill="#1b2a31"/></g>')
    body = ''.join([
        f'<g filter="url(#drop)">{disc}<rect x="{sx}" y="{sy}" width="{s}" height="{s}" rx="6" fill="{item["sleeve"]}"/></g>',
        f'<rect x="{sx + 7}" y="{sy + 7}" width="{s - 14}" height="{s - 14}" rx="3" fill="none" stroke="{item["rim"]}"/>',
        text(MONO, f'NO. {item["no"]}', 10.5, sx + 20, sy + 30, item['soft'], 0.16),
        f'<circle cx="{num(sx + s - 20 - lw - 11)}" cy="{sy + 26}" r="3.6" fill="{C["copper_bright"]}"/>',
        text(MONO, 'LIVE', 10.5, sx + s - 20, sy + 30, item['soft'], 0.16, 'end'),
        f'<image href="{image}" {shot} preserveAspectRatio="xMidYMin slice" clip-path="url(#shot)"/>',
        f'<rect {shot} rx="3" fill="none" stroke="{item["rim"]}"/>',
        text(SERIF, item['name'], fit(SERIF, item['name'], 31, s - 40), sx + 19, sy + 222, item['ink']),
        text(ITALIC, item['tag'], fit(ITALIC, item['tag'], 17, s - 40), sx + 20, sy + 247, item['soft']),
        text(MONO, item['tech'], 11.5, sx + 2, sy + s + 38, t['faint']),
        link_text('Visit site', 14, sx + 2, sy + s + 68, t['accent']),
    ])
    return doc(h, body, title=f'{item["name"]}: {item["tag"]}', desc=f'{item["name"]}, {item["tag"]}. Built with {item["tech"]}. Live.', style=style, defs=defs, w=400)


# ---- 4. Footer ---------------------------------------------------------------------------------

def footer():
    h = 260
    avatar, (aw, ah) = data_uri(f'{SITE}/avatar/wave.webp', 360, 'WEBP', 80)
    avatar_h = 380
    avatar_w = avatar_h * aw / ah
    notes = ''.join(
        f'<g class="note" style="animation-delay:{delay}s;transform-origin:{x}px {y}px"><g transform="translate({x - 18} {y - 18}) scale(1.5)" '
        f'fill="{color}" stroke="{C["espresso"]}" stroke-width="1.4" paint-order="stroke">{shape}</g></g>'
        for x, y, delay, shape, color in [(880, 190, 0, NOTE_EIGHTH, C['blue_bright']), (1110, 150, 1.6, NOTE_PAIR, C['copper_bright']), (905, 120, 3.2, NOTE_PAIR, C['blue_bright'])]
    )
    rings = ''.join(f'<circle cx="-40" cy="{h + 30}" r="{r}" fill="none" stroke="rgba(143,182,198,{0.06 if i % 4 else 0.1})"/>' for i, r in enumerate(range(120, 520, 12)))
    style = ('.note { opacity: 0; transform-box: view-box; animation: rise 4.8s ease-out infinite; } '
             '@keyframes rise { 0% { opacity: 0; transform: translate(0,0) scale(.5); } 15% { opacity: 1; } 100% { opacity: 0; transform: translate(-30px,-90px) scale(1) rotate(-8deg); } } ' + REDUCE)
    defs = (f'<clipPath id="card"><rect x="1" y="1" width="{W - 2}" height="{h - 2}" rx="28"/></clipPath>'
            f'<radialGradient id="glow" cx="220" cy="0" r="900" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="{C["panel"]}"/><stop offset="1" stop-color="{C["espresso"]}"/></radialGradient>')
    body = ''.join([
        f'<g clip-path="url(#card)"><rect width="{W}" height="{h}" fill="url(#glow)"/>{rings}',
        text(MONO, 'END OF SIDE B', 12.5, 72, 96, C['blue_bright'], 0.22),
        text(ITALIC, 'Thanks for listening.', 60, 70, 164, C['on_dark']),
        text(SANS_LIGHT, "Let's build something together.", 18, 72, 206, C['on_dark_muted']),
        f'{notes}<image href="{avatar}" x="{num(1000 - avatar_w / 2)}" y="40" width="{num(avatar_w)}" height="{avatar_h}"/></g>',
        f'<rect x="1" y="1" width="{W - 2}" height="{h - 2}" rx="28" fill="none" stroke="rgba(241,235,224,0.12)" stroke-width="1.5"/>',
    ])
    return doc(h, body, title='End of side B. Thanks for listening.', desc="Let's build something together.", style=style, defs=defs)


# ---- 5. Lettering for the GitHub charts ----------------------------------------------

def chart_glyphs():
    """Outlines charts.py needs: fixed lines already in place, plus single characters it can set."""
    def table(face, chars):
        out = {}
        for ch in chars:
            run = face.shape(ch)
            if not run:
                continue
            name, adv, _, _ = run[0]
            out[ch] = {'d': face.glyph_path(name, 100, 0, 0), 'adv': round(adv * 100 / face.upem, 2)}
        return out

    return {
        'title': SERIF.path('A year in grooves', 54, 72, 108),
        'subtitle1': SANS_LIGHT.path('Every day on GitHub, pressed into one record.', 18.5, 72, 146),
        'subtitle2': SANS_LIGHT.path('The busier the day, the brighter the groove.', 18.5, 72, 174),
        'labels': {k: MONO.path(v, 11, 0, 0, 0.14) for k, v in {
            'total': 'CONTRIBUTIONS', 'streak': 'LONGEST STREAK', 'month': 'BEST MONTH', 'week': 'PER WEEK', 'day': 'BY DAY OF THE WEEK'}.items()},
        'days': MONO.path('DAYS', 11, 0, 0, 0.14),
        'less': MONO.path('LESS', 10, 0, 0, 0.14), 'more': MONO.path('MORE', 10, 0, 0, 0.14),
        'mark': ITALIC_SEMI.path('A.Q.S', 26, 0, 0, 0, 'middle'),
        'serif': table(SERIF, '0123456789,'),
        'mono': table(MONO, ''.join(chr(c) for c in range(32, 127)) + '–·'),
    }


if __name__ == '__main__':
    files = {'intro.svg': intro(), 'footer.svg': footer()}
    for theme in ('light', 'dark'):
        files[f'header-{theme}.svg'] = header(theme)
        files[f'projects-{theme}.svg'] = heading(theme, 'Selected projects', 'MORE IN MY PINNED REPOSITORIES')
        for i, item in enumerate(FEATURED):
            files[f'sleeve-{item["no"]}-{theme}.svg'] = sleeve(theme, i, item)
    for old in HERE.glob('*.svg'):
        if old.name not in files and not old.name.startswith('grooves-'):
            old.unlink()
    for name, svg in files.items():
        (HERE / name).write_text(svg)
    (HERE / 'glyphs.json').write_text(json.dumps(chart_glyphs(), separators=(',', ':')))
    print(f'{len(files)} pictures, {sum(len(s) for s in files.values()) / 1024:.0f} KB in all')
