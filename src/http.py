# -*- coding: utf-8 -*-

import async
import socket
import traceback
import sys
import utils
import email
import resolver

TIMEOUT = 30 # seconds
BUFLEN = 8192
AVT_HOST = "avt.foto.mail.ru"

def encode_mail(mail):
	user, domain = mail.split("@")
	return (domain.split('.')[0], user)

class GetUrl(async.dispatcher_with_send):
	def __init__(self, parent, mail, callbacks=None, proxy=None):
		self.buf = ""
		self.mail = mail
		self.parent = parent
		self.callbacks = callbacks
		async.dispatcher_with_send.__init__(self)
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.set_timer(TIMEOUT, "stop")
		self.domain, self.user = encode_mail(mail)
		if proxy:
			self.url = 'http://%s/%s/%s/_mrimavatar' % (AVT_HOST, self.domain, self.user)
			host, port = proxy
			self.server = (resolver.gethostbyname(host), port)
		else:
			self.url = '/%s/%s/_mrimavatar' % (self.domain, self.user)
			self.server = (resolver.gethostbyname(AVT_HOST), 80)

	#def __del__(self):
	#	print "deleting http.GetUrl @", self

	def run(self):
		self.async_connect(self.server)

	def handle_expt(self):
		self.terminate(("error", "unexpected socket error"))

	def handle_error(self):
		t, err, tb = sys.exc_info()
		if t == socket.error:
			reason = utils.socket_error(err)
		else:
			traceback.print_exc()
			reason = "unknown error"
		self.terminate(("error", reason))

	def handle_connect(self):
		self.async_send("GET %s HTTP/1.0\r\n\r\n" % self.url)

	def handle_timer(self, tref, msg):
		if msg=="stop":
			self.terminate(("error", "no response within %s seconds" % TIMEOUT))

	def handle_read(self):
		self.buf += self.recv(BUFLEN)

	def handle_close(self):
		try:
			msg = Response(self.buf)
			msg.encode()
			msg.album = 'http://%s/%s/%s/' % (AVT_HOST, self.domain, self.user)
			result = ("ok", msg)
		except:
			result = ("error", "invalid HTTP response: '%s'" % self.buf)
		self.terminate(result)

	def terminate(self, result):
		self.close()
		try:
			self.parent.process_http_response((result, self.callbacks))
		except:
			pass

class Response:
	def __init__(self, data):
		self.data = data
		self.headers = None

	def encode(self):
		header, body = self.data.split('\r\n\r\n', 1)
		headers = header.strip().split('\r\n', 1)
		self.body = body
		self.encode_headers(headers)

	def encode_headers(self, hdrs):
		start = hdrs[0].strip()
		version, code, reason = start.split(' ', 2)
		self.version = version
		self.code = int(code)
		self.reason = reason
		self.headers = email.message_from_string(hdrs[1])
