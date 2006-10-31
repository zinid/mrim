from mmptypes import *
import utils

import UserDict
import cStringIO
import socket
import struct
import email
from email.Utils import parsedate

wp_request = {}
wp_request_reversed = {}

for k,v in [(key, locals()[key]) for key in locals().keys() if key.startswith('MRIM_CS_WP_REQUEST_PARAM')]:
	wp_request[v] = k

for k,v in wp_request.items():
	wp_request_reversed[v] = k

del k,v

message_flags = tuple([v for k,v in locals().items() if k.startswith('MESSAGE_FLAG')])

class MMPParsingError(Exception):
	def __init__(self, text, packet):
		self.args = text,packet
		self.text = text
		self.packet = packet
	def __str__(self):
		return self.text

class MMPHeader(UserDict.UserDict):

	def __init__(self,typ=0,dlen=0,seq=0,fromip='0.0.0.0',fromport='0',header=''):
		UserDict.UserDict.__init__(self)
		self.header = header
		self.typ = typ
		self.frmt = '5I4s4s16B'
		if not self.header:
			self['magic'] = CS_MAGIC
			self['proto'] = PROTO_VERSION
			self['seq'] = seq
			self['msg'] = typ
			self['from'] = fromip
			self['fromport'] = fromport
			self['dlen'] = dlen
			self['reserved'] = tuple([0 for i in range(16)])
		else:
			try:
				unpacked_header = struct.unpack(self.frmt, self.header)
			except struct.error:
				raise MMPParsingError("Can't unpack header", self.header)
			self['magic'] = unpacked_header[0]
			self['proto'] = unpacked_header[1]
			self['seq'] = unpacked_header[2]
			self['msg'] = unpacked_header[3]
			self['dlen'] = unpacked_header[4]
			self['from'] = socket.inet_ntoa(unpacked_header[5])
			self['fromport'] = socket.inet_ntoa(unpacked_header[6])
			self['reserved'] = unpacked_header[7:]

	def __str__(self):
		if not self.header:
			try:
				new_header = struct.pack(
					self.frmt,
					self['magic'],
					self['proto'],
					self['seq'],
					self['msg'],
					self['dlen'],
					socket.inet_aton(self['from']),
					socket.inet_aton(self['fromport']),
					*self['reserved']
				)
			except (struct.error, KeyError):
				raise MMPParsingError("Can't pack header", self)
			return new_header
		else:
			return self.header

