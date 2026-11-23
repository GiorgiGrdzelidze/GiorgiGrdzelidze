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
                 glyph='rgba(145,152,161,.18)', surface='rgba(101,108,118,.14)', surfaceb='rgba(61,68,77,.7)'),
    'light': dict(text='#1f2328', muted='#59636e', faint='#818b98', border='#d1d9e0', accent='#1a7f37',
                  grid='rgba(129,139,152,.3)', chip='rgba(129,139,152,.12)', chipb='#d1d9e0',
                  glyph='rgba(129,139,152,.22)', surface='rgba(129,139,152,.07)', surfaceb='rgba(209,217,224,.7)'),
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
def hero(theme):
    T = THEMES[theme]
    years = TODAY.year - LARAVEL_SINCE
    contrib = STATS.get('contributions')
    sdks = (kfmt(total_installs()), 'PACKAGIST INSTALLS') if TOTAL_IN == 'hero' else (str(len(PACKAGES)), 'OPEN-SOURCE SDKS')
    stats = [(f'{years}+', 'YEARS WITH LARAVEL'), sdks,
             (kfmt(contrib) if contrib else '—', 'GITHUB CONTRIBUTIONS'), ('Pirdapir.ge', 'FOUNDER & DIRECTOR')]
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
    # composer line cycling through the packages
    py, ph, cs = L['py'], L['ph'], L['comp']
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


def pkg_row(theme, idx, name, cat, desc, tags, slug=None, link=None):
    """One package per row. link=(text, ...) turns the row into the 'more work' row with an arrow instead of stats."""
    T = THEMES[theme]
    X = 8 if OPEN else 48
    info = {} if link else STATS['packages'].get(name, {})
    meta = ([(info['version'], 'mono', T['muted']), (f' · {date(info["date"], "short")}', 'mono', T['faint'])]
            if info.get('version') else [(link, 'mono', T['faint'])] if link else [])
    if PKG_LAYOUT == 'split':
        lines = wrap(desc, 'sans', 26, 1600 - X - RIGHT_X - STAT_W)[:2]
        d = Doc(1600, 196, f'{name} — {desc}', crop=(20, 180))
        card(d, T)
        d.t(X, 56, f'{idx:02d}', 'mono', 21, T['accent'], ls=2)
        d.t(X + 56, 56, cat, 'mono', 21, T['faint'], ls=2)
        d.t(X, 116, name, 'sansb', 48, T['text'], ls=-0.8)
        if info.get('downloads', 0) >= SHOW_DOWNLOADS_FROM:
            downloads(d, T, d.w - X, 116, info['downloads'])  # last in the row, like the link arrows below
        else:
            arrow(d, d.w - X, 92, 22, T['muted'])
        if meta:
            d.spans(X, 156, meta, 19, ls=1.2)
        for i, line in enumerate(lines):
            d.t(RIGHT_X, 66 + i * 36, line, 'sans', 26, T['muted'])
        tag_chips(d, T, RIGHT_X, 124, tags)
    else:
        lines = wrap(desc, 'sans', 26, 1600 - 2 * X)[:2]
        ty = 166 + (len(lines) - 1) * 36 + 24
        bottom = ty + 40 if tags else ty - 14
        d = Doc(1600, bottom + 32, f'{name} — {desc}', crop=(20, bottom + 16))
        card(d, T)
        d.t(X, 56, f'{idx:02d}', 'mono', 21, T['accent'], ls=2)
        d.t(X + 56, 56, cat, 'mono', 21, T['faint'], ls=2)
        if meta:
            d.spans(d.w - X, 55, meta, 19, anchor='end', ls=1.2)
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


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for th in THEMES:
        hero(th)
        now(th)
        for i, link in enumerate(LINKS, 1):
            link_row(th, i, *link)
        section(th, '01', 'Open-source SDKs', f'{kfmt(total_installs())} INSTALLS ON PACKAGIST' if TOTAL_IN == 'header' else 'GIORGIGRDZELIDZE/*', 'sec-open-source')
        section(th, '02', 'Stack', 'WHAT I BUILD WITH', 'sec-stack')
        section(th, '03', 'Work together', 'TBILISI · REMOTE', 'sec-contact')
        section(th, '04', 'Elsewhere', 'LINKS', 'sec-links')
        for i, p in enumerate(PACKAGES, 1):
            pkg_row(th, i, *p)
        more_row(th)
        contact(th)
    print(f'built {len(os.listdir(OUT))} files in {OUT} ({VARIANT})')
