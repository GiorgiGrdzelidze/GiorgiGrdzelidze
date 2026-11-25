#!/usr/bin/env python3
"""Fetch live profile stats (Packagist releases, test status, GitHub contributions and streak) into data/stats.json.

Anything that fails keeps its previous value, so a flaky API never blanks the profile.
"""
import datetime, json, os, re, urllib.error, urllib.request

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


def github_api(path):
    """GET from the GitHub API, with the workflow's token when there is one (60 requests/hour without)."""
    headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
    token = os.environ.get('GITHUB_TOKEN')
    try:
        return json.loads(get(f'https://api.github.com/{path}', {**headers, **({'Authorization': f'Bearer {token}'} if token else {})}))
    except urllib.error.HTTPError as e:
        if token and e.code in (401, 403):
            return json.loads(get(f'https://api.github.com/{path}', headers))
        raise


def tests(name):
    """'passing' when the latest finished run of every workflow on main succeeded, otherwise 'failing'.

    Pull requests, cancelled and skipped runs don't count; only what landed on main does.
    """
    runs = github_api(f'repos/{USER}/{name}/actions/runs?branch=main&per_page=50')['workflow_runs']
    latest = {}
    for run in runs:  # newest first
        if run['event'] != 'pull_request' and run['status'] == 'completed' and run['conclusion'] not in ('cancelled', 'skipped', 'neutral', None):
            latest.setdefault(run['workflow_id'], run['conclusion'])
    if not latest:
        raise ValueError('no finished runs on main')
    return 'passing' if all(c == 'success' for c in latest.values()) else 'failing'


def calendar(year):
    """One year of the public contribution graph: (total for the year, {date: (count, level 0-4)})."""
    html = get(f'https://github.com/users/{USER}/contributions?from={year}-01-01&to={year}-12-31',
               {'X-Requested-With': 'XMLHttpRequest'})
    tips = {}  # cell id -> count, from the screen-reader tooltips ("9 contributions on November 24th.")
    for cell_id, text in re.findall(r'<tool-tip[^>]*\bfor="([^"]+)"[^>]*>\s*([^<]*)</tool-tip>', html):
        m = re.match(r'(No|[\d,]+) contributions? on', text.strip())
        if m:
            tips[cell_id] = 0 if m.group(1) == 'No' else int(m.group(1).replace(',', ''))
    days = {}
    for tag in re.findall(r'<td\b[^>]*\bdata-date="[^"]+"[^>]*>', html):
        attr = dict(re.findall(r'([\w-]+)="([^"]*)"', tag))
        level = int(attr.get('data-level', 0))
        days[attr['data-date']] = (tips.get(attr.get('id'), level), level)  # level as a fallback count: still >0 when active
    m = re.search(r'([\d,]+)\s+contributions?\s+in\s+' + str(year), html)
    total = int(m.group(1).replace(',', '')) if m else sum(c for c, _ in days.values())
    return total, days


def streaks(days, today, weeks=24):
    """Current and longest run of days with at least one contribution, plus the last `weeks` of levels.

    Today not counting yet (the run happens at 07:17 Tbilisi) doesn't break the current streak.
    """
    dates = sorted(d for d in days if d <= today.isoformat())
    longest = run = 0
    longest_span = run_start = None
    for d in dates:
        if days[d][0] > 0:
            run_start = d if run == 0 else run_start
            run += 1
            if run > longest:
                longest, longest_span = run, (run_start, d)
        else:
            run = 0
    i = len(dates) - 1
    if i >= 0 and days[dates[i]][0] == 0:
        i -= 1  # nothing yet today: the streak is still alive if yesterday counted
    current, start = 0, None
    while i >= 0 and days[dates[i]][0] > 0:
        current, start, i = current + 1, dates[i], i - 1
    # the heatmap: whole weeks (Sunday first, like GitHub) ending with the current one
    first = today - datetime.timedelta(days=(today.weekday() + 1) % 7 + 7 * (weeks - 1))
    span = [(first + datetime.timedelta(days=n)).isoformat() for n in range((today - first).days + 1)]
    return {
        'current': current, 'current_start': start,
        'longest': longest, 'longest_start': longest_span and longest_span[0], 'longest_end': longest_span and longest_span[1],
        'year': sum(c for d, (c, _) in days.items() if d.startswith(str(today.year)) and d <= today.isoformat()),
        'active_days': sum(1 for d in dates if days[d][0] > 0),
        'grid': {'start': span[0], 'end': span[-1], 'levels': ''.join(str(days.get(d, (0, 0))[1]) for d in span)},
    }


def main():
    try:
        with open(PATH) as fh:
            stats = json.load(fh)
    except (OSError, ValueError):
        stats = {}
    stats.setdefault('packages', {})
    for name in PACKAGES:
        last = stats['packages'].get(name, {})
        try:
            stats['packages'][name] = package(name)
        except Exception as e:  # keep the last known value
            print(f'packagist {name} failed: {e}')
        try:
            stats['packages'][name]['tests'] = tests(name)
        except Exception as e:
            print(f'tests {name} failed: {e}')
            if 'tests' in last:
                stats['packages'][name]['tests'] = last['tests']
    try:
        today, total, days = datetime.date.today(), 0, {}
        for y in range(FIRST_YEAR, today.year + 1):
            year_total, year_days = calendar(y)
            total += year_total
            days.update(year_days)
        stats['contributions'] = total
        stats['streak'] = streaks(days, today)
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