class MMPBody(UserDict.UserDict):

	def __init__(self, typ=0, dict={}, body=''):
		UserDict.UserDict.__init__(self)
		self.dict = dict
		self.body = body
		self.typ = typ
		if self.body:
			self.io = cStringIO.StringIO(body)
			self.str2dict(body)
		elif self.dict:
			self.io = cStringIO.StringIO()
			self.update(dict)

	def __str__(self):
		if self.body:
			return self.body
		elif self.dict:
			return self.dict2str(self.dict)
		else:
			return ''

	def str2dict(self, body):
		try:
			return self._str2dict(body)
		except struct.error:
			raise MMPParsingError("Can't unpack body", body)

	def dict2str(self, dict):
		try:
			return self._dict2str(dict)
		except (struct.error, KeyError):
			raise MMPParsingError("Can't pack body", dict)

	def _str2dict(self, body):
		if self.typ == MRIM_CS_HELLO_ACK:
			self['ping_period'] = self._read_ul()
		elif self.typ == MRIM_CS_LOGIN_REJ:
			self['reason'] = self._read_lps()
		elif self.typ == MRIM_CS_MESSAGE:
			self['flags'] = self._read_ul()
			self['to'] = self._read_lps()
			self['message'] = self._read_lps()
			self['rtf-message'] = self.readl_lps()
		elif self.typ == MRIM_CS_MESSAGE_ACK:
			self['msg_id'] = self._read_ul()
			self['flags'] = self._read_ul()
			self['from'] = self._read_lps()
			self['message'] = self._read_lps()
			try:
				self['rtf-message'] = self._read_lps()
			except struct.error:
				self['rtf-message'] = ' '
		elif self.typ == MRIM_CS_MESSAGE_RECV:
			self['from'] = self._read_lps()
			self['msg_id'] = self._read_ul()
		elif self.typ == MRIM_CS_MESSAGE_STATUS:
			self['status'] = self._read_ul()
		elif self.typ == MRIM_CS_USER_STATUS:
			self['status'] = self._read_ul()
			self['user'] = self._read_lps()
		elif self.typ == MRIM_CS_LOGOUT:
			self['reason'] = self._read_ul()
		elif self.typ == MRIM_CS_CONNECTION_PARAMS:
			self['ping_period'] = self._read_ul()
		elif self.typ == MRIM_CS_ADD_CONTACT:
			self['flags'] = self._read_ul()
			self['group_id'] = self._read_ul()
			self['email'] = self._read_lps()
			self['name'] = self._read_lps()
			self['phones'] = self._read_ul()
			self['text'] = self._read_lps()
		elif self.typ == MRIM_CS_ADD_CONTACT_ACK:
			self['status'] = self._read_ul()
			current_position = self.io.tell()
			next_char = self.io.read(1)
			if next_char:
				self.io.seek(current_position)
				self['contact_id'] = self._read_ul()
			else:
				return
		elif self.typ == MRIM_CS_MODIFY_CONTACT:
			self['id'] = self._read_ul()
			self['flags'] = self._read_ul()
			self['group_id'] = self._read_ul()
			self['contact'] = self._read_lps()
			self['name'] = self._read_lps()
			self['phones'] = self._read_lps()
		elif self.typ == MRIM_CS_MODIFY_CONTACT_ACK:
			self['status'] = self._read_ul()
		elif self.typ == MRIM_CS_OFFLINE_MESSAGE_ACK:
			self['uidl'] = self._read_uidl()
			self['message'] = self._read_lps()
		elif self.typ == MRIM_CS_DELETE_OFFLINE_MESSAGE:
			self['uidl'] = self._read_uidl()
		elif self.typ == MRIM_CS_AUTHORIZE:
			self['user'] = self._read_lps()
		elif self.typ == MRIM_CS_AUTHORIZE_ACK:
			self['user'] = self._read_lps()
		elif self.typ == MRIM_CS_CHANGE_STATUS:
			self['status'] = self._read_ul()
		elif self.typ == MRIM_CS_GET_MPOP_SESSION_ACK:
			self['status'] = self._read_ul()
			self['session'] = self._read_lps()
		elif self.typ == MRIM_CS_WP_REQUEST:
			current_position = self.io.tell()
			while 1:
				next_char = self.io.read(1)
				if next_char:
					self.io.seek(current_position)
					field = self._read_ul()
					self[field] = self._read_lps()
					current_position = self.io.tell()
				else:
					break
		elif self.typ == MRIM_CS_ANKETA_INFO:
			self['status'] = self._read_ul()
			self['fields_num'] = self._read_ul()
			self['max_rows'] = self._read_ul()
			self['server_time'] = self._read_ul()
			self['fields'] = [self._read_lps() for i in range(self['fields_num'])]
			self['values'] = []
			current_position = self.io.tell()
			while 1:
				next_char = self.io.read(1)
				if next_char:
					self.io.seek(current_position)
					self['values'].append(tuple([self._read_lps() for i in range(self['fields_num'])]))
					current_position = self.io.tell()
				else:
					break
		elif self.typ == MRIM_CS_MAILBOX_STATUS:
			self['count'] = self._read_ul()
			self['sender'] = self._read_lps()
			self['subject'] = self._read_lps()
			self['unix_time'] = self._read_ul()
			self['key'] = self._read_ul()
		elif self.typ == MRIM_CS_MAILBOX_STATUS_OLD:
			self['status'] = self._read_ul()
		elif self.typ == MRIM_CS_CONTACT_LIST2:
			self['status'] = self._read_ul()
			if self['status'] == GET_CONTACTS_OK:
				self['groups_number'] = self._read_ul()
				self['groups_mask'] = self._read_lps()
				self['contacts_mask'] = self._read_lps()
				self['groups'] = [
					self._read_masked_field(self['groups_mask']) \
						for i in range(self['groups_number'])
				]
				self['contacts'] = []
				while 1:
					current_position = self.io.tell()
					next_char = self.io.read(1)
					if next_char:
						self.io.seek(current_position)
						self['contacts'].append(
							self._read_masked_field(self['contacts_mask'])
						)
					else:
						break
			else:
				self['groups_number'] = 0
				self['groups_mask'] = self['contacts_mask'] = ''
				self['groups'] = self['contacts'] = []

		elif self.typ == MRIM_CS_LOGIN2:
			self['login'] = self._read_lps()
			self['password'] = self._read_lps()
			self['status'] = self._read_ul()
			self['user_agent'] = self._read_lps()
		elif self.typ == MRIM_CS_SMS:
			self['UNKNOWN'] = self._read_ul()
			self['number'] = self._read_lps()
			self['text'] = self._read_lps()
		elif self.typ == MRIM_CS_SMS_ACK:
			self['status'] = self._read_ul()

		elif self.typ == MRIM_CS_USER_INFO:
			current_position = self.io.tell()
			while 1:
				next_char = self.io.read(1)
				if next_char:
					self.io.seek(current_position)
					field = self._read_lps()
					if field == 'MESSAGES.TOTAL':
						self['total'] = int(self._read_lps())
					elif field == 'MESSAGES.UNREAD':
						self['unread'] = int(self._read_lps())
					elif field == 'MRIM.NICKNAME':
						self['nickname'] = self._read_lps()
					else:
						self[field] = self._read_lps()
					current_position = self.io.tell()
				else:
					break

	def _dict2str(self, dict):
		self.io = cStringIO.StringIO()
		if self.typ == MRIM_CS_HELLO_ACK:
			self._write_ul(dict['ping_period'])
		elif self.typ == MRIM_CS_LOGIN_REJ:
			self._write_lps(dict['reason'])
		elif self.typ == MRIM_CS_MESSAGE:
			self._write_ul(dict['flags'])
			self._write_lps(dict['to'])
			self._write_lps(dict['message'])
			self._write_lps(dict['rtf-message'])
		elif self.typ == MRIM_CS_MESSAGE_ACK:
			self._write_ul(dict['msg_id'])
			self._write_ul(dict['flags'])
			self._write_lps(dict['from'])
			self._write_lps(dict['message'])
			self._write_lps(dict['rtf-message'])
		elif self.typ == MRIM_CS_MESSAGE_RECV:
			self._write_lps(dict['from'])
			self._write_ul(dict['msg_id'])
		elif self.typ == MRIM_CS_MESSAGE_STATUS:
			self._write_ul(dict['status'])
		elif self.typ == MRIM_CS_USER_STATUS:
			self._write_ul(dict['status'])
			self._write_lps(dict['user'])
		elif self.typ == MRIM_CS_LOGOUT:
			self._write_ul(dict['reason'])
		elif self.typ == MRIM_CS_CONNECTION_PARAMS:
			self._write_ul(dict['ping_period'])
		elif self.typ == MRIM_CS_ADD_CONTACT:
			self._write_ul(dict['flags'])
			self._write_ul(dict['group_id'])
			self._write_lps(dict['email'])
			self._write_lps(dict['name'])
			self._write_lps(dict['phones'])
			self._write_lps(dict['text'])
		elif self.typ == MRIM_CS_ADD_CONTACT_ACK:
			self._write_ul(dict['status'])
			self._write_ul(dict['contact_id'])
		elif self.typ == MRIM_CS_MODIFY_CONTACT:
			self._write_ul(dict['id'])
			self._write_ul(dict['flags'])
			self._write_ul(dict['group_id'])
			self._write_lps(dict['contact'])
			self._write_lps(dict['name'])
			self._write_lps(dict['phones'])
		elif self.typ == MRIM_CS_MODIFY_CONTACT_ACK:
			self._write_ul(dict['status'])
		elif self.typ == MRIM_CS_OFFLINE_MESSAGE_ACK:
			self._write_uidl(dict['uidl'])
			self._write_lps(dict['message'])
		elif self.typ == MRIM_CS_DELETE_OFFLINE_MESSAGE:
			self._write_uidl(dict['uidl'])
		elif self.typ == MRIM_CS_AUTHORIZE:
			self._write_lps(dict['user'])
		elif self.typ == MRIM_CS_AUTHORIZE_ACK:
			self._write_lps(dict['user'])
		elif self.typ == MRIM_CS_CHANGE_STATUS:
			self._write_ul(dict['status'])
		elif self.typ == MRIM_CS_GET_MPOP_SESSION_ACK:
			self._write_ul(dict['status'])
			self._write_lps(dict['session'])
		elif self.typ == MRIM_CS_WP_REQUEST:
			for k,v in [(p,s) for p,s in dict.items() if p != MRIM_CS_WP_REQUEST_PARAM_ONLINE]:
				self._write_ul(k)
				self._write_lps(v)
			if dict.has_key(MRIM_CS_WP_REQUEST_PARAM_ONLINE):
				self._write_ul(MRIM_CS_WP_REQUEST_PARAM_ONLINE)
				self._write_lps(dict[MRIM_CS_WP_REQUEST_PARAM_ONLINE])
		elif self.typ == MRIM_CS_ANKETA_INFO:
			self._write_ul(dict['status'])
			self._write_ul(dict['fields_num'])
			self._write_ul(dict['max_rows'])
			self._write_ul(dict['server_time'])
			for field in dict['fields']:
				self._write_lps(field)
			for value in dict['values']:
				self._write_lps(value)
		elif self.typ == MRIM_CS_MAILBOX_STATUS:
			self._write_ul(dict['status'])
		elif self.typ == MRIM_CS_LOGIN2:
			self._write_lps(dict['login'])
			self._write_lps(dict['password'])
			self._write_ul(dict['status'])
			self._write_lps(dict['user_agent'])
		elif self.typ == MRIM_CS_SMS:
			self._write_ul(dict['UNKNOWN'])
			self._write_lps(dict['number'])
			self._write_lps(dict['text'])
		self.io.seek(0)
		return self.io.read()

	def _read_ul(self):
		return struct.unpack('I', self.io.read(4))[0]

	def _read_lps(self):
		return self.io.read(self._read_ul())

	def _read_uidl(self):
		return self.io.read(8)

	def _write_ul(self, ul):
		self.io.write(struct.pack('I', ul))

	def _write_lps(self, lps):
		self._write_ul(len(lps))
		self.io.write(lps)

	def _write_uidl(self, uidl):
		self.io.write(uidl[:8])

	def _read_masked_field(self, mask):
		group = []
		for i in range(len(mask)):
			symbol = mask[i]
			if symbol == 'u':
				group.append(self._read_ul())
			elif symbol == 's':
				group.append(self._read_lps())
		return tuple(group)

