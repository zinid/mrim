import ConfigParser
import sys
import exceptions
import traceback
import os
import re

PROGRAM = 'Mrim'
VERSION = '0.1-svn-20060305'
DEFAULTS = {
	'server':'localhost',
	'disconame':'Mail.ru IM',
	'port':'5347',
	'admins':'',
	'reconnect':'on',
	'probe':'on',
	'show_os':'on',
	'show_version':'on',
	'psyco':'off',
	'timestamp':'%%d/%%m/%%y-%%H:%%M:%%S',
	'http_proxy': '',
	'xml_formatting': 'off'
}

class Config:

	def __init__(self):

		self.config_file = '../mrim.conf'
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
		self.name = config.get('main', 'name')
		self.disconame = config.get('main', 'disconame')
		self.server = config.get('main', 'server')
		self.port = config.getint('main', 'port')
		self.passwd = config.get('main', 'password')
		self.psyco = config.getboolean('main', 'psyco')
		admins = config.get('main', 'admins')
		self.admins = re.split(' *, *',admins)
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
		self.loglevel = config.get('logger', 'loglevel')
		self.timestamp = config.get('logger', 'timestamp')
		self.http_proxy = config.get('main', 'http_proxy')
		self.xml_formatting = config.getboolean('logger', 'xml_formatting')

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
		#return '%s (%s)' % (ver_python, ver_os)
		return ver_os
