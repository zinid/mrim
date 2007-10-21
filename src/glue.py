# -*- coding: utf-8 -*-

import protocol
import core
from mmptypes import *
import xmpp
import i18n
import traceback
import profile
import utils
import sys
import time
import base64
import urllib2
import locale
import random
import socket
import logging
import mrim
import forms
import async
import pool
import config

conf = mrim.conf

class MMPConnection(core.Client):

	def __init__(self, user, password, xmpp_conn, jid, init_status, iq_register):
		self.iq_register = iq_register
		self.user = user
		self.password = password
		self.xmpp_conn = xmpp_conn
		self.jid = xmpp.JID(xmpp.JID(jid).getStripped())
		self.starttime = time.time()
		self.init_status = utils.show2status(init_status)
		self.roster_action = {}
		self.ids = []
		self.resources = [xmpp.JID(jid).getResource()]
		self.current_status = self.init_status
		self.authed_users = []
		self.Roster = profile.Profile(self.jid)
		core.Client.__init__(self,self.user,self.password,xmpp_conn.logger,
			                 agent=conf.agent,status=self.init_status,proxy=conf.http_proxy)
		pool.add(self.jid, self)

	#def __del__(self):
	#	print "deleting glue.MMPConnection @", self

	def send_stanza(self, stanza, jid=None):
		typ = stanza.getType()
		if typ in ['subscribe','subscribed','unsubscribe','unsubscribed']:
			stanza.setTo(self.jid)
			self.xmpp_conn.send(stanza)
		elif jid:
			stanza.setTo(jid)
			self.xmpp_conn.send(stanza)
		else:
			for resource in self.getResources():
				To = xmpp.JID(self.jid)
				To.setResource(resource)
				stanza.setTo(To)
				self.xmpp_conn.send(stanza)

	def broadcast_offline(self, jid=None):
		offline = xmpp.Presence(frm=conf.name,typ='unavailable')
		self.send_stanza(offline, jid)
		if not self._got_roster:
			return
		for e_mail in self.contact_list.getEmails():
			mrim_status = self.contact_list.getUserStatus(e_mail)
			typ, s = utils.status2show(mrim_status)
			if not typ:
				user_offline = xmpp.Presence(frm=utils.mail2jid(e_mail),typ='unavailable')
				self.send_stanza(user_offline, jid)

	def broadcast_online(self, jid=None):
		if not self._got_roster:
			return
		for e_mail in self.contact_list.getEmails():
			mrim_status = self.contact_list.getUserStatus(e_mail)
			typ, s = utils.status2show(mrim_status)
			if not typ:
				p = xmpp.Presence(frm=utils.mail2jid(e_mail))
				p.setTag('c', namespace=xmpp.NS_CAPS,attrs={'node':'unknown','ver':utils.c_caps_ver()})
				if s:
					p.setShow(s)
				self.send_stanza(p, jid)

	def handle_expt(self):

		self.failure_exit("Connection has been closed abnormally")

	def handle_error(self):

		t, err, tb = sys.exc_info()
		if t == socket.error:
			reason = utils.socket_error(err)
		else:
			reason = "Unhandled exception"
			traceback.print_exc()
		self.failure_exit(reason)

	def exit(self, notify=True):
		if notify:
			self.broadcast_offline()
		pool.rm(self.jid)
		self.mmp_connection_close()

	def failure_exit(self,errtxt):
		if self.iq_register:
			rej = xmpp.ERR_INTERNAL_SERVER_ERROR
			rej_txt = i18n.CONNECTION_ERROR
			self.xmpp_conn.send_error(self.iq_register,rej,rej_txt)
		else:
			self.broadcast_offline()
		try:
			pool.rm(self.jid)
			self.close()
		except:
			pass
		self.log(logging.INFO, "Connection error (%s): %s" % (self.mrim_host, errtxt))
		timeout = random.choice(xrange(1,10))
		if self.state != 'session_established' and not self.iq_register:
			timeout = 60
			error = xmpp.Presence(to=self.jid, frm=conf.name)
			error_txt = i18n.REMOTE_SERVER_ERROR
			self.xmpp_conn.send_error(error,xmpp.ERR_INTERNAL_SERVER_ERROR,error_txt,reply=0)
		if not self.iq_register:
			self.xmpp_conn.reconnect_user(self.jid, self.user, timeout)

	def start(self, server, port):
		self.mrim_host = server
		self.mrim_port = port
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.log(logging.INFO, "Connecting to %s:%s" % (self.mrim_host,self.mrim_port))
		self.state = 'wait_for_connect'
		self.async_connect((self.mrim_host,self.mrim_port))
		self.connect_timer = self.set_timer(30, "timeout")

	def mmp_handler_server_authorized(self):
		if self.iq_register:
			ok_iq = self.iq_register.buildReply(typ='result')
			ok_iq.setPayload([],add=0)
			self.xmpp_conn.send(ok_iq)
			account = profile.Profile(self.jid)
			account.setUsername(self.user)
			account.setPassword(self.password)
			self.exit(notify=False)
		subscribe = xmpp.Presence(frm=conf.name,typ='subscribe')
		online = xmpp.Presence(frm=conf.name)
		online.setTag('c', namespace=xmpp.NS_CAPS,
			attrs={'node':config.NODE,'ver':utils.s_caps_ver()})
		if self.current_status != self.init_status:
			self.mmp_change_status(self.current_status)
		typ,show = utils.status2show(self.current_status)
		if show:
			online.setShow(show)
		self.send_stanza(subscribe)
		self.send_stanza(online)
		self.starttime = time.time()

	def mmp_handler_server_not_authorized(self, reason):
		if self.iq_register:
			err = xmpp.ERR_NOT_ACCEPTABLE
			txt = i18n.WRONG_USER_OR_PASSWORD
			self.xmpp_conn.send_error(self.iq_register,err,txt)
			self.exit()
		else:
			reject = xmpp.Message(to=self.jid, frm=conf.name)
			reject.setSubject(i18n.AUTH_ERROR)
			reject.setBody(' ')
			if reason == 'Invalid login':
				rej_txt = i18n.WRONG_USER_OR_PASSWORD
			else:
				rej_txt = '%s: %s' % (i18n.SERVER_REPLIED, reason)
			err = xmpp.ERR_NOT_AUTHORIZED
			self.xmpp_conn.send_error(reject,err,rej_txt,reply=0)
			self.exit()

	def mmp_handler_got_user_status(self, e_mail, mrim_status):
		jid_from = utils.mail2jid(e_mail)
		typ, s = utils.status2show(mrim_status)
		p = xmpp.Presence(frm=jid_from)
		if typ:
			p.setType(typ)
		elif s:
			p.setShow(s)
		self.send_stanza(p)

	def mmp_handler_got_contact_list2(self):

		for e_mail in self.contact_list.getEmails():
			if self.contact_list.isValidUser(e_mail):
				nickname = self.contact_list.getUserNick(e_mail)
				if not nickname:
					nickname = e_mail
				jid_from = utils.mail2jid(e_mail)
				subscribe = xmpp.Presence(frm=jid_from,typ='subscribe')
				subscribe.addChild(name='nick',payload=[nickname],namespace=xmpp.NS_NICK)
				self.authed_users.append(e_mail)
				self.send_stanza(subscribe)
				mrim_status = self.contact_list.getUserStatus(e_mail)
				typ, s = utils.status2show(mrim_status)
				p = xmpp.Presence(frm=jid_from)
				if typ:
					p.setType(typ)
				elif s:
					p.setShow(s)
				if not typ:
					p.setTag('c', namespace=xmpp.NS_CAPS,
						attrs={'node':'unknown','ver':utils.c_caps_ver()})
				self.send_stanza(p)

	def mmp_handler_got_message(self, mess, offtime):
		mail = utils.win2str(mess.getFrom())
		body = mess.getBodyPayload()
		jid_from = utils.mail2jid(mail)
		msg = xmpp.Message(frm=jid_from)
		msg.setBody(body)
		if mess.hasFlag(MESSAGE_FLAG_SYSTEM):
			msg.setSubject(i18n.SYSTEM_NOFIFY)
			msg.setFrom(conf.name)
		elif mess.hasFlag(MESSAGE_FLAG_SMS_STATUS):
			msg.setSubject(i18n.SMS_DELIVERY_STATUS + mail)
			msg.setFrom(conf.name)
		else:
			msg.setType('chat')
			if not offtime:
				xevent = xmpp.simplexml.Node('x', attrs={'xmlns':'jabber:x:event'})
				xevent.setTag('composing')
				active = xmpp.Node('active', attrs={'xmlns':xmpp.NS_CHATSTATES})
				msg.addChild(node=xevent)
				msg.addChild(node=active)
			else:
				old_stamp = time.strftime('%Y%m%dT%H:%M:%S', offtime)
				old_delay = xmpp.Node('x',
					attrs={'xmlns':xmpp.NS_DELAY, 'from':conf.name, 'stamp':old_stamp})
				new_stamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', offtime)
				new_delay = xmpp.Node('delay',
					attrs={'xmlns':xmpp.NS_NEW_DELAY, 'from':conf.name, 'stamp':new_stamp})
				msg.addChild(node=old_delay)
				msg.addChild(node=new_delay)
		self.send_stanza(msg, self.jid)

	def mmp_handler_got_sms(self, number, users, text, offtime):
		jids = [utils.mail2jid(u) for u in users]
		msg = xmpp.Message(frm=conf.name)
		msg.setSubject(i18n.INCOMING_SMS + number)
		msg.setBody(text)
		if offtime:
			stamp = time.strftime('%Y%m%dT%H:%M:%S', offtime)
			delay = xmpp.Node('x', attrs={'xmlns':xmpp.NS_DELAY, 'from':conf.name})
			delay.setAttr('stamp', stamp)
			msg.addChild(node=delay)
		if not jids:
			jid_from = conf.name
		else:
			jid_from = jids[0]
		msg.setFrom(jid_from)
		self.send_stanza(msg, self.jid)

	def mmp_handler_got_subscribe(self, e_mail, name, txt, offtime):
		
		subscribe = xmpp.Presence(frm=utils.mail2jid(e_mail),typ='subscribe')
		if not name:
			name = e_mail
		subscribe.addChild(name='nick',payload=[name],namespace=xmpp.NS_NICK)
		if offtime:
			stamp = time.strftime('%Y%m%dT%H:%M:%S', offtime)
			delay = xmpp.Node('x', attrs={'xmlns':xmpp.NS_DELAY, 'from':conf.name})
			delay.setAttr('stamp', stamp)
			subscribe.addChild(node=delay)
		self.send_stanza(subscribe)

	def mmp_handler_got_subscribed(self, e_mail):
		subscribed = xmpp.Presence(frm=utils.mail2jid(e_mail),typ='subscribed')
		self.send_stanza(subscribed)

	def mmp_send_subscribed(self, to):
		"Roster-sync workaround"
		p = protocol.MMPPacket(typ=MRIM_CS_AUTHORIZE,dict={'user':to})
		try:
			self.authed_users.pop(self.authed_users.index(to))
		except (ValueError,IndexError):
			self._send_packet(p)

	def mmp_handler_dual_login(self):
		reject = xmpp.Message(to=self.jid, frm=conf.name)
		reject.setBody(' ')
		reject.setSubject(i18n.CONNECTION_ERROR)
		err = xmpp.ERR_CONFLICT
		err_txt = i18n.DUAL_LOGIN
		self.xmpp_conn.send_error(reject,err,err_txt,reply=0)
		self.exit()

	def mmp_handler_composing_start(self, e_mail):
		xevent = xmpp.Node('x', attrs={'xmlns':'jabber:x:event'})
		xevent.setTag('composing')
		xevent.setTag('id')
		c = xmpp.Node('composing', attrs={'xmlns':xmpp.NS_CHATSTATES})
		composing = xmpp.Message(frm=utils.mail2jid(e_mail))
		composing.addChild(node=xevent)
		composing.addChild(node=c)
		self.send_stanza(composing, self.jid)

	def mmp_handler_composing_stop(self, e_mail):
		xevent = xmpp.simplexml.Node('x', attrs={'xmlns':'jabber:x:event'})
		xevent.setTag('id')
		paused = xmpp.Node('paused', attrs={'xmlns':xmpp.NS_CHATSTATES})
		composing = xmpp.Message(frm=utils.mail2jid(e_mail))
		composing.addChild(node=xevent)
		composing.addChild(node=paused)
		self.send_stanza(composing, self.jid)

	def mmp_handler_got_mbox_status(self, url, total, unread):
		if not unread or profile.Options(self.jid).getMboxStatus()!='1':
			return
		body = "Непрочитанных писем: %s\nВсего писем: %s" % (unread, total)
		subject = "У вас есть непрочитанные письма"
		xoob = xmpp.simplexml.Node('x', attrs={'xmlns':'jabber:x:oob'})
		xoob.setTagData('url', url)
		xoob.setTagData('desc', 'Просмотреть')
		msg = xmpp.Message(frm=conf.name,typ='headline')
		msg.setSubject(subject)
		msg.setBody(body)
		msg.addChild(node=xoob)
		self.send_stanza(msg, self.jid)

	def mmp_handler_got_new_mail(self, url, number, sender, subject, unix_time):
		if profile.Options(self.jid).getNewMail()!='1':
			return
		ltime = time.strftime('%c', time.localtime(unix_time))
		xmpp_subject = "Вам пришло новое почтовое сообщение"
		body = "Отправитель: %s\n" % sender
		body += "Тема: %s\n" % subject
		body += 6*"-"+"\n"
		body += "Всего непрочитанных писем: %s" % number
		xoob = xmpp.simplexml.Node('x', attrs={'xmlns':'jabber:x:oob'})
		xoob.setTagData('url', url)
		xoob.setTagData('desc', 'Просмотреть')
		msg = xmpp.Message(frm=conf.name,typ='headline')
		msg.setSubject(xmpp_subject)
		msg.setBody(body)
		msg.addChild(node=xoob)
		self.send_stanza(msg, self.jid)

	def mmp_handler_got_contact_list(self, mail, clist, offtime):
		body = ''
		for address,nick in clist:
			body += "%s (%s)\n" % (address, nick)
		jid_from = utils.mail2jid(mail)
		msg = xmpp.Message(frm=jid_from)
		msg.setBody(body)
		msg.setSubject('Список контактов')
		if offtime:
			stamp = time.strftime('%Y%m%dT%H:%M:%S', offtime)
			delay = xmpp.Node('x', attrs={'xmlns':xmpp.NS_DELAY, 'from':conf.name})
			delay.setAttr('stamp', stamp)
			msg.addChild(node=delay)
		self.send_stanza(msg, self.jid)

	def add_contact(self, mail):
		if utils.is_valid_email(mail):
			self.mmp_add_contact_with_search(mail, ackf=self.add_contact_result,
				acka={'mail':mail})
		else:
			reject = xmpp.Message(frm=utils.mail2jid(mail),to=self.jid)
			reject.setSubject('Ошибка добавления пользователя')
			reject.setBody(' ')
			err = xmpp.ERR_ITEM_NOT_FOUND
			error_reason = 'Добавляемого пользователя не существует в системе'
			self.xmpp_conn.send_error(reject,err,error_reason,reply=0)

	def del_contact(self, mail):
		if utils.is_valid_email(mail):
			self.mmp_del_contact(mail, ackf=self.del_contact_result, acka={'mail':mail})

	def add_contact_result(self, status, mail):
		if status == CONTACT_OPER_SUCCESS:
			#self.mmp_send_subscribe(mail)
			return
		reject = xmpp.Message(frm=utils.mail2jid(mail),to=self.jid)
		if status == CONTACT_OPER_ERROR:
			error_reason = 'Переданные данные были некорректны'
		elif status == CONTACT_OPER_INTERR:
			error_reason = 'При обработке запроса произошла внутренняя ошибка'
		elif status == CONTACT_OPER_NO_SUCH_USER:
			error_reason = 'Добавляемого пользователя не существует в системе'
		elif status == CONTACT_OPER_INVALID_INFO:
			error_reason = 'Некорректное имя пользователя'
		elif status == CONTACT_OPER_USER_EXISTS:
			#error_reason = 'Пользователь уже есть в контакт-листе'
			return
		elif status == CONTACT_OPER_GROUP_LIMIT:
			error_reason = 'Превышено максимально допустимое количество групп (20)'
		else:
			error_reason = 'Неизвестный код ошибки (%s)' % status
		reject.setSubject('Ошибка добавления пользователя')
		reject.setBody(' ')
		err = xmpp.ERR_ITEM_NOT_FOUND
		self.xmpp_conn.send_error(reject,err,error_reason,reply=0)

	def del_contact_result(self, status, mail):
		pass

	def got_vcard(self, anketa, mail, msg):
		anketa_entries = anketa.getVCards()
		status = anketa.getStatus()
		jid_to = msg.getFrom()
		if len(anketa_entries) == 1:
			self.mmp_send_avatar_request(mail, ackf=self.got_full_vcard,
				acka={'vcard':anketa_entries[0], 'msg':msg, 'mail':mail})
		else:
			if status == MRIM_ANKETA_INFO_STATUS_NOUSER:
				err = xmpp.ERR_ITEM_NOT_FOUND
				err_txt = 'Нет такого пользователя'
			elif status == MRIM_ANKETA_INFO_STATUS_DBERR:
				err = xmpp.ERR_INTERNAL_SERVER_ERROR
				err_txt = 'Ошибка обработки данных'
			elif status == MRIM_ANKETA_INFO_STATUS_RATELIMERR:
				err = xmpp.ERR_REMOTE_SERVER_TIMEOUT
				err_txt = 'Слишком много запросов, поиск временно запрещен'
			else:
				err = xmpp.ERR_INTERNAL_SERVER_ERROR
				err_txt = 'Неизвестная ошибка'
			self.xmpp_conn.send_error(msg,err,err_txt)

	def got_full_vcard(self, avatara, typ, album, vcard, msg, mail):
		jid_from = msg.getTo()
		jid_to = msg.getFrom()
		iq = xmpp.Iq(frm=jid_from,typ='result')
		iq.setAttr('id', msg.getAttr('id'))
		card = self.anketa2vcard(vcard, avatara, typ, album)
		iq.setPayload([card])
		self.send_stanza(iq, jid_to)

	def got_status(self, anketa, mail):
		anketa_entries = anketa.getVCards()
		jid_from = utils.mail2jid(mail)
		status = anketa.getStatus()
		if len(anketa_entries) == 1:
			mrim_status = int(anketa_entries[0]['mrim_status'])
			if mail in self.contact_list.getEmails():
				self.contact_list.setUserStatus(mail,mrim_status)
			self.mmp_handler_got_user_status(mail, status)

	def send_message(self, mail_to, body, mess):
		if utils.is_valid_email(mail_to):
			self.mmp_send_message(mail_to,body,ackf=self.got_message_status,acka={'msg':mess})
		else:
			err_txt = 'Нет такого пользователя'
			self.xmpp_conn.send_error(mess,xmpp.ERR_ITEM_NOT_FOUND,err_txt)

	def got_message_status(self,status,msg):

		_id = msg.getAttr('id')
		if status != MESSAGE_DELIVERED:
			if status == MESSAGE_REJECTED_NOUSER:
				error_name = xmpp.ERR_ITEM_NOT_FOUND
				error_text = 'Нет такого пользователя'
			elif status == MESSAGE_REJECTED_LIMIT_EXCEEDED:
				error_name = xmpp.ERR_NOT_ALLOWED
				error_text = 'Пользователь отключен от сети, и сообщение не помещается в его почтовый ящик'
			elif status == MESSAGE_REJECTED_TOO_LARGE:
				error_name = xmpp.ERR_NOT_ACCEPTABLE
				error_text = 'Размер сообщения превышает максимально допустимый'
			elif status == MESSAGE_REJECTED_DENY_OFFMSG:
				error_name = xmpp.ERR_NOT_ALLOWED
				error_text = 'Пользователь отключен от сети, а настройки его почтового ящика не допускают наличие оффлайновых сообщений'
			else:
				error_name = xmpp.ERR_INTERNAL_SERVER_ERROR
				error_text = 'Произошла внутренняя ошибка'
			self.xmpp_conn.send_error(msg,error_name,error_text)
		elif _id:
			x = msg.getTag('x')
			request = msg.getTag('request')
			if x or request:
				repl_msg = xmpp.Message(frm=msg.getTo())
				repl_msg.setAttr('id', _id)
				need_reply = False
				if x and (x.getNamespace()=='jabber:x:event') \
			       and (not x.getTag('id')) and x.getTag('delivered'):
					id_x = xmpp.Node('x',attrs={'xmlns':'jabber:x:event'})
					id_x.setTag('delivered')
					id_x.setTagData('id',_id)
					repl_msg.addChild(node=id_x)
					need_reply = True
				if request and (request.getNamespace()==xmpp.NS_RECEIPTS):
					id_request = xmpp.Node('received', attrs={'xmlns':xmpp.NS_RECEIPTS})
					repl_msg.addChild(node=id_request)
					need_reply = True
				if need_reply:
					self.send_stanza(repl_msg,msg.getFrom())

	def get_vcard(self, mail, mess):
		if utils.is_valid_email(mail):
			user,domain = mail.split('@')
			d = {
				MRIM_CS_WP_REQUEST_PARAM_USER:user,
				MRIM_CS_WP_REQUEST_PARAM_DOMAIN:domain
			}
			self.mmp_send_wp_request(d, ackf=self.got_vcard, acka={'mail':mail, 'msg':mess})
		else:
			err = xmpp.ERR_ITEM_NOT_FOUND
			err_txt = 'Нет такого пользователя'
			self.xmpp_conn.send_error(mess,err,err_txt)

	def anketa2vcard(self, anketa, avatara, ava_typ, album):
		attributes = {'xmlns':"vcard-temp"}
		e_mail = xmpp.Node('EMAIL')
		tel = xmpp.Node('TEL')
		adr = xmpp.Node('ADR')
		N = xmpp.Node('N')
		vcard = xmpp.Node('vCard', attrs=attributes)
		vcard.setTagData('FN', anketa['FirstName'] + ' ' + anketa['LastName'])
		N.setTagData('FAMILY', anketa['LastName'])
		N.setTagData('GIVEN', anketa['FirstName'])
		vcard.addChild(node=N)
		if anketa['Nickname'].strip():
			vcard.setTagData('NICKNAME', anketa['Nickname'])
		else:
			vcard.setTagData('NICKNAME', anketa['Username'])
		try:
			vcard.setTagData('BDAY',anketa['Birthday'])
		except:
			pass
		e_mail.setTagData('INTERNET', '')
		e_mail.setTagData('USERID', anketa['Username']+'@'+anketa['Domain'])
		tel.setTagData('HOME', '')
		tel.setTagData('VOICE', '')
		tel.setTagData('NUMBER', anketa['Phone'])
		vcard.setPayload([tel,e_mail],add=1)
		desc = ''
		if anketa['Sex'] == '1':
			desc = 'Пол: Мужской\n'
		elif anketa['Sex'] == '2':
			desc = 'Пол: Женский\n'
		if ZODIAC.has_key(anketa['Zodiac']):
			desc += 'Знак зодиака: %s\n' % ZODIAC[anketa['Zodiac']]
		location = anketa['Location']
		if location:
			coords = location.strip().split(',')
			if len(coords) == 1:
				country = coords[0].strip()
				adr.setTagData('CTRY', country)
			elif len(coords) == 2:
				country = coords[0].strip()
				city = coords[1].strip()
				adr.setTagData('CTRY', country)
				adr.setTagData('LOCALITY', city)
			elif len(coords) > 2:
				country = coords[0].strip()
				region = ','.join(coords[1:-1]).strip()
				city = coords[-1].strip()
				adr.setTagData('CTRY', country)
				adr.setTagData('REGION', region)
				adr.setTagData('LOCALITY', city)
			vcard.setPayload([adr],add=1)
		if avatara and (ava_typ in ['image/gif','image/jpeg','image/png']):
			photo = xmpp.Node('PHOTO')
			avahex = base64.encodestring(avatara)
			photo.setTagData('TYPE', ava_typ)
			photo.setTagData('BINVAL', '\n'+avahex)
			vcard.setPayload([photo],add=1)
			desc += 'Фотоальбом: %s\n' % album.__str__()
		vcard.setTagData('DESC', desc)
		return vcard

	def search(self, vals, mess):
		err = xmpp.ERR_NOT_ACCEPTABLE
		err_txt = 'Переданы неверные данные для поиска'
		if not vals:
			self.xmpp_conn.send_error(mess,err,err_txt)
			return
		else:
			self.mmp_send_wp_request(vals, self.got_search_result, {'mess':mess})

	def got_search_result(self, anketa, mess):
		status = anketa.getStatus()
		if status not in [MRIM_ANKETA_INFO_STATUS_OK, MRIM_ANKETA_INFO_STATUS_NOUSER]:
			if status == MRIM_ANKETA_INFO_STATUS_DBERR:
				error_name = xmpp.ERR_ITEM_NOT_FOUND
				error_text = 'Ошибка поиска в базе данных'
			elif status == MRIM_ANKETA_INFO_STATUS_RATELIMERR:
				error_name = xmpp.ERR_REMOTE_SERVER_TIMEOUT
				error_text = 'Слишком много запросов. Поиск временно приостановлен'
			else:
				error_name = xmpp.ERR_ITEM_NOT_FOUND
				error_text = 'Неизвестная ошибка'
			self.xmpp_conn.send_error(mess,error_name,error_text)
			return
		xdf = forms.anketa2search(anketa.getVCards())
		iq_form = xmpp.Iq(frm=conf.name,typ='result')
		iq_form.setAttr('id', mess.getAttr('id'))
		iq_form.setQueryNS(xmpp.NS_SEARCH)
		iq_form.setQueryPayload([xdf])
		self.send_stanza(iq_form, mess.getFrom())

	def set_sms_phones(self, mail, numbers):
		self.mmp_modify_sms(mail, numbers)

	def uptime(self):
		return utils.uptime(time.time() - self.starttime)

	def getResources(self):
		return self.resources

	def delResource(self, resource):
		if resource in self.resources:
			self.resources.remove(resource)

	def addResource(self, resource):
		if resource not in self.resources:
			self.resources.append(resource)
