from mmptypes import *
import protocol
import utils

import socket
import asyncore
import struct
import traceback
import threading
import time
import re
import signal
import urllib2
import errno
import logging
import config

conf = config.Config()

packet_types = [locals()[key] for key in locals().keys() if key.startswith('MRIM_CS')]

num_type = {}
for k,v in [(key, locals()[key]) for key in locals().keys() if key.startswith('MRIM_CS')]:
	num_type[v] = k
del k,v

class Client(asyncore.dispatcher_with_send):

	def __init__(self, login, password,logger,agent='Python MMP Library 0.1',
			status=0,server='mrim.mail.ru',port=2042):

		# some initial values
		self.__server = server
		self.__port = port
		self.__login = login
		self.__password = password
		self.__agent = agent
		self.__status = status
		self._got_roster = False
		self._is_authorized = False
		self._is_connected = False
		self._mbox_url = "http://win.mail.ru/cgi-bin/auth?Login=%s&agent=" % self.__login
		self.__composing_container = []
		self.__continue_body = False
		self.__continue_header = False
		self.contact_list = protocol.ContactList()
		self._traff_in = 0
		self._traff_out = 0
		self.ack_buf = {}
		self._pings = 0
		self.ping_period = 30
		self.wp_req_pool = []
		self.last_wp_req_time = time.time()
		self.last_ping_time = time.time()
		asyncore.dispatcher_with_send.__init__(self)
		self.logger = logger

	def log(self, level, message):
		self.logger.log(level, '[%s] %s' % (self.__login, message))

	def dump_packet(self, p):
		dump = "--- begin ---\n"
		dump += "Header: %s\nBody: %s\n" % (p.getHeader().__repr__(), p.getBody().__repr__())
		dump += "--- end ---"
		return dump

	def recv(self, buffer_size):

		try:
			data = self.socket.recv(buffer_size)
			if not data:
				self.handle_close()
				return ''
			else:
				return data
		except socket.error, why:
			if why[0] in [errno.ECONNRESET, errno.ENOTCONN, errno.ESHUTDOWN]:
				self.handle_close()
				return ''
			elif why[0] in [errno.EWOULDBLOCK, errno.EAGAIN]:
				return ''
			else:
				raise socket.error, why

	def handle_connect(self):

		self._is_connected = True
		p = protocol.MMPPacket(typ=MRIM_CS_HELLO)
		self.log(logging.INFO, "Connection OK, sending HELLO")
		self._send_packet(p)

	def handle_expt(self):

		self.log(logging.INFO, "Connection reset by peer")
		self.mmp_handler_connection_close()

	def handle_read(self):

		if self.__continue_body:
			body_part = self.recv(self._blen)
			self._traff_in += len(body_part)
			self._body += body_part
			if len(body_part)<self._blen:
				self._blen -= len(body_part)
				return
			else:
				self.__continue_body = False
				self._parse_raw_packet(self._header,self._body)
		
		elif self.__continue_header:
			header_part = self.recv(self._hlen)
			self._traff_in += len(header_part)
			self._header += header_part
			if len(header_part)<self._hlen:
				self._hlen -= len(header_part)
				return
			else:
				self.__continue_header = False
				self.__parse_data()
		else:
			self._header = self.recv(44)
			self._traff_in += len(self._header)
			if len(self._header) == 44 and struct.unpack('I',self._header[:4])[0] == CS_MAGIC:
				self.__parse_data()
			elif 0 < len(self._header) < 44:
				self._hlen = len(self._header)
				self.__continue_header = True
				self._hlen = 44 - self._hlen
				return
			elif len(self._header) >= 44:
				self.log(logging.WARNING, "Got junk or unexpected continuation of MMP packet")
				return

	def __parse_data(self):
		self._blen = struct.unpack('I',self._header[16:20])[0]
		if self._blen: 
			self._body = self.recv(self._blen)
			self._traff_in += len(self._body)
		if self._body:
			if len(self._body)<self._blen:
				self.__continue_body = True
				self._blen -= len(self._body)
				return
			else:
				self._parse_raw_packet(self._header,self._body)
		else:
			self._parse_raw_packet(self._header,self._body)

	def _parse_raw_packet(self,header,body):

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
		try:
			mmp_packet = protocol.MMPPacket(packet=header+body)
		except:
			parse_error = "Can't parse packet - protocol parsing error!\n"
			parse_error += "Packet dump: %s\n" % (header+body).__repr__()
			self.log(logging.ERROR, log_got_packet+parse_error)
			traceback.print_exc()
			return
		self.log(logging.DEBUG, log_got_packet+self.dump_packet(mmp_packet))
		self._workup_packet(mmp_packet)

	def handle_close(self):

		self._is_connected = False
		self.log(logging.INFO, "Connection reset by peer")
		self.close()

	def run(self,server=None, port=None):

		if server and port:
			ip_port = (server,port)
		else:
			ip_port = utils.get_server(self.__server,self.__port)
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.log(logging.INFO, "Connecting to %s:%s..." % ip_port)
		self.connect(ip_port)

	def ping(self):

		self._pings += 1
		self._send_packet(protocol.MMPPacket(typ=MRIM_CS_PING))

	def _workup_packet(self, mmp_packet):

		ptype = mmp_packet.getType()
		msg_id = mmp_packet.getId()
		_ack = self._get_buffer_acks(msg_id)

		if ptype == MRIM_CS_HELLO_ACK:
			self.ping_period = mmp_packet.getBodyAttr('ping_period')
			self.log(logging.INFO, "Successfully connected")
			self.log(logging.INFO, "Server version is %s" % mmp_packet.getVersion())
			self.log(logging.INFO, "Server has set ping period to %d seconds" % self.ping_period)
			self._got_hello_ack()

		elif ptype == MRIM_CS_LOGIN_ACK:
			self.ping()
			self._is_authorized = True
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
			utils.start_daemon(self._got_new_mail, (n,sender,subject,unix_time,email_key))
		
		elif ptype == MRIM_CS_MAILBOX_STATUS_OLD:
			status = mmp_packet.getBodyAttr('status')
			self.mmp_handler_got_mailbox_status_old(status)

		elif ptype == MRIM_CS_USER_INFO:
			total = mmp_packet.getBodyAttr('total')
			unread = mmp_packet.getBodyAttr('unread')
			nickname = mmp_packet.getBodyAttr('nickname')
			utils.start_daemon(self._got_mbox_status, (total, unread))

		elif ptype == MRIM_CS_USER_STATUS:
			if self._got_roster:
				status = mmp_packet.getBodyAttr('status')
				e_mail = mmp_packet.getBodyAttr('user')
				self.contact_list.setUserStatus(e_mail, status)
				self.mmp_handler_got_user_status(e_mail, status)

		elif ptype == MRIM_CS_LOGOUT:
			log_reason = "Server force logout with reason: "
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
					'status':_ack['status']
				}
				self.contact_list.cids[_ack['mail']] = mmp_packet.getBodyAttr('contact_id')
			_ack['ackf'](status, **_ack['acka'])

		elif ptype == MRIM_CS_MODIFY_CONTACT_ACK:
			status = mmp_packet.getBodyAttr('status')
			if status == CONTACT_OPER_SUCCESS:
				self.contact_list.delUser(_ack['mail'])
			_ack['ackf'](status, **_ack['acka'])

	def _send_packet(self, p):

		typ = p.getType()
		if not (self._is_authorized or (typ in [MRIM_CS_HELLO, MRIM_CS_LOGIN2])):
			return p.getId()
		if typ!= MRIM_CS_PING:
			self.log(logging.DEBUG, "Send %s packet (type=%s):\n%s" % 
				(num_type[typ],hex(int(typ)), self.dump_packet(p)))
		else:
			self.log(logging.DEBUG, "Ping")
		self.send(p.__str__())
		self.last_ping_time = time.time()
		self._traff_out += len(p.__str__())
		return p.getId()

	def _typing_notifier(self, user):

		c = 10
		while c>0:
			if user not in self.__composing_container:
				return
			else:
				c -= 0.1
				time.sleep(0.1)
		try:
			self.__composing_container.remove(user)
		except ValueError:
			return
		self.mmp_handler_composing_stop(user)

	def _got_hello_ack(self):

		self.log(logging.INFO, "Sending credentials")
		d = {
			'login':utils.str2win(self.__login),
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
			self.mmp_handler_got_subscribe(frm, text, offtime)
		else:
			try:
				self.__composing_container.remove(mess.getFrom())
			except ValueError:
				pass
			self.mmp_handler_got_message(mess, offtime)

	def _parse_typing_notify(self, frm):

		try:
			self.__composing_container.remove(frm)
		except ValueError:
			pass
		time.sleep(0.2)
		self.mmp_handler_composing_start(frm)
		self.__composing_container.append(frm)
		utils.start_daemon(self._typing_notifier, (frm,))

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

	def _get_avatar(self, mail, ackf, acka):
		avatara = ''
		album = ''
		content_type = None
		try:
			user, domain = mail.split('@')
			url = 'http://avt.foto.mail.ru/%s/%s/_mrimavatar' % (domain.split('.')[0], user)
			album = 'http://avt.foto.mail.ru/%s/%s/' % (domain.split('.')[0], user)
			req = urllib2.Request(url)
			u = urllib2.urlopen(req)
			content_type = u.headers['Content-Type']
			buf = u.read()
			self._traff_in += len(buf)
			avatara = buf
		except urllib2.HTTPError, e:
			http_err = "Can't connect to http://avt.foto.mail.ru (%s)" % e
			self.log(logging.ERROR, http_err)
		except urllib2.URLError, e:
			if hasattr(e.reason, 'args') and len(e.reason.args)==2:
				http_err = "Can't connect to http://avt.foto.mail.ru (%s)" % e.reason.args[1]
			else:
				http_err = "Can't connect to http://avt.foto.mail.ru (%s)" % e.reason
			self.log(logging.ERROR, http_err)
		except socket.error, e:
			if len(e.args)>1:
				err_txt = e.args[1]
			else:
				err_txt = e.args[0]
			http_err = "Can't connect to http://avt.foto.mail.ru (%s)" % err_txt
			self.log(logging.ERROR, http_err)
		except:
			traceback.print_exc()
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

	def _send_ws_req(self):

		interval = 2
		while self.wp_req_pool:
			T = time.time() - self.last_wp_req_time
			if T >= interval:
				try:
					fields, ackf, acka, add = self.wp_req_pool.pop(0)
				except IndexError:
					break
				msg = protocol.MMPPacket(typ=MRIM_CS_WP_REQUEST,dict=fields)
				ret_id = msg.getId()
				if ackf:
					self.ack_buf[ret_id] = {'add':add,'ackf':ackf,'acka':acka}
				self._send_packet(msg)
				self.last_wp_req_time = time.time()
			else:
				time.sleep(interval-T)

	def mmp_get_mbox_key(self, ackf=None, acka={}):

		p = protocol.MMPPacket(typ=MRIM_CS_GET_MPOP_SESSION)
		ret_id = self._send_packet(p)
		if ackf:
			self.ack_buf[ret_id] = {'ackf':ackf, 'acka':acka}

	def mmp_send_typing_notify(self, to):

		p = protocol.Message(to,flags=[MESSAGE_FLAG_NOTIFY])
		self._send_packet(p)

	def mmp_send_message(self, to, body, ackf=None, acka={}):

		enc_body = utils.str2win(body)
		msg = protocol.Message(to,enc_body)
		ret_id = self._send_packet(msg)
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

		self.wp_req_pool.append([fields,ackf,acka,add])
		if len(self.wp_req_pool) == 1:
			utils.start_daemon(self._send_ws_req, (), 'anketa')

	def mmp_send_avatar_request(self, mail, ackf, acka={}):

		utils.start_daemon(self._get_avatar, (mail, ackf, acka))

	def mmp_add_contact(self,e_mail,nick='',status=0,ackf=None,acka={}):

		if (e_mail in self.contact_list.getEmails()) \
		   and (not self.contact_list.getUserFlags(e_mail)):
			return
		if not nick:
			nick = e_mail
		enc_nick = utils.str2win(nick)
		d = {
			'flags': 0,
			'group_id': 0,
			'email': e_mail,
			'name': enc_nick,
			'UNKNOWN':0,
			'text':' '
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

		if (e_mail in self.contact_list.getEmails()) \
		   and (not self.contact_list.getUserFlags(e_mail)):
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
			d = {
				'id':contact_id,
				'flags':1,
				'group_id':0,
				'contact':e_mail,
				'name':utils.str2win(name),
				'UNKNOWN':0
			}
			p = protocol.MMPPacket(typ=MRIM_CS_MODIFY_CONTACT,dict=d)
			ret_id = self._send_packet(p)
			self.ack_buf[ret_id] = {'mail':e_mail}
			if ackf:
				self.ack_buf[ret_id].update({'ackf':ackf,'acka':acka})

	def mmp_connection_close(self):

		self._is_connected = False
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

	def mmp_handler_got_subscribed(self, frm, time):
		pass

	def mmp_handler_got_subscribe(self, frm, text):
		pass

	def mmp_handler_got_add_contact_ack(self, status, contact_id):
		pass

	def mmp_handler_got_modify_contact_ack(self, status):
		pass
