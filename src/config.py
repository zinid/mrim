import ConfigParser
import sys
import exceptions
import traceback
import os
import re
import logging

COPYRIGHT = 'Copyright (c) 2005-2010 Jabber.Ru'
PROGRAM = 'Mrim'
VERSION = '0.2-git-20111002'
DEFAULTS = {
	'server':'localhost',
	'disconame':'Mail.ru IM',
	'port':'5347',
	'admins':'',
	'reconnect':'on',
	'reconnect_timeout':'60',
	'probe':'on',
	'show_os':'on',
	'show_version':'on',
	'psyco':'off',
	'timestamp':'%%d/%%m/%%y-%%H:%%M:%%S',
	'http_proxy': '',
	'profiling':'off',
	'xml_formatting': 'off',
	'pidfile': '',
	'allow_domains': []
}

class Config:

	def __init__(self, config_file):

		self.config_file = config_file
		try:
			self.parse()
		except IOError, e:
			print "Config file I/O error (%s): %s" % (self.config_file, e.strerror)
			sys.exit(1)
		except exceptions.Exception, e:
			if hasattr(e,'__module__') and e.__module__ == 'ConfigParser':
				print "Wrong config file format (%s)" % self.config_file
				print e
			else:
				traceback.print_exc()
			sys.exit(1)

	def parse(self):

		open(self.config_file).close()
		config = ConfigParser.SafeConfigParser(DEFAULTS)
		config.read([self.config_file])
		self.copyright = COPYRIGHT
		self.name = config.get('main', 'name')
		self.disconame = config.get('main', 'disconame')
		self.server = config.get('main', 'server')
		self.port = config.getint('main', 'port')
		self.passwd = config.get('main', 'password', raw=True)
		self.psyco = config.getboolean('main', 'psyco')
		admins = config.get('main', 'admins')
		self.admins = re.split(' *, *',admins)
		allow_domains = config.get('main', 'allow_domains')
		if allow_domains.strip():
			self.allow_domains = re.split(' *, *',allow_domains)
		else:
			self.allow_domains = []
		self.reconnect = config.getboolean('main', 'reconnect')
		self.probe = config.getboolean('main', 'probe')
		self.program = PROGRAM
		show_version = config.getboolean('main', 'show_version')
		if show_version:
			self.version = VERSION
		else:
			self.version = ''
		agent_string = self.program+' '+self.version
		show_os = config.getboolean('main', 'show_os')
		if show_os:
			self.os = self.get_os()
			agent_string += ' / '+self.os
		else:
			self.os = ''
		self.agent = agent_string[:255]
		self.profile_type = config.get('profile', 'type')
		if self.profile_type == 'xml':
			self.profile_dir = config.get('profile', 'dir')
		self.logfile = config.get('logger','logfile')
		self.profiling = config.getboolean('logger', 'profiling')
		self.loglevel = config.get('logger', 'loglevel')
		self.timestamp = config.get('logger', 'timestamp')
		self.http_proxy = config.get('main', 'http_proxy')
		self.xml_formatting = config.getboolean('logger', 'xml_formatting')
		self.pidfile = config.get('main', 'pidfile')
		self.reconnect_timeout = config.getint('main', 'reconnect_timeout')

	def get_os(self):
		v = [str(x) for x in sys.version_info[:3]]
		ver_python = 'Python '+'.'.join(v)+'-'+str(sys.version_info[3])
		if hasattr(os, 'uname'):
			uname = os.uname()
			ver_os = uname[0]+' '+uname[2]
		elif sys.platform.startswith('win'):
			try:
				import _winreg
				reg = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE,
					"SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion")
				win_ver = _winreg.QueryValueEx(reg, 'CurrentVersion')
				win_build = _winreg.QueryValueEx(reg, 'CurrentBuildNumber')
				_winreg.CloseKey(reg)
				ver_os = 'Windows %s.%s' % (win_ver[0],win_build[0])
			except:
				ver_os = 'Windows'
		else:
			ver_os = sys.platform
		return ver_os
