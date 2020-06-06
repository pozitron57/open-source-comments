#! /usr/bin/env python 
#coding=utf8

'''
Plot stars vs time for top competitors except Discourse.
'''

import os
import re
import json
from json.decoder import JSONDecodeError
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
rc('text', usetex=False)
rc('legend', fontsize=fs)
rc('font',  size=fs)
rc('xtick.major', size=10, width=2)
rc('ytick.major', size=10, width=2)
rc('xtick.minor', size=5, width=1.3)
rc('ytick.minor', size=5, width=1.3)
rcParams['font.family'] = 'sans-serif'
rcParams['font.sans-serif'] = ['Lucida Grande']


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

            print (mydate)
            with open(mydate, 'r') as f:
                try:
                    data = json.load(f)
                except JSONDecodeError:
                    pass

            if data.get('isso') and str(data['isso']['stars']).isdigit(): # remove undefined
                isso_stars  = np.append(isso_stars, data['isso']['stars'])
                isso_dates  = np.append(isso_dates, re.sub('file_', '', mydate))

            if data.get('commento') and str(data['commento']['stars']).isdigit(): # remove undefined
                commento_stars  = np.append(commento_stars, data['commento']['stars'])
                commento_dates  = np.append(commento_dates, re.sub('file_', '', mydate))

            if data.get('juvia') and str(data['juvia']['stars']).isdigit(): # remove undefined
                juvia_stars  = np.append(juvia_stars, data['juvia']['stars'])
                juvia_dates  = np.append(juvia_dates, re.sub('file_', '', mydate))

            if data.get('staticman') and str(data['staticman']['stars']).isdigit(): # remove undefined
                staticman_stars  = np.append(staticman_stars, data['staticman']['stars'])
                staticman_dates  = np.append(staticman_dates, re.sub('file_', '', mydate))

            if data.get('schnak') and str(data['schnak']['stars']).isdigit(): # remove undefined
                schnak_stars  = np.append(schnak_stars, data['schnak']['stars'])
                schnak_dates  = np.append(schnak_dates, re.sub('file_', '', mydate))

            if data.get('remark') and str(data['remark']['stars']).isdigit(): # remove undefined
                remark_stars  = np.append(remark_stars, data['remark']['stars'])
                remark_dates  = np.append(remark_dates, re.sub('file_', '', mydate))

            if data.get('valine') and str(data['valine']['stars']).isdigit(): # remove undefined
                valine_stars  = np.append(valine_stars, data['valine']['stars'])
                valine_dates  = np.append(valine_dates, re.sub('file_', '', mydate))

lw=2.85

x = [datetime.datetime.strptime(d,'%Y-%m-%d').date() for d in isso_dates]
ax.plot_date(x, isso_stars, label='Isso', lw=lw, ls='-', marker=None, color='tab:blue')

x = [datetime.datetime.strptime(d,'%Y-%m-%d').date() for d in commento_dates]
ax.plot_date(x, commento_stars, label='Commento', lw=lw, ls='-', marker=None, color='tab:orange')

x = [datetime.datetime.strptime(d,'%Y-%m-%d').date() for d in juvia_dates]
ax.plot_date(x, juvia_stars, label='Juvia', lw=lw, ls=':', marker=None, color='tab:green')

x = [datetime.datetime.strptime(d,'%Y-%m-%d').date() for d in staticman_dates]
ax.plot_date(x, staticman_stars, label='Staticman', lw=lw, ls='--', marker=None, color='tab:red')

x = [datetime.datetime.strptime(d,'%Y-%m-%d').date() for d in schnak_dates]
ax.plot_date(x, schnak_stars, label='Schnak', lw=lw, ls='-', marker=None, color='tab:gray')

x = [datetime.datetime.strptime(d,'%Y-%m-%d').date() for d in remark_dates]
ax.plot_date(x, remark_stars, label='Remark42', lw=lw, ls='-', marker=None, color='tab:pink')

x = [datetime.datetime.strptime(d,'%Y-%m-%d').date() for d in valine_dates]
ax.plot_date(x, valine_stars, label='Valine', lw=lw, ls='-.', marker=None, color='tab:purple')

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
ax.legend(ncol=3, loc='center') # bbox_to_anchor=(0.5, 1.05)
ax.grid(ls=':', lw=1)

#today = date.today()
last  = np.amax(x)
ax.axvline(x=last,  ls=':', color='tab:gray', lw=1)
ax2.set_xlim(ax.get_xlim())
ax2.set_xticks([last])

plt.savefig('../stars-v-date.png', dpi=300, bbox_inches='tight')
print('stars-v-date.png is updated')

#plt.show()
