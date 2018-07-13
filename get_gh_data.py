#! /usr/bin/env python 
#coding=utf8

'''
Github limits the API usage. Don't run the script 
frequently or your IP will be banned for a some time.
The quota is 60 requests per hour for unauthenticated 
requests and 5000 requests per hour for authenticated 
requests.

Run of this file will make more than 60 requests.
'''

import re
import os
import yaml as ya
import ruamel.yaml

from datetime import datetime, date
import dateutil.parser

# Setup yaml parser
yaml = ruamel.yaml.YAML()
yaml.indent(mapping=4, sequence=4, offset=2)
yaml.preserve_quotes = True

# Get project names and github urls 
# Entry name is used instead of "name" field
# since doesn't contain spaces etc.
with open("data.yaml", 'r') as f:
    #data = ruamel.yaml.round_trip_load(f)
    data = yaml.load(f)

comment_systems = []
github_urls = []        # url for project
github_commit_urls = [] # url for the last master/ commit

for i in data:

    #e.g., https://api.github.com/repos/posativ/isso
    api_url = re.sub('github.com', 'api.github.com/repos', data[i]["github"])

    #e.g., https://api.github.com/repos/posativ/isso/commits/master
    api_commit_url = api_url + '/commits/master'

    github_urls.append(api_url)
    github_commit_urls.append(api_commit_url)
    comment_systems.append(i)

# Define today's path
p = 'apigh/'+str(date.today())+'/'

# Write and wget files only if haven't done today
if not os.path.isdir(p):
    os.system('mkdir {}'.format(p) )

    # Save github repo info to apigh/YYYY-MM-DD/<comment_system>
    # Attention! There is a limit of requests per IP per hour
    # (created, license, open_issues)
    for url, cs in zip(github_urls, comment_systems):
        os.system('wget {} -O {}'.format(url,p+cs))

    # Save info on the last commit to apigh/YYYY-MM-DD/<comment_system.commit>
    # (created, license, open_issues)
    for url, cs in zip(github_commit_urls, comment_systems):
        os.system('wget {} -O {}'.format(url,p+cs+'.commit'))

# Read info from ./apigh/YYYY-MM-DD/<comment_system>
# and ./apigh/YYYY-MM-DD/<comment_system.commit>
for cs in os.listdir(p):
    if not '.swp' in cs: # if opened in vim
        if not '.commit' in cs:
            with open(p+cs, 'r') as f:
                api_data = yaml.load(f)
                stars       = api_data["stargazers_count"]
                created     = dateutil.parser.parse(api_data["created_at"])
                open_issues = api_data["open_issues"] # what is it? With all forks?

                if api_data["license"]:
                    if "spdx_id" in api_data["license"]:
                        license = api_data["license"]["spdx_id"] # "MIT"
                        data[cs]["license"] = license
                    elif "name" in api_data["license"]:
                        license = api_data["license"]["name"]   # "MIT License"
                        data[cs]["license"] = license

                # Change values with fresh ones
                data[cs]["stars"]       = stars
                data[cs]["open_issues"] = open_issues
                data[cs]["created"]     = created.strftime('%Y&#8209;%m&#8209;%d')
                print(cs, created)

        else:
            print()
            with open(p+cs, 'r') as f:
                api_commit_data = yaml.load(f)
                last_committed = dateutil.parser.parse(api_commit_data["commit"]["committer"]["date"])
                data[re.sub('.commit','',cs)]["last_committed"] = last_committed.strftime('%Y&#8209;%m&#8209;%d')
                print(cs, last_committed)
            

# Not safe! data.yaml is re-written. No backup
#Update data.yaml file with fresh values
with open('data.yaml', 'w') as f:
    yaml.dump(data, stream=f)
