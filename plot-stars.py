import os
import re
import json
import tempfile
from json.decoder import JSONDecodeError

os.environ.setdefault('MPLBACKEND', 'Agg')
os.environ.setdefault('MPLCONFIGDIR', tempfile.gettempdir())

import matplotlib.dates as mdates
from matplotlib import rc, rcParams
import matplotlib.pyplot as plt

import datetime

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

fig = plt.figure('figure', figsize=(10,8))
fig.subplots_adjust(top=.80)
ax = plt.subplot(111)

series = {
    'isso': {'label': 'Isso', 'color': 'tab:blue', 'ls': '-'},
    'commento': {'label': 'Commento', 'color': 'tab:orange', 'ls': '-'},
    'juvia': {'label': 'Juvia', 'color': 'tab:green', 'ls': ':'},
    'staticman': {'label': 'Staticman', 'color': 'tab:red', 'ls': '--'},
    'schnak': {'label': 'Schnak', 'color': 'tab:gray', 'ls': '-'},
    'remark': {'label': 'Remark42', 'color': 'tab:pink', 'ls': '-'},
    'valine': {'label': 'Valine', 'color': 'tab:purple', 'ls': '-.'},
}

stars_by_project = {project: [] for project in series}
dates_by_project = {project: [] for project in series}

for filename in sorted(os.listdir('apigh')):
    if not re.fullmatch(r'file_\d{4}-\d{2}-\d{2}', filename):
        continue

    date_str = filename.replace('file_', '')
    date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()

    with open(os.path.join('apigh', filename), 'r') as f:
        try:
            data = json.load(f)
        except JSONDecodeError:
            continue

    for project in series:
        stars = data.get(project, {}).get('stars')
        if not str(stars).isdigit(): # remove undefined
            continue
        if project == 'isso' and datetime.date(2024, 3, 6) <= date_obj <= datetime.date(2024, 3, 12):
            continue

        stars_by_project[project].append(int(stars))
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

plt.savefig(tmp_name, dpi=300, bbox_inches='tight')
os.chmod(tmp_name, mode)
os.replace(tmp_name, output)
print('stars-v-date.svg is updated through {}'.format(last))

#plt.show()
