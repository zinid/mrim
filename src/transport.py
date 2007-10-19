import async
import xmpp
from mmptypes import *
import utils
import time
import profile
import core
import glue
import pool
import mrim
import forms
import i18n
import traceback
import sys
import os
import socket
import logging
import gw

xmpp.NS_GATEWAY = 'jabber:iq:gateway'
xmpp.NS_STATS = 'http://jabber.org/protocol/stats'
xmpp.NS_ROSTERX = 'http://jabber.org/protocol/rosterx'
xmpp.NS_NICK = 'http://jabber.org/protocol/nick'
xmpp.NS_RECEIPTS = 'urn:xmpp:receipts'

conf = mrim.conf

class XMPPTransport(gw.XMPPSocket):

	def __init__(self, name, disconame, server, port, password, logger):
		self.name = name
		self.disconame = disconame
		self.port = port
		self.server = server
		self.password = password
		self.logger = logger
		self.reconnectors = {}
		self.last_version_time = time.strftime('%Y%m%d-%H%M')
		self.server_features = [
			xmpp.NS_DISCO_INFO,
			xmpp.NS_DISCO_ITEMS,
			xmpp.NS_STATS,
			xmpp.NS_COMMANDS,
			xmpp.NS_VCARD,
			xmpp.NS_SEARCH,
			xmpp.NS_REGISTER,
			xmpp.NS_TIME,
			xmpp.NS_VERSION,
			xmpp.NS_LAST,
			xmpp.NS_GATEWAY,
			xmpp.NS_RECEIPTS
		]
		self.server_ids = {
			'category':'gateway',
			'type':'mrim',
			'name':self.disconame
		}
		self.item_features = [
			xmpp.NS_DISCO_INFO,
			xmpp.NS_DISCO_ITEMS,
			xmpp.NS_COMMANDS,
			xmpp.NS_VCARD
		]
		gw.XMPPSocket.__init__(self)

	def run(self):
		self.start(self.server, self.port, self.name, self.password)
		self.startup = time.time()
		self.RegisterDefaultHandler(lambda x,y: None)
		self.RegisterHandler('iq',       self.process_iq)
		self.RegisterHandler('presence', self.process_presence)
		self.RegisterHandler('message',  self.process_message)
		self.sform = forms.get_search_form()
		self.Features = forms.get_disco_features(self.server_ids,self.server_features)
		if conf.probe:
			self.start_all_connections()
		async.loop(use_poll=True)

	def process_iq(self, conn, iq):
		ns = iq.getQueryNS()
		typ = iq.getType()
		if ns == xmpp.NS_REGISTER:
			self.iq_register_handler(iq)
		elif ns == xmpp.NS_GATEWAY:
			self.iq_gateway_handler(iq)
		elif ns == xmpp.NS_STATS:
			self.iq_stats_handler(iq)
		elif ns == xmpp.NS_TIME:
			self.iq_time_handler(iq)
		elif ns == xmpp.NS_LAST:
			self.iq_last_handler(iq)
		elif ns == xmpp.NS_SEARCH:
			self.iq_search_handler(iq)
		elif ns == xmpp.NS_VERSION:
			self.iq_version_handler(iq)
		elif iq.getTag('vCard') and iq.getTag('vCard').getNamespace()==xmpp.NS_VCARD:
			self.iq_vcard_handler(iq)
		elif iq.getTag('command') and iq.getTag('command').getNamespace()==xmpp.NS_COMMANDS:
			self.iq_command_handler(iq)
		elif ns == xmpp.NS_DISCO_INFO:
			self.iq_disco_info_handler(iq)
		elif ns == xmpp.NS_DISCO_ITEMS:
			self.iq_disco_items_handler(iq)
		elif (ns not in self.server_features):
			self.send_not_implemented(iq)
		else:
			pass

	def process_presence(self, conn, presence):
		typ = presence.getType()
		if typ == 'unavailable':
			self.presence_unavailable_handler(presence)
		elif typ == 'subscribe':
			self.presence_subscribe_handler(presence)
		elif typ == 'subscribed':
			self.presence_subscribed_handler(presence)
		elif typ == 'unsubscribe':
			self.presence_unsubscribe_handler(presence)
		elif typ == 'unsubscribed':
			self.presence_unsubscribed_handler(presence)
		elif typ == 'probe':
			pass
		elif typ == 'error':
			self.presence_error_handler(presence)
		elif not typ:
			self.presence_available_handler(presence)

	def process_message(self, conn, message):
		jid_to = message.getTo()
		jid_to_stripped = jid_to.getStripped()
		if message.getType() == 'error':
			self.message_error_handler(message)
		elif jid_to_stripped == self.name:
			self.message_server_handler(message)
		else:
			self.message_user_handler(message)

	def iq_disco_info_handler(self, iq):
		jid_from = iq.getFrom()
		jid_from_stripped = jid_from.getStripped()
		jid_to = iq.getTo()
		jid_to_stripped = jid_to.getStripped()
		typ = iq.getType()
		node = iq.getTagAttr('query','node')
		if jid_to_stripped==self.name and typ=='get' and not node:
			reply = iq.buildReply(typ='result')
			reply.setQueryPayload(self.Features)
			self.send(reply)
		elif jid_to_stripped==self.name and typ=='get' and node:
			self.iq_disco_node_info_handler(iq, node)
		elif utils.is_valid_email(utils.jid2mail(jid_to_stripped)) and typ=='get':
			if node:
				self.iq_disco_user_node_info_handler(iq, node)
			else:
				ids = {
					'category':'client',
					'type':'pc',
					'name':utils.jid2mail(jid_to_stripped)
				}
				feats = forms.get_disco_features(ids, self.item_features)
				reply = iq.buildReply(typ='result')
				reply.setQueryPayload(feats)
				self.send(reply)
		else:
			self.send_not_implemented(iq)

	def iq_disco_items_handler(self, iq):
		jid_from = iq.getFrom()
		jid_from_stripped = jid_from.getStripped()
		jid_to = iq.getTo()
		jid_to_stripped = jid_to.getStripped()
		jid_to_node = jid_to.getNode()
		typ = iq.getType()
		node = iq.getTagAttr('query','node')
		if jid_to_stripped==self.name and typ=='get' and node:
			self.iq_disco_node_items_handler(iq, node)
		elif jid_to_stripped==self.name and typ=='get' and not node:
			reply = iq.buildReply(typ='result')
			if jid_from_stripped in conf.admins:
				item = xmpp.Node('item',attrs={
							'jid':self.name,
							'name':'online',
							'node':'online'
						}
				)
				reply.setQueryPayload([item])
			command = xmpp.Node('item', attrs={
						'jid':self.name,
						'name':'commands',
						'node':xmpp.NS_COMMANDS
					}
			)
			reply.getTag('query').addChild(node=command)
			self.send(reply)
		elif utils.is_valid_email(utils.jid2mail(jid_to_stripped)) and typ=='get':
			if node:
				self.iq_disco_user_node_items_handler(iq, node)
			else:
				reply = iq.buildReply(typ='result')
				command = xmpp.Node('item', attrs={
						'jid':jid_to,
						'name':'commands',
						'node':xmpp.NS_COMMANDS
					}
				)
				reply.getTag('query').addChild(node=command)
				self.send(reply)
		else:
			self.send_not_implemented(iq)

	def iq_disco_node_info_handler(self, iq, node):
		jid_from = iq.getFrom()
		jid_from_stripped = jid_from.getStripped()
		jid_to = iq.getTo()
		jid_to_stripped = jid_to.getStripped()
		typ = iq.getType()
		if node=='online':
			if jid_from_stripped not in conf.admins:
				self.send_not_implemented(iq)
				return
			count = len(pool.getJids())
			ids = {
				'category':'directory',
				'type':'user',
				'name':'Users Online (%s)' % count
			} 
			features = [
				xmpp.NS_DISCO_INFO,
				xmpp.NS_DISCO_ITEMS
			]
			reply = iq.buildReply(typ='result')
			reply.setQueryPayload(forms.get_disco_features(ids,features))
			reply.setTagAttr('query','node','online')
			self.send(reply)
		elif node==xmpp.NS_COMMANDS:
			ids = {
				'category':'automation',
				'type':'command-list',
				'name':'Service Commands'
			}
			features = [xmpp.NS_COMMANDS]
			reply = iq.buildReply(typ='result')
			reply.setQueryPayload(forms.get_disco_features(ids,features))
			reply.setTagAttr('query','node',xmpp.NS_COMMANDS)
			self.send(reply)
		elif node in ['mail', 'sms']:
			if node=='mail':
				node_name = 'Mail Events'
			elif node=='sms':
				node_name = 'Send SMS'
			ids = {
				'category':'automation',
				'type':'command-node',
				'name':node_name
			}
			features = [
				xmpp.NS_COMMANDS,
				xmpp.NS_DATA
			]
			reply = iq.buildReply(typ='result')
			reply.setQueryPayload(forms.get_disco_features(ids,features))
			reply.setTagAttr('query','node',node)
			self.send(reply)
		else:
			self.send_not_implemented(iq)

	def iq_disco_user_node_info_handler(self, iq, node):
		jid_from = iq.getFrom()
		jid_from_stripped = jid_from.getStripped()
		jid_to = iq.getTo()
		jid_to_stripped = jid_to.getStripped()
		typ = iq.getType()
		if node==xmpp.NS_COMMANDS:
			ids = {
				'category':'automation',
				'type':'command-list',
				'name':'User Commands'
			}
			features = [xmpp.NS_COMMANDS]
			reply = iq.buildReply(typ='result')
			reply.setQueryPayload(forms.get_disco_features(ids,features))
			reply.setTagAttr('query','node',xmpp.NS_COMMANDS)
			self.send(reply)
		elif node in ['conf_sms', 'send_sms']:
			if node=='conf_sms':
				node_name = 'Configure SMS'
			elif node=='send_sms':
				node_name = 'Send SMS'
			ids = {
				'category':'automation',
				'type':'command-node',
				'name':node_name
			}
			features = [
				xmpp.NS_COMMANDS,
				xmpp.NS_DATA
			]
			reply = iq.buildReply(typ='result')
			reply.setQueryPayload(forms.get_disco_features(ids,features))
			reply.setTagAttr('query','node',node)
			self.send(reply)
		else:
			self.send_not_implemented(iq)

	def iq_disco_node_items_handler(self, iq, node):
		jid_from = iq.getFrom()
		jid_from_stripped = jid_from.getStripped()
		jid_to = iq.getTo()
		jid_to_stripped = jid_to.getStripped()
		typ = iq.getType()
		if node=='online':
			items = []
			reply = iq.buildReply(typ='result')
			if jid_from_stripped in conf.admins:
				for jid in pool.getJids():
					try:
						legacy_user = pool.get(jid).user
						item_attrs = {
							'jid':jid,
							'name':legacy_user,
						}
						item = xmpp.Node('item',attrs=item_attrs)
						items.append(item)
					except:
						pass
				reply.setQueryPayload(items)
				reply.setTagAttr('query','node','online')
			else:
				reply.setQueryPayload([])
			self.send(reply)
		elif node==xmpp.NS_COMMANDS:
			mail_attrs = {'jid':self.name,'node':'mail','name':'Mail Events'}
			sms_attrs = {'jid':self.name,'node':'sms','name':'Send SMS'}
			mail = xmpp.Node('item',attrs=mail_attrs)
			sms = xmpp.Node('item',attrs=sms_attrs)
			reply = iq.buildReply(typ='result')
			reply.setTagAttr('query','node',xmpp.NS_COMMANDS)
			reply.setQueryPayload([mail, sms])
			self.send(reply)
		elif node in ['mail', 'sms']:
			reply = iq.buildReply(typ='result')
			reply.setTagAttr('query','node',node)
			self.send(reply)
		else:
			self.send_not_implemented(iq)

	def iq_disco_user_node_items_handler(self, iq, node):
		jid_from = iq.getFrom()
		jid_from_stripped = jid_from.getStripped()
		jid_to = iq.getTo()
		jid_to_stripped = jid_to.getStripped()
		typ = iq.getType()
		if node==xmpp.NS_COMMANDS:
			mail_attrs = {'jid':jid_to,'node':'conf_sms','name':'Configure SMS'}
			sms_attrs = {'jid':jid_to,'node':'send_sms','name':'Send SMS'}
			mail = xmpp.Node('item',attrs=mail_attrs)
			sms = xmpp.Node('item',attrs=sms_attrs)
			reply = iq.buildReply(typ='result')
			reply.setTagAttr('query','node',xmpp.NS_COMMANDS)
			reply.setQueryPayload([mail, sms])
			self.send(reply)
		elif node in ['conf_sms', 'send_sms']:
			reply = iq.buildReply(typ='result')
			reply.setTagAttr('query','node',node)
			self.send(reply)
		else:
			self.send_not_implemented(iq)

	def iq_register_handler(self, iq):
		jid_from = iq.getFrom()
		jid_from_stripped = jid_from.getStripped()
		jid_to = iq.getTo()
		jid_to_stripped = jid_to.getStripped()
		typ = iq.getType()
		iq_children = iq.getQueryChildren()
		if (typ=='get') and (jid_to_stripped==self.name) and (not iq_children):
			repl = iq.buildReply(typ='result')
			repl.setQueryPayload(self.get_register_form(jid_from_stripped))
			self.send(repl)
		elif typ == 'set' and (jid_to_stripped==self.name) and iq_children:
			query_tag = iq.getTag('query')
			if query_tag.getTag('email') and query_tag.getTag('password'):
				user = query_tag.getTagData('email')
				password = query_tag.getTagData('password')
				error = xmpp.ERR_BAD_REQUEST
				if not user:
					text = i18n.NULL_EMAIL
					self.send_error(iq,error,text)
					return
				if not password:
					text = i18n.NULL_PASSWORD
					self.send_error(iq,error,text)
					return
				if not utils.is_valid_email(user):
					text = i18n.UNACCEPTABLE_EMAIL
					self.send_error(iq,error,text)
					return
				if not utils.is_valid_password(password):
					text = i18n.UNACCEPTABLE_PASSWORD
					self.send_error(iq,error,text)
					return
				mmp_conn = pool.get(jid_from)
				if mmp_conn:
					mmp_conn.exit()
				self.mrim_connection_start(jid_from, None, iq)
			elif query_tag.getTag('remove'):
				account = profile.Profile(jid_from_stripped)
				if account.remove():
					profile.Options(jid_from).remove()
					ok_iq = iq.buildReply(typ='result')
					ok_iq.setPayload([],add=0)
					self.send(ok_iq)
					unsub = xmpp.Presence(to=jid_from_stripped,frm=self.name)
					unsub.setType('unsubscribe')
					self.send(unsub)
					unsub.setType('unsubscribed')
					self.send(unsub)
				else:
					pass
				mmp_conn = pool.get(jid_from)
				if mmp_conn:
					mmp_conn.exit()
			else:
				tags_in_register_form = [child.getName() for child in query_tag.getChildren()]
				if ['username', 'password', 'nick', 'key'] == tags_in_register_form:
					pandion_suxx = "Please report to Pandion developers that their client doesn't really support forms and we know it ;)"
					pandion_error = xmpp.Error(iq,xmpp.ERR_NOT_ACCEPTABLE)
					pandion_error.getTag('error').setTagData('text', pandion_suxx)
					self.send(pandion_error)
				else:
					unknown_client_suxx = "Nice try =) Please report to developers that your client doesn't really support forms."
					self.send_error(iq,error=xmpp.ERR_NOT_ACCEPTABLE,text=unknown_client_suxx)
		else:
			self.send_not_implemented(iq)

	def iq_gateway_handler(self, iq):
		jid_to = iq.getTo()
		jid_to_stripped = jid_to.getStripped()
		iq_children = iq.getQueryChildren()
		typ = iq.getType()
		if (typ=='get') and (jid_to_stripped==self.name) and (not iq_children):
			repl = iq.buildReply(typ='result')
			query = xmpp.Node('query', attrs={'xmlns':xmpp.NS_GATEWAY})
			query.setTagData('desc', i18n.ENTER_EMAIL)
			query.setTag('prompt')
			repl.setPayload([query])
			self.send(repl)
		elif (typ=='set') and (jid_to_stripped==self.name) and iq_children:
			e_mail = [node.getData() for node in iq_children if node.getName()=='prompt']
			if len(e_mail) == 1:
				prompt = xmpp.simplexml.Node('prompt')
				prompt.setData(utils.mail2jid(e_mail[0]))
				repl = iq.buildReply(typ='result')
				repl.setQueryPayload([prompt])
				self.send(repl)
			else:
				self.send_bad_request(iq)
		else:
			self.send_not_implemented(iq)

	def iq_search_handler(self, iq):
		jid_from = iq.getFrom()
		jid_to = iq.getTo()
		jid_to_stripped = jid_to.getStripped()
		typ = iq.getType()
		iq_children = iq.getQueryChildren()
		if (typ=='get') and (jid_to_stripped==self.name):
			if iq_children:
				self.send_bad_request(iq)
			else:
				mmp_conn = pool.get(jid_from)
				if mmp_conn:
					repl = iq.buildReply(typ='result')
					repl.setQueryPayload([self.sform])
					self.send(repl)
				else:
					err = xmpp.ERR_REGISTRATION_REQUIRED
					txt = i18n.NOT_CONNECTED
					self.send_error(iq, err, txt)
		elif typ=='set' and (jid_to_stripped==self.name):
			if not iq_children:
				self.send_bad_request(iq)
			else:
				proto_dict = forms.workup_search_input(iq)
				mmp_conn = pool.get(jid_from)
				if mmp_conn:
					mmp_conn.search(proto_dict,iq)
				else:
					err = xmpp.ERR_REGISTRATION_REQUIRED
					txt = i18n.NOT_CONNECTED
					self.send_error(iq, err, txt)
		else:
			self.send_not_implemented(iq)

	def iq_version_handler(self, iq):
		jid_to = iq.getTo()
		jid_to_stripped = jid_to.getStripped()
		jid_from = iq.getFrom()
		jid_from_stripped = jid_from.getStripped()
		typ = iq.getType()
		iq_children = iq.getQueryChildren()
		if typ=='get' and (jid_to_stripped==self.name):
			if iq_children:
				self.send_bad_request(iq)
			else:
				repl = iq.buildReply(typ='result')
				query = repl.getTag('query')
				query.setTagData('name', conf.program)
				query.setTagData('version', conf.version)
				query.setTagData('os', conf.os)
				self.send(repl)
		elif typ=='result':
			query = iq.getTag('query')
			Name = query.getTagData('name') and query.getTagData('name').encode('utf-8', 'replace')
			Version = query.getTagData('version') and query.getTagData('version').encode('utf-8', 'replace')
			Os = query.getTagData('os') and query.getTagData('os').encode('utf-8', 'replace')
			resource = jid_from.getResource().encode('utf-8', 'replace')
			user = jid_from_stripped.encode('utf-8', 'replace')+'/'+resource
			fd = open(
				os.path.join(conf.profile_dir,'version_stats-'+self.last_version_time),'a+'
			)
			fd.write("%s\t%s\t%s\t%s\n" % (user, Name, Version, Os))
			fd.close()
		else:
			self.send_not_implemented(iq)

	def iq_time_handler(self, iq):
		jid_to = iq.getTo()
		jid_to_stripped = jid_to.getStripped()
		typ = iq.getType()
		iq_children = iq.getQueryChildren()
		if typ=='get' and (jid_to_stripped==self.name):
			if iq_children:
				self.send_bad_request(iq)
			else:
				repl = iq.buildReply(typ='result')
				query = xmpp.Node('query',attrs={'xmlns':xmpp.NS_TIME})
				T = utils.gettime()
				query.setTagData('utc', T['utc'])
				query.setTagData('tz', T['tz'])
				query.setTagData('display', T['display'])
				repl.setPayload([query])
				self.send(repl)
		else:
			self.send_not_implemented(iq)

	def iq_last_handler(self, iq):
		jid_to = iq.getTo()
		jid_to_stripped = jid_to.getStripped()
		typ = iq.getType()
		iq_children = iq.getQueryChildren()
		if (jid_to_stripped==self.name) and typ=='get':
			if iq_children:
				self.send_bad_request(iq)
			else:
				repl = iq.buildReply(typ='result')
				repl.getTag('query').setAttr('seconds', int(time.time()-self.startup))
				self.send(repl)
		else:
			self.send_not_implemented(iq)

	def iq_vcard_handler(self, iq):
		jid_from = iq.getFrom()
		jid_to = iq.getTo()
		jid_from_stripped = jid_from.getStripped()
		jid_to_stripped = jid_to.getStripped()
		typ = iq.getType()
		if jid_to_stripped!=self.name and typ=='get':
			mmp_conn = pool.get(jid_from)
			if mmp_conn:
				e_mail = utils.jid2mail(jid_to_stripped)
				mmp_conn.get_vcard(e_mail, iq)
			else:
				err = xmpp.ERR_REGISTRATION_REQUIRED
				txt = i18n.NOT_CONNECTED
				self.send_error(iq,err,txt)
		elif jid_to_stripped==self.name and typ=='get':
			vcard = xmpp.Node('vCard', attrs={'xmlns':xmpp.NS_VCARD})
			vcard.setTagData('NICKNAME', conf.program)
			vcard.setTagData('DESC', 'XMPP to Mail.Ru-IM Transport\n'+conf.copyright)
			vcard.setTagData('URL', 'http://svn.xmpp.ru/repos/mrim')
			repl = iq.buildReply(typ='result')
			repl.setPayload([vcard])
			self.send(repl)
		else:
			self.send_not_implemented(iq)

	def iq_stats_handler(self, iq):
		jid_to_stripped = iq.getTo()
		typ = iq.getType()
		iq_children = iq.getQueryChildren()
		if jid_to_stripped==self.name and typ=='get':
			payload = []
			if not iq_children:
				total = xmpp.Node('stat', attrs={'name':'users/total'})
				online = xmpp.Node('stat', attrs={'name':'users/online'})
				payload = [total,online]
			else:
				for n in [child for child in iq_children if child.getName()=='stat']:
					if n.getAttr('name') == 'users/online':
						stat = xmpp.Node('stat', attrs={'units':'users'})
						stat.setAttr('name','users/online')
						stat.setAttr('value',len(pool.getConnections()))
						payload.append(stat)
					elif n.getAttr('name') == 'users/total':
						stat = xmpp.Node('stat', attrs={'units':'users'})
						stat.setAttr('name','users/total')
						users_total = len([
							i for i in os.listdir(conf.profile_dir) if i.endswith('.xdb')
						])
						stat.setAttr('value',users_total)
						payload.append(stat)
					else:
						s = xmpp.Node('stat', attrs={'name':n.getAttr('name')})
						err = xmpp.Node('error', attrs={'code':'404'})
						err.setData('Not Found')
						s = xmpp.Node('stat', attrs={'name':n.getAttr('name')})
						s.addChild(node=err)
						payload.append(s)
			if not payload:
				pass
			else:
				iq_repl = iq.buildReply(typ='result')
				iq_repl.setQueryPayload(payload)
				self.send(iq_repl)

	def iq_command_handler(self, iq):
		jid_from = iq.getFrom()
		jid_to = iq.getTo()
		jid_from_stripped = jid_from.getStripped()
		jid_to_stripped = jid_to.getStripped()
		typ = iq.getType()
		command = iq.getTag('command')
		sessionid = command.getAttr('sessionid')
		action = command.getAttr('action')
		node = command.getAttr('node')
		if not profile.is_registered(jid_from):
			err = xmpp.ERR_REGISTRATION_REQUIRED
			txt = i18n.NOT_REGISTERED
			self.send_error(iq,err,txt)
			return
		if typ=='set' and node=='mail' and jid_to_stripped==self.name:
			self.process_mail_cmd(iq, jid_from, command, sessionid, action)
		elif typ=='set' and node in ['sms', 'conf_sms', 'send_sms']:
			if pool.get(jid_from):
				if node=='sms' and jid_to_stripped==self.name:
					self.process_sms_cmd(iq, jid_from, command, sessionid, action)
				elif node=='conf_sms' and utils.is_valid_email(utils.jid2mail(jid_to_stripped)):
					self.process_conf_sms_cmd(iq, jid_from, command, sessionid, action)
				elif node=='send_sms' and utils.is_valid_email(utils.jid2mail(jid_to_stripped)):
					self.process_send_sms_cmd(iq, jid_from, command, sessionid, action)
			else:
				err = xmpp.ERR_REGISTRATION_REQUIRED
				txt = i18n.NOT_CONNECTED
				self.send_error(iq, err, txt)
		else:
			self.send_error(iq, xmpp.ERR_SERVICE_UNAVAILABLE)

	def process_mail_cmd(self, iq, jid, command, sessionid, action):
		if action=='execute' or (not action and not sessionid):
			response = forms.get_cmd_header('executing','mail')
			opts = profile.Options(jid)
			response.setPayload([
				forms.get_mail_form(opts.getMboxStatus(),opts.getNewMail())
			])
			reply = iq.buildReply(typ='result')
			reply.setPayload([response])
			self.send(reply)
		elif action=='complete' or (not action and sessionid):
			response = forms.get_cmd_header('completed','mail',sessionid)
			xdata = iq.getTag('command').getTag('x')
			if forms.process_mail_command_xdata(jid, xdata):
				note = xmpp.Node('note', attrs={'type':'info'})
				note.setData(i18n.COMMAND_SAVE_OK)
				response.setPayload([note])
				reply = iq.buildReply(typ='result')
				reply.setPayload([response])
				self.send(reply)
			else:
				self.send_bad_request(iq)
		elif action=='cancel':
			response = forms.get_cmd_header('canceled','mail',sessionid)
			reply = iq.buildReply(typ='result')
			reply.setPayload([response])
			self.send(reply)
		else:
			self.send_bad_request(iq)

	def process_sms_cmd(self, iq, jid, command, sessionid, action):
		mmp_conn = pool.get(jid)
		if action=='execute' or (not action and not sessionid):
			response = forms.get_cmd_header('executing','sms')
			response.setPayload([forms.gate_sms_form()])
			reply = iq.buildReply(typ='result')
			reply.setPayload([response])
			self.send(reply)
		elif action=='cancel':
			response = forms.get_cmd_header('canceled','sms',sessionid)
			reply = iq.buildReply(typ='result')
			reply.setPayload([response])
			self.send(reply)
		elif action=='complete' or (not action and sessionid):
			response = forms.get_cmd_header('completed','sms',sessionid)
			xdata = iq.getTag('command').getTag('x')
			code, result = forms.process_send_sms_xdata(xdata)
			if code:
				number, text = result
				mmp_conn.mmp_send_sms(to=number,body=text)
				note = xmpp.Node('note', attrs={'type':'info'})
				note.setData(i18n.SMS_SEND_OK)
				response.setPayload([note])
				reply = iq.buildReply(typ='result')
				reply.setPayload([response])
				self.send(reply)
			else:
				self.send_error(iq, xmpp.ERR_BAD_REQUEST, result)
		else:
			self.send_bad_request(iq)

	def process_send_sms_cmd(self, iq, jid, command, sessionid, action):
		jid_to = iq.getTo().getStripped()
		mail = utils.jid2mail(jid_to)
		mmp_conn = pool.get(jid)
		if action=='execute' or (not action and not sessionid):
			err = xmpp.ERR_ITEM_NOT_FOUND
			if mail in mmp_conn.contact_list.getEmails():
				nums = mmp_conn.contact_list.getPhones(mail)
				if nums:
					response = forms.get_cmd_header('executing','send_sms')
					response.setPayload([forms.user_sms_form(nums)])
					reply = iq.buildReply(typ='result')
					reply.setPayload([response])
					self.send(reply)
				else:
					txt = i18n.USER_HAS_NO_PHONES
					self.send_error(iq, err, txt)
			else:
				txt = i18n.USER_NOT_IN_CLIST
				self.send_error(iq, err, txt)
		elif action=='cancel':
			response = forms.get_cmd_header('canceled','send_sms',sessionid)
			reply = iq.buildReply(typ='result')
			reply.setPayload([response])
			self.send(reply)
		elif action=='complete' or (not action and sessionid):
			response = forms.get_cmd_header('completed','send_sms',sessionid)
			xdata = iq.getTag('command').getTag('x')
			code, result = forms.process_send_sms_xdata(xdata)
			if code:
				number, text = result
				mmp_conn.mmp_send_sms(to=number,body=text)
				note = xmpp.Node('note', attrs={'type':'info'})
				note.setData(i18n.SMS_SEND_OK)
				response.setPayload([note])
				reply = iq.buildReply(typ='result')
				reply.setPayload([response])
				self.send(reply)
			else:
				self.send_error(iq, xmpp.ERR_BAD_REQUEST, result)
		else:
			self.send_bad_request(iq)

	def process_conf_sms_cmd(self, iq, jid, command, sessionid, action):
		jid_to = iq.getTo().getStripped()
		mail = utils.jid2mail(jid_to)
		mmp_conn = pool.get(jid)
		if action=='execute' or (not action and not sessionid):
			if mail in mmp_conn.contact_list.getEmails():
				nums = mmp_conn.contact_list.getPhones(mail)
				response = forms.get_cmd_header('executing','conf_sms')
				response.setPayload([forms.conf_sms_form(nums)])
				reply = iq.buildReply(typ='result')
				reply.setPayload([response])
				self.send(reply)
			else:
				err = xmpp.ERR_ITEM_NOT_FOUND
				txt = i18n.USER_NOT_IN_CLIST
				self.send_error(iq, err, txt)
		elif action=='complete' or (not action and sessionid):
			response = forms.get_cmd_header('completed','send_sms',sessionid)
			xdata = iq.getTag('command').getTag('x')
			code, result = forms.process_conf_sms_xdata(xdata)
			if code:
				if mail in mmp_conn.contact_list.getEmails():
					mmp_conn.set_sms_phones(mail, result)
					mmp_conn.contact_list.setPhones(mail, result)
					note = xmpp.Node('note', attrs={'type':'info'})
					note.setData(i18n.COMMAND_SAVE_OK)
					response.setPayload([note])
					reply = iq.buildReply(typ='result')
					reply.setPayload([response])
					self.send(reply)
				else:
					err = xmpp.ERR_ITEM_NOT_FOUND
					txt = i18n.USER_NOT_IN_CLIST
					self.send_error(iq, err, txt)
			else:
				self.send_error(iq, xmpp.ERR_BAD_REQUEST, result)
		elif action=='cancel':
			response = forms.get_cmd_header('canceled','conf_sms',sessionid)
			reply = iq.buildReply(typ='result')
			reply.setPayload([response])
			self.send(reply)

	def presence_available_handler(self, presence):
		jid_from = presence.getFrom()
		jid_from_stripped = jid_from.getStripped()
		jid_to = presence.getTo()
		jid_to_stripped = jid_to.getStripped()
		show = presence.getShow()
		if jid_to_stripped!=self.name:
			return
		mmp_conn = pool.get(jid_from, online=False)
		if mmp_conn:
			self.show_status(jid_from, show, mmp_conn)
		else:
			self.mrim_connection_start(jid_from, show)

	def presence_unavailable_handler(self, presence):
		jid_from = presence.getFrom()
		resource = jid_from.getResource()
		jid_from_stripped = jid_from.getStripped()
		jid_to = presence.getTo()
		jid_to_stripped = jid_to.getStripped()
		if jid_to_stripped!=self.name:
			return
		mmp_conn = pool.get(jid_from, online=False)
		offline = xmpp.Presence(to=jid_from, frm=self.name,typ='unavailable')
		if mmp_conn:
			if [jid_from.getResource()] != mmp_conn.getResources():
				mmp_conn.broadcast_offline(jid_from)
				mmp_conn.delResource(resource)
			else:
				mmp_conn.exit()
		else:
			self.send(offline)

	def presence_subscribe_handler(self, presence):
		'''To be completely rewritten'''
		jid_from = presence.getFrom()
		jid_from_stripped = jid_from.getStripped()
		jid_to = presence.getTo()
		jid_to_stripped = jid_to.getStripped()
		if jid_to_stripped==self.name:
			self.send(xmpp.Presence(frm=self.name,to=jid_from_stripped,typ='subscribed'))
			self.send(xmpp.Presence(frm=self.name,to=jid_from))
		else:
			e_mail = utils.jid2mail(jid_to_stripped)
			mmp_conn = pool.get(jid_from)
			if not mmp_conn:
				return
			if (e_mail in mmp_conn.contact_list.getEmails()) and \
			       mmp_conn.contact_list.isAuthorized(e_mail) and \
			       mmp_conn.contact_list.isValidUser(e_mail):
				subd = xmpp.Presence(frm=jid_to_stripped,to=jid_from_stripped,typ='subscribed')
				self.send(subd)
				pres = xmpp.Presence(frm=jid_to_stripped,to=jid_from)
				status = mmp_conn.contact_list.getUserStatus(e_mail)
				if status == STATUS_AWAY:
					pres.setShow('away')
					self.send(pres)
				elif status == STATUS_ONLINE:
					self.send(pres)
			else:
				mmp_conn.add_contact(e_mail)

	def presence_subscribed_handler(self, presence):
		jid_from = presence.getFrom()
		jid_from_stripped = jid_from.getStripped()
		jid_to = presence.getTo()
		jid_to_stripped = jid_to.getStripped()
		if jid_to_stripped==self.name:
			pass
		else:
			e_mail = utils.jid2mail(jid_to_stripped)
			mmp_conn = pool.get(jid_from)
			if mmp_conn:
				mmp_conn.mmp_send_subscribed(e_mail)

	def presence_unsubscribe_handler(self, presence):
		jid_from = presence.getFrom()
		jid_to = presence.getTo()
		jid_from_stripped = jid_from.getStripped()
		jid_to_stripped = jid_to.getStripped()
		if jid_to_stripped==self.name:
			return
		mmp_conn = pool.get(jid_from)
		if mmp_conn and mmp_conn._got_roster:
			e_mail = utils.jid2mail(jid_to_stripped)
			mmp_conn.del_contact(e_mail)

	def presence_unsubscribed_handler(self, presence):
		self.presence_unsubscribe_handler(presence)

	def presence_error_handler(self, presence):
		jid_from = presence.getFrom()
		mmp_conn = pool.get(jid_from)
		if mmp_conn:
			mmp_conn.exit(notify=False)

	def message_error_handler(self, message):
		jid_from = message.getFrom()
		mmp_conn = pool.get(jid_from)
		if mmp_conn:
			self.send_probe(jid_from.getStripped())

	def message_server_handler(self, message):
		jid_from = message.getFrom()
		jid_from_stripped = jid_from.getStripped()
		body = message.getBody()
		if body:
			command = body.strip()
			if jid_from_stripped in conf.admins:
				if command=='version':
					self.collect_versions()

	def collect_versions(self):
		self.last_version_time = time.strftime('%Y%m%d-%H%M')
		version = xmpp.Iq(frm=conf.name,typ='get',queryNS=xmpp.NS_VERSION)
		for mmp_conn in pool.getConnections():
			for resource in mmp_conn.getResources():
				To = xmpp.JID(mmp_conn.jid)
				To.setResource(resource)
				version.setTo(To)
				self.send(version)

	def message_user_handler(self, message):
		jid_from = message.getFrom()
		jid_to = message.getTo()
		jid_to_stripped = jid_to.getStripped()
		mail_to = utils.jid2mail(jid_to_stripped)
		body = message.getBody()
		x = message.getTag('x')
		mmp_conn = pool.get(jid_from)
		if not mmp_conn:
			if body:
				err = xmpp.ERR_REGISTRATION_REQUIRED
				txt = i18n.NOT_CONNECTED
				self.send_error(message, err, txt)
		elif body:
			if len(body)<=65536:
				mmp_conn.cancel_composing(mail_to)
				mmp_conn.send_message(mail_to,body,message)
			else:
				err = xmpp.ERR_NOT_ACCEPTABLE
				txt = i18n.MESSAGE_TOO_BIG
				self.send_error(message, err, txt)

		elif x and x.getNamespace()=='jabber:x:event':
			if x.getTag('composing') and x.getTag('id'):
				mmp_conn.mmp_send_typing_notify(mail_to)
			elif x.getTag('id'):
				mmp_conn.cancel_composing(mail_to)

	def get_register_form(self, jid):
		user = profile.Profile(jid).getUsername()
		instr = xmpp.Node('instructions')
		instr.setData(i18n.ENTER_EMAIL_AND_PASSWORD)
		email = xmpp.Node('email')
		passwd = xmpp.Node('password')
		if user:
			reg = xmpp.Node('registered')
			email.setData(user)
			return [instr,reg,email,passwd]
		else:
			return [instr,email,passwd]

	def show_status(self, jid, show, mmp_conn):
		resource = xmpp.JID(jid).getResource()
		status = utils.show2status(show)
		mmp_conn.current_status = status
		mmp_conn.mmp_change_status(status)
		if mmp_conn.state == 'session_established':
			if resource not in mmp_conn.getResources():
				mmp_conn.addResource(resource)
				self.send(xmpp.Presence(frm=self.name,to=jid))
				mmp_conn.broadcast_online(jid)
			ricochet = xmpp.Presence(frm=self.name)
			if show in ['dnd', 'xa', 'away']:
				ricochet.setShow('away')
			for resource in mmp_conn.getResources():
				To = xmpp.JID(jid)
				To.setResource(resource)
				ricochet.setTo(To)
				self.send(ricochet)
		else:
			mmp_conn.addResource(resource)

	def mrim_connection_start(self, jid, init_status, iq_register=None):
		if iq_register:
			user = iq_register.getTag('query').getTagData('email')
			password = iq_register.getTag('query').getTagData('password')
		else:
			account = profile.Profile(xmpp.JID(jid).getStripped())
			user = account.getUsername()
			password = account.getPassword()
			if not (user and password):
				return
		try:
			timer = self.reconnectors.pop(user)
			self.cancel_timer(timer)
		except:
			pass
		glue.MMPConnection(user,password,self,jid,init_status,iq_register).run()

	def send_not_implemented(self, iq):
		if iq.getType() in ['set','get']:
			self.send_error(iq)

	def send_bad_request(self, iq):
		if iq.getType() in ['set','get']:
			self.send_error(iq,xmpp.ERR_BAD_REQUEST)

	def send_error(self, stanza, error=xmpp.ERR_FEATURE_NOT_IMPLEMENTED, text='', reply=1):
		e = xmpp.Error(stanza,error,reply)
		if text:
			e.getTag('error').setTagData('text', text)
			e.getTag('error').getTag('text').setAttr('xml:lang','ru-RU')
		else:
			e.getTag('error').delChild('text')
		self.send(e)

	def send_probe(self, jid):
		probe = xmpp.Presence(frm=self.name,to=jid,typ='probe')
		self.send(probe)

	def stop(self, notify=True):
		for mmp_conn in pool.getConnections(online=False):
			mmp_conn.exit(notify)

	def start_all_connections(self):
		probe = xmpp.Presence(frm=conf.name,typ='probe')
		users = [f[:f.find('.xdb')] for f in os.listdir(conf.profile_dir) if f.endswith('.xdb')]
		for user in users:
			probe.setTo(user)
			self.send(probe)

	def reconnect_user(self, jid, mail, timeout):
		if conf.reconnect:
			self.logger.info("[%s] Reconnect over %s seconds" % (mail, timeout))
			self.reconnectors[mail] = self.set_timer(timeout, ("reconnect", jid, mail))

	def handle_timer(self, tref, (typ, jid, mail)):
		if typ=="reconnect":
			try:
				del self.reconnectors[mail]
			except:
				pass
			probe = xmpp.Presence(frm=self.name,to=jid,typ='probe')
			self.send(probe)

	def handle_close(self):
		self.close()
		self.stop(notify=False)
		self.logger.critical("Connection to server lost")

	def handle_error(self):
		if sys.exc_info()[0]==IOError:
			self.handle_close()
		else:
			traceback.print_exc()
