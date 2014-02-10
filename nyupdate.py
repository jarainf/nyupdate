#!/usr/bin/python3
# Author: Jan 'jarainf' Rathner <jan@rathner.net>

import feedparser
import re
import subprocess
import time
import sys
import signal
from os.path import expanduser
from os import linesep

BASEDIR = expanduser('~/.nyupdate/')
SEEDFILE = BASEDIR + 'feeds'
NYAAREX = re.compile('.+tid=(\d+)')
UPDATEINTERVAL = 600
RED = '\033[31m'
BLUE = '\033[34m'
GREEN = '\033[32m'
ENDC = '\033[0m'

def _get_torrents(url):
	rssfeed = feedparser.parse(url)
	if not bool(rssfeed.bozo):
		return { entry.link : entry.title for entry in rssfeed.entries }
	else:
		return False


def _check_rss(feeds): 
	for feed, last in feeds.items():
		data = _get_torrents(feed)
		if not data:
			print(RED + 'RSS-Feed: ' + feed + ' is not reachable or invalid!' + ENDC)
			continue
		else:
			print('RSS-Feed: ' + feed + ' is now being processed!')
		newlast = last
		for url, title in data.items():
			tuid = int(NYAAREX.match(url).group(1))
			if tuid <= last:
				continue
			if tuid > newlast:
				newlast = tuid
			print(GREEN + title + ' has been added to queue!' + ENDC)
			_addtorrent(url)
		feeds[feed] = newlast
	return feeds

def _addtorrent(url):
	subprocess.call(['transmission-remote', '--add', url])

def _read_feeds():
	feeds = {}
	with open(SEEDFILE, 'r') as f:
		for a_line in f:
			line = ''.join(a_line.split())
			if line.startswith('#'):
				continue

			parsed = line.split('@')
			if len(parsed) < 2 and parsed[0] != '':
				feeds[parsed[0]] = 0
			elif len(parsed) == 2:
				try:
					feeds[parsed[0]] = int(parsed[1])
				except:
					print(RED + 'Line: ' + line + ' in ' + FEEDFILE + ' is invalid!' + ENDC)
			else:
				print(RED + 'Line: ' + line + ' in ' + FEEDFILE + ' is invalid!' + ENDC)
	return feeds

def _write_feeds(memfeeds):
	hashtext = ''
	with open(SEEDFILE, 'r') as f:
		for line in f:
			hashtext += line
	hashtext = hashtext.split(linesep)
	with open(SEEDFILE, 'w') as f:
		for line in hashtext:
			if line.startswith('#'):
				f.write(line + linesep)
		for (key, value) in memfeeds.items():
			f.write(key + ' @ ' + str(value) + linesep)

def _signals(signum = None, frame = None):
	global _parsed_feeds
	_parsed_feeds = _reload_config(_parsed_feeds)
	if signum == 1:
		print('Reloading feed information')
	else:
		print('Program is stopping now.')
		_write_feeds(_parsed_feeds)
		print('Program has been successfully terminated!')
		sys.exit(0)

def _reload_config(memfeeds):
	feeds = _read_feeds()
	for feed in feeds.keys():
		if feed in memfeeds.keys():
			feeds[feed] = _parsed_feeds[feed]
	return feeds

def main():
	feedparser.PREFERRED_XML_PARSERS.remove('drv_libxml2') # This parser seems to be broken with Python3	

	global _parsed_feeds
	_parsed_feeds = _read_feeds()
	
	for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGQUIT, signal.SIGHUP]:
		signal.signal(sig, _signals)

	while True:
		print(BLUE + 'Checking feeds now...' + ENDC)
		_parsed_feeds = _check_rss(_parsed_feeds)
		timeout = UPDATEINTERVAL
		print((BLUE + 'Checking in %.2f minutes again.' + ENDC) % (timeout / 60))
		time.sleep(timeout)

if __name__ == '__main__':
	main()
