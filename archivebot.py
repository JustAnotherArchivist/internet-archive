#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2018 emijrp <emijrp@gmail.com>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import json
import re
import sys
import time
import urllib.parse
import urllib.request
#import pywikibot
#import pywikibot.pagegenerators as pagegenerators

from archiveteamfun import *

def curateurlscore(url=''):
    url2 = url.strip()
    if url2.startswith('http'):
        if '://' in url2 and not '/' in url2.split('://')[1]:
            url2 = url2 + "/"
    return url2

def curateurls(wlist=''):
    # Returns a dict of sectionname => list of URLs entries
    # sectionname is None for URLs outside of a section (i.e. on a page without section or before the first section).
    # A "URL entry" in the list is a tuple (URL, label); the label is None if it isn't present.

    lines = []
    currentsectionname = None
    currentsectionentries = []
    sectionentries = {}

    def endsection():
        nonlocal currentsectionentries, lines, sectionentries, currentsectionname
        currentsectionentries.sort()
        lines.extend(url + ' | ' + label if label else url for url, label in currentsectionentries)
        sectionentries[currentsectionname] = currentsectionentries
        currentsectionentries = []

    for line in wlist.text.strip().splitlines():
        if line.strip().startswith('='):
            # New section, sort and append previous section
            endsection()
            currentsectionname = line.strip().strip('=').strip()
            if currentsectionname in sectionentries:
                print('Warning: duplicate section name {!r} on page {}'.format(currentsectionname, wlist.title()))
            lines.append(line.strip())
        elif line.strip():
            label = ''
            if '|' in line:
                url, label = line.split('|')[0:2]
            else:
                url = line.strip()
            url = curateurlscore(url=url)
            if label:
                line = url.strip() + ' | ' + label.strip()
            else:
                line = url
            currentsectionentries.append((url.strip(), label.strip() if label else None))
    endsection()

    lines = '\n'.join(lines)
    if wlist.text != lines:
        wlist.text = lines
        wlist.save("BOT - Sorting list")

    return sectionentries


class MockPage:
    def __init__(self, title, text):
        self._title = title
        self.text = text

    def title(self):
        return self._title

    def exists(self):
        return True

    def save(self, comment):
        print('save {!r} with comment {!r} and contents:'.format(self._title, comment))
        print('===========start contents================')
        print(self.text)
        print('===========end contents==================')


def main():
#    atsite = pywikibot.Site('archiveteam', 'archiveteam')
#    cat = pywikibot.Category(atsite, "Category:ArchiveBot")
#    gen = pagegenerators.CategorizedPageGenerator(cat, start="!")
#    pre = pagegenerators.PreloadingGenerator(gen, pageNumber=60)
    
#    for page in pre:
    for page in [MockPage('ArchiveBot/Example', 'Foo\n<!-- bot:Main --><!-- /bot -->\nBar\n<!-- bot:Foo --><!-- /bot -->\nBaz')]:
        wtitle = page.title()
        wtext = page.text
        
        if len(sys.argv)>1 and not sys.argv[1] in wtitle:
            continue
        
        #if not wtitle.startswith('ArchiveBot/National Film'):
        if not wtitle.startswith('ArchiveBot/'):
            continue
#        wlist = pywikibot.Page(atsite, '%s/list' % (wtitle))
        wlist = MockPage('ArchiveBot/Example/list', '= Main =\nhttp://archiveteam.org/\n\n= Foo =\nhttps://foo.archiveteam.org/\nhttps://bar.archiveteam.org/')
        if not wlist.exists():
            print("Page %s/list doesnt exist" % (wtitle))
            continue
        sectionentries = curateurls(wlist=wlist)
        
        print('\n===', wtitle, '===')
        if (not '<!-- bot -->' in wtext and not '<!-- bot:' in wtext) or not '<!-- /bot -->' in wtext:
            print("No <!-- bot --> tag. Skiping...")
            continue

        newtext = []

        # Find blocks of page text that end with a bot tag
        blocks = wtext.split('<!-- /bot -->')

        # The last block must be tag-free, so only iterate over the previous ones
        for block in blocks[:-1]:
            # Find beginning of bot tag
            pos = block.find('<!-- bot')
            if pos == -1:
                # Broken block (no opening tag), skip
                newtext.append(block)
                continue

            if block[pos:].startswith('<!-- bot -->'):
                # Sectionless tag, use section None
                section = None
                openingtag = '<!-- bot -->'
            elif block[pos:].startswith('<!-- bot:'):
                # Extract section name
                openend = block.find('-->', pos)
                if openend == -1:
                    # Broken block (no end of opening tag), skip
                    newtext.append(block)
                    continue
                section = block[pos + 9:openend].strip() # 9 = len('<!-- bot:')
                openingtag = block[pos:openend + 3]
            else:
                # Invalid bot tag, skip
                newtext.append(block)
                continue

            if section not in sectionentries:
                # Broken block (section doesn't exist), skip
                newtext.append(block)
                continue

            # Add prefixed text (if any)
            newtext.append(block[:pos])

            # Add opening tag (as it was before)
            newtext.append(openingtag)

            # Generate table
            c = 1
            rowsplain = ""
            totaljobsize = 0
            for url, label in sectionentries[section]:
                viewerplain = ''
                viewerdetailsplain = ''
                viewer = [getArchiveBotViewer(url=url)]
                if viewer[0][0]:
                    viewerplain = "[%s {{saved}}]" % (viewer[0][1])
                    viewerdetailsplain = viewer[0][2]
                else:
                    viewerplain = "[%s {{notsaved}}]" % (viewer[0][1])
                    viewerdetailsplain = ''
                totaljobsize += viewer[0][3]
                rowspan = len(re.findall(r'\|-', viewerdetailsplain))+1
                rowspanplain = 'rowspan=%d | ' % (rowspan) if rowspan>1 else ''
                if label:
                    rowsplain += "\n|-\n| %s[%s %s] || %s%s\n%s " % (rowspanplain, url, label, rowspanplain, viewerplain, viewerdetailsplain if viewerdetailsplain else '|  ||  ||  || ')
                else:
                    rowsplain += "\n|-\n| %s%s || %s%s\n%s " % (rowspanplain, url, rowspanplain, viewerplain, viewerdetailsplain if viewerdetailsplain else '|  ||  ||  || ')
                c += 1
        
            output = """
* '''Statistics''': {{saved}} (%s){{·}} {{notsaved}} (%s){{·}} Total size (%s)

Do not edit this table, it is automatically updated by bot. There is a [[{{FULLPAGENAME}}/list|raw list]] of URLs that you can edit.

{| class="wikitable sortable plainlinks"
! rowspan=2 | Website !! rowspan=2 | [[ArchiveBot]] !! colspan=4 | Archive details
|-
! Domain !! Job !! Date !! Size %s
|}
""" % (len(re.findall(r'{{saved}}', rowsplain)), len(re.findall(r'{{notsaved}}', rowsplain)), convertsize(b=totaljobsize), rowsplain)
            newtext.append(output)

            newtext.append('<!-- /bot -->')

        # Add the last, tag-free block
        newtext.append(blocks[-1])

        newtext = ''.join(newtext)

        if wtext != newtext:
#            pywikibot.showDiff(wtext, newtext)
            page.text = newtext
            page.save("BOT - Updating page: {{saved}} (%s), {{notsaved}} (%s), Total size (%s)" % (len(re.findall(r'{{saved}}', rowsplain)), len(re.findall(r'{{notsaved}}', rowsplain)), convertsize(b=totaljobsize)))
        else:
            print("No changes needed in", page.title())

if __name__ == '__main__':
    main()
