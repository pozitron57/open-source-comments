#! /usr/bin/env python
#coding=utf8

'''
Convert data.yaml to data.js
'''

import re
import yaml
from markdown import markdown

fields = [
    'stars',
    'stars_dif',
    'name',
    'source',
    'open_issues',
    'demo',
    'js_kB',
    'css_kB',
    'language',
    'db',
    'markdown_support',
    'social_network_login',
    'anonymous_comments',
    'edit',
    'vote',
    'moderation',
    'nested_comments',
    'mail_notification',
    'antispam',
    'bad_words_list',
    'use_cookies',
    'avatar',
    'provided_hosting',
    'collapse_comments',
    'sort',
    'docker',
    'paging',
    'rate_limit',
    'hide_long_threads',
    'import_from_wordpress',
    'import_from_disqus',
    'english_documentation',
    'dependency',
    'webmention',
    'display_images',
    'license',
    'rss',
    'static',
    'created',
   #'updated', # What's this date?
    'last_committed',
   #'unmaintained', #or Maintaned?
    'description',
]

fields_dic={
    'stars':                 'Github stars',
    'stars_dif':             'Stars&nbsp;in 2&nbsp;weeks',
    'name':                  'Name',
    'source':                'Source code',
    'demo':                  'Demo & examples',
    'js_kB':                 'js, kB',
    'css_kB':                'css, kB',
    'language':              'Language',
    'db':                    'Database',
    'mail_notification':     'Mail notification',
    'edit':                  'User can edit',
    'vote':                  'User can vote',
    'antispam':              'Antispam',
    'bad_words_list':        'Bad words list',
    'use_cookies':           'Uses cookies',
    'avatar':                'Avatar',
    'markdown_support':      'Markdown support',
    'moderation':            'Moderation',
    'dependency':            'Dependencies',
    'webmention':            'Supports Webmention',
    'nested_comments':       'Nested comments',
    'provided_hosting':      'Can host for you',
    'collapse_comments':     'Collapse comments',
    'sort':                  'Configurable order',
    'rate_limit':            'Comment rate limit',
    'docker':                'Docker container',
    'paging':                'Paging',
    'hide_long_threads':     'Hide long threads',
    'anonymous_comments':    'Anonymous comments',
    'social_network_login':  'Social network login',
    'import_from_wordpress': 'Import from wordpress',
    'import_from_disqus':    'Import from disqus',
    'english_documentation': 'English documentation',
    'rss':                   'RSS',
    'display_images':        'Display images',
    'static':                'Static',
    'description':           'Description',
    'updated':               'Updated (y‑m‑d)',
    'last_committed':        'Updated (y‑m‑d)',
    'created':               'Created (y‑m‑d)',
    'license':               'License',
    'open_issues':           'Open issues + PR',
    'unmaintained':          'Unmaintained',
}

def source_urlify(x):
    ar=[]
    if type(x) is list:
        for i in range(len(x)):
            if re.search('github.com', x[i]):
                ar.append('<a href="{}">{}</a>'.format(x[i],'github') )
            elif re.search('gitlab.com', x[i]):
                ar.append('<a href="{}">{}</a>'.format(x[i],'gitlab') )
            elif re.match('^http', x[i]):
                ar.append('<a href="{}">[{}]</a>'.format(x[i],i+1) )
            else:
                m = markdown(str(x[i]))
                m = re.sub('<p>','', m)
                m = re.sub('</p>','', m)
                ar.append(m)
        return "'"+ ', '.join(ar) + "'"
    else:
        if re.search('github.com', x):
            return '<a href="{}">{}</a>'.format(x,'github')
        elif re.search('gitlab.com', x):
            return '<a href="{}">{}</a>'.format(x,'gitlab')
        else:
            return '<a href="{}">{}</a>'.format(x,'link')

def urlify(x):
    ar=[]
    if type(x) is list:
        for i in range(len(x)):
            if re.search('github.com', x[i]):
                ar.append('<a href="{}">{}</a>'.format(x[i],'github') )
            elif re.search('gitlab.com', x[i]):
                ar.append('<a href="{}">{}</a>'.format(x[i],'gitlab') )
            elif re.match('^http', x[i]):
                ar.append('<a href="{}">[{}]</a>'.format(x[i],i+1) )
            else:
                m = markdown(str(x[i]))
                m = re.sub('<p>','', m)
                m = re.sub('</p>','', m)
                ar.append(m)
        return "'"+ ', '.join(ar) + "'"
    else:
        if re.match('http', str(x)):
            return '<a href="{}">{}</a>'.format(x,'demo')
        else:
            m = markdown(str(x))
            m = re.sub('<p>','', m)
            m = re.sub('</p>','', m)
            return m

# Read YAML file
with open("data.yaml", 'r') as f:
    data = yaml.load(f)

# Write to data.js
with open("data.js", 'w') as out:
    print ('var osc_data = [', file=out)
    for el in data:
        print('[', end=' ', file=out)
        for fi in fields:
            # Check if the field exists (e.g. "Demo" for "Isso")
            if fi=='source':
                if type(data[el][fi]) is list:
                    print (source_urlify(data[el][fi]), end=", ", file=out)
                else:
                    print ("'" + source_urlify(data[el][fi]) +"',", end=' ', file=out)
            elif fi in data[el]:
                if type(data[el][fi]) is list:
                    print (urlify(data[el][fi]), end=", ", file=out)
                else:
                    print ("'" + urlify(data[el][fi]) +"',", end=' ', file=out)
            else:
                    print ("'?',", end=' ', file=out)
        print('],', file=out)
    print(']', file=out)

    # Add 'cols' variable to data.js
    # It contains all column names
    print('var cols=[', file=out)
    for fi in fields:
        print ('{title: "' + fields_dic[fi] + '"}, ', file=out)
    print(']', file=out)
