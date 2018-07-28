#! /usr/bin/env python 
#coding=utf8

'''
Injects html generated from index.md to index.html
'''

import re
from datetime import date
import mistune

renderer = mistune.Renderer(hard_wrap=False)
markdown = mistune.Markdown(renderer=renderer)

# Read index.md and convert to html
with open('index.md', 'r') as f:
    text = f.read()
    preamble = re.sub('## Share your experience.*', '', text, flags=re.S)
    preamble = markdown(preamble)
    share = re.sub('.*Choose columns to show', '', text, flags=re.S)
    share = markdown(share)


# Inject it into index.html
with open('index.html', 'r+') as f:
    text = f.read()

    # Inject preamble
    text = re.sub(
        '<div class="preamble">(.*?)div>',
        '<div class="preamble">{}</div>'.format(preamble),
        text, flags=re.S)

    # Inject 'share your experience' after the table
    text = re.sub(
        '<div class="isso-comments">(.*?)<section id="isso-thread">',
        '<div class="isso-comments">{}<section id="isso-thread">'.format(share),
        text, flags=re.S)

    # Update date in index.html footer
    text = re.sub('Last updated:.*','Last updated: {} <br>'.format(date.today()), text)

    f.seek(0)
    f.write(text)
    f.truncate()
