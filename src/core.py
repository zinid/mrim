from mmptypes import *
import protocol
import utils

import socket
import async
import struct
import traceback
import time
import re
import signal
import http
import errno
import logging
import mrim
import base64
import resolver

conf = mrim.conf

packet_types = [locals()[key] for key in locals().keys() if key.startswith('MRIM_CS')]

num_type = {}
for k,v in [(key, locals()[key]) for key in locals().keys() if key.startswith('MRIM_CS')]:
	num_type[v] = k
del k,v

class Client(async.dispatcher_with_send):

	def __init__(self, login, password,logger,agent='Python MMP Library 0.1',
			status=0,server='mrim.mail.ru',port=2042,proxy=None):

		# some initial values
		self._login = login
		self.__password = password
		self.__agent = agent
		self.__status = status
		self._got_roster = False
		self.proxy = proxy
		self.state = 'init'
		self._mbox_url = "http://win.mail.ru/cgi-bin/auth?Login=%s&agent=" % self._login
		self._composers = {}
		self._compose_to = {}
		self.contact_list = protocol.ContactList()
		self.ack_buf = {}
		self.pinger_timer = 0
		self.connect_timer = 0
		self.ping_period = 30
		self.mrim_host = resolver.gethostbyname(server)
		self.mrim_port = port
		async.dispatcher_with_send.__init__(self)
		self.buf_limit = 1024*100
		self.logger = logger
		self.myname = ''
		self.wait_for_header = True
		self.buflen = 44
		self.recbuf = ''
		self.balancer_buf = ''

	def log(self, level, message):
		self.logger.log(level, '[%s] %s' % (self._login, message))

	def dump_packet(self, p):
		dump = "--- begin ---\n"
		dump += "Header: %s\nBody: %s\n" % (p.getHeader().__repr__(), p.getBody().__repr__())
		dump += "--- end ---"
		return dump

	def handle_connect(self):

		if self.state != 'init':
			p = protocol.MMPPacket(typ=MRIM_CS_HELLO)
			self.log(logging.DEBUG, "Connection OK, sending HELLO")
			self._send_packet(p)

	def failure_exit(self, err):

		self.mmp_handler_connection_close()

	def handle_expt(self):

		self.log(logging.INFO, "Connection reset by peer")
		self.mmp_handler_connection_close()

	def handle_read(self):

		if self.state == 'init':
			self.balancer_buf += self.recv(8192)
		else:
			buf = self.recv(self.buflen)
			size = len(buf)
			self.recbuf += buf
			if 0<size<self.buflen:
				self.buflen -= size
			elif size and self.wait_for_header:
				dlen = struct.unpack('I',self.recbuf[16:20])[0]
				if dlen:
					self.buflen = dlen
					self.wait_for_header = False
				else:
					data = self.recbuf
					self.recbuf = ''
					self.buflen = 44
					self._decode_packet(data)
			elif size:
				self.wait_for_header = True
				self.buflen = 44
				data = self.recbuf
				self.recbuf = ''
				self._decode_packet(data)

	def _decode_packet(self, data):

		header, body = data[:44], data[44:]
		typ = struct.unpack('I', header[12:16])[0]
		if typ not in packet_types:
			ignore_msg = "!!! Ignore unknown MMP packet with type %s !!!\n"  % hex(int(typ))
			ignore_msg += "--- cut ---\n"
			ignore_msg += "Parsed header: %s\n" % protocol.MMPHeader(header=header).__repr__()
			ignore_msg += "Header dump: %s\n" % header.__repr__()
			ignore_msg += "Body dump: %s\n" % body.__repr__()
			ignore_msg += "--- cut ---\n"
			self.log(logging.ERROR, ignore_msg)
			return
		log_got_packet = 'Got %s packet (type=%s):\n' % (num_type[typ], hex(int(typ)))
		mmp_packet = protocol.MMPPacket(packet=header+body)
		self.log(logging.DEBUG, log_got_packet+self.dump_packet(mmp_packet))
		self._process_packet(mmp_packet)

	def handle_close(self):

		if self.state == 'init':
			host, port = self.balancer_buf.strip().split(':')
			port_int = int(port)
			self.close()
			self.start(host, port_int)
		else:
			self.failure_exit("Connection reset by peer")

	def handle_timer(self, tref, msg):
		if msg=='ping':
			self.ping()
		elif msg=='timeout':
			self.failure_exit("Connection timeout")
		elif len(msg)==2:
			typ, val = msg
			if typ=='compose_stop':
				del self._composers[val]
				self.mmp_handler_composing_stop(val)
			elif typ=='compose_send':
				self.cancel_composing(val)
				self.mmp_send_typing_notify(val)
		else:
			self.log(logging.INFO, "Got unexpected timer message: %s" % msg)

	def run(self):

		ip_port = (self.mrim_host,self.mrim_port)
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.log(logging.INFO, "Obtaining address from balancer at %s:%s" % ip_port)
		self.async_connect(ip_port)
		self.connect_timer = self.set_timer(30, "timeout")

	def ping(self):

		self._send_packet(protocol.MMPPacket(typ=MRIM_CS_PING))
		self.pinger_timer = self.set_timer(self.ping_period, "ping")

	def _process_packet(self, mmp_packet):

		ptype = mmp_packet.getType()
		msg_id = mmp_packet.getId()
		_ack = self._get_buffer_acks(msg_id)

		if ptype == MRIM_CS_HELLO_ACK:
			self.ping_period = mmp_packet.getBodyAttr('ping_period')
			self.log(logging.INFO, "Successfully connected")
			self.log(logging.DEBUG, "Server version is %s" % mmp_packet.getVersion())
			self.log(logging.DEBUG, "Server has set ping period to %d seconds" % self.ping_period)
			self._got_hello_ack()

		elif ptype == MRIM_CS_LOGIN_ACK:
			self.cancel_timer(self.connect_timer)
			self.ping()
			self.state = 'session_established'
			self.log(logging.INFO, "Authorization successfull: logged in")
			self.mmp_handler_server_authorized()

		elif ptype == MRIM_CS_LOGIN_REJ:
			res = utils.win2str(mmp_packet.getBodyAttr('reason'))
			self.log(logging.INFO, "Authorization failure: %s" % res)
			self.mmp_handler_server_not_authorized(res)

		elif ptype == MRIM_CS_MESSAGE_ACK:
			mess = protocol.Message(payload=mmp_packet)
			if not mess.hasFlag(MESSAGE_FLAG_NORECV):
				msg_body_id = mess.getBodyAttr('msg_id')
				frm = mess.getBodyAttr('from')
				d = {
					'msg_id':msg_body_id,
					'from':frm
				}
				mess_reply = protocol.MMPPacket(typ=MRIM_CS_MESSAGE_RECV,dict=d)
				self._send_packet(mess_reply)
			self._parse_message(mess)

		elif ptype == MRIM_CS_MESSAGE_STATUS:
			status = mmp_packet.getBodyAttr('status')
			_ack['ackf'](status, **_ack['acka'])
			self.mmp_handler_got_message_status(status,msg_id)

		elif ptype == MRIM_CS_CONTACT_LIST2:
			self.contact_list = protocol.ContactList(mmp_packet)
			self._got_roster = True
			self.mmp_handler_got_contact_list2()

		elif ptype == MRIM_CS_MAILBOX_STATUS:
			n = mmp_packet.getBodyAttr('count')
			sender = utils.win2str(mmp_packet.getBodyAttr('sender'))
			subject = utils.win2str(mmp_packet.getBodyAttr('subject'))
			unix_time = mmp_packet.getBodyAttr('unix_time')
			email_key = mmp_packet.getBodyAttr('key')
			self._got_new_mail(n,sender,subject,unix_time,email_key)
		
		elif ptype == MRIM_CS_MAILBOX_STATUS_OLD:
			status = mmp_packet.getBodyAttr('status')
			self.mmp_handler_got_mailbox_status_old(status)

		elif ptype == MRIM_CS_USER_INFO:
			try:
				total = mmp_packet.getBodyAttr('total')
				unread = mmp_packet.getBodyAttr('unread')
			except KeyError:
				try:
					nickname = mmp_packet.getBodyAttr('nickname')
					self.myname = utils.win2str(nickname)
				except KeyError:
					self.myname = self._login
				self.mmp_get_mbox_key()
				return
			self._got_mbox_status(total, unread)

		elif ptype == MRIM_CS_USER_STATUS:
			if self._got_roster:
				status = mmp_packet.getBodyAttr('status')
				e_mail = mmp_packet.getBodyAttr('user')
				try:
					self.contact_list.setUserStatus(e_mail, status)
				except KeyError:
					self.log(logging.ERROR,
						"Got status from unknown user. There is no %s in contact list: %s" 
							% (e_mail, self.contact_list.getEmails()))
					return
				self.mmp_handler_got_user_status(e_mail, status)

		elif ptype == MRIM_CS_LOGOUT:
			log_reason = "Server has forced logout with reason: "
			reason = mmp_packet.getBodyAttr('reason')
			if reason == LOGOUT_NO_RELOGIN_FLAG:
				log_reason += "dual login"
				self.log(logging.INFO, log_reason)
				self.mmp_handler_dual_login()
			else:
				log_reason += "unknown (%s)" % hex(reason)
				self.log(logging.INFO, log_reason)

		elif ptype == MRIM_CS_GET_MPOP_SESSION_ACK:
			if mmp_packet.getBodyAttr('status'):
				hash_key = mmp_packet.getBodyAttr('session')
				_ack['ackf'](self._mbox_url+hash_key, **_ack['acka'])

		elif ptype == MRIM_CS_CONNECTION_PARAMS:
			self.ping_period = mmp_packet.getBodyAttr('ping_period')

		elif ptype == MRIM_CS_OFFLINE_MESSAGE_ACK:
			uid = mmp_packet.getBodyAttr('uidl')
			d = {'uidl':uid}
			p = protocol.MMPPacket(typ=MRIM_CS_DELETE_OFFLINE_MESSAGE,dict=d)
			self._send_packet(p)
			offmsg = protocol.OfflineMessage(mmp_packet.getBodyAttr('message'))
			msg = offmsg.buildMessage()
			offtime = offmsg.getUTCTime()
			self._parse_message(msg, offtime)

		elif ptype == MRIM_CS_ANKETA_INFO:
			anketa = protocol.Anketa(mmp_packet.__str__())
			if _ack['add']:
				status = anketa.getStatus()
				if status == MRIM_ANKETA_INFO_STATUS_OK:
					card = anketa.getVCards()[0]
					e_mail = card['Username']+'@'+card['Domain']
					nickname = card['Nickname'].strip() or e_mail
					#mrim_status = int(card['mrim_status'])
					self.mmp_add_contact(e_mail,nick=nickname,status=0,
						ackf=_ack['ackf'],acka=_ack['acka'])
				else:
					if status == MRIM_ANKETA_INFO_STATUS_NOUSER:
						s = CONTACT_OPER_NO_SUCH_USER
					elif status == MRIM_ANKETA_INFO_STATUS_DBERR:
						s = CONTACT_OPER_ERROR
					else:
						s =  CONTACT_OPER_INTERR
					_ack['ackf'](s, **_ack['acka'])
			else:
				_ack['ackf'](anketa, **_ack['acka'])

		elif ptype == MRIM_CS_AUTHORIZE_ACK:
			user = mmp_packet.getBodyAttr('user')
			if self._got_roster:
				self.contact_list.setAuthFlag(user,0)
			self.mmp_handler_got_subscribed(user)

		elif ptype == MRIM_CS_ADD_CONTACT_ACK:
			status = mmp_packet.getBodyAttr('status')
			if status == CONTACT_OPER_SUCCESS:
				self.contact_list.users[_ack['mail']] = {
					'flags':0,
					'group':0,
					'nick':_ack['nick'],
					'server_flags':1,
					'status':_ack['status'],
					'phones':''
				}
				self.contact_list.cids[_ack['mail']] = mmp_packet.getBodyAttr('contact_id')
			_ack['ackf'](status, **_ack['acka'])

		elif ptype == MRIM_CS_MODIFY_CONTACT_ACK:
			status = mmp_packet.getBodyAttr('status')
			if status == CONTACT_OPER_SUCCESS:
				try:
					self.contact_list.delUser(_ack['mail'])
				except KeyError:
					pass
			_ack['ackf'](status, **_ack['acka'])

	def _send_packet(self, p):

		typ = p.getType()
		if not ((self.state=='session_established') or (typ in [MRIM_CS_HELLO, MRIM_CS_LOGIN2])):
			return p.getId()
		if typ!= MRIM_CS_PING:
			self.log(logging.DEBUG, "Send %s packet (type=%s):\n%s" % 
				(num_type[typ],hex(int(typ)), self.dump_packet(p)))
		else:
			self.log(logging.DEBUG, "Ping")
		self.async_send(p.__str__())
		return p.getId()

	def _got_hello_ack(self):

		self.log(logging.INFO, "Sending credentials")
		d = {
			'login':utils.str2win(self._login),
			'password':utils.str2win(self.__password),
			'status':self.__status,
			'user_agent':utils.str2win(self.__agent)
		}
		p = protocol.MMPPacket(typ=MRIM_CS_LOGIN2,dict=d)
		self._send_packet(p)

	def _parse_contacts(self, mess):

		cont_list = mess.getBodyPayload().split(';')
		cont_list.reverse()
		d = []
		while 1:
			try:
				d.append((cont_list.pop(),cont_list.pop()))
			except IndexError:
				return d

	def _parse_message(self, mess, offtime=()):

		frm = mess.getFrom()

		if mess.hasFlag(MESSAGE_FLAG_CONTACT):
			roster = self._parse_contacts(mess)
			self.mmp_handler_got_contact_list(frm, roster, offtime)
		elif mess.hasFlag(MESSAGE_FLAG_NOTIFY) and not offtime:
			self._parse_typing_notify(mess.getFrom())
		elif mess.hasFlag(MESSAGE_FLAG_AUTHORIZE):
			text = mess.getBodyPayload()
			auth_name, auth_text = utils.decode_auth_string(text)
			self.mmp_handler_got_subscribe(frm, auth_name, auth_text, offtime)
		elif mess.hasFlag(MESSAGE_FLAG_SMS):
			number = frm.replace('+','')
			text = mess.getBodyPayload()
			users = []
			for user in self.contact_list.getEmails():
				if number in self.contact_list.getPhones(user):
					users.append(user)
			self.mmp_handler_got_sms(frm, users, text, offtime)
		else:
			self.mmp_handler_got_message(mess, offtime)

	def _parse_typing_notify(self, frm):

		if self._composers.has_key(frm):
			tref = self._composers[frm]
			self.cancel_timer(tref)
		self._composers[frm] = self.set_timer(10, ("compose_stop", frm))
		self.mmp_handler_composing_start(frm)

	def _got_mbox_status(self, total, unread):

		self.mmp_get_mbox_key(ackf=self.mmp_handler_got_mbox_status,
			acka={'total':total,'unread':unread})

	def _got_new_mail(self, number, sender, subject, unix_time, email_key):
		d = {
			'number':number,
			'sender':sender,
			'subject':subject,
			'unix_time':unix_time
		}
		self.mmp_get_mbox_key(ackf=self.mmp_handler_got_new_mail,acka=d)

	def process_http_response(self, response):
		avatara = ''
		album = ''
		content_type = None
		result, [ackf, acka] = response
		if result[0]=='ok':
			msg = result[1]
			content_type = msg.headers['Content-Type']
			if msg.code == 200:
				avatara = msg.body
				album = msg.album
			elif msg.code != 404:
				http_err = "Can't connect to http://avt.foto.mail.ru (%s)" % msg.reason
				self.log(logging.ERROR, http_err)
		else:
			http_err = "Can't connect to http://avt.foto.mail.ru (%s)" % result[1]
			self.log(logging.ERROR, http_err)
		ackf(avatara, content_type, album, **acka)

	def _null_callback(*x, **y):
		pass

	def _get_buffer_acks(self, msg_id):
		d = {'ackf':self._null_callback, 'acka':{}}
		try:
			d = self.ack_buf.pop(msg_id)
		except KeyError:
			pass
		return d

	def cancel_composing(self, to):

		if self._compose_to.has_key(to):
			tref = self._compose_to[to]
			del self._compose_to[to]
			self.cancel_timer(tref)

	def mmp_get_mbox_key(self, ackf=None, acka={}):

		p = protocol.MMPPacket(typ=MRIM_CS_GET_MPOP_SESSION)
		ret_id = self._send_packet(p)
		if ackf:
			self.ack_buf[ret_id] = {'ackf':ackf, 'acka':acka}

	def mmp_send_typing_notify(self, to):

		self.cancel_composing(to)
		self._compose_to[to] = self.set_timer(5, ('compose_send', to))
		p = protocol.Message(to,flags=[MESSAGE_FLAG_NOTIFY])
		self._send_packet(p)

	def mmp_send_message(self, to, body, ackf=None, acka={}):

		enc_body = utils.str2win(body)
		msg = protocol.Message(to,enc_body,flags=[MESSAGE_FLAG_RTF])
		ret_id = self._send_packet(msg)
		if ackf:
			self.ack_buf[ret_id] = {'ackf':ackf,'acka':acka}

	def mmp_send_sms(self, to, body, ackf=None, acka={}):

		d = {'UNKNOWN':0, 'number':to, 'text':body}
		p = protocol.MMPPacket(typ=MRIM_CS_SMS,dict=d)
		ret_id = self._send_packet(p)
		if ackf:
			self.ack_buf[ret_id] = {'ackf':ackf,'acka':acka}

	def mmp_send_subscribe(self, to, body=' '):

		if (to in self.contact_list.getEmails()) and (not self.contact_list.getAuthFlag(to)):
			return
		enc_body = utils.str2win(body)
		msg = protocol.Message(to,enc_body,flags=[MESSAGE_FLAG_AUTHORIZE])
		self._send_packet(msg)

	def mmp_send_subscribed(self, to):

		p = protocol.MMPPacket(typ=MRIM_CS_AUTHORIZE,dict={'user':to})
		self._send_packet(p)

	def mmp_send_wp_request(self, fields, ackf=None, acka={}, add=False):

		p = protocol.MMPPacket(typ=MRIM_CS_WP_REQUEST,dict=fields)
		ret_id = self._send_packet(p)
		if ackf:
			self.ack_buf[ret_id] = {'add':add,'ackf':ackf,'acka':acka}

	def mmp_send_avatar_request(self, mail, ackf, acka={}):

		http.GetUrl(self, mail, [ackf, acka], self.proxy).run()

	def mmp_add_contact(self,e_mail,nick='',status=0,ackf=None,acka={}):

		if (e_mail in self.contact_list.getEmails()) and not \
			   (self.contact_list.isIgnoredUser(e_mail) or \
			    self.contact_list.isRemovedUser(e_mail)):
			return
		if not nick:
			nick = e_mail
		enc_nick = utils.str2win(nick)
		d = {
			'flags': 0,
			'group_id': 0,
			'email': e_mail,
			'name': enc_nick,
			'phones': '',
			'text':utils.encode_auth_string(self.myname,' ')
		}
		p = protocol.MMPPacket(typ=MRIM_CS_ADD_CONTACT,dict=d)
		ret_id = self._send_packet(p)
		self.ack_buf[ret_id] = {
			'mail':e_mail,
			'nick':nick,
			'status':status
		}
		if ackf:
			self.ack_buf[ret_id].update({'ackf':ackf,'acka':acka})

	def mmp_add_contact_with_search(self,e_mail,ackf=None,acka={}):

		if (e_mail in self.contact_list.getEmails()) and not \
			   (self.contact_list.isIgnoredUser(e_mail) or \
			    self.contact_list.isRemovedUser(e_mail)):
			return
		try:
			user,domain = e_mail.split('@')
		except:
			if ackf:
				ackf(CONTACT_OPER_NO_SUCH_USER,**acka)
				return
		d = {
			MRIM_CS_WP_REQUEST_PARAM_USER:user,
			MRIM_CS_WP_REQUEST_PARAM_DOMAIN:domain
		}
		self.mmp_send_wp_request(d,ackf,acka,add=True)

	def mmp_del_contact(self, e_mail, ackf=None, acka={}):

		if e_mail in self.contact_list.getEmails():
			contact_id = self.contact_list.getUserId(e_mail)
			name = self.contact_list.getUserNick(e_mail)
			phones = self.contact_list.getPhones(e_mail)
			flags = self.contact_list.getUserFlags(e_mail) | 0x1
			d = {
				'id':contact_id,
				'flags': flags,
				'group_id':0,
				'contact':e_mail,
				'name':utils.str2win(name),
				'phones':','.join(phones)
			}
			p = protocol.MMPPacket(typ=MRIM_CS_MODIFY_CONTACT,dict=d)
			ret_id = self._send_packet(p)
			self.ack_buf[ret_id] = {'mail':e_mail}
			if ackf:
				self.ack_buf[ret_id].update({'ackf':ackf,'acka':acka})

	def mmp_modify_sms(self, e_mail, numbers, ackf=None, acka={}):

		if e_mail in self.contact_list.getEmails():
			contact_id = self.contact_list.getUserId(e_mail)
			name = self.contact_list.getUserNick(e_mail)
			phones = ','.join(numbers)
			group_id = self.contact_list.getUserGroup(e_mail)
			flags = self.contact_list.getUserFlags(e_mail)
			d = {
				'id':contact_id,
				'flags': flags,
				'group_id':group_id,
				'contact':e_mail,
				'name':utils.str2win(name),
				'phones':phones
			}
			p = protocol.MMPPacket(typ=MRIM_CS_MODIFY_CONTACT,dict=d)
			ret_id = self._send_packet(p)
			if ackf:
				self.ack_buf[ret_id].update({'ackf':ackf,'acka':acka})

	def mmp_connection_close(self):

		try:
			self.close()
		except:
			pass
		self.log(logging.INFO, "Connection closed by ourselves")

	def mmp_change_status(self, status):

		p = protocol.MMPPacket(typ=MRIM_CS_CHANGE_STATUS,dict={'status':status})
		self._send_packet(p)

	def mmp_handler_server_authorized(self):
		pass

	def mmp_handler_server_not_authorized(self, reason):
		self.close()

	def mmp_handler_composing_start(self, frm):
		pass

	def mmp_handler_composing_stop(self, frm):
		pass

	def mmp_handler_got_message(self, mess, time):
		pass

	def mmp_handler_got_new_mail(self, url, number, sender, subject, unix_time):
		pass

	def mmp_handler_got_user_status(self, e_mail, status):
		pass

	def mmp_handler_dual_login(self):
		pass

	def mmp_handler_got_contact_list(self, frm, roster, offtime):
		pass

	def mmp_handler_got_contact_list2(self):
		pass

	def mmp_handler_got_message_status(self, status, msg_id):
		pass

	def mmp_handler_got_user_status(self, e_mail, status):
		pass

	def mmp_handler_connection_close(self):
		pass

	def mmp_handler_got_mbox_status(self, url, total, unread):
		pass

	def mmp_handler_got_mailbox_status_old(self, status):
		pass

	def mmp_handler_got_anketa(self, anketa, msg_id):
		pass

	def mmp_handler_got_subscribed(self, frm, name, text, time):
		pass

	def mmp_handler_got_subscribe(self, frm, text):
		pass

	def mmp_handler_got_add_contact_ack(self, status, contact_id):
		pass

	def mmp_handler_got_modify_contact_ack(self, status):
		pass

	def mmp_handler_got_sms(self, number, users, text, offtime):
		pass
