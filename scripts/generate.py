#!/usr/bin/env python3
"""Build the profile README images (light + dark SVG) from data/stats.json.

Colours follow GitHub's own Primer palette, and card backgrounds are transparent (or a
translucent tint), so the images sit on whatever GitHub theme the visitor uses:
Light, Dark, Dark dimmed or high contrast.

Fonts (Geist, OFL) are subset and embedded, so the images render the same everywhere.
Usage: FONT_DIR=node_modules/@fontsource python scripts/generate.py assets
       VARIANT=compact|tinted|ruled|outline|surface switches the card style (default: open)
       PKG_LAYOUT=stacked puts each package in one column instead of name | description (default: split)
       TOTAL_IN=hero moves total Packagist installs from the section title into the top stats
       SDK_NOTE=installs keeps installs in section 01's title even when every package's tests pass (default: tests)
"""
import base64, datetime, io, json, os, sys
from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
FONT_DIR = os.environ.get('FONT_DIR', 'node_modules/@fontsource')
OUT = sys.argv[1] if len(sys.argv) > 1 else 'assets'
STATS_FILE = os.environ.get('STATS_FILE', os.path.join(ROOT, 'data', 'stats.json'))
LARAVEL_SINCE = 2014          # "N+ years with Laravel"
SHOW_DOWNLOADS_FROM = 1000    # a package row shows its own count once it passes this; below it, an arrow
TOTAL_IN = os.environ.get('TOTAL_IN', 'header')  # where total Packagist installs go: header (section 01) | hero
SDK_NOTE = os.environ.get('SDK_NOTE', 'tests')   # section 01's note when all tests pass: tests | installs
TODAY = datetime.date.today()

PACKAGES = [  # name, category, description, tags
    ('laravel-bog-sdk', 'FINTECH · BANK OF GEORGIA',
     'Payments, iPay, Installment, Billing, Bonline, BOG-ID and Open Banking — with OAuth2, typed DTOs and signed callbacks.',
     ['PHP 8.3', 'Laravel 12', 'OAuth2', 'OpenID']),
    ('laravel-rsge', 'GOV · REVENUE SERVICE',
     'The rs.ge SOAP API for Laravel — Z-reports, taxpayer info, waybills and more, without touching raw XML.',
     ['SOAP', 'PHPStan', 'PHPUnit']),
    ('laravel-fina-sdk', 'ERP · FINA WEB API v8',
     'Auth, operations and reporting for FINA ERP — typed DTOs, request chunking and validation out of the box.',
     ['PHP 8.2', 'Typed DTOs', 'PHPStan']),
    ('laravel-shopify-sdk', 'COMMERCE · SHOPIFY',
     'Shopify Admin API for Laravel 12 — OAuth, webhooks, GraphQL & REST, data mirroring, multi-store and a Filament panel.',
     ['PHP 8.3', 'GraphQL', 'Filament', 'Pest']),
    ('laravel-stringer', 'AI · CONTENT',
     'A Telegram-driven LLM blog drafter — per-locale drafts, generated cover images, Filament admin and multi-channel SEO.',
     ['Laravel 12', 'Telegram', 'LLM', 'Filament']),
]
NAMES = [p[0] for p in PACKAGES]

try:
    with open(STATS_FILE) as fh:
        STATS = json.load(fh)
except (OSError, ValueError):
    STATS = {}
STATS.setdefault('packages', {})

# GitHub Primer colours. Text and line colours are the ones GitHub's Dark and Dark dimmed
# themes share; fills are translucent so they tint whichever canvas is underneath.
THEMES = {
    'dark': dict(text='#e6edf3', muted='#9198a1', faint='#7d8590', border='#3d444d', accent='#3fb950',
                 grid='rgba(145,152,161,.22)', chip='rgba(101,108,118,.2)', chipb='#3d444d',
                 glyph='rgba(145,152,161,.18)', surface='rgba(101,108,118,.14)', surfaceb='rgba(61,68,77,.7)', danger='#f85149'),
    'light': dict(text='#1f2328', muted='#59636e', faint='#818b98', border='#d1d9e0', accent='#1a7f37',
                  grid='rgba(129,139,152,.3)', chip='rgba(129,139,152,.12)', chipb='#d1d9e0',
                  glyph='rgba(129,139,152,.22)', surface='rgba(129,139,152,.07)', surfaceb='rgba(209,217,224,.7)', danger='#d1242f'),
}

VARIANTS = {
    # frame: border | tint (translucent fill) | rule (hairline on top) | none
    # dots: fading dot grid · compact: tighter layout
    'outline': dict(frame='border', dots=True, compact=False),
    'surface': dict(frame='tint', dots=False, compact=False),
    'compact': dict(frame='border', dots=True, compact=True),
    'tinted':  dict(frame='tint', dots=True, compact=True),
    'open':    dict(frame='none', dots=False, compact=True),
    'ruled':   dict(frame='rule', dots=False, compact=True),
}
VARIANT = os.environ.get('VARIANT', 'open')
V = VARIANTS[VARIANT]
C = V['compact']
OPEN = V['frame'] in ('none', 'rule')  # no box: content runs to the edges and the empty padding is cropped
RADIUS = 14  # ≈ GitHub's 6px corner radius once the image is scaled into the README

# ------------------------------------------------------------------ fonts
FONTS = {  # key: (css family, file)
    'disp':  ('Dsp',  'geist-sans/files/geist-sans-latin-600-normal.woff2'),
    'sans':  ('San',  'geist-sans/files/geist-sans-latin-400-normal.woff2'),
    'sansm': ('SanM', 'geist-sans/files/geist-sans-latin-500-normal.woff2'),
    'sansb': ('SanB', 'geist-sans/files/geist-sans-latin-600-normal.woff2'),
    'mono':  ('Mon',  'geist-mono/files/geist-mono-latin-400-normal.woff2'),
}
DS, DLS = 0.72, -0.035  # display size scale and tracking
_tt = {}


def font(key):
    if key not in _tt:
        _tt[key] = TTFont(os.path.join(FONT_DIR, FONTS[key][1]))
    return _tt[key]


def dsize(key, size, ls):
    if key == 'disp':
        size = round(size * DS, 1)
        ls = round(DLS * size, 2)
    return size, ls


def measure(text, key, size, ls=0.0):
    size, ls = dsize(key, size, ls)
    f = font(key)
    cmap, hmtx, upm = f.getBestCmap(), f['hmtx'], f['head'].unitsPerEm
    return sum(hmtx[cmap[ord(ch)]][0] * size / upm + ls for ch in text)


