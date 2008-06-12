# -*- coding: utf-8 -*-

import xmpp
from mmptypes import *
import utils
import spool
import i18n
import time
import traceback

def get_search_form():
	xform = xmpp.protocol.DataForm(typ='form', title=i18n.SEARCH)
	instr = i18n.SEARCH_INSTRUCTION
	xform.setInstructions(instr)
	
	default = xmpp.simplexml.Node('value')
	
	e_mail = xform.setField('email')
	e_mail.setAttr('label', 'E-Mail')

	mail_note = xform.setField('notes')
	mail_note.setAttr('type', 'fixed')
	mail_note.setTagData('value', i18n.SEARCH_NOTES)
	nickname = xform.setField('nick')
	nickname.setAttr('label', i18n.SEARCH_NICK)

	firstname = xform.setField('firstname')
	firstname.setAttr('label', i18n.SEARCH_NAME)

	lastname = xform.setField('lastname')
	lastname.setAttr('label', i18n.SEARCH_LASTNAME)
	
	sex = xform.setField('sex')
	sex.setAttr('type', 'list-single')
	sex.setAttr('label', i18n.SEARCH_SEX)
	sexs = [('---',''),(i18n.SEARCH_MALE,'1'),(i18n.SEARCH_FEMALE,'2')]
	sex_pool = [default]
	for k,v in sexs:
		sex_option = xmpp.simplexml.Node('option', attrs={'label':k})
		sex_option.setTagData('value', v)
		sex_pool.append(sex_option)
	sex.setPayload(sex_pool, add=1)

	country_id = xform.setField('country_id')
	country_id.setAttr('type', 'list-single')
	country_id.setAttr('label', i18n.SEARCH_COUNTRY)
	country_pool = [default]
	countries = [(v,k) for k,v in COUNTRY.items()]
	countries.append(('---', ''))
	countries.sort()
	for k,v in countries:
		country_option = xmpp.simplexml.Node('option', attrs={'label':k})
		country_option.setTagData('value', v)
		country_pool.append(country_option)
	country_id.setPayload(country_pool, add=1)

	city_id = xform.setField('city_id')
	city_id.setAttr('type', 'list-single')
	city_id.setAttr('label', i18n.SEARCH_REGION)
	city_pool = [default]
	cities = [(v,k) for k,v in CITY.items()]
	cities.append(('---', ''))
	cities.sort()
	for k,v in cities:
		city_option = xmpp.simplexml.Node('option', attrs={'label':k})
		city_option.setTagData('value', v)
		city_pool.append(city_option)
	city_id.setPayload(city_pool, add=1)
		
	bdate = xform.setField('birthdate')
	bdate.setAttr('type', 'fixed')
	bdate.setTagData('value', i18n.SEARCH_BIRTHDAY)

	bday = xform.setField('birthday')
	bday.setAttr('type', 'list-single')
	bday.setAttr('label', i18n.SEARCH_DAY)
	bday_pool = [default]
	bdays = [('---', '')]
	bdays += [(str(v),str(v)) for v in range(1,32)]
	for k,v in bdays:
		bday_option = xmpp.Node('option', attrs={'label':k})
		bday_option.setTagData('value', v)
		bday_pool.append(bday_option)
	bday.setPayload(bday_pool, add=1)
		
	bmonth = xform.setField('birthmonth')
	bmonth.setAttr('type', 'list-single')
	bmonth.setAttr('label', i18n.SEARCH_MONTH)
	bmonth_pool = [default]
	bmonths = [('', '---')]
	_bmonths = [(int(k),v) for k,v in MONTH.items()]
	_bmonths.sort()
	bmonths += _bmonths
	for k,v in bmonths:
		bmonth_option = xmpp.Node('option', attrs={'label':v})
		bmonth_option.setTagData('value', k)
		bmonth_pool.append(bmonth_option)
	bmonth.setPayload(bmonth_pool, add=1)

	zodiac = xform.setField('zodiac')
	zodiac.setAttr('type', 'list-single')
	zodiac.setAttr('label', i18n.SEARCH_ZODIAC)
	zodiac_pool = [default]
	zodiacs = [('', '---')]
	_zodiacs = [(int(k),v) for k,v in ZODIAC.items()]
	_zodiacs.sort()
	zodiacs += _zodiacs
	for k,v in zodiacs:
		zodiac_option = xmpp.Node('option', attrs={'label':v})
		zodiac_option.setTagData('value', k)
		zodiac_pool.append(zodiac_option)
	zodiac.setPayload(zodiac_pool, add=1)
		
	age = xform.setField('age')
	age.setAttr('type', 'fixed')
	age.setTagData('value', i18n.SEARCH_AGE)
		
	ot = xform.setField('age_from')
	ot.setAttr('label', i18n.SEARCH_AGE_FROM)
		
	do = xform.setField('age_to')
	do.setAttr('label', i18n.SEARCH_AGE_TO)
		
	online = xform.setField('online')
	online.setAttr('type', 'boolean')
	online.setAttr('label', i18n.SEARCH_ONLINE)

	return xform

