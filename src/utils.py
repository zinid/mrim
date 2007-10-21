import random
import sys
import types
import os
import xmpp
import struct
import datetime
import time
import socket
from mmptypes import *
import re
import mrim
import zlib
import base64
import cStringIO
import xmpp
import sha

conf = mrim.conf
ENCODING = 'utf-8'

xmpp.NS_GATEWAY = 'jabber:iq:gateway'
xmpp.NS_STATS = 'http://jabber.org/protocol/stats'
xmpp.NS_ROSTERX = 'http://jabber.org/protocol/rosterx'
xmpp.NS_NICK = 'http://jabber.org/protocol/nick'
xmpp.NS_RECEIPTS = 'urn:xmpp:receipts'
xmpp.NS_CHATSTATES = 'http://jabber.org/protocol/chatstates'
xmpp.NS_NEW_DELAY = 'urn:xmpp:delay'
xmpp.NS_NEW_TIME = 'urn:xmpp:time'
xmpp.NS_PING = 'urn:xmpp:ping'
xmpp.NS_CAPS = 'http://jabber.org/protocol/caps'

common_features = [
	xmpp.NS_DISCO_INFO,
	xmpp.NS_DISCO_ITEMS,
	xmpp.NS_VCARD,
	xmpp.NS_COMMANDS,
	xmpp.NS_CAPS]
client_features = common_features + [
	xmpp.NS_RECEIPTS,
	xmpp.NS_CHATSTATES]
server_features = common_features + [
	xmpp.NS_STATS,
	xmpp.NS_SEARCH,
	xmpp.NS_REGISTER,
	xmpp.NS_TIME,
	xmpp.NS_VERSION,
	xmpp.NS_LAST,
	xmpp.NS_GATEWAY,
	xmpp.NS_NEW_TIME,
	xmpp.NS_DELAY,
	xmpp.NS_NEW_DELAY,
	xmpp.NS_PING]

client_features.sort()
server_features.sort()

mail_pattern = re.compile(
	'[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,15}@(mail\.ru|inbox\.ru|bk\.ru|list\.ru|corp\.mail\.ru)$'
)
password_pattern = re.compile('[\040-\176]{4,}$')
number_pattern = re.compile('\+{0,1}[0-9]+$')
upper_ascii_pattern = re.compile('[\200-\377]+')
invalid_chars = re.compile(
	'[\000-\011\013\014\016-\037\202\204-\207\210\211\213\221-\227\230\231\233\271]'
)
RTF_H = '{\\rtf1\\ansi\\ansicpg1251\\deff0\\deflang1049{\\fonttbl{\\f0\\fnil\\fcharset204 Tahoma;}}\r\n{\\colortbl ;\\red0\\green0\\blue0;}\r\n\\viewkind4\\uc1\\pard\\cf1\\f0\\fs18 '
RTF_T = '\\par\r\n}\r\n'

INTRANSTBL = [chr(i) for i in range(0x0,0x09)+range(0x0b,0x0d)+range(0x7f,256)]
OUTTRANSTBL = [hex(ord(i)).replace('0x',"\\'") for i in INTRANSTBL]
INSYMS = ['\\','\r','\n','\t','{','}']
OUTSYMS = ['\\\\','','\\par\r\n','\\tab','\\{','\\}']
INSMILES = [
	':)',';)',':-))',';-P','8-)','):-D','}:o)','$-)',
	":-'",'):-(','8-(',":'(",":''()",'S:-o','(:-o','8-0',
	'8-[o]','):-p',':-(','):-$',':-D',':-E',':devil:',':vampire:',
	':-][',':-|','B-j',':~o','(_I_)',':heart:',':-*',':sleepy:',
	':cool:',':viva:',':ok:',':yo:',':suxx:',':think:',':figu:',':kulak:',':fuck:'
]
OUTSMILES = [
	'<###20###img010>','<###20###img011>','<###20###img012>','<###20###img013>',
	'<###20###img014>','<###20###img030>','<###20###img016>','<###20###img017>',
	'<###20###img018>','<###20###img028>','<###20###img020>','<###20###img021>',
	'<###20###img022>','<###20###img023>','<###20###img024>','<###20###img025>',
	'<###20###img026>','<###20###img027>','<###20###img019>','<###20###img029>',
	'<###20###img015>','<###20###img031>','<###20###img032>','<###20###img033>',
	'<###20###img034>','<###20###img035>','<###20###img036>','<###20###img037>',
	'<###20###img038>','<###20###img039>','<###20###img040>','<###20###img041>',
	'<###20###img000>','<###20###img001>','<###20###img002>','<###20###img003>',
	'<###20###img005>','<###20###img006>','<###20###img007>','<###20###img008>',
	'<###20###img009>'
]

INCHARS = tuple(INSYMS+INTRANSTBL+INSMILES)
OUTCHARS = tuple(OUTSYMS+OUTTRANSTBL+OUTSMILES)