def subset_b64(key, chars):
    opts = subset.Options()
    opts.flavor, opts.layout_features, opts.name_IDs = 'woff2', ['kern', 'liga', 'calt'], []
    f = TTFont(os.path.join(FONT_DIR, FONTS[key][1]))
    sub = subset.Subsetter(opts)
    sub.populate(text=''.join(sorted(set(chars))) + ' ')
    sub.subset(f)
    buf = io.BytesIO()
    f.flavor = 'woff2'
    f.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


class Doc:
    """Collects SVG elements and the characters each font needs."""

    def __init__(self, w, h, title, crop=None):
        """crop=(top, bottom): the visible band when there is no box around the content."""
        self.w, self.h, self.title = w, h, title
        self.y0, self.vh = (crop[0], crop[1] - crop[0]) if crop and OPEN else (0, h)
        self.els, self.chars, self.css = [], {}, []

    def t(self, x, y, text, key, size, fill, anchor='start', ls=0, extra=''):
        self.chars.setdefault(key, set()).update(text)
        size, ls = dsize(key, size, ls)
        a = f' text-anchor="{anchor}"' if anchor != 'start' else ''
        l = f' letter-spacing="{ls}"' if ls else ''
        self.els.append(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONTS[key][0]}" font-size="{size}" '
                        f'fill="{fill}"{a}{l} {extra}>{esc(text)}</text>')

    def spans(self, x, y, parts, size, anchor='start', ls=0):
        """parts: (text, font key, fill); all parts share one size."""
        if all(k == 'disp' for _, k, _ in parts):
            size, ls = dsize('disp', size, ls)
        out = []
        for text, key, fill in parts:
            self.chars.setdefault(key, set()).update(text)
            out.append(f'<tspan font-family="{FONTS[key][0]}" fill="{fill}">{esc(text)}</tspan>')
        a = f' text-anchor="{anchor}"' if anchor != 'start' else ''
        l = f' letter-spacing="{ls}"' if ls else ''
        self.els.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" xml:space="preserve"{a}{l}>{"".join(out)}</text>')

    def raw(self, s):
        self.els.append(s)

    def save(self, name, theme):
        faces = [f"@font-face{{font-family:'{FONTS[k][0]}';src:url(data:font/woff2;base64,{subset_b64(k, c)}) format('woff2')}}"
                 for k, c in self.chars.items()]
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.vh}" viewBox="0 {self.y0} {self.w} {self.vh}" '
               f'role="img" aria-label="{esc(self.title)}">\n<title>{esc(self.title)}</title>\n'
               f'<style>\n' + '\n'.join(faces + self.css) + '\n</style>\n' + '\n'.join(self.els) + '\n</svg>\n')
        with open(os.path.join(OUT, f'{name}-{theme}.svg'), 'w') as fh:
            fh.write(svg)


def card(d, T, r=RADIUS):
    frame = V['frame']
    if frame == 'border':
        d.raw(f'<rect x="0.5" y="0.5" width="{d.w - 1}" height="{d.h - 1}" rx="{r}" fill="none" stroke="{T["border"]}"/>')
    elif frame == 'tint':
        d.raw(f'<rect width="{d.w}" height="{d.h}" rx="{r}" fill="{T["surface"]}"/>')
    elif frame == 'rule':  # ≈1px hairline across the top once scaled into the README
        d.raw(f'<line x1="0" x2="{d.w}" y1="{d.y0 + 1.2}" y2="{d.y0 + 1.2}" stroke="{T["border"]}" stroke-width="2.4"/>')


def dots(d, T, start=0.35):
    """Dot grid that fades in towards the right edge."""
    if not V['dots']:
        return
    d.raw(f'<defs><pattern id="dots" width="28" height="28" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.3" fill="{T["grid"]}"/></pattern>'
          f'<linearGradient id="fade" x1="0" x2="1"><stop offset="{start}" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff"/></linearGradient>'
          f'<mask id="m"><rect width="{d.w}" height="{d.h}" fill="url(#fade)"/></mask>'
          f'<clipPath id="clip"><rect x="1" y="1" width="{d.w - 2}" height="{d.h - 2}" rx="{RADIUS}"/></clipPath></defs>'
          f'<g clip-path="url(#clip)"><rect width="{d.w}" height="{d.h}" fill="url(#dots)" mask="url(#m)"/></g>')