def get_disco_features(ids, features):
	payload = [xmpp.Node('identity',attrs=ids)]
	for ns in features:
		feature = xmpp.Node('feature', attrs={'var':ns})
		payload.append(feature)
	return payload

def get_cmd_header(status, node, sess=None):
	if sess==None:
		sess = node+':'+str(time.time())
	return xmpp.Node('command', attrs={
				'xmlns':xmpp.NS_COMMANDS,
				'sessionid':sess,
				'status':status,
				'node':node
	})

def workup_search_input(mess):
	xdf = [i for i in mess.getQueryChildren() if i.getNamespace() == xmpp.NS_DATA]
	d = {}
	if not xdf:
		return d
	xdata = xmpp.protocol.DataForm(node=xdf[0])
	for k,v in xdata.asDict().items():
		if not v:
			continue
		value = utils.str2win(v.strip())
		if not value:
			continue
		if k == 'email':
			d = {}
			user = domain = ''
			try:
				user, domain = value.split('@')
			except ValueError:
				pass
			if user and domain:
				d[MRIM_CS_WP_REQUEST_PARAM_USER] = user
				d[MRIM_CS_WP_REQUEST_PARAM_DOMAIN] = domain
			return d
		elif k == 'nick':
			d[MRIM_CS_WP_REQUEST_PARAM_NICKNAME] = value
		elif k == 'firstname':
			d[MRIM_CS_WP_REQUEST_PARAM_FIRSTNAME] = value
		elif k == 'lastname':
			d[MRIM_CS_WP_REQUEST_PARAM_LASTNAME] = value
		elif k == 'sex':
			d[MRIM_CS_WP_REQUEST_PARAM_SEX] = value
		elif k == 'age_from':
			d[MRIM_CS_WP_REQUEST_PARAM_DATE1] = value
		elif k == 'age_to':
			d[MRIM_CS_WP_REQUEST_PARAM_DATE2] = value
		elif k == 'city_id':
			d[MRIM_CS_WP_REQUEST_PARAM_CITY_ID] = value
		elif k == 'country_id':
			d[MRIM_CS_WP_REQUEST_PARAM_COUNTRY_ID] = value
		elif k == 'zodiac':
			d[MRIM_CS_WP_REQUEST_PARAM_ZODIAC] = value
		elif k == 'birthmonth':
			d[MRIM_CS_WP_REQUEST_PARAM_BIRTHDAY_MONTH] = value
		elif k == 'birthday':
			d[MRIM_CS_WP_REQUEST_PARAM_BIRTHDAY_DAY] = value
		elif k == 'online' and value in ['1', 'true']:
			d[MRIM_CS_WP_REQUEST_PARAM_ONLINE] = ' '
	return d

