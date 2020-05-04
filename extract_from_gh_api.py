#! /usr/bin/env python 
#coding=utf8

'''
THIS FILE IS UNDER DEVELOPMENT AND CURRENTLY
IS NOT WORKING

Extract the needed data from github api responses
and REWRITE files
'''

import re
import os
import ruamel.yaml
import fileinput

from datetime import date, timedelta
import dateutil.parser

# Setup yaml parser
yaml = ruamel.yaml.YAML()
yaml.indent(mapping=4, sequence=4, offset=2)
yaml.preserve_quotes = True
import fileinput

import json

f = 'apigh/2019-04-06/talkyard.commit'

with open(f) as json_data:
    #api_commit_data = yaml.load(f)
    api_commit_data  = json.load(json_data)

print (api_commit_data['commit']['committer']['date'])
#print (api_commit_data['commit']['committer']['date'])

#last_committed = dateutil.parser.parse(api_commit_data['commit']['committer']['date'])
print (last_committed)
