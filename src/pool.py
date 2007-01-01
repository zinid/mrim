# -*- coding: utf-8 -*-

import xmpp
import async

channels = {}

def getConnections(online=True):
	if online:
		return [c for c in async.socket_map.values() if hasattr(c, 'jid') and c.state=='session_established']
	else:
		return [c for c in async.socket_map.values() if hasattr(c, 'jid')]

def getJids(online=True):
	if online:
		return [c.jid for c in async.socket_map.values() if hasattr(c, 'jid') and c.state=='session_established']
	else:
		return [c.jid for c in async.socket_map.values() if hasattr(c, 'jid')]

def add(jid, obj):
	channels[jid] = obj

def rm(jid):
	try:
		del channels[jid]
	except KeyError:
		pass

def get(Jid, online=True):
	jid = xmpp.JID(Jid)
	jid_stripped = jid.getStripped()
	try:
		obj = channels[jid_stripped]
		if not online:
			return obj
		elif obj.state=='session_established':
			return obj
	except KeyError:
		pass
