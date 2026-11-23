#!/usr/bin/env python3
"""Fetch live profile stats (Packagist releases + GitHub contributions) into data/stats.json.

Anything that fails keeps its previous value, so a flaky API never blanks the profile.
"""
import datetime, json, os, re, urllib.request

USER = 'GiorgiGrdzelidze'
VENDOR = 'giorgigrdzelidze'
FIRST_YEAR = 2014
PACKAGES = ['laravel-bog-sdk', 'laravel-rsge', 'laravel-fina-sdk', 'laravel-shopify-sdk', 'laravel-stringer']
PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'stats.json')


def get(url, headers=None):
    req = urllib.request.Request(url, headers={'User-Agent': 'profile-stats/1.0', **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8')


def package(name):
    pkg = json.loads(get(f'https://packagist.org/packages/{VENDOR}/{name}.json'))['package']
    tags = [v for v in pkg['versions'].values() if not v['version'].startswith('dev-') and not v['version'].endswith('-dev')]
    tags.sort(key=lambda v: v['time'], reverse=True)
    stable = [v for v in tags if not re.search(r'alpha|beta|rc', v['version'], re.I)] or tags
    return {
        'version': stable[0]['version'], 'date': stable[0]['time'][:10],
        'latest': tags[0]['version'], 'latest_date': tags[0]['time'][:10],
        'downloads': pkg['downloads']['total'],
    }


def contributions(year):
    html = get(f'https://github.com/users/{USER}/contributions?from={year}-01-01&to={year}-12-31',
               {'X-Requested-With': 'XMLHttpRequest'})
    m = re.search(r'([\d,]+)\s+contributions?\s+in\s+' + str(year), html)
    if m:
        return int(m.group(1).replace(',', ''))
    return sum(int(n) for n in re.findall(r'(\d+) contributions? on', html))


def main():
    try:
        with open(PATH) as fh:
            stats = json.load(fh)
    except (OSError, ValueError):
        stats = {}
    stats.setdefault('packages', {})
    for name in PACKAGES:
        try:
            stats['packages'][name] = package(name)
        except Exception as e:  # keep the last known value
            print(f'packagist {name} failed: {e}')
    try:
        stats['contributions'] = sum(contributions(y) for y in range(FIRST_YEAR, datetime.date.today().year + 1))
    except Exception as e:
        print(f'contributions failed: {e}')
    stats['updated'] = datetime.date.today().isoformat()
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, 'w') as fh:
        json.dump(stats, fh, indent=2)
        fh.write('\n')
    print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    main()
