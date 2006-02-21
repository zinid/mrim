#!/usr/bin/env python

import transport
import config
import signal
import urllib2
import time
import sys
import traceback
import utils
import logging
import xmpp
import os

conf = config.Config()

def logger_init():
	formatter = logging.Formatter('%(asctime)s %(message)s', conf.timestamp)
	#log_file_handler = logging.FileHandler(conf.logfile)
	log_file_handler = logging.StreamHandler()
	log_file_handler.setFormatter(formatter)
	logger = logging.getLogger('mrim')
	logger.addHandler(log_file_handler)
	l = conf.loglevel
	if l == 'debug':
		level = logging.DEBUG
	elif l == 'info':
		level = logging.INFO
	elif l == 'warning':
		level = logging.WARNING
	elif l == 'error':
		level = logging.ERROR
	elif l == 'critical':
		level = logging.CRITICAL
	else:
		level = logging.CRITICAL
	logger.setLevel(level)
	return logger

logger = logger_init()

class xmpppy_debug:
	def __init__(self, *args, **kwargs):
		self.debug_flags = []
	def show(self, *args, **kwargs):
		pass
	def is_active(self, flag):
		pass
	def active_set(self, active_flags=None):
		return 0
	def Show(self, *args, **kwargs):
		typ = args[0]
		s = args[1]
		action = args[2]
		if action in ['got','sent']:
			log_string = '[%s/%s] %s stanza:\n%s' % (typ,action,action,s)
			logger.debug(log_string)
		elif typ != 'nodebuilder':
			logger.debug('[%s/%s] %s' % (typ,action,s))

xmpp.debug.Debug = xmpppy_debug

class LogFile:
	def __init__(self, f):
		self.f = f
	def write(self, s):
		self.f.write(s)
		self.f.flush()
	def flush(self):
		self.f.flush()

def daemonize():
	try:
		pid = os.fork()
	except OSError, e:
		print >>sys.stderr, "fork #1 failed: %d (%s)" % (e.errno, e.strerror)
		sys.exit(1)
	if (pid == 0):
		os.setsid()
		signal.signal(signal.SIGHUP, signal.SIG_IGN)
		try:
			pid = os.fork()
		except OSError, e:
			print >>sys.stderr, "fork #2 failed: %d (%s)" % (e.errno, e.strerror)
			sys.exit(1)
		if (pid == 0):
			os.chdir("/")
			os.umask(0)
		else:
			os._exit(0)
	else:
		os._exit(0)
	return(0)
	sys.exit(0)

def main():
	if conf.psyco:
		try:
			import psyco
			psyco.full()
			logger.critical("Enabling psyco support.")
		except:
			logger.critical("Looks like psyco is not installed in your system. Psyco acceleration will not be enabled.")
			pass
	while 1:
		try:
			xmpp_con = transport.XMPPTransport(conf.name,conf.disconame,
					conf.server,conf.port,conf.passwd,logger)
			logger.critical("Connecting to XMPP server")
			xmpp_con.run()
		except KeyboardInterrupt:
			logger.critical('Got SIGINT, closing connections')
			xmpp_con.stop()
			logger.critical('Shutdown')
			sys.exit(0)
		except:
			traceback.print_exc()
			logger.critical("Connection to server lost")
			logger.critical("Trying to reconnect over 5 seconds")
			try:
				xmpp_con.stop(notify=False)
				del xmpp_con
			except:
				traceback.print_exc()
				pass
			time.sleep(5)

if __name__ == "__main__":
	#daemonize()
	#sys.stdout = sys.stderr = LogFile(open(conf.logfile, 'a+'))
	main()