class MMPPacket:

	def __init__(self,typ=0,seq=0,fromip='0.0.0.0',fromport='0',dict={},packet=''):
		self.header = ''
		self.body = ''
		self.typ = typ

		if packet:
			raw_header = packet[:44]
			try:
				magic = struct.unpack('I', raw_header[:4])[0]
			except:
				magic = 0
			if magic == CS_MAGIC:
				self.header = MMPHeader(header=raw_header)
				if self.header:
					self.typ = self.header['msg']
					dlen = self.header['dlen']
					self.body = MMPBody(typ=self.typ,body=packet[44:44+dlen])

		else:
			self.body = MMPBody(self.typ,dict)
			dlen = len(self.body.__str__())
			self.header = MMPHeader(self.typ,dlen,seq,fromip,fromport)
			self.setHeaderAttr('seq', utils.seq())

	def __str__(self):
		return self.header.__str__() + self.body.__str__()

	def getRawVersion(self):
		return self.header['proto']

	def getVersion(self):
		p = self.getRawVersion()
		return '%s.%s' % (utils.get_proto_major(p), utils.get_proto_minor(p))

	def getType(self):
		return self.header['msg']

	def getHeader(self):
		return self.header

	def getBody(self):
		return self.body

	def getBodyAttr(self, attr):
		return self.body[attr]
	
	def getHeaderAttr(self, attr):
		return self.header[attr]
	
	def setHeaderAttr(self, attr, val):
		self.header[attr] = val

	def setBodyAttr(self, attr, val):
		self.body[attr] = val
		self.body = MMPBody(self.getType(),dict=self.body)
		self.setHeaderAttr('dlen', len(self.body.__str__()))

	def setIp(self, ip):
		self.setHeaderAttr('from', ip)
	
	def setPort(self, port):
		self.setHeaderAttr('fromport', port)

	def setType(self, new_typ):
		self.setHeaderAttr['msg'] = new_typ

	def setId(self, _id):
		self.setHeaderAttr('seq', _id)

	def getId(self):
		return self.getHeaderAttr('seq')

	def setMsgId(self, msg_id):
		self.setBodyAttr('msg_id', msg_id)

	def getMsgId(self):
		if self.getBody().has_key('msg_id'):
			return self.getBodyAttr('msg_id')

