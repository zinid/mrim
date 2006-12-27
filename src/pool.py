# -*- coding: utf-8 -*-

import xmpp
import async

def get(Jid, online=True):
	jid = xmpp.JID(Jid)
	jid_stripped = jid.getStripped()
	for c in async.socket_map.values():
		if hasattr(c, 'jid') and c.jid==jid_stripped:
			if not online:
				return c
			elif c.state=='session_established':
				return c
			else:
				return

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