def arrow(d, x, y, s, color, sw=2.2):
    d.raw(f'<path d="M{x - s} {y + s} L{x} {y} M{x - s * 0.62} {y} L{x} {y} L{x} {y + s * 0.62}" fill="none" '
          f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"/>')


def wrap(text, key, size, maxw):
    lines, cur = [], ''
    for word in text.split(' '):
        trial = (cur + ' ' + word).strip()
        if measure(trial, key, size) <= maxw:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + [cur]


def kfmt(n):
    return f'{n / 1000:.1f}k'.replace('.0k', 'k') if n >= 1000 else str(n)


def total_installs():
    return sum(STATS['packages'].get(n, {}).get('downloads', 0) for n in NAMES)


def date(iso, fmt='long'):
    d = datetime.date.fromisoformat(iso)
    return f'{d:%b} {d.day}, {d.year}' if fmt == 'long' else f'{d:%b %Y}'.upper()


PULSE = ('@media (prefers-reduced-motion:no-preference){{.pulse{{transform-origin:{x}px {y}px;animation:pulse 2.4s ease-out infinite}}'
         '@keyframes pulse{{0%{{transform:scale(1);opacity:.7}}100%{{transform:scale(3);opacity:0}}}}}}')


def status_dot(d, T, x, y):
    d.raw(f'<circle cx="{x}" cy="{y}" r="7" fill="{T["accent"]}"/>'
          f'<circle class="pulse" cx="{x}" cy="{y}" r="7" fill="none" stroke="{T["accent"]}" stroke-width="2"/>')
    d.css.append(PULSE.format(x=x, y=y))


# ------------------------------------------------------------------ hero
def hero_stats():
    contrib = STATS.get('contributions')
    sdks = (kfmt(total_installs()), 'PACKAGIST INSTALLS') if TOTAL_IN == 'hero' else (str(len(PACKAGES)), 'OPEN-SOURCE SDKS')
    return [(f'{TODAY.year - LARAVEL_SINCE}+', 'YEARS WITH LARAVEL'), sdks,
            (kfmt(contrib) if contrib else '—', 'GITHUB CONTRIBUTIONS'), ('Pirdapir.ge', 'FOUNDER & DIRECTOR')]


def composer(d, T, X, py, ph, cs):
    """`$ composer require giorgigrdzelidze/<package>`, cycling through the packages."""
    base = py + ph / 2 + cs * 0.36
    prefix = [('$ ', 'mono', T['accent']), ('composer require ', 'mono', T['text']), ('giorgigrdzelidze/', 'mono', T['muted'])]
    pw = sum(measure(t, 'mono', cs) for t, _, _ in prefix)
    longest = max(measure(n, 'mono', cs) for n in NAMES)
    d.raw(f'<rect x="{X}" y="{py}" width="{pw + longest + 70:.0f}" height="{ph}" rx="12" fill="{T["chip"]}" stroke="{T["chipb"]}"/>')
    d.spans(X + 26, base, prefix, cs)
    step = 15 / len(NAMES)
    for i, name in enumerate(NAMES):
        nx = X + 26 + pw
        d.chars.setdefault('mono', set()).update(name)
        d.raw(f'<g class="pkg{" p0" if i == 0 else ""}" style="animation-delay:{i * step:.1f}s"><text x="{nx:.1f}" y="{base:.1f}" font-family="Mon" font-size="{cs}" fill="{T["text"]}">{name}</text>'
              f'<rect class="cur" x="{nx + measure(name, "mono", cs) + 5:.1f}" y="{base - cs * 0.92:.1f}" width="{cs / 2:.0f}" height="{cs * 1.15:.0f}" fill="{T["accent"]}"/></g>')
    share = 100 / len(NAMES)
    d.css.append('.pkg{opacity:0}.p0{opacity:1}'
                 '@media (prefers-reduced-motion:no-preference){.pkg{animation:cycle 15s infinite}'
                 f'@keyframes cycle{{0%{{opacity:0;transform:translateY(8px)}}{share * .12:.1f}%{{opacity:1;transform:translateY(0)}}'
                 f'{share * .88:.1f}%{{opacity:1;transform:translateY(0)}}{share:.1f}%{{opacity:0;transform:translateY(-8px)}}100%{{opacity:0}}}}'
                 '.cur{animation:blink 1s steps(1) infinite}@keyframes blink{50%{opacity:0}}}')


def composer_width(cs):
    return measure('$ composer require giorgigrdzelidze/', 'mono', cs) + max(measure(n, 'mono', cs) for n in NAMES) + 70


def hero(theme):
    T = THEMES[theme]
    years = TODAY.year - LARAVEL_SINCE
    stats = hero_stats()
    if C:
        L = dict(H=652, top=78, rule=106, name_y=232, name_size=150, tag_y=(310, 352), tag_size=30,
                 py=386, ph=64, comp=24, sy=484, num_dy=84, num_size=62, lab_dy=124, glyph=380)
    else:
        L = dict(H=760, top=90, rule=120, name_y=276, name_size=172, tag_y=(362, 410), tag_size=32,
                 py=446, ph=72, comp=26, sy=568, num_dy=92, num_size=70, lab_dy=136, glyph=440)
    d = Doc(1600, L['H'], f'Giorgi Grdzelidze — Senior Laravel engineer in Tbilisi, Georgia. {years}+ years with Laravel, '
                          f'{len(PACKAGES)} open-source SDKs, founder of Pirdapir.ge.',
            crop=(40, L['sy'] + L['lab_dy'] + 14))
    W, H, X = d.w, d.h, (8 if OPEN else 96)
    card(d, T)
    dots(d, T)
    d.raw(f'<defs><clipPath id="gclip"><rect x="0" y="{L["rule"] + 2}" width="{W}" height="{L["sy"] - L["rule"] - 2}"/></clipPath></defs><g clip-path="url(#gclip)">')
    d.t(W - (8 if OPEN else 70), L['sy'] + 30, 'GG', 'disp', L['glyph'], 'none', anchor='end', extra=f'stroke="{T["glyph"]}" stroke-width="2.5"')
    d.raw('</g>')
    for cx, cy in ([] if OPEN else [(40, 40), (W - 40, 40), (40, H - 40), (W - 40, H - 40)]):
        d.raw(f'<path d="M{cx - 7} {cy} H{cx + 7} M{cx} {cy - 7} V{cy + 7}" stroke="{T["faint"]}" stroke-width="1.4"/>')
    status_dot(d, T, X + 7, L['top'] - 8)
    d.t(X + 30, L['top'], 'AVAILABLE FOR SENIOR CONTRACTS', 'mono', 22, T['muted'], ls=2.4)
    d.t(W - X, L['top'], 'TBILISI, GE · 41.7151° N, 44.8271° E', 'mono', 22, T['faint'], anchor='end', ls=2.4)
    d.raw(f'<line x1="{X}" x2="{W - X}" y1="{L["rule"]}" y2="{L["rule"]}" stroke="{T["border"]}"/>')
    d.t(X - 4, L['name_y'], 'Giorgi Grdzelidze', 'disp', L['name_size'], T['text'])
    for y, line in zip(L['tag_y'], [
        [('Senior Laravel engineer. ', 'sansm', T['text']), ('I design APIs, wire up integrations', 'sans', T['muted'])],
        [('and publish the ', 'sans', T['muted']), ('SDKs Georgian businesses run on.', 'sansm', T['text'])],
    ]):
        d.spans(X, y, line, L['tag_size'])
    composer(d, T, X, L['py'], L['ph'], L['comp'])
    sy, colw = L['sy'], (W - 2 * X) / 4
    d.raw(f'<line x1="{X}" x2="{W - X}" y1="{sy}" y2="{sy}" stroke="{T["border"]}"/>')
    for i, (num, label) in enumerate(stats):
        cx = X + i * colw + (40 if i else 0)
        if i:
            d.raw(f'<line x1="{X + i * colw:.1f}" x2="{X + i * colw:.1f}" y1="{sy + 32}" y2="{sy + L["lab_dy"] + 8}" stroke="{T["border"]}"/>')
        d.t(cx, sy + L['num_dy'], num, 'disp', L['num_size'], T['text'])
        d.t(cx, sy + L['lab_dy'], label, 'mono', 19, T['faint'], ls=2.2)
    d.save('hero', theme)


# ------------------------------------------------------------------ latest release strip
def now(theme):
    T = THEMES[theme]
    rel = [(p['latest_date'], n, p['latest']) for n, p in STATS['packages'].items() if n in NAMES and p.get('latest_date')]
    d = Doc(1600, 92 if C else 104, 'Latest release', crop=(14, 76))
    c, X = d.h / 2, (8 if OPEN else 49)
    card(d, T)
    status_dot(d, T, X + 7, c)
    d.t(X + 31, c + 7, 'LATEST RELEASE', 'mono', 19, T['faint'], ls=2.2)
    if rel:
        when, name, ver = max(rel)
        d.title = f'Latest release: {name} {ver}, {date(when)}'
        x = 380
        d.t(x, c + 10, name, 'sansm', 32, T['text'])
        x += measure(name, 'sansm', 32) + 18
        d.t(x, c + 9, ver, 'mono', 26, T['accent'])
        x += measure(ver, 'mono', 26) + 18
        d.t(x, c + 10, f'· {date(when)}', 'sans', 30, T['muted'])
    if STATS.get('updated'):
        d.t(d.w - (8 if OPEN else 56), c + 7, f'SYNCED {date(STATS["updated"]).upper()}', 'mono', 19, T['faint'], anchor='end', ls=2.2)
    d.save('now', theme)


# ------------------------------------------------------------------ contribution streak
CELL, GAP = 17, 5                       # heatmap cell and gap; one column per week, Sunday on top like GitHub
LEVEL_OPACITY = [0, .32, .55, .78, 1]   # GitHub's data-level 0-4 as accent opacity


def streak(theme):
    T = THEMES[theme]
    s = STATS.get('streak') or {}
    cur, best, year = s.get('current', 0), s.get('longest', 0), s.get('year', 0)
    days = lambda n: 'day' if n == 1 else 'days'
    since = date(s['current_start']) if cur and s.get('current_start') else None
    d = Doc(1600, 290, f'Contribution streak: {cur} {days(cur)} in a row' + (f' since {since}' if since else '')
                       + f'. Longest streak {best} {days(best)}. {year:,} contributions in {TODAY.year}.', crop=(22, 272))
    W, X = d.w, (8 if OPEN else 56)
    card(d, T)
    # header: status, label, since
    if cur:
        status_dot(d, T, X + 7, 52)
    else:
        d.raw(f'<circle cx="{X + 7}" cy="52" r="7" fill="none" stroke="{T["faint"]}" stroke-width="2"/>')
    d.t(X + 30, 60, 'CONTRIBUTION STREAK', 'mono', 20, T['muted'], ls=2.4)
    note = f'EVERY DAY SINCE {since.upper()}' if since else 'NEXT ONE STARTS TODAY'
    d.t(W - X, 60, note, 'mono', 20, T['faint'], anchor='end', ls=2.4)
    d.raw(f'<line x1="{X}" x2="{W - X}" y1="86" y2="86" stroke="{T["border"]}"/>')
    # heatmap of the last weeks, right-aligned; the current streak at full strength, older days dimmed
    grid = s.get('grid') or {}
    levels, start = grid.get('levels', ''), grid.get('start')
    weeks = -(-len(levels) // 7)
    hx, hy, pitch = W - X - (weeks * (CELL + GAP) - GAP), 106, CELL + GAP
    if levels and start:
        first = datetime.date.fromisoformat(start)
        streak_from = s.get('current_start') if cur else None
        for i, lv in enumerate(levels):
            day = (first + datetime.timedelta(days=i)).isoformat()
            x, y = hx + (i // 7) * pitch, hy + (i % 7) * pitch
            lv = int(lv)
            if lv == 0:
                d.raw(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="4" fill="{T["chip"]}"/>')
            else:
                op = LEVEL_OPACITY[lv] * (1 if streak_from and day >= streak_from else .45)
                d.raw(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="4" fill="{T["accent"]}" fill-opacity="{op:.2f}"/>')
            if i == len(levels) - 1:  # today
                d.raw(f'<rect x="{x - 3}" y="{y - 3}" width="{CELL + 6}" height="{CELL + 6}" rx="6" fill="none" stroke="{T["accent"]}" stroke-width="2"/>')
    # numbers: current streak large, then longest and this year, in the hero's stat style
    base, lab = 214, 253
    cols = [((f'{cur:,}', 150), days(cur), 'CURRENT STREAK'),
            ((f'{best:,}', 62), days(best), 'LONGEST STREAK'),
            ((f'{year:,}', 62), None, f'CONTRIBUTIONS IN {TODAY.year}')]
    x = X
    for i, ((num, size), unit, label) in enumerate(cols):
        if i:
            d.raw(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{base - 70}" y2="{lab + 8}" stroke="{T["border"]}"/>')
            x += 40
        d.t(x - (4 if i == 0 else 0), base, num, 'disp', size, T['text'])
        w = measure(num, 'disp', size)
        if unit:
            usize = 36 if i == 0 else 26
            d.t(x + w + (14 if i == 0 else 10), base, unit, 'sansm', usize, T['muted'])
            w += measure(unit, 'sansm', usize) + 14
        d.t(x, lab, label, 'mono', 19, T['faint'], ls=2.2)
        x += max(w, measure(label, 'mono', 19, 2.2)) + 40
    assert x - 40 + 48 < hx, f'streak numbers run into the heatmap ({x - 40:.0f} vs {hx})'
    d.save('streak', theme)


# ------------------------------------------------------------------ link list
LINKS = [  # slug, category, name, short description
    ('site', 'WEBSITE', 'grdzelo.com', 'Portfolio, case studies and how I work'),
    ('email', 'EMAIL', 'grdzelog@gmail.com', 'Project enquiries — replies within two business days'),
    ('linkedin', 'CAREER', 'LinkedIn', 'Work history and professional updates'),
    ('pirdapir', 'PRODUCT', 'Pirdapir.ge', 'Owner-direct real-estate marketplace I founded'),
    ('packagist', 'PACKAGES', 'Packagist', 'Every giorgigrdzelidze/* Laravel package'),
    ('youtube', 'VIDEO', 'YouTube', 'Scuba diving in Tbilisi Sea and off-road Georgia'),
    ('instagram', 'PHOTO', 'Instagram', '@iamgrdzelo'),
    ('facebook', 'SOCIAL', 'Facebook', '@iamgrdzelo'),
]


def link_row(theme, idx, slug, cat, name, desc):
    T = THEMES[theme]
    d = Doc(1600, 72 if C else 88, f'{name} — {desc}', crop=(12, 62))
    c, X = d.h / 2, (8 if OPEN else 48)
    card(d, T)
    name_x = 380
    desc_x = name_x + max(measure(n, 'sansb', 34) for _, _, n, _ in LINKS) + 64
    d.t(X, c + 7, f'{idx:02d}', 'mono', 20, T['accent'], ls=2)
    d.t(X + 56, c + 7, cat, 'mono', 20, T['faint'], ls=2.2)
    d.t(name_x, c + 11, name, 'sansb', 34, T['text'], ls=-0.4)
    assert desc_x + measure(desc, 'sans', 27) < d.w - 110, desc
    d.t(desc_x, c + 10, desc, 'sans', 27, T['muted'])
    arrow(d, d.w - X, c - 11, 22, T['accent'] if idx == 1 else T['muted'])
    d.save(f'link-{slug}', theme)


# ------------------------------------------------------------------ section titles
def section(theme, num, title, note, name):
    T = THEMES[theme]
    s = 60 if C else 72              # title size
    base = 56 if C else 72           # title baseline
    d = Doc(1600, base + (18 if C else 24), f'{num} — {title}')
    d.t(8, base - 6, num, 'mono', 24, T['accent'], ls=2)
    d.t(76, base, title, 'disp', s, T['text'])
    x1 = 76 + measure(title, 'disp', s) + 36
    x2 = d.w - 8 - measure(note, 'mono', 21, 2.4) - 32
    d.raw(f'<line x1="{x1:.0f}" x2="{x2:.0f}" y1="{base - 15}" y2="{base - 15}" stroke="{T["border"]}"/>')
    d.t(d.w - 8, base - 9, note, 'mono', 21, T['faint'], anchor='end', ls=2.4)
    d.save(name, theme)


# ------------------------------------------------------------------ package rows (one full-width image each)
PKG_LAYOUT = os.environ.get('PKG_LAYOUT', 'split')  # split: name left, description right · stacked: one column
RIGHT_X, STAT_W = 560, 160                           # split: description column start, room kept for downloads at the end


def downloads(d, T, x, y, n):
    """Download icon + total Packagist downloads, right-aligned at x."""
    num = kfmt(n)
    d.t(x, y, num, 'sansb', 34, T['text'], anchor='end', ls=-0.4)
    ix, iy = x - measure(num, 'sansb', 34, -0.4) - 26, y - 12  # arrow into a tray
    d.raw(f'<path d="M{ix} {iy - 13} V{iy + 3} M{ix - 7} {iy - 4} L{ix} {iy + 3} L{ix + 7} {iy - 4} M{ix - 10} {iy + 11} H{ix + 10}" '
          f'fill="none" stroke="{T["accent"]}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>')


def tag_chips(d, T, x, y, tags):
    for tag in tags:
        tw = measure(tag, 'mono', 19)
        d.raw(f'<rect x="{x}" y="{y}" width="{tw + 34:.0f}" height="40" rx="20" fill="{T["chip"]}" stroke="{T["chipb"]}"/>')
        d.t(x + 17, y + 27, tag, 'mono', 19, T['muted'])
        x += tw + 46


def badge_width(status, size):
    return size * 1.12 + measure('TESTS PASSING' if status == 'passing' else 'TESTS FAILING', 'mono', size, 1.2)


def tests_badge(d, T, x, y, status, size, anchor='start'):
    """A check and TESTS PASSING (accent), or a cross and TESTS FAILING (red), on baseline y."""
    ok = status == 'passing'
    color, text = (T['accent'], 'TESTS PASSING') if ok else (T['danger'], 'TESTS FAILING')
    s, gap = size * 0.62, size * 0.5
    w = badge_width(status, size)
    x0, top = (x - w if anchor == 'end' else x), y - size * 0.68
    if ok:
        path = f'M{x0:.1f} {top + s * .55:.1f} L{x0 + s * .36:.1f} {top + s * .9:.1f} L{x0 + s:.1f} {top + s * .1:.1f}'
    else:
        path = (f'M{x0 + s * .12:.1f} {top + s * .12:.1f} L{x0 + s * .88:.1f} {top + s * .88:.1f} '
                f'M{x0 + s * .88:.1f} {top + s * .12:.1f} L{x0 + s * .12:.1f} {top + s * .88:.1f}')
    d.raw(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{size * .13:.1f}" stroke-linecap="round" stroke-linejoin="round"/>')
    d.t(x0 + s + gap, y, text, 'mono', size, color, ls=1.2)


def meta_row(d, T, x, y, meta, status, size, anchor='start'):
    """version · date, then the test badge when the package has a status."""
    if status:
        meta = meta + [(' · ', 'mono', T['faint'])]
    mw = sum(measure(t, 'mono', size, 1.2) for t, _, _ in meta)
    bw = badge_width(status, size) if status else 0
    x0 = x - mw - bw if anchor == 'end' else x
    d.spans(x0, y, meta, size, ls=1.2)
    if status:
        tests_badge(d, T, x0 + mw, y, status, size)


def tests_title(info):
    return f' Tests {info["tests"]}.' if info.get('tests') else ''


def sdk_note():
    """Section 01's note: tests passing on every package when that is true, otherwise total installs."""
    status = [STATS['packages'].get(n, {}).get('tests') for n in NAMES]
    if SDK_NOTE == 'tests' and all(st == 'passing' for st in status):
        return f'TESTS PASSING ON ALL {len(NAMES)}'
    return f'{kfmt(total_installs())} INSTALLS ON PACKAGIST' if TOTAL_IN == 'header' else 'GIORGIGRDZELIDZE/*'


def pkg_row(theme, idx, name, cat, desc, tags, slug=None, link=None):
    """One package per row. link=(text, ...) turns the row into the 'more work' row with an arrow instead of stats."""
    T = THEMES[theme]
    X = 8 if OPEN else 48
    info = {} if link else STATS['packages'].get(name, {})
    meta = ([(info['version'], 'mono', T['muted']), (f' · {date(info["date"], "short")}', 'mono', T['faint'])]
            if info.get('version') else [(link, 'mono', T['faint'])] if link else [])
    if PKG_LAYOUT == 'split':
        lines = wrap(desc, 'sans', 26, 1600 - X - RIGHT_X - STAT_W)[:2]
        d = Doc(1600, 196, f'{name} — {desc}' + tests_title(info), crop=(20, 180))
        card(d, T)
        d.t(X, 56, f'{idx:02d}', 'mono', 21, T['accent'], ls=2)
        d.t(X + 56, 56, cat, 'mono', 21, T['faint'], ls=2)
        d.t(X, 116, name, 'sansb', 48, T['text'], ls=-0.8)
        if info.get('downloads', 0) >= SHOW_DOWNLOADS_FROM:
            downloads(d, T, d.w - X, 116, info['downloads'])  # last in the row, like the link arrows below
        else:
            arrow(d, d.w - X, 92, 22, T['muted'])
        if meta:
            meta_row(d, T, X, 156, meta, info.get('tests'), 19)
        for i, line in enumerate(lines):
            d.t(RIGHT_X, 66 + i * 36, line, 'sans', 26, T['muted'])
        tag_chips(d, T, RIGHT_X, 124, tags)
    else:
        lines = wrap(desc, 'sans', 26, 1600 - 2 * X)[:2]
        ty = 166 + (len(lines) - 1) * 36 + 24
        bottom = ty + 40 if tags else ty - 14
        d = Doc(1600, bottom + 32, f'{name} — {desc}' + tests_title(info), crop=(20, bottom + 16))
        card(d, T)
        d.t(X, 56, f'{idx:02d}', 'mono', 21, T['accent'], ls=2)
        d.t(X + 56, 56, cat, 'mono', 21, T['faint'], ls=2)
        if meta:
            meta_row(d, T, d.w - X, 55, meta, info.get('tests'), 19, anchor='end')
        d.t(X, 120, name, 'sansb', 48, T['text'], ls=-0.8)
        if info.get('downloads', 0) >= SHOW_DOWNLOADS_FROM:
            downloads(d, T, d.w - X, 120, info['downloads'])
        else:
            arrow(d, d.w - X, 96, 22, T['muted'])
        for i, line in enumerate(lines):
            d.t(X, 166 + i * 36, line, 'sans', 26, T['muted'])
        tag_chips(d, T, X, ty, tags)
    d.save(f'pkg-{slug or name}', theme)


def more_row(theme):
    pkg_row(theme, len(PACKAGES) + 1, 'grdzelo.com', 'ELSEWHERE',
            'More work: client projects, the story behind Pirdapir.ge and notes on shipping Laravel.',
            [], slug='more', link='CASE STUDIES · WRITING')


# ------------------------------------------------------------------ contact
def contact(theme):
    T = THEMES[theme]
    if C:
        L = dict(H=310, top=72, size=76, t=(170, 246), r0=78, step=78, val=36, vsize=30)
    else:
        L = dict(H=384, top=90, size=88, t=(206, 296), r0=100, step=96, val=40, vsize=32)
    d = Doc(1600, L['H'], 'Have a Laravel project in mind? Let’s talk — grdzelo.com/en/contact', crop=(40, 286))
    X, rx = (8 if OPEN else 96), 1080
    card(d, T)
    dots(d, T, 0.45)
    status_dot(d, T, X + 7, L['top'] - 8)
    d.t(X + 30, L['top'], 'OPEN TO NEW WORK', 'mono', 22, T['muted'], ls=2.4)
    d.t(X - 3, L['t'][0], 'Have a Laravel project', 'disp', L['size'], T['text'])
    d.spans(X - 3, L['t'][1], [('in mind? ', 'disp', T['text']), ('Let’s talk.', 'disp', T['accent'])], L['size'])
    d.raw(f'<line x1="{rx - 52}" x2="{rx - 52}" y1="48" y2="{d.h - 48}" stroke="{T["border"]}"/>')
    for i, (label, value) in enumerate([('START A PROJECT', 'grdzelo.com/contact'), ('EMAIL', 'grdzelog@gmail.com'),
                                        ('RESPONSE', 'Within two business days')]):
        y = L['r0'] + i * L['step']
        d.t(rx, y, label, 'mono', 19, T['faint'], ls=2.2)
        d.t(rx, y + L['val'], value, 'sansm', L['vsize'], T['text'])
    arrow(d, rx + measure('grdzelo.com/contact', 'sansm', L['vsize']) + 36, L['r0'] + L['val'] - 23, 15, T['accent'], 2.4)
    d.save('contact', theme)


# ------------------------------------------------------------------ phone layouts (*-m-light.svg / *-m-dark.svg)
# GitHub scales each image to the README's width. On a phone that is ~330px, so the 1600-wide images above
# shrink to a fifth and their 19-26px labels and descriptions land at 4-5px. These versions are drawn on a
# 720-wide canvas with bigger type and stacked layouts; the README serves them to screens under 1012px.
MW = 720
MX = 8 if OPEN else 36
LAB = 22     # mono labels, ≈10px on a phone
BODY = 28    # body copy, ≈13px


def fit(text, key, size, maxw, ls=0):
    """The largest size up to `size` at which `text` fits in `maxw`."""
    while size > 8 and measure(text, key, size, ls) > maxw:
        size -= 1
    return size


def label(d, T, x, y, text, fill=None, anchor='start', size=LAB):
    d.t(x, y, text, 'mono', size, fill or T['faint'], anchor=anchor, ls=1.8)


def chips(d, T, x0, y, tags, maxx):
    """Tag chips that wrap onto a new row; returns the bottom edge."""
    x, h = x0, 42
    for tag in tags:
        w = measure(tag, 'mono', 20) + 34
        if x > x0 and x + w > maxx:
            x, y = x0, y + h + 12
        d.raw(f'<rect x="{x:.0f}" y="{y}" width="{w:.0f}" height="{h}" rx="21" fill="{T["chip"]}" stroke="{T["chipb"]}"/>')
        d.t(x + 17, y + 28, tag, 'mono', 20, T['muted'])
        x += w + 12
    return y + h if tags else y - 28


def hero_m(theme):
    T = THEMES[theme]
    W, X = MW, MX
    years = TODAY.year - LARAVEL_SINCE
    top, rule = 56, 84
    ns = fit('Giorgi Grdzelidze', 'disp', 140, W - 2 * X + 6)
    name_y = rule + 20 + round(dsize('disp', ns, 0)[0] * 0.74)
    tag_y, lh, ts = name_y + 60, 42, 30
    tagline = [[('Senior Laravel engineer. ', 'sansm', T['text']), ('I design APIs,', 'sans', T['muted'])],
               [('wire up integrations and publish the', 'sans', T['muted'])],
               [('SDKs Georgian businesses run on.', 'sansm', T['text'])]]
    py, ph = tag_y + (len(tagline) - 1) * lh + 34, 58
    cs = 22
    while cs > 12 and composer_width(cs) > W - 2 * X:
        cs -= 1
    sy, rowh = py + ph + 40, 118
    H = sy + 2 * rowh
    d = Doc(W, H + 30, f'Giorgi Grdzelidze — Senior Laravel engineer in Tbilisi, Georgia. {years}+ years with Laravel, '
                       f'{len(PACKAGES)} open-source SDKs, founder of Pirdapir.ge.', crop=(top - 32, H + 4))
    card(d, T)
    status_dot(d, T, X + 7, top - 8)
    label(d, T, X + 30, top, 'AVAILABLE FOR SENIOR CONTRACTS', T['muted'])
    if X + 30 + measure('AVAILABLE FOR SENIOR CONTRACTS', 'mono', LAB, 1.8) + 24 < W - X - measure('TBILISI, GE', 'mono', LAB, 1.8):
        label(d, T, W - X, top, 'TBILISI, GE', anchor='end')  # only when there is room (not in the boxed variants)
    d.raw(f'<line x1="{X}" x2="{W - X}" y1="{rule}" y2="{rule}" stroke="{T["border"]}"/>')
    d.t(X - 3, name_y, 'Giorgi Grdzelidze', 'disp', ns, T['text'])
    for i, line in enumerate(tagline):
        assert sum(measure(t, k, ts) for t, k, _ in line) <= W - 2 * X, line
        d.spans(X, tag_y + i * lh, line, ts)
    composer(d, T, X, py, ph, cs)
    # stats as a 2 × 2 grid
    colw = (W - 2 * X) / 2
    d.raw(f'<line x1="{X}" x2="{W - X}" y1="{sy}" y2="{sy}" stroke="{T["border"]}"/>')
    d.raw(f'<line x1="{X}" x2="{W - X}" y1="{sy + rowh}" y2="{sy + rowh}" stroke="{T["border"]}"/>')
    for i, (num, lab) in enumerate(hero_stats()):
        r, c = divmod(i, 2)
        cx, ty = X + c * colw + (28 if c else 0), sy + r * rowh
        if c:
            d.raw(f'<line x1="{X + colw:.1f}" x2="{X + colw:.1f}" y1="{ty + 22}" y2="{ty + rowh - 18}" stroke="{T["border"]}"/>')
        d.t(cx, ty + 66, num, 'disp', 64, T['text'])
        label(d, T, cx, ty + 98, lab)
    d.save('hero-m', theme)


def now_m(theme):
    T = THEMES[theme]
    W, X = MW, MX
    rel = [(p['latest_date'], n, p['latest']) for n, p in STATS['packages'].items() if n in NAMES and p.get('latest_date')]
    d = Doc(W, 128, 'Latest release', crop=(14, 122))
    card(d, T)
    status_dot(d, T, X + 7, 38)
    label(d, T, X + 30, 46, 'LATEST RELEASE')
    if rel:
        when, name, ver = max(rel)
        d.title = f'Latest release: {name} {ver}, {date(when)}'
        label(d, T, W - X, 46, date(when).upper(), anchor='end')
        d.t(X, 104, name, 'sansm', 36, T['text'])
        d.t(X + measure(name, 'sansm', 36) + 16, 103, ver, 'mono', 28, T['accent'])
    d.save('now-m', theme)


def streak_m(theme):
    T = THEMES[theme]
    W, X = MW, MX
    s = STATS.get('streak') or {}
    cur, best, year = s.get('current', 0), s.get('longest', 0), s.get('year', 0)
    days = lambda n: 'day' if n == 1 else 'days'
    since = date(s['current_start']) if cur and s.get('current_start') else None
    levels, start = (s.get('grid') or {}).get('levels', ''), (s.get('grid') or {}).get('start')
    weeks, gap = -(-len(levels) // 7), 5
    pitch = (W - 2 * X + gap) / max(weeks, 1)
    hy = 248
    H = hy + 7 * pitch - gap
    d = Doc(W, H + 24, f'Contribution streak: {cur} {days(cur)} in a row' + (f' since {since}' if since else '')
                       + f'. Longest streak {best} {days(best)}. {year:,} contributions in {TODAY.year}.', crop=(14, H + 12))
    card(d, T)
    if cur:
        status_dot(d, T, X + 7, 38)
    else:
        d.raw(f'<circle cx="{X + 7}" cy="38" r="7" fill="none" stroke="{T["faint"]}" stroke-width="2"/>')
    label(d, T, X + 30, 46, 'CONTRIBUTION STREAK', T['muted'])
    started = datetime.date.fromisoformat(s['current_start']) if since else None
    label(d, T, W - X, 46, f'SINCE {started:%b} {started.day}'.upper() if started else 'STARTS TODAY', anchor='end')
    d.raw(f'<line x1="{X}" x2="{W - X}" y1="72" y2="72" stroke="{T["border"]}"/>')
    # current streak large on the left, longest and this year stacked on the right
    d.t(X - 4, 176, f'{cur:,}', 'disp', 150, T['text'])
    d.t(X + measure(f'{cur:,}', 'disp', 150) + 12, 176, days(cur), 'sansm', 36, T['muted'])
    label(d, T, X, 216, 'CURRENT STREAK')
    mid = X + (W - 2 * X) * 0.5
    d.raw(f'<line x1="{mid:.1f}" x2="{mid:.1f}" y1="96" y2="222" stroke="{T["border"]}"/>')
    for y, lab, val in [(136, 'LONGEST', f'{best:,} {days(best)}'), (206, f'IN {TODAY.year}', f'{year:,}')]:
        label(d, T, mid + 28, y - 2, lab)
        d.t(W - X, y, val, 'sansb', 34, T['text'], anchor='end', ls=-0.4)
    if levels and start:
        first = datetime.date.fromisoformat(start)
        streak_from = s.get('current_start') if cur else None
        cell = pitch - gap
        for i, lv in enumerate(levels):
            day = (first + datetime.timedelta(days=i)).isoformat()
            x, y, lv = X + (i // 7) * pitch, hy + (i % 7) * pitch, int(lv)
            if lv == 0:
                d.raw(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" height="{cell:.1f}" rx="5" fill="{T["chip"]}"/>')
            else:
                op = LEVEL_OPACITY[lv] * (1 if streak_from and day >= streak_from else .45)
                d.raw(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" height="{cell:.1f}" rx="5" fill="{T["accent"]}" fill-opacity="{op:.2f}"/>')
            if i == len(levels) - 1:
                d.raw(f'<rect x="{x - 3:.1f}" y="{y - 3:.1f}" width="{cell + 6:.1f}" height="{cell + 6:.1f}" rx="7" fill="none" stroke="{T["accent"]}" stroke-width="2"/>')
    d.save('streak-m', theme)


def section_m(theme, num, title, note, name):
    T = THEMES[theme]
    W, X = MW, MX
    d = Doc(W, 116, f'{num} — {title}')
    label(d, T, X, 50, num, T['accent'])
    d.t(X + 50, 56, title, 'disp', fit(title, 'disp', 66, W - 2 * X - 50), T['text'])
    nw = measure(note, 'mono', LAB, 1.8)
    label(d, T, X + 50, 98, note)
    d.raw(f'<line x1="{X + 50 + nw + 22:.0f}" x2="{W - X}" y1="91" y2="91" stroke="{T["border"]}"/>')
    d.save(f'{name}-m', theme)


def pkg_row_m(theme, idx, name, cat, desc, tags, slug=None, link=None):
    T = THEMES[theme]
    W, X = MW, MX
    info = {} if link else STATS['packages'].get(name, {})
    meta = ([(info['version'], 'mono', T['muted']), (f' · {date(info["date"], "short")}', 'mono', T['faint'])]
            if info.get('version') else [(link, 'mono', T['faint'])] if link else [])
    lines = wrap(desc, 'sans', BODY, W - 2 * X)
    probe = Doc(W, 0, '')  # measure the chip rows before sizing the image
    bottom = chips(probe, T, X, 186 + (len(lines) - 1) * 40 + 30, tags, W - X)
    d = Doc(W, bottom + 40, f'{name} — {desc}' + tests_title(info), crop=(16, bottom + 26))
    card(d, T)
    label(d, T, X, 46, f'{idx:02d}', T['accent'])
    label(d, T, X + 48, 46, cat)
    d.t(X, 102, name, 'sansb', fit(name, 'sansb', 46, W - 2 * X - 140, -0.8), T['text'], ls=-0.8)
    if info.get('downloads', 0) >= SHOW_DOWNLOADS_FROM:
        downloads(d, T, W - X, 102, info['downloads'])
    else:
        arrow(d, W - X, 72, 20, T['muted'])
    if meta:
        meta_row(d, T, X, 140, meta, info.get('tests'), 20)
    for i, line in enumerate(lines):
        d.t(X, 186 + i * 40, line, 'sans', BODY, T['muted'])
    chips(d, T, X, 186 + (len(lines) - 1) * 40 + 30, tags, W - X)
    d.save(f'pkg-{slug or name}-m', theme)


def more_row_m(theme):
    pkg_row_m(theme, len(PACKAGES) + 1, 'grdzelo.com', 'ELSEWHERE',
              'More work: client projects, the story behind Pirdapir.ge and notes on shipping Laravel.',
              [], slug='more', link='CASE STUDIES · WRITING')


def contact_m(theme):
    T = THEMES[theme]
    W, X = MW, MX
    top = 56
    hs = fit('Have a Laravel project', 'disp', 100, W - 2 * X + 6)
    ha = dsize('disp', hs, 0)[0]
    y1 = top + 30 + round(ha * 0.74)
    y2 = y1 + round(ha * 1.14)
    rule = y2 + 40
    rows = [('START A PROJECT', 'grdzelo.com/contact'), ('EMAIL', 'grdzelog@gmail.com'), ('RESPONSE', 'Within two business days')]
    H = rule + 36 + len(rows) * 86
    d = Doc(W, H + 20, 'Have a Laravel project in mind? Let’s talk — grdzelo.com/en/contact', crop=(top - 32, H))
    card(d, T)
    status_dot(d, T, X + 7, top - 8)
    label(d, T, X + 30, top, 'OPEN TO NEW WORK', T['muted'])
    d.t(X - 3, y1, 'Have a Laravel project', 'disp', hs, T['text'])
    d.spans(X - 3, y2, [('in mind? ', 'disp', T['text']), ('Let’s talk.', 'disp', T['accent'])], hs)
    d.raw(f'<line x1="{X}" x2="{W - X}" y1="{rule}" y2="{rule}" stroke="{T["border"]}"/>')
    for i, (lab, value) in enumerate(rows):
        y = rule + 48 + i * 86
        label(d, T, X, y, lab)
        d.t(X, y + 38, value, 'sansm', 32, T['text'])
    arrow(d, X + measure('grdzelo.com/contact', 'sansm', 32) + 34, rule + 48 + 38 - 22, 15, T['accent'], 2.4)
    d.save('contact-m', theme)


def link_row_m(theme, idx, slug, cat, name, desc):
    T = THEMES[theme]
    W, X = MW, MX
    lines = wrap(desc, 'sans', 26, W - 2 * X - 50 - 50)[:2]
    H = 92 + (len(lines) - 1) * 34
    d = Doc(W, H + 22, f'{name} — {desc}', crop=(10, H + 14))
    card(d, T)
    label(d, T, X, 45, f'{idx:02d}', T['accent'])
    d.t(X + 50, 48, name, 'sansb', 36, T['text'], ls=-0.4)
    cx = X + 50 + measure(name, 'sansb', 36, -0.4) + 18
    assert cx + measure(cat, 'mono', LAB, 1.8) < W - X - 48, name
    label(d, T, cx, 45, cat)
    for i, line in enumerate(lines):
        d.t(X + 50, 88 + i * 34, line, 'sans', 26, T['muted'])
    arrow(d, W - X, 30, 20, T['accent'] if idx == 1 else T['muted'])
    d.save(f'link-{slug}-m', theme)


SECTIONS = [  # num, title, note, file
    ('01', 'Open-source SDKs', sdk_note(), 'sec-open-source'),
    ('02', 'Stack', 'WHAT I BUILD WITH', 'sec-stack'),
    ('03', 'Work together', 'TBILISI · REMOTE', 'sec-contact'),
    ('04', 'Elsewhere', 'LINKS', 'sec-links'),
]


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for th in THEMES:
        hero(th)
        now(th)
        streak(th)
        for i, link in enumerate(LINKS, 1):
            link_row(th, i, *link)
        for sec in SECTIONS:
            section(th, *sec)
        for i, p in enumerate(PACKAGES, 1):
            pkg_row(th, i, *p)
        more_row(th)
        contact(th)
        # phone versions
        hero_m(th)
        now_m(th)
        streak_m(th)
        for i, link in enumerate(LINKS, 1):
            link_row_m(th, i, *link)
        for sec in SECTIONS:
            section_m(th, *sec)
        for i, p in enumerate(PACKAGES, 1):
            pkg_row_m(th, i, *p)
        more_row_m(th)
        contact_m(th)
    print(f'built {len(os.listdir(OUT))} files in {OUT} ({VARIANT})')