IN_TRANSLIT_TBL = tuple(["'",chr(0xa8),chr(0xb8)] + [chr(i) for i in range(0xc0,256)])
_lat = [
	'a','b','v','g','d','e','zh','z','i','jj','k','l','m','n','o','p','r',
	's','t','u','f','kh','c','ch','sh','shh','"','y',"'",'eh','yu','ya'
]
OUT_TRANSLIT_TBL = tuple(['*','Jo','jo'] + [x[0].upper()+x[1:] for x in _lat] + _lat)

UPPER_ASCII = tuple([chr(i) for i in range(128,256)])
NULL_ASCII = tuple(['' for i in range(128,256)])

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

def is_valid_sms_number(number):
	if number_pattern.match(number):
		return True
	else:
		return False

def is_valid_sms_text(text):
	has_not_ascii = upper_ascii_pattern.search(text)
	if has_not_ascii and len(text)<=37:
		return True
	elif (not has_not_ascii) and len(text)<=137:
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

def translate(s, t1, t2, index=0):
	if index<len(t1):
		return translate(s.replace(t1[index],t2[index]), t1, t2, index+1)
	else:
		return s

def winrtf(s):
	return translate(s, INCHARS, OUTCHARS)

def translit(s):
	en = translate(s, IN_TRANSLIT_TBL, OUT_TRANSLIT_TBL)
	return translate(en, UPPER_ASCII, NULL_ASCII)

def win2str(s):
	t = invalid_chars.sub(' ',s)
	u_s = unicode(t, 'cp1251')
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

def decode_auth_string(enc_str):
	try:
		s = base64.decodestring(enc_str)
		num = struct.unpack('I', s[:4])[0]
		name, txt = '',''
		if num>1:
			try:
				nlen = struct.unpack('I', s[4:8])[0]
				name = s[8:8+nlen]
				tlen = struct.unpack('I', s[8+nlen:12+nlen])[0]
				txt = s[12+nlen:12+nlen+tlen]
				if not name.strip():
					name = ''
				if not txt.strip():
					txt = ''
			except:
				pass
		name = win2str(name)
		txt = win2str(txt)
	except:
		name, txt = '',''
	return (name,txt)

def encode_auth_string(name, text):
	name = str2win(name)
	text = str2win(text)
	num = struct.pack('I', 2)
	nlen = struct.pack('I', len(name))
	tlen = struct.pack('I', len(text))
	return base64.encodestring(num+nlen+name+tlen+text)

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

def socket_error(e):
	if len(e.args)>1:
		err_txt = e.args[1]
	else:
		err_txt = e.args[0]
	return err_txt

def gettime():
	T = {}
	if time.daylight:
		T['tz'] = time.tzname[1]
	else:
		T['tz'] = time.tzname[0]
	T['utc'] = time.strftime('%Y%m%dT%H:%M:%S', time.gmtime())
	T['display'] = time.asctime()
	return T

def uptime(T):
	t = int(T)
	days, s = (t/86400, t % 86400)
	hours, s = (s/3600, s % 3600)
	minutes, secs = (s/60, s % 60)
	return "%s days, %s hours %s minutes %s secs" % (days, hours, minutes, secs)

def xep_202_time():
	if time.daylight != 0:
		offset = time.altzone
	else:
		offset = time.timezone
	hours, reminder = divmod(abs(offset), 3600)
	mins, secs = divmod(reminder, 60)
	if offset >= 0:
		tzo = "%.2d:%.2d" % (hours, mins)
	else:
		tzo = "-%.2d:%.2d" % (hours, mins)
	utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
	return (tzo, utc)

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

def unpack_rtf(s):
	res = [s, ()]
	try:
		decoded = base64.decodestring(s)
		unzipped = zlib.decompress(decoded)
		body = cStringIO.StringIO(unzipped)
		number = struct.unpack('I', body.read(4))[0]
		text = body.read(struct.unpack('I', body.read(4))[0])
		color = struct.unpack('I',
			body.read(
				struct.unpack('I', body.read(4))[0]
			)
		)[0]
		R = color & 0xFF
		G = (color & 0xFF00) >> 8
		B = (color & 0xFF0000) >> 16
		res = [text, (R,G,B)]
	except:
		pass
	return res

def pack_rtf(s):
	enc = winrtf(s)
	io_s = cStringIO.StringIO()
	io_s.write(struct.pack('I', 2))
	text = RTF_H+enc+RTF_T
	io_s.write(struct.pack('I',len(text)))
	io_s.write(text)
	io_s.write(struct.pack('I', 4))
	io_s.write(struct.pack('I', 0x00ffffff))
	io_s.seek(0)
	gzipped = zlib.compress(io_s.read())
	return base64.encodestring(gzipped).replace('\n','')

def get_proxy(proxy_str):
	host, port = proxy_str.split('http://')[1].split(':')
	return (host, int(port))

def s_caps_ver():
	s = 'gateway/mrim<'
	for feature in server_features:
		s += feature + '<'
	return base64.encodestring(sha.new(s).digest()).strip()

def c_caps_ver():
	s = 'client/pc<'
	for feature in client_features:
		s += feature + '<'
	return base64.encodestring(sha.new(s).digest()).strip()