class Message(MMPPacket):

	def __init__(self,to='',body=' ',flags=[],payload=None):
		if not payload:
			d = {}
			flags_sum = 0
			for f in flags:
				flags_sum += f
			d['flags'] = flags_sum & MESSAGE_USERFLAGS_MASK
			d['to'] = to
			d['message'] = body
			if MESSAGE_FLAG_RTF in flags:
				d['rtf-message'] = utils.pack_rtf(body)
			else:
				d['rtf-message'] = ' '
			MMPPacket.__init__(self,typ=MRIM_CS_MESSAGE,dict=d)
			self.setHeaderAttr('seq', utils.seq())
		else:
			MMPPacket.__init__(self,typ=payload.getType(),dict=payload.getBody())

	def getTo(self):
		return self.getBodyAttr('to')

	def getFrom(self):
		return self.getBodyAttr('from')

	def getBodyPayload(self):
		return utils.win2str(self.getBodyAttr('message'))

	def getFlags(self):
		flag_code = self.getBodyAttr('flags')
		flags = []
		for f in message_flags:
			x = flag_code & f
			if x:
				flags.append(x)
		return flags

	def hasFlag(self, flag):
		return flag in self.getFlags()

class OfflineMessage(UserDict.UserDict):

	def __init__(self, data):
		UserDict.UserDict.__init__(self)
		self.msg = email.message_from_string(data)
		self.boundary = self.msg['Boundary']
		self.payload = self.msg.get_payload().split('--%s--' % self.boundary)
		self['from'] = self.msg['From']
		self['date'] = parsedate(self.msg['Date'])
		self['subject'] = self.msg['Subject']
		self['flags'] = eval('0x'+self.msg['X-MRIM-Flags'])
		self['version'] = self.msg['Version']
		self['message'] = utils.win2str(self.payload[0].strip())
		self['rtf-message'] = self.payload[1].strip()

	def buildMessage(self):
		d = {
			'msg_id':0,
			'flags':self['flags'],
			'from':self['from'],
			'message':self.payload[0].strip(),
			'rtf-message':self['rtf-message']
		}
		m = MMPPacket(typ=MRIM_CS_MESSAGE_ACK,dict=d)
		return Message(payload=m)

	def getUTCTime(self):
		return utils.msk2utc(self['date'])