def anketa2search(anketa):
	xdf = xmpp.protocol.DataForm(typ='result')
	f1 = xdf.setField("FORM_TYPE")
	f1.setType("hidden")
	f1.setTagData('value', xmpp.NS_SEARCH)
	reported = xmpp.Node('reported')
	items = []
	a = (
		'E-mail', 'Псевдоним', 'Имя',
		'Фамилия', 'Пол', 'Возраст', 'Статус', 'JID'
	)
	fvals = (
		'email', 'nick', 'firstname',
		'lastname', 'sex', 'age', 'status', 'jid'
	)
	for k,v in zip(a,fvals):
		if k != 'JID':
			field = xmpp.Node('field', attrs={'type':'text-single', 'label':k, 'var':v})
			reported.addChild(node=field)
		else:
			field = xmpp.Node('field', attrs={'type':'hidden', 'label':k, 'var':v})
			reported.addChild(node=field)
	xdf.addChild(node=reported)
	for record in anketa:
		item = xmpp.Node('item')
		record_field = xmpp.Node('field', attrs={'var':'jid'})
		record_field.setTagData('value',
			utils.mail2jid(record['Username']+'@'+record['Domain']))
		item.addChild(node=record_field)
		for fval in fvals:
			value = ''
			try:
				if fval == 'nick':
					value = record['Nickname']
				elif fval == 'email':
					value = record['Username']+'@'+record['Domain']
				elif fval == 'firstname':
					value = record['FirstName']
				elif fval == 'lastname':
					value = record['LastName']
				elif fval == 'sex':
					r = record['Sex']
					if r == '1':
						value = 'М'
					elif r == '2':
						value = 'Ж'
				elif fval == 'status':
					s = eval('0x0'+record['mrim_status'])
					if s == STATUS_OFFLINE:
						value = 'Отключен'
					elif s == STATUS_ONLINE:
						value = 'Онлайн'
					elif s == STATUS_AWAY:
						value = 'Отошёл'
					elif s == STATUS_FLAG_INVISIBLE:
						value = 'Невидимый'
					else:
						value = 'Нет информации'
				elif fval == 'age':
					try:
						bdate = [int(x) for x in record['Birthday'].split('-')]
						nowdate = list(time.localtime())
						age = nowdate[0] - bdate[0] - int(bdate[1:]>nowdate[1:])
						value = age
					except:
						pass
				elif fval == 'jid':
					continue
			except:
				traceback.print_exc()
			record_field = xmpp.Node('field',
				attrs={'var':fval})
			record_field.setTagData('value', value)
			item.addChild(node=record_field)
		items.append(item)
	xdf.setPayload(items,add=1)
	return xdf

def get_mail_form(notify1, notify2):
	xform = xmpp.protocol.DataForm(typ='form', title=i18n.MAIL_COMMAND)
	instr = i18n.MAIL_COMMAND_INSTRUCTION
	xform.setInstructions(instr)

	mbox_status = xform.setField('mbox_status')
	mbox_status.setAttr('type', 'boolean')
	mbox_status.setAttr('label', i18n.MAILBOX_STATUS)
	mbox_status.setTagData('value', notify1)

	notify_new_mail = xform.setField('new_mail')
	notify_new_mail.setAttr('type', 'boolean')
	notify_new_mail.setAttr('label', i18n.NOTIFY_NEW_MAIL)
	notify_new_mail.setTagData('value', notify2)

	return xform

def gate_sms_form():
	xform = xmpp.protocol.DataForm(typ='form', title=i18n.GATE_SMS_COMMAND)
	instr = i18n.GATE_SMS_COMMAND_INSTRUCTION
	xform.setInstructions(instr)

	number = xform.setField('number')
	number.setAttr('label', i18n.NUMBER)

	text = xform.setField('text')
	text.setAttr('type', 'text-multi')
	text.setAttr('label', i18n.TEXT)

	translit = xform.setField('translit')
	translit.setAttr('type', 'boolean')
	translit.setAttr('label', i18n.TRANSLIT)
	translit.setTagData('value', '0')

	return xform

