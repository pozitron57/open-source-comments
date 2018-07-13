#! /usr/bin/env python 
#coding=utf8

import numpy as np
import re
import yaml
from markdown import markdown

print()
fields = [
    'stars',
    'name',
    'github',
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
    'display_images',
    'updated',
    'created',
    'rss',
    'static',
    'description',
]
d={
    'stars':                 'Github ★',
    'name':                  'Name',
    'github':                'Github',
    'demo':                  'Demo',
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
    'nested_comments':       'Nested comments',
    'provided_hosting':      'Provided hosting',
    'collapse_comments':     'Collapse comments',
    'sort':                  'Configurable order',
    'rate_limit':            'Limit amount of comments per time',
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
    'static':                'Static (comments are placed to html)',
    'description':           'Description/note',
    'updated':               'Updated',
    'created':               'Created',
}

def urlify(x):
    ar=np.array([])
    if type(x) is list:
        for i in range(len(x)):
            if re.match('^http', x[i]):
                ar = np.append (ar, '<a href="{}">[{}]</a>'.format(x[i],i+1) )
            else:
                m = markdown(str(x[i]))
                f = re.sub('<p>','', m)
                f = re.sub('</p>','', f)
                ar = np.append (ar, f )
        return "'"+ ', '.join(ar) + "'"
    else:
        if re.match('http', str(x)):
            return '<a href="{}">[{}]</a>'.format(x,'link')
        else:
            m = markdown(str(x))
            f = re.sub('<p>','', m)
            f = re.sub('</p>','', f)
            return f


#d = "https://posativ.org/isso/"
#d = ['https://posativ.org/isso/', "https://lisakov.com/blog/", "https://vincent.bernat.im/en/blog/2018-more-privacy-blog"]
#d = "ps://posativ.org/isso/"
#print( urlify(d) )


# Read YAML file
with open("data.yaml", 'r') as f:
    data = yaml.load(f)

# Write to data.js
with open("data.js", 'w') as out:
    print ('var osc_data = [', file=out)
    for el in data:
        print('[', end=' ', file=out)
        for fi in fields:
            # Check if field exists (e.g. "Demo" for "Isso")
            if fi in data[el]:
                if type(data[el][fi]) is list:
                    print( urlify(data[el][fi]), end=", ", file=out)
                else:
                    print ("'" + urlify(data[el][fi]) +"',", end=' ', file=out)
            else:
                    print ("'?',", end=' ', file=out)
        print('],', file=out)
    print(']', file=out)

    # Add cols variable to data.js
    print('var cols=[', file=out)
    for fi in fields:
        print ('{title: "' + d[fi] + '"}, ', file=out)
    print(']', file=out)
