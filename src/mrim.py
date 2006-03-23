#!/usr/bin/env python

import config
import sys
import getopt
import signal

usage = '''Usage:
-d        detach from console
-c file   path to config file'''

daemon = False
config_file = None

try:
	opts, args = getopt.getopt(sys.argv[1:], "hdc:")
except getopt.GetoptError, e:
	print "Can't start:", e.msg
	print usage
	sys.exit(1)

for k,v in opts:
	if k == '-h':
		print usage
		sys.exit(0)
	elif k == '-d':
		daemon = True
	elif k == '-c':
		config_file = v

if not config_file:
	print usage
	sys.exit(1)

conf = config.Config(config_file)
conf.daemon = daemon

if __name__ == "__main__":
	import init
	init.start()