def user_sms_form(numbers):
	xform = xmpp.protocol.DataForm(typ='form', title=i18n.GATE_SMS_COMMAND)
	instr = i18n.GATE_SMS_COMMAND_INSTRUCTION
	xform.setInstructions(instr)

	phone = xform.setField('number')
	phone.setAttr('type', 'list-single')
	phone.setAttr('label', i18n.NUMBER)
	phs = [(x,x) for x in numbers]
	default = xmpp.Node('value')
	default.setData(numbers[0])
	phone_pool = [default]
	for k,v in phs:
		phone_option = xmpp.Node('option', attrs={'label':k})
		phone_option.setTagData('value', v)
		phone_pool.append(phone_option)
	phone.setPayload(phone_pool, add=1)

	text = xform.setField('text')
	text.setAttr('type', 'text-multi')
	text.setAttr('label', i18n.TEXT)

	translit = xform.setField('translit')
	translit.setAttr('type', 'boolean')
	translit.setAttr('label', i18n.TRANSLIT)
	translit.setTagData('value', '0')

	return xform

def conf_sms_form(numbers):
	xform = xmpp.protocol.DataForm(typ='form', title=i18n.CONFIGURE_SMS_COMMAND)
	instr = i18n.GATE_SMS_COMMAND_INSTRUCTION
	xform.setInstructions(instr)

	n = [xform.setField(str(x)) for x in range(3)]
	for i in range(3):
		n[i].setAttr('label', i18n.NUMBER+' '+str(i+1))
		if len(numbers)>i:
			n[i].setTagData('value', numbers[i])

	return xform

def process_mail_command_xdata(jid, xdata):
	fields = validate_mail_command_xdata(xdata)
	if not fields:
		return False
	mbox_status = fields['mbox_status']
	new_mail = fields['new_mail']
	options = spool.Options(jid)
	options.setNewMail(new_mail)
	options.setMboxStatus(mbox_status)
	return True

def validate_mail_command_xdata(xdata):
	ns = xdata.getNamespace()
	typ = xdata.getAttr('type')
	data = {}
	if ns==xmpp.NS_DATA and typ=='submit':
		d = xmpp.protocol.DataForm(node=xdata).asDict()
		for k,v in d.items():
			if v not in ['0', '1']:
				continue
			if k in ['mbox_status', 'new_mail']:
				data[k] = v
	if len(data.keys())==2:
		return data

def process_send_sms_xdata(xdata):
	ret_code = False
	fields = validate_send_sms_xdata(xdata)
	if not fields:
		result = i18n.BAD_XDATA
	else:
		number = fields['number']
		text = fields['text']
		translit = fields['translit']
		if utils.is_valid_sms_number(number):
			enc_text = utils.str2win(text)
			if translit=='1':
				enc_text = utils.translit(enc_text)
			if utils.is_valid_sms_text(enc_text):
				ret_code = True
				result = [number, enc_text]
			else:
				result = i18n.TOO_BIG_SMS_TEXT
		else:
			result = i18n.INCORRECT_SMS_NUMBER
	return (ret_code, result)

def validate_send_sms_xdata(xdata):
	ns = xdata.getNamespace()
	typ = xdata.getAttr('type')
	data = {}
	if ns==xmpp.NS_DATA and typ=='submit':
		d = xmpp.protocol.DataForm(node=xdata).asDict()
		fields = [x for x in xdata.getChildren() if x.getName()=='field']
		sms_text = ''
		for elem in fields:
			if elem.getAttr('var')=='text':
				sms_text = '\n'.join([x.getData() for x in elem.getChildren() if x.getName()=='value'])
		for k,v in d.items():
			if k=='number' and v!=None:
				data[k] = v.strip()
			elif k=='text' and sms_text.strip():
				data[k] = sms_text
			elif k=='translit' and v in ['0','1']:
				data[k] = v
	if len(data.keys())==3:
		return data

def process_conf_sms_xdata(xdata):
	ret_code = False
	fields = validate_conf_sms_xdata(xdata)
	for n in fields:
		if not utils.is_valid_sms_number(n):
			result = i18n.INCORRECT_SMS_NUMBER
			return (False, result)
	return (True, fields)

def validate_conf_sms_xdata(xdata):
	ns = xdata.getNamespace()
	typ = xdata.getAttr('type')
	data = []
	if ns==xmpp.NS_DATA and typ=='submit':
		d = xmpp.protocol.DataForm(node=xdata).asDict()
		for i in range(3):
			if d.has_key(str(i)):
				v = d[str(i)]
				if v!=None and v.strip():
					data.append(v.strip())
	return data
