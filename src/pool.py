# -*- coding: utf-8 -*-

import xmpp
import threading

class MMPPool:

	def __init__(self):

		self.connections = {}
		self.resources = {}
		self.locks = []
		self.access = threading.Semaphore()

	def push(self, Jid, conn=None):

		self.lock(Jid)
		jid = xmpp.JID(Jid)
		jid_stripped = jid.getStripped()
		jid_resource = jid.getResource()
		if not self.connections.has_key(jid_stripped) and (conn is not None):
			self.connections[jid_stripped] = conn
		if not self.resources.has_key(jid_stripped):
			self.resources[jid_stripped] = []
		if jid_resource not in self.getResources(jid_stripped):
			self.resources[jid_stripped].append(jid_resource)

	def lock(self, Jid):

		jid = xmpp.JID(Jid)
		jid_stripped = jid.getStripped()
		self.access.acquire()
		if jid_stripped in self.locks:
			result = False
		else:
			self.locks.append(jid_stripped)
			
			result = True
		self.access.release()
		return result

	def unlock(self, Jid):

		jid = xmpp.JID(Jid)
		jid_stripped = jid.getStripped()
		try:
			self.locks.remove(jid_stripped)
		except ValueError:
			pass

	def pop(self, Jid):

		jid = xmpp.JID(Jid)
		jid_stripped = jid.getStripped()
		jid_resource = jid.getResource()
		if jid_resource in self.getResources(jid):
			self.resources[jid_stripped].remove(jid_resource)
		if not self.getResources(jid):
			try:
				self.connections.pop(jid_stripped)
			except KeyError:
				pass
			self.unlock(Jid)

	def get(self, Jid):

		jid = xmpp.JID(Jid)
		jid_stripped = jid.getStripped()
		if self.connections.has_key(jid_stripped):
			return self.connections[jid_stripped]

	def remove(self, Jid):

		jid = xmpp.JID(Jid)
		jid_stripped = jid.getStripped()
		try:
			self.connections.pop(jid_stripped)
			self.resources.pop(jid_stripped)
		except KeyError:
			pass
		self.unlock(Jid)

	def getConnections(self):
		return self.connections.values()

	def getJids(self):
		return self.connections.keys()

	def getResources(self, Jid):

		jid_stripped = xmpp.JID(Jid).getStripped()
		if self.resources.has_key(jid_stripped):
			return self.resources[jid_stripped]
		else:
			return []