class Anketa(MMPPacket):

	def __init__(self, data):
		MMPPacket.__init__(self,packet=data)

	def getStatus(self):
		return self.getBodyAttr('status')

	def getFields(self):
		return self.getBodyAttr('fields')

	def getVCards(self):
		vcards = []
		fields = self.getFields()
		for card in self.getBodyAttr('values'):
			card_dict = {}
			for n in range(self.getBodyAttr('fields_num')):
				card_dict[fields[n]] = utils.win2str(card[n])
			vcards.append(card_dict)
		return vcards

class ContactList:

	def __init__(self, packet=None):
		self.cids = {}
		self.users = {}
		self.group = {}
		if packet:
			self.packet = packet
			self.users = self.getUsers()
			self.groups = self.getGroups()
			i = 0
			for u in self.packet.getBodyAttr('contacts'):
				_id = 20+i
				if (u[0] & CONTACT_FLAG_SMS):
					self.cids[u[6]] = _id
				else:
					self.cids[u[2]] = _id
				i += 1

	def getGroups(self):
		d = {}
		for g in self.packet.getBodyAttr('groups'):
			d[g[0]] = {'name':utils.win2str(g[1])}
		return d

	def getUsers(self):
		d = {}
		for u in self.packet.getBodyAttr('contacts'):
			contact = {
					'flags':u[0],
					'group':u[1],
					'nick':utils.win2str(u[3]),
					'server_flags':u[4],
					'status':u[5],
					'phones':u[6]
			}
			if (u[0] & CONTACT_FLAG_SMS):
				d[u[6]] = contact
			else:
				d[u[2]] = contact
		return d

	def getEmails(self):
		return self.users.keys()

	def getUserFlags(self, mail):
		return self.users[mail]['flags']

	def isValidUser(self, mail):
		return not (self.isIgnoredUser(mail) or self.isRemovedUser(mail) or self.isSMSNumber(mail))

	def isIgnoredUser(self, mail):
		flags = self.getUserFlags(mail)
		return bool(flags & CONTACT_FLAG_IGNORE)

	def isRemovedUser(self, mail):
		flags = self.getUserFlags(mail)
		return bool(flags & CONTACT_FLAG_REMOVED)

	def isSMSNumber(self, phone):
		return not utils.is_valid_email(phone)

	def getUserId(self, mail):
		return self.cids[mail]

	def setUserId(self, mail, _id):
		self.cids[mail] = _id

	def getUserStatus(self, mail):
		status = 1
		if utils.is_valid_email(mail):
			status = self.users[mail]['status']
		return status

	def setUserStatus(self, mail, status):
		self.users[mail]['status'] = status

	def getAuthFlag(self, mail):
		return self.users[mail]['server_flags']

	def setAuthFlag(self, mail, flag):
		self.users[mail]['server_flags'] = flag

	def isAuthorized(self, mail):
		return not bool(self.getAuthFlag(mail) & 0x1)

	def getUserGroup(self, mail):
		return self.users[mail]['group']

	def setUserGroup(self, mail, gid):
		self.users[mail]['group'] = gid

	def getUserNick(self, mail):
		return self.users[mail]['nick']

	def setUserNick(self, mail, nick):
		self.users[mail]['nick'] = nick

	def delUser(self, mail):
		return self.users.pop(mail)

	def delGroup(self, gid):
		return self.groups.pop(gid)

	def getGroupName(self, gid):
		name = 'unknown'
		try:
			name = self.groups[gid]
		except KeyError:
			pass
		return name

	def setGroupName(self, gid, name):
		self.groups[gid] = name

	def getGroupMembers(self, gid):
		members = []
		for u in self.users:
			if self.getUserGroup(u) == gid:
				members.append(u)
		return members

	def getPhones(self, mail):
		phones = self.users[mail]['phones']
		if phones:
			return phones.split(',')
		else:
			return []

	def setPhones(self, mail, phones):
		self.users[mail]['phones'] = ','.join(phones[:3])
