#! /usr/bin/env python 
#coding=utf8

'''
Github limits the API usage. Don't run the script 
frequently or your IP will be banned for a some time.
The quota is 60 requests per hour for unauthenticated 
requests and 5000 requests per hour for authenticated 
requests.

A single run of this script makes more than 60 requests
(number of commenting servers times two).
You need to set your github credentials.
Use
    curl -i https://api.github.com
or
    curl -i https://api.github.com -u username:password
to check how many requests are left.
'''

import re
import os
import json
import ruamel.yaml
import fileinput

from datetime import date, timedelta
import dateutil.parser

# Setup yaml parser
yaml = ruamel.yaml.YAML()
yaml.indent(mapping=4, sequence=4, offset=2)
yaml.preserve_quotes = True

# Get project names and github urls 
# Entry name is used instead of 'name' field
# since doesn't contain spaces etc.
with open('data.yaml', 'r') as f:
    #data = ruamel.yaml.round_trip_load(f)
    data = yaml.load(f)

comment_systems = []
github_urls = []        # url for project
github_commit_urls = [] # url for the last master/ commit

for i in data:

    #e.g., https://api.github.com/repos/posativ/isso
    # If more than 1 link to source code
    if type(data[i]['source']) is ruamel.yaml.comments.CommentedSeq:
        for x in range(len(data[i]['source'])):
            if re.search('github.com', data[i]['source'][x]):
                api_url = re.sub('github.com', 'api.github.com/repos', data[i]['source'][x])
    else:
        api_url = re.sub('github.com', 'api.github.com/repos', data[i]['source'])

    #e.g., https://api.github.com/repos/posativ/isso/commits/master
    api_commit_url = api_url + '/commits/master'

    if not 'pelican_static' in i:
        github_urls.append(api_url)
        github_commit_urls.append(api_commit_url)
        comment_systems.append(i)

# Define today's path
p = 'apigh/'+str(date.today())+'/'

# Write and download files only if haven't done today
if not os.path.isdir(p):
    os.system('mkdir -p {}'.format(p) )

    # Save github repo info to apigh/YYYY-MM-DD/<comment_system>
    # Attention, there is a limit of requests per IP per hour
    # (created, license, open_issues)

    ## If run manually just type your credentials
    #github_username = input('Type your github username: ')
    #github_password = input('Type your github password: (will be visible!) ')

    ## If run with script, read your credentials from the file outside of 
    # the repo (probably it's a bad idea, use for a fast automated solution)
    with open('/home/slisakov/gh_credentials', 'r') as f:
        for line in f:
            github_username = line.split()[0]
            github_password = line.split()[1]

    for url, cs in zip(github_urls, comment_systems):
        os.system('curl {} -u {}:{} -o {}'.format(url,github_username,github_password,p+cs))

    # Save info on the last commit to apigh/YYYY-MM-DD/<comment_system.commit>
    # (created, license, open_issues)
    for url, cs in zip(github_commit_urls, comment_systems):
        os.system('curl {} -u {}:{} -o {}'.format(url,github_username,github_password,p+cs+'.commit'))



# Calc Github stars change in the last N days
N=14
date_N_days_ago = date.today() - timedelta(days=N)
#print (date.today(), date_N_days_ago)
all_dates=[]
for d in sorted(os.listdir('apigh')):
    all_dates.append(d)

stars_N_days_ago = {}
p_N_days_ago = 'apigh/'+str(date_N_days_ago)+'/'
for cs in os.listdir(p_N_days_ago):
    if not '.swp' in cs and not 'pelican_static' in cs: # if opened in vim
        if not '.commit' in cs:

            with open(p_N_days_ago+cs, 'r') as f:
                #api_data = yaml.load(f)
                api_data = json.load(f)
                if 'stargazers_count' in api_data:
                    stars = api_data['stargazers_count']
                else:
                    stars = 'undefined'
                stars_N_days_ago[cs] = stars


# Read info from ./apigh/YYYY-MM-DD/<comment_system>
# and ./apigh/YYYY-MM-DD/<comment_system.commit>
print ( '{:<27}{:<6}{:<5}{:<5}{}'.format('Name', '★', 'Δ★', 'I+PR', 'Created')    )
for cs in os.listdir(p):
    if not '.swp' in cs and not 'pelican_static' in cs: # if opened in vim
        if not '.commit' in cs:

            with open(p+cs, 'r') as f:
                #api_data = yaml.load(f)
                api_data = json.load(f)
                if 'stargazers_count' in api_data:
                    stars = api_data['stargazers_count']
                else:
                    stars = 'undefined'
                created     = dateutil.parser.parse(api_data['created_at'])
                open_issues = api_data['open_issues']

                if api_data['license']:
                    if 'spdx_id' in api_data['license']:
                        license = api_data['license']['spdx_id'] # 'MIT'
                        data[cs]['license'] = license
                    elif 'name' in api_data['license']:
                        license = api_data['license']['name']    # 'MIT License'
                        data[cs]['license'] = license

                # Update the values
                data[cs]['stars']       = stars
                data[cs]['open_issues'] = open_issues
                data[cs]['created']     = created.strftime('%Y‑%m‑%d') # only useful once
                if cs in stars_N_days_ago and cs in data and isinstance(data[cs]['stars'],int) and isinstance(stars_N_days_ago[cs],int):
                    #print (cs, stars_N_days_ago[cs], data[cs]['stars'])
                    ds = data[cs]['stars'] - stars_N_days_ago[cs]
                    data[cs]['stars_dif'] = ds
                    #if ds>0:
                        #data[cs]['stars_dif'] = '+'+str(ds)
                    #else:
                        #data[cs]['stars_dif'] = '−'+str(ds)
                    print ( '{:<27}{:<6}{:<5}{:<5}{}'.format(cs, stars, ds, open_issues, created.strftime('%Y‑%m‑%d')) )
                else:
                    data[cs]['stars_dif'] = '?'
                    print ( '{:<27}{:<6}{:<5}{:<5}{}'.format(cs, stars, '—', open_issues, created.strftime('%Y‑%m‑%d')) )

        else:

            with open(p+cs, 'r') as f:
                #api_commit_data = yaml.load(f)
                api_commit_data = json.load(f)
                last_committed = dateutil.parser.parse(api_commit_data['commit']['committer']['date'])
                # Update the value
                data[re.sub('.commit','',cs)]['last_committed'] = last_committed.strftime('%Y‑%m‑%d')
                

# Update data.yaml file with fresh values.
# data.yaml is re-written, no backup.
with open('data.yaml', 'w') as f:
    yaml.dump(data, stream=f)

# Update index.html date
for line in fileinput.input('index.html', inplace=True):
    if 'Last updated:' in line:
        line = re.sub('Last updated:.*','Last updated: {} <br>'.format(date.today()), line)
    print ( line, end='' )
