import xmpp
from mmptypes import *
import i18n

class SearchForm:

	def __init__(self):
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
		self.xform = xform

	def create(self):
		return self.xform

class DiscoFeatures:

	def __init__(self, ids, features):
		self.payload = [xmpp.Node('identity',attrs=ids)]
		for ns in features:
			feature = xmpp.Node('feature', attrs={'var':ns})
			self.payload.append(feature)
	def create(self):
		return self.payload
