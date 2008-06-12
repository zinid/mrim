# dirty,dirty hack for xmpppy to use asyncore
import async
import xmpp

BUFLEN = 8192

class XMPPSocket(async.dispatcher_with_send, xmpp.Component):

	def __init__(self):
		self.Namespace=xmpp.dispatcher.NS_COMPONENT_ACCEPT
		self.DBG=xmpp.client.DBG_COMPONENT
		self.socket = None

	def start(self, server, port, name, passwd):
		xmpp.Component.__init__(self, name)
		self.connect((server, port))
		self.auth(name, passwd)
		self.socket = self.Connection._sock
		self.Connection.pending_data = lambda x: True
		self.Connection.receive = self.receive
		async.dispatcher_with_send.__init__(self, sock=self.socket)
		self.Connection._send = self.async_send

	def handle_read(self):
		self.Process()

	def handle_connect(self):
		pass

	def receive(self):
		received = self.recv(BUFLEN)
		received = received.replace('<caps:c', '<c')
		if received:
			self.Connection.DEBUG(received,'got')
			if hasattr(self, 'Dispatcher'):
				self.Dispatcher.Event('', 'DATA_RECEIVED', received)
		return received
