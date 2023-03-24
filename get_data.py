#! /usr/bin/env python 
#coding=utf8

'''
1. Download comment_system and comment_system.commit to YYYY-MM-DD/
2. Read these files and write file_YYYY-MM-DD only with needed information
3. Remove YYYY-MM-DD/

TODO: check that everything is really downloaded
Get rid of yaml
'''

import os
#import os.path
import re
import json
import ruamel.yaml
import fileinput
import dateutil.parser
from datetime import datetime, date, timedelta
from json.decoder import JSONDecodeError

github_token = os.environ['GITHUB_TOKEN']

# Setup yaml parser
yaml = ruamel.yaml.YAML()
yaml.indent(mapping=4, sequence=4, offset=2)
yaml.preserve_quotes = True

# Get project names and github urls  Entry name is used instead of 
#'name' field since doesn't contain spaces etc.
with open('data.yaml', 'r') as f:
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
#mydate = date(2020,5,20)
mydate = datetime.strptime(os.environ['INPUT_DATE'], '%Y-%m-%d').date() if os.environ['INPUT_DATE'] else date.today()
p     = 'apigh/'      + str(mydate)+'/'
fdate = 'apigh/file_' + str(mydate)
open(fdate, 'w').close() # clear fdate content if existed
dtr = {}

#### IF NEED TO WORK WITH MANY DIRs YYYY-MM-DD/
###mydates = sorted(os.listdir('apigh'))
###for mydate in mydates:
    ###p     = 'apigh/' + mydate + '/'
    ###if re.match('20\d\d-\d\d-\d\d$', mydate):
        ###fdate = 'apigh/file_' + mydate
        ###print (fdate)
        ###if os.path.exists(fdate):
            ###open(fdate, 'w').close()
            ####with open(fdate, 'w') as f:
                ####print ( '{:<27}{:<6}{:<5}{}'.format('#name', 'stars', 'i_pr', 'created'), file=f  )
### SHIFT >> ONE TABSTOP EVERYTHING BELOW


# Download files only if haven't done today
if not os.path.isdir(p):
    print(p, 'will be written')
    os.system('mkdir -p {}'.format(p))

    for url, cs in zip(github_urls, comment_systems):
        print(cs,)
        os.system("curl -H 'Authorization: token {}' {} > {}".format(github_token,url,p+cs))

    # Save info on the last commit to apigh/YYYY-MM-DD/<comment_system.commit>
    # (created, license, open_issues)
    for url, cs in zip(github_commit_urls, comment_systems):
        print(cs,)
        os.system("curl -H 'Authorization: token {}' {} > {}".format(github_token,url,p+cs+'.commit'))
else:
    print(p, 'already exists. Stopping.')

# Calculate Github stars change in the last N days
N=14
#date_N_days_ago = date.today() - timedelta(days=N)
date_N_days_ago = mydate - timedelta(days=N)
all_dates=[]
for d in sorted(os.listdir('apigh')):
    all_dates.append(d)

stars_N_days_ago = {}
file_N_days_ago = 'apigh/file_' + str(date_N_days_ago)
if os.path.isfile(file_N_days_ago):
    print ('File to read N days ago', file_N_days_ago)
    with open(file_N_days_ago, 'r') as f:
        data_N_days_ago = json.load(f)
else:
    print ('File N days ago DOES NOT EXIST')


# Read info from ./apigh/YYYY-MM-DD/<comment_system>
# and ./apigh/YYYY-MM-DD/<comment_system.commit>
print ( '{:<27}{:<6}{:<5}{:<5}{}'.format('Name', '★', 'Δ★', 'I+PR', 'Created')    )

for filename in os.listdir(p):
    cs = re.sub('.commit', '', filename)
    if not '.swp' in filename and not 'pelican_static' in filename: # if opened in vim
        if not '.commit' in filename:

            with open(p+cs, 'r') as f:
                try:
                    api_data = json.load(f)

                    if api_data.get('stargazers_count'):
                        stars = api_data['stargazers_count']
                    else:
                        #stars = 'undefined'
                        stars = 0

                    if api_data.get('created_at'):
                        created = dateutil.parser.parse(api_data['created_at']).strftime('%Y‑%m‑%d')
                    else:
                        created = 'undefined'

                    if api_data.get('open_issues'):
                        open_issues = api_data['open_issues']
                    else:
                        open_issues = 0

                    if api_data.get('license'):
                        if 'spdx_id' in api_data['license']:
                            if data.get(cs):
                                data[cs]['license'] = api_data['license']['spdx_id']  # MIT
                        elif 'name' in api_data['license']:
                            if data.get(cs):
                                data[cs]['license'] = api_data['license']['name'] # MIT License
                    else:
                        data[cs]['license'] = 'undefined'

                    dtr[cs] = {"stars" : stars, "created" : created, "open_issues" : open_issues, 
                             "license" : data[cs]['license']}
                except JSONDecodeError:
                    pass

                # Update the values
                if created != 'undefined' and data.get(cs):
                    if len(str(stars)) > 0:
                        data[cs]['stars']   = stars
                    else:
                        #data[cs]['stars']   = 'undefined'
                        data[cs]['stars']   = 0
                    data[cs]['open_issues'] = open_issues
                    data[cs]['created']     = created
                    if os.path.isfile(file_N_days_ago):
                        if cs in data_N_days_ago:
                            stars_N_days_ago = data_N_days_ago[cs]['stars']
                        else:
                            stars_N_days_ago = 'undefined'
                    else:
                        stars_N_days_ago = 'undefined'
                    #if in stars_N_days_ago and cs in data and isinstance(data[cs]['stars'],int) and isinstance(stars_N_days_ago[cs],int):
                    if stars_N_days_ago != 'undefined' and len(str(stars)) > 0 and stars != 'undefined' and stars != 0:
                        ds = int(data[cs]['stars']) - stars_N_days_ago
                        data[cs]['stars_dif'] = ds
                        print ('{:<27}{:<16}{:<5}{:<5}{}'.format(cs, stars, ds,  open_issues, created))

                    else:
                        data[cs]['stars_dif'] = '?'
                        print ('{:<27}{:<16}{:<5}{:<5}{}'.format(cs, stars, '—', open_issues, created))

# Loop through *.commit files
for filename in os.listdir(p):
    cs = re.sub('.commit', '', filename)
    if not '.swp' in filename and not 'pelican_static' in filename: # if opened in vim
        if '.commit' in filename:

            with open(p+filename, 'r') as f:
                api_commit_data = json.load(f)
                #if api_commit_data.get('commit') and data.get(cs):
                if api_commit_data.get('commit') and dtr.get(cs):
                    last_commit = dateutil.parser.parse(api_commit_data['commit']['committer']['date']).strftime('%Y‑%m‑%d')
                    data[cs]['last_committed'] = last_commit
                    dtr [cs]['last_commit'] = last_commit

with open(fdate, 'a', encoding='utf-8') as f:
    json.dump(dtr, f, ensure_ascii=False, indent=4, sort_keys = True)

# Update data.yaml file with fresh values.
# data.yaml is rewritten, NO BACKUP
with open('data.yaml', 'w') as f:
    yaml.dump(data, stream=f)

# Update index.html date
for line in fileinput.input('index.html', inplace=True):
    if 'Last updated:' in line:
        #line = re.sub('Last updated:.*','Last updated: {} <br>'.format(date.today()), line)
        line = re.sub('Last updated:.*','Last updated: {} <br>'.format(mydate), line)
    print ( line, end='' )
