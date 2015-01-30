#!/usr/bin/python3
# Author: Jan 'jarainf' Rathner <jan@rathner.net>

import feedparser
import re
import subprocess
import time
import sys
import signal
import os

BASEDIR = os.path.expanduser('~/.nyupdate/')
FEEDFILE = BASEDIR + 'feeds'
QUEUEFILE = BASEDIR + 'queue'
FAILFILE = BASEDIR + 'fails'
NYAAREX = re.compile('.+tid=(\d+)')
UPDATEINTERVAL = 600
RETRYINTERVAL = 5
RETRYATTEMPTS = 5
QUEUERETRIES = 5
ERRORC = '\033[31m'
STATUSC = '\033[34m'
OKC = '\033[32m'
ENDC = '\033[0m'

INVALIDFEED = 'RSS-Feed: %s is not reachable or invalid!'
VALIDFEED = 'RSS-Feed: %s is now being processed!'
INVALIDLINE = 'Line: %s in %s is invalid!'

def _err(string):
	return ERRORC + string + ENDC

def _stat(string):
	return STATUSC + string + ENDC

def _ok(string):
	return OKC + string + ENDC

def _get_torrents(url):
	rssfeed = feedparser.parse(url)
	if not bool(rssfeed.bozo):
		return { entry.link : entry.title for entry in rssfeed.entries }
	else:
		return False

def _check_queue(queue):
	deletions = ()
	if queue:
		print(_stat('Retrying torrents from queue...'))
	else:
		return
	for torrent, tries in queue.items():
		print('Attempting to add torrent \'%s\' to queue...' % torrent) 
		if _addtorrent(torrent):
			print(_ok('Success!'))
			deletions += (torrent,)
		else:
			queue[torrent] += 1
			if tries >= QUEUERETRIES:
				print(_err('Failed to queue torrent after %d tries and %d cycles, human intervention required.' % (RETRYATTEMPTS, tries)))
				_append_file(torrent, FAILFILE)
				deletions += (torrent,)
			else:
				print(_err('Failed to queue torrent after %d tries and %d cycles, retrying in next cycle.' % (RETRYATTEMPTS, tries)))

	for deletion in deletions:
		del queue[deletion]
	_write_file(queue, QUEUEFILE)
	return queue

def _check_rss(feeds):
	global _queue
	for feed, last in feeds.items():
		data = _get_torrents(feed)
		if not data:
			print(_err(INVALIDFEED % feed))
			continue
		else:
			print(VALIDFEED % feed)
		newlast = last
		for url, title in sorted(data.items(), key = lambda x: NYAAREX.match(x[0]).group(1)):
			tuid = int(NYAAREX.match(url).group(1))
			if tuid <= last:
				continue
			if tuid > newlast:
				newlast = tuid
			print(_ok('Adding %s to queue!' % title))
			if not _addtorrent(url):
				print(_err('Failed to queue torrent after %d tries, skipping.' % RETRYATTEMPTS))
				_queue[url] = 0
				_append_file(url, QUEUEFILE)
		feeds[feed] = newlast
	return feeds

def _addtorrent(url):
	exitcode = subprocess.call(['transmission-remote', '--add', url])
	for i in (j for j in range(RETRYATTEMPTS - 1) if bool(exitcode)):
		print(_err('Failed to queue torrent, retrying in %d seconds.' % RETRYINTERVAL))
		time.sleep(RETRYINTERVAL)
		exitcode = subprocess.call(['transmission-remote', '--add', url])
	return not bool(exitcode)

def _read_file(dfile):
	data = {}
	with open(dfile, 'r') as f:
		for a_line in f:
			line = ''.join(a_line.split())
			if line.startswith('#') or line == '':
				continue
			parsed = line.split('@')
			if len(parsed) < 2:
				data[parsed[0]] = 0
			elif len(parsed) == 2:
				try:
					data[parsed[0]] = int(parsed[1])
				except:
					print(_err(INVALIDLINE % (line, dfile)))
			else:
				print(_err(INVALIDLINE % (line, dfile)))
	return data

def _append_file(data, dfile):
	with open(dfile, 'a') as f:
		f.write(data + os.linesep)


def _write_file(data, dfile):
	hashtext = ''
	with open(dfile, 'r') as f:
		for line in f:
			hashtext += line
	hashtext = hashtext.split(os.linesep)
	with open(dfile + '.new', 'w') as f:
		for line in hashtext:
			if line.startswith('#'):
				f.write(line + os.linesep)
		f.write(os.linesep)
		for (key, value) in data.items():
			f.write(key + ' @ ' + str(value) + os.linesep)
	os.rename(dfile + '.new', dfile)

def _signals(signum = None, frame = None):
	global _parsed_feeds
	_parsed_feeds = _reload_config(_parsed_feeds)
	if signum == 1:
		print('Reloaded feed information')
	else:
		print('Program is stopping now.')
		_write_file(_parsed_feeds, FEEDFILE)
		print('Program has successfully terminated!')
		sys.exit(0)

def _reload_config(memfeeds):
	feeds = _read_file(FEEDFILE)
	for feed in feeds.keys():
		if feed in memfeeds.keys():
			feeds[feed] = _parsed_feeds[feed]
	return feeds

def main():
	feedparser.PREFERRED_XML_PARSERS.remove('drv_libxml2') # This parser appears to be broken with Python3	

	global _parsed_feeds
	_parsed_feeds = _read_file(FEEDFILE)

	global _queue
	_queue = _read_file(QUEUEFILE)

	for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGQUIT, signal.SIGHUP]:
		signal.signal(sig, _signals)

	while True:
		print(_stat('Checking feeds now...'))
		_parsed_feeds = _check_rss(_parsed_feeds)
		_queue = _check_queue(_queue)
		print(_stat('Checking again in %.2f minutes.' % (UPDATEINTERVAL / 60)))
		time.sleep(UPDATEINTERVAL)

if __name__ == '__main__':
	main()
