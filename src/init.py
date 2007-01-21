import mrim
import signal
import time
import sys
import traceback
import logging
import os
import re

conf = mrim.conf

class LogFile:
	def __init__(self):
		self.f = open(conf.logfile, 'a+')
	def write(self, s):
		self.f.write(s)
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
			#os.chdir("/")
			os.umask(0)
		else:
			os._exit(0)
	else:
		os._exit(0)
	return(0)
	sys.exit(0)

if conf.daemon:
	daemonize()
	sys.stdout = sys.stderr = LogFile()

def logger_init():
	formatter = logging.Formatter('%(asctime)s %(message)s', conf.timestamp)
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

if conf.pidfile:
	try:
		pidfile = open(conf.pidfile, 'w')
		pidfile.write(`os.getpid()`+'\n')
		pidfile.close()
	except IOError, e:
		logger.critical("PID file I/O error (%s): %s" % (conf.pidfile, e.strerror))

import xmpp
import transport
import utils

class xmpppy_debug:
	def __init__(self, *args, **kwargs):
		self.debug_flags = []
		if (logger.level != logging.DEBUG) or (not conf.xml_formatting):
			utils.pretty_xml = lambda x: x
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
			try:
				xml_s = utils.pretty_xml(s)
			except:
				xml_s = s
			log_string = '[%s/%s] %s stanza(s):\n%s' % (typ,action,action,xml_s)
			logger.debug(log_string)
		elif typ not in ['nodebuilder','dispatcher']:
			logger.debug('[%s/%s] %s' % (typ,action,s))

xmpp.debug.Debug = xmpppy_debug

def start():
	if conf.psyco:
		try:
			import psyco
			psyco.full()
			logger.critical("Enabling psyco support.")
		except:
			logger.critical("Looks like psyco is not installed in your system. Psyco acceleration will not be enabled.")
			pass
	if conf.http_proxy:
		try:
			conf.http_proxy = utils.get_proxy(conf.http_proxy)
		except:
			logger.critical("Invalid format of HTTP-proxy. No proxy will be used.")
			conf.http_proxy = None
	while 1:
		try:
			xmpp_con = transport.XMPPTransport(conf.name,conf.disconame,
					conf.server,conf.port,conf.passwd,logger)
			logger.critical("Connecting to XMPP server")
			xmpp_con.run()
		except KeyboardInterrupt:
			logger.critical('Got SIGINT, closing connections')
			xmpp_con.stop()
			try:
				os.unlink(conf.pidfile)
			except OSError:
				pass
			logger.critical('Shutdown')
			break
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
