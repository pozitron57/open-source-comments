#! /usr/bin/env python 
#coding=utf8

'''
Plot stars vs time for top competitors except Discourse.
'''

import os
import re
import json
import numpy as np

import matplotlib.dates as mdates
from matplotlib import rc, rcParams
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.ticker import AutoMinorLocator, MultipleLocator, FuncFormatter, FixedLocator

import datetime
from datetime import date

fs=15
rc('axes', linewidth=2)
rc('text', usetex=True)
rc('legend', fontsize=fs)
rc('font',  size=fs)
rc('font',  family='sans-serif')
rc('xtick.major', size=8, width=1.8)
rc('ytick.major', size=8, width=1.8)
rc('xtick.minor', size=5, width=1.3)
rc('ytick.minor', size=5, width=1.3)
fig = plt.figure('figure', figsize=(10,6))
ax = plt.subplot(111)

mydates = sorted(os.listdir('apigh'))
os.chdir('apigh')

isso_stars = np.array([])
isso_dates = np.array([])

remark_stars = np.array([])
remark_dates = np.array([])

commento_stars = np.array([])
commento_dates = np.array([])

schnak_stars = np.array([])
schnak_dates = np.array([])

staticman_stars = np.array([])
staticman_dates = np.array([])

juvia_stars = np.array([])
juvia_dates = np.array([])

valine_stars = np.array([])
valine_dates = np.array([])

discourse_stars = np.array([])
discourse_dates = np.array([])

for mydate in mydates:
    if os.path.isfile(mydate):
        if re.match('file_\d\d\d\d-\d\d-\d\d', mydate):

            with open(mydate, 'r') as f:
                data = json.load(f)

            if str(data['isso']['stars']).isdigit(): # remove undefined
                isso_stars  = np.append(isso_stars, data['isso']['stars'])
                isso_dates  = np.append(isso_dates, re.sub('file_', '', mydate))

            if str(data['commento']['stars']).isdigit(): # remove undefined
                commento_stars  = np.append(commento_stars, data['commento']['stars'])
                commento_dates  = np.append(commento_dates, re.sub('file_', '', mydate))

            if str(data['juvia']['stars']).isdigit(): # remove undefined
                juvia_stars  = np.append(juvia_stars, data['juvia']['stars'])
                juvia_dates  = np.append(juvia_dates, re.sub('file_', '', mydate))

            if str(data['staticman']['stars']).isdigit(): # remove undefined
                staticman_stars  = np.append(staticman_stars, data['staticman']['stars'])
                staticman_dates  = np.append(staticman_dates, re.sub('file_', '', mydate))

            if str(data['schnak']['stars']).isdigit(): # remove undefined
                schnak_stars  = np.append(schnak_stars, data['schnak']['stars'])
                schnak_dates  = np.append(schnak_dates, re.sub('file_', '', mydate))

            if str(data['remark']['stars']).isdigit(): # remove undefined
                remark_stars  = np.append(remark_stars, data['remark']['stars'])
                remark_dates  = np.append(remark_dates, re.sub('file_', '', mydate))

            if str(data['valine']['stars']).isdigit(): # remove undefined
                valine_stars  = np.append(valine_stars, data['valine']['stars'])
                valine_dates  = np.append(valine_dates, re.sub('file_', '', mydate))

lw=2.85


x = [datetime.datetime.strptime(d,'%Y-%m-%d').date() for d in isso_dates]
plt.plot_date(x, isso_stars, label='Isso', lw=lw, ls='-', marker=None)

x = [datetime.datetime.strptime(d,'%Y-%m-%d').date() for d in commento_dates]
plt.plot_date(x, commento_stars, label='Commento', lw=lw, ls='-', marker=None)

x = [datetime.datetime.strptime(d,'%Y-%m-%d').date() for d in juvia_dates]
plt.plot_date(x, juvia_stars, label='Juvia', lw=lw, ls=':', marker=None)

x = [datetime.datetime.strptime(d,'%Y-%m-%d').date() for d in staticman_dates]
plt.plot_date(x, staticman_stars, label='Staticman', lw=lw, ls='--', marker=None)

x = [datetime.datetime.strptime(d,'%Y-%m-%d').date() for d in schnak_dates]
plt.plot_date(x, schnak_stars, label='Schnak', lw=lw, ls='-', marker=None, color='tab:gray')

x = [datetime.datetime.strptime(d,'%Y-%m-%d').date() for d in remark_dates]
plt.plot_date(x, remark_stars, label='Remark42', lw=lw, ls='-', marker=None, color='tab:pink')

x = [datetime.datetime.strptime(d,'%Y-%m-%d').date() for d in valine_dates]
plt.plot_date(x, valine_stars, label='Valine', lw=lw, ls='-.', marker=None)

years = mdates.YearLocator()    # every year
months = mdates.MonthLocator()  # every month
yearsFmt = mdates.DateFormatter('%Y')
ax.xaxis.set_major_locator(years)
ax.xaxis.set_major_formatter(yearsFmt)
ax.xaxis.set_minor_locator(months)

ax.set_xlabel('Date')
ax.set_ylabel('Github stars')
plt.legend(ncol=3, loc='center') #loc='center', bbox_to_anchor=(0.5, 1.05),
plt.grid(ls=':')

today = date.today()
plt.axvline(x=today, ls=':', color='tab:gray', lw=0.7)

plt.savefig('../stars-v-date.png', dpi=300, bbox_inches='tight')
print('stars-v-date.png is updated')

#plt.show()
