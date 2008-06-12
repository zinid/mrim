#!/usr/bin/env python

import config
import sys
import getopt
import signal
import os
import hotshot, hotshot.stats

usage = '''Usage:
-d        detach from console
-c file   path to config file
-s file   analyse the profiling file
-p file   path to pid file'''

daemon = False
config_file = None
pid = None

try:
	opts, args = getopt.getopt(sys.argv[1:], "hdc:ps:")
except getopt.GetoptError, e:
	print "Can't start:", e.msg
	print usage
	sys.exit(1)

for k,v in opts:
	if k == '-h':
		print usage
		sys.exit(0)
	elif k == '-s':
		s = hotshot.stats.load(v)
		s.strip_dirs()
		s.sort_stats('time', 'calls')
		s.print_stats(20)
		sys.exit(0)
	elif k == '-d':
		daemon = True
	elif k == '-c':
		config_file = v
	elif k == '-p':
		pid = v

if not config_file:
	print usage
	sys.exit(1)

conf = config.Config(config_file)
conf.daemon = daemon
if pid:
	conf.pidfile = pid

if __name__ == "__main__":
	import init
	if conf.profiling:
		pfile = os.path.join(conf.profile_dir, "mrim.prof")
		p = hotshot.Profile(pfile)
		p.runcall(init.start)
		p.close()
	else:
		init.start()
