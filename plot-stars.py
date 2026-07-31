import os
import tempfile
import xml.etree.ElementTree as ET

os.environ.setdefault('MPLBACKEND', 'Agg')
os.environ.setdefault('MPLCONFIGDIR', tempfile.gettempdir())

import matplotlib.dates as mdates
from matplotlib import rc, rcParams
import matplotlib.pyplot as plt

import datetime

from history_store import field_on_or_before, load_history

'''
Plot stars vs time for top competitors except Discourse.
'''

fs=15
rc('axes', linewidth=2)
rc('text', usetex=False)
rc('legend', fontsize=fs)
rc('font',  size=fs)
rc('xtick.major', size=10, width=2)
rc('ytick.major', size=10, width=2)
rc('xtick.minor', size=5, width=1.3)
rc('ytick.minor', size=5, width=1.3)
rcParams['font.family'] = 'sans-serif'
rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Lucida Grande']
rcParams['svg.hashsalt'] = 'open-source-comments'

fig = plt.figure('figure', figsize=(10,8))
fig.subplots_adjust(top=.80)
ax = plt.subplot(111)

series = {
    'isso': {'label': 'Isso', 'color': 'tab:blue', 'ls': '-'},
    'commento': {'label': 'Commento', 'color': 'tab:orange', 'ls': '-'},
    'Waline': {'label': 'Waline', 'color': 'tab:green', 'ls': ':'},
    'staticman': {'label': 'Staticman', 'color': 'tab:red', 'ls': '--'},
    'Artalk': {'label': 'Artalk', 'color': 'tab:gray', 'ls': '-'},
    'remark': {'label': 'Remark42', 'color': 'tab:pink', 'ls': '-'},
    'valine': {'label': 'Valine', 'color': 'tab:purple', 'ls': '-.'},
}

stars_by_project = {project: [] for project in series}
dates_by_project = {project: [] for project in series}
history = load_history()

for date_str in history['dates']:
    date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    for project in series:
        stars = field_on_or_before(history, project, 'stars', date_str)
        if stars is None:
            continue
        if isinstance(stars, bool) or not isinstance(stars, int):
            raise RuntimeError(
                'Invalid star history value for {} on {}: {!r}'.format(
                    project,
                    date_str,
                    stars,
                )
            )
        if stars <= 0:
            if dates_by_project[project]:
                dates_by_project[project].append(date_obj)
                stars_by_project[project].append(float('nan'))
            continue
        if project == 'isso' and datetime.date(2024, 3, 6) <= date_obj <= datetime.date(2024, 3, 12):
            continue

        stars_by_project[project].append(stars)
        dates_by_project[project].append(date_obj)

lw=2.85

all_dates = []
for project, style in series.items():
    dates = dates_by_project[project]
    stars = stars_by_project[project]
    if not dates:
        raise RuntimeError('No data points for {}'.format(project))

    all_dates.extend(dates)
    ax.plot(dates, stars, label=style['label'], lw=lw, ls=style['ls'], color=style['color'])

ax2 = ax.twiny()
years = mdates.YearLocator()    # every year
months = mdates.MonthLocator()  # every month
yearsFmt = mdates.DateFormatter('%Y')
dateFmt = mdates.DateFormatter('%d %B, %Y')

ax2.xaxis.set_major_locator(years)
ax2.xaxis.set_major_formatter(dateFmt)
ax2.xaxis.set_minor_locator(months)

ax.xaxis.set_major_locator(years)
ax.xaxis.set_major_formatter(yearsFmt)
ax.xaxis.set_minor_locator(months)

ax.set_xlabel('Date')
ax.set_ylabel('Github stars')
ax.legend(ncol=3, loc='center', bbox_to_anchor=(0.4, 1.15))
ax.grid(ls=':', lw=1)

last  = max(all_dates)
ax.axvline(x=last,  ls=':', color='tab:gray', lw=1)
ax2.set_xlim(ax.get_xlim())
ax2.set_xticks([last])

output = 'stars-v-date.svg'
mode = os.stat(output).st_mode if os.path.exists(output) else 0o644
with tempfile.NamedTemporaryFile(dir='.', suffix='.svg', delete=False) as tmp:
    tmp_name = tmp.name

try:
    plt.savefig(tmp_name, dpi=300, bbox_inches='tight', metadata={'Date': None})
    with open(tmp_name, 'r', encoding='utf-8') as svg_file:
        svg = svg_file.read()
    with open(tmp_name, 'w', encoding='utf-8') as svg_file:
        svg_file.write('\n'.join(line.rstrip() for line in svg.splitlines()))
        svg_file.write('\n')
        svg_file.flush()
        os.fsync(svg_file.fileno())

    if len(svg) < 10000:
        raise RuntimeError('Generated SVG is unexpectedly small')
    ET.parse(tmp_name)
    missing_labels = [
        style['label']
        for style in series.values()
        if '<!-- {} -->'.format(style['label']) not in svg
    ]
    if missing_labels:
        raise RuntimeError(
            'Generated SVG is missing series labels: {}'.format(', '.join(missing_labels))
        )

    os.chmod(tmp_name, mode)
    os.replace(tmp_name, output)
    tmp_name = None
finally:
    plt.close(fig)
    if tmp_name and os.path.exists(tmp_name):
        os.unlink(tmp_name)
print('stars-v-date.svg is updated through {}'.format(last))

#plt.show()
