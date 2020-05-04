#! /usr/bin/env python 
#coding=utf8

'''
Plot stars vs time. Except Discourse.
'''

import re
import os
import numpy as np

import matplotlib
from matplotlib import rc, rcParams
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.ticker import AutoMinorLocator, MultipleLocator, FuncFormatter

import matplotlib.dates as mdates

import datetime


#import yaml
import json
from ruamel.yaml import YAML
yaml = YAML()

# Plot parameters {{{
rcParams['font.size'] = 13.
font = {'family': 'normal', 'size': 13}
rc('axes', linewidth=1.1)
rc("text", usetex=True)
rc('font', family='serif')
rc('font', serif='Times')
rc('legend', fontsize=12)
rc('xtick.major', size=5, width=1.1)
rc('ytick.major', size=5, width=1.1)
rc('xtick.minor', size=3, width=1)
rc('ytick.minor', size=3, width=1)
fig = plt.figure('figure')#, figsize=(8,6))
fig.subplots_adjust(left=.15, bottom=.10, right=.95, top=.90)
ax = plt.subplot(111)
#}}}
# Smooth setup {{{
def gaussian_convol(sig,x,y) :

    x0 = int(min(x))+1
    x1 = int(max(x))-1
    nx = (x1-x0) / 2
    xi = np.linspace(x0,x1,nx)
    f = interpolate.interp1d(x,y)
    yi = f(xi)

    dx = (max(x) - min(x)) / float(nx)

    ng_on2 = int(6.0 * (sig / dx)) + 1
    ng = 2*ng_on2+1
    gau = np.zeros(ng)
    gau[ng_on2] = 1.0
    for i in range(ng_on2-1) :
        gau[ng_on2-i-1] = np.exp( -0.5 * (float(i+1)*dx/sig)**2  )
        gau[ng_on2+i+1] = gau[ng_on2-i-1]

    norm = np.zeros(nx)
    yn   = np.zeros(nx)
    for i in range(nx) :
        for ig in range(ng) :
            j = i + (ig-ng_on2)
            if (j >= 0) and (j<=nx-1) :
                yn[i] = yn[i] + gau[ig]*yi[j]
                norm[i] = norm[i] + gau[ig]

    yn = yn / norm

    return (xi,yn)
    # }}}

path = '/home/slisakov/open-source-comments/apigh/'

# Create array with all dates
dates=[]
for date in os.listdir(path):
    y=int(date[0:4])
    m=date[5:7]
    if re.search('^0', m):
        m=int(m[1])
    else:
        m=int(m)
    d=int(date[8:10])
    dates.append(datetime.date(y,m,d))

selected_cs = ['discourse', 'isso', 'commento', 'schnak', 'staticman', 'juvia']

d={}
for date in dates:
    print (date)
    for cs in os.listdir(path+str(date)):
        #if not '.swp' in cs and not 'pelican_static' in cs: # if opened in vim
        if not '.swp' in cs and not 'pelican_static' in cs and cs in selected_cs: # if opened in vim
            if not '.commit' in cs:
                with open(path+str(date)+'/'+cs, 'r') as f:
                    api_data = json.load(f)
                    if "stargazers_count" in api_data:
                        stars = api_data["stargazers_count"]
                    else:
                        stars = 'undefined'
                    print ("{0:>26s}".format(cs), 
                           "{0:<11s}".format(str(date)), 
                           "{0:<5}".format(stars))
                    # Write to arrays [cs,date,stars]

    print('End of the date')



#d = { 'discourse' : [['2019-03-22', '2019-03-23', '2019-03-24'], [20,30,102]],
      #'isso'      : [['2019-03-22', '2019-03-23', '2019-03-24'], [2,3,10]],
    #}
#for cs in d.keys():
    #ax.plot (d[cs][0], d[cs][1])


#dates = matplotlib.dates.date2num(dates)
#ax.plot(dates, [7,8])

#matplotlib.pyplot.plot_date(dates, [7,8,9,10], '-')
#matplotlib.pyplot.plot_date(dates, [8,9,10,12], '-')
#myFmt = mdates.DateFormatter('%d-%B-%Y')
#plt.gca().xaxis.set_major_formatter(myFmt)
#plt.gcf().autofmt_xdate()

#plt.show()
