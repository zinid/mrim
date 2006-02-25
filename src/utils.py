import threading
import random
import sys
import types
import os
import xmpp
import config
import struct
import datetime
import time
import socket
from mmptypes import *
import re

conf = config.Config()
ENCODING = 'utf-8'
mail_pattern = re.compile(
	'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,15}@(mail\.ru|inbox\.ru|bk\.ru|list\.ru|corp\.mail\.ru)$'
)
password_pattern = re.compile('[\040-\176]{4,}$')

try:

	import xml.dom.ext
	import xml.dom.minidom
	import cStringIO

	def pretty_xml(xml_string):
		io_string = cStringIO.StringIO()
		xml_string = '<stanza>'+xml_string+'</stanza>'
		xml.dom.ext.PrettyPrint(
			root = xml.dom.minidom.parseString(xml_string),
			stream = io_string,
			indent = '    '
		)
		io_string.seek(0)
		res = []
		for x in io_string.readlines()[2:-1]:
			if x.startswith('    '):
				res.append(x[4:])
			else:
				res.append(x)
		sum = ''
		for i in res:
			sum += i
		return sum.strip('\n')

except:

	def pretty_xml(xml_string):
		return xml_string

def start_daemon(func, variables, thread_name=''):
	if thread_name:
		daemon = threading.Thread(target=func, args=variables, name=thread_name)
	else:
		daemon = threading.Thread(target=func, args=variables)
	daemon.setDaemon(True)
	daemon.start()
	daemon_name = daemon.getName()
	#if daemon_name != 'asyncore_loop':
	#	print "Thread %s has started" % daemon_name

def is_valid_email(mail):
	if mail_pattern.match(mail):
		return True
	else:
		return False

def is_valid_password(password):
	if password_pattern.match(password):
		return True
	else:
		return False

def dump_packet(p):
	print "--- Begin of dump ---"
	print "Header: %s" % p.getHeader().__repr__()
	print "Body: %s" % p.getBody().__repr__()
	print "---- End of dump ----\n"

def seq():
	return long(random.random()*100000)

def str2win(s):
	if type(s) == types.StringType:
		r = unicode(s, ENCODING).encode('cp1251', 'replace')
	elif type(s) == types.UnicodeType:
		r = s.encode('cp1251', 'replace')
	else:
		raise TypeError('value %s is neither unicode nor string' % s)
	return r

def win2str(s):
	u_s = unicode(s, 'cp1251')
	#return unicode(u_s.encode(ENCODING, 'replace'),'utf-8')
	return u_s.encode(ENCODING, 'replace')

def log_handler(f, typ):
	print "Invoke method %s for %s packet" % (f,hex(typ))

def get_proto_major(p):
	return (p & 0xFFFF0000L) >> 16

def get_proto_minor(p):
	return (p & 0x0000FFFFL)

def mail2jid(e_mail):
	return e_mail.replace('@', '%') + '@' + conf.name

def jid2mail(jid):
	return jid.split('@')[0].replace('%', '@')

def dec2bin(n):
	bStr = ''
	if n < 0:
		raise ValueError, "must be a positive integer"
	if n == 0:
		return '0'
	while n > 0:
		bStr = str(n % 2) + bStr
		n = n >> 1
	return bStr

class MoscowTimeZone(datetime.tzinfo):

	def __init__(self):

		self.HOUR = datetime.timedelta(hours=1)
		self.ZERO = datetime.timedelta(0)
		self.DSTSTART = datetime.datetime(1, 3, 25, 2)
		self.DSTEND = datetime.datetime(1, 10, 25, 3)

	def utcoffset(self, dt):
		
		return datetime.timedelta(hours=3) + self.dst(dt)

	def dst(self, dt):

		start = self.first_sunday_on_or_after(self.DSTSTART.replace(year=dt.year))
		end = self.first_sunday_on_or_after(self.DSTEND.replace(year=dt.year))
		if start <= dt.replace(tzinfo=None) < end:
			return self.HOUR
		else:
			return self.ZERO

	def first_sunday_on_or_after(self, dt):
		days_to_go = 6 - dt.weekday()
		if days_to_go:
			dt += datetime.timedelta(days_to_go)
			return dt

def msk2utc(t):
	tz = MoscowTimeZone()
	T = t[:6]+(0,tz)
	d = datetime.datetime(*T)
	return d.utctimetuple()

def gettime():
	T = {}
	if time.daylight:
		T['tz'] = time.tzname[0]
	else:
		T['tz'] = time.tzname[1]
	T['utc'] = time.strftime('%Y%m%dT%H:%M:%S', time.gmtime())
	T['display'] = time.asctime()
	return T

def get_server(host='mrim.mail.ru', port=2042):
	socket.setdefaulttimeout(30)
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((host, port))
	data = s.recv(1024)
	s.close()
	serv, serv_port = data.strip().split(':')
	return (serv, int(serv_port))

def uptime(T):
	t = int(T)
	days, s = (t/86400, t % 86400)
	hours, s = (s/3600, s % 3600)
	minutes, secs = (s/60, s % 60)
	return "%s days, %s hours %s minutes %s secs" % (days, hours, minutes, secs)

def show2status(show):
	if show in [None, 'chat']:
		status = STATUS_ONLINE
	elif show in ['dnd','xa','away']:
		status = STATUS_AWAY
	else:
		status = STATUS_UNDETERMINATED
	return status

def status2show(status):
	typ, show = None, None
	if status == STATUS_AWAY:
		show = 'away'
	elif status != STATUS_ONLINE:
		typ = 'unavailable'
	return (typ,show)
