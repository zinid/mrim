# -*- coding: utf-8 -*-
# Pythonized version of C-header with some additions (country/region/zodiac codes)

PROTO_VERSION_MAJOR = 1L
PROTO_VERSION_MINOR = 9L
PROTO_VERSION = (PROTO_VERSION_MAJOR << 16) | (PROTO_VERSION_MINOR)

CS_MAGIC = 0xDEADBEEFL		# Клиентский Magic ( C <-> S )

MRIM_CS_HELLO = 0x1001		# C -> S
MRIM_CS_HELLO_ACK = 0x1002	# S -> C
MRIM_CS_LOGIN_ACK = 0x1004	# S -> C
MRIM_CS_LOGIN_REJ = 0x1005	# S -> C
MRIM_CS_PING = 0x1006		# C -> S

########
MRIM_CS_MESSAGE = 0x1008	# C -> S
'''
	UL flags
	LPS to
	LPS message
	LPS rtf-formatted message (>=1.1)
'''
MESSAGE_FLAG_OFFLINE = 0x00000001
MESSAGE_FLAG_NORECV = 0x00000004
MESSAGE_FLAG_AUTHORIZE = 0x00000008	# X-MRIM-Flags: 00000008
MESSAGE_FLAG_SYSTEM = 0x00000040
MESSAGE_FLAG_RTF = 0x00000080
MESSAGE_FLAG_CONTACT = 0x00000200
MESSAGE_FLAG_NOTIFY = 0x00000400
MESSAGE_FLAG_SMS = 0x00000800
MESSAGE_FLAG_MULTICAST = 0x00001000
MESSAGE_FLAG_SMS_STATUS = 0x00002000
##############

MAX_MULTICAST_RECIPIENTS = 50
MESSAGE_USERFLAGS_MASK = 0x00003688	# Flags that user is allowed to set himself
MESSAGE_SERVERFLAGS_MASK = 0x000016CD

MRIM_CS_MESSAGE_ACK = 0x1009		# S -> C
'''
	UL msg_id
	UL flags
	LPS from
	LPS message
	LPS rtf-formatted message (>=1.1)
'''

MRIM_CS_MESSAGE_RECV = 0x1011		# C -> S
'''
	LPS from
	UL msg_id
'''

####################################
MRIM_CS_MESSAGE_STATUS = 0x1012		# S -> C
'''
	UL status
'''
MESSAGE_DELIVERED = 0x0000			# Message delivered directly to user
MESSAGE_REJECTED_NOUSER = 0x8001		# Message rejected - no such user
MESSAGE_REJECTED_LIMIT_EXCEEDED = 0x8004	# Offline messages limit exceeded
MESSAGE_REJECTED_TOO_LARGE = 0x8005		# Message is too large
MESSAGE_REJECTED_DENY_OFFMSG = 0x8006		# User does not accept offline messages
####################################

####################################
MRIM_CS_USER_STATUS = 0x100F		# S -> C
'''
	UL status
'''
STATUS_OFFLINE = 0x00000000
STATUS_ONLINE = 0x00000001
STATUS_AWAY = 0x00000002
STATUS_UNDETERMINATED = 0x00000003
STATUS_FLAG_INVISIBLE = 0x80000000L
'''
	LPS user
'''
####################################

####################################
MRIM_CS_LOGOUT = 0x1013			# S -> C
'''
	UL reason
'''
LOGOUT_NO_RELOGIN_FLAG = 0x0010			# Logout due to double login
####################################

MRIM_CS_CONNECTION_PARAMS = 0x1014		# S -> C

####################################
MRIM_CS_ADD_CONTACT = 0x1019			# C -> S
'''
	UL flags (group(2) or usual(0) 
	UL group id (unused if contact is group)
	LPS contact
	LPS name
'''
CONTACT_FLAG_REMOVED   = 0x00000001
CONTACT_FLAG_GROUP     = 0x00000002
CONTACT_FLAG_INVISIBLE = 0x00000004
CONTACT_FLAG_VISIBLE   = 0x00000008
CONTACT_FLAG_IGNORE    = 0x00000010
CONTACT_FLAG_SHADOW    = 0x00000020
CONTACT_FLAG_SMS       = 0x00100000
####################################

MRIM_CS_USER_INFO = 0x1015			# S -> C

####################################
MRIM_CS_ADD_CONTACT_ACK = 0x101A		# S -> C
'''
	UL status
	UL contact_id or (u_long)-1 if status is not OK
'''
CONTACT_OPER_SUCCESS = 0x0000
CONTACT_OPER_ERROR = 0x0001
CONTACT_OPER_INTERR = 0x0002
CONTACT_OPER_NO_SUCH_USER = 0x0003
CONTACT_OPER_INVALID_INFO = 0x0004
CONTACT_OPER_USER_EXISTS = 0x0005
CONTACT_OPER_GROUP_LIMIT = 0x6
####################################

MRIM_CS_MODIFY_CONTACT = 0x101B			#C -> S
'''
	UL id
	UL flags - same as for MRIM_CS_ADD_CONTACT
	UL group id (unused if contact is group)
	LPS contact
	LPS name
	LPS sms numbers
'''

MRIM_CS_MODIFY_CONTACT_ACK = 0x101C		# S -> C
'''
	UL status, same as for MRIM_CS_ADD_CONTACT_ACK
'''

MRIM_CS_OFFLINE_MESSAGE_ACK = 0x101D		# S -> C
'''
	UIDL
	LPS offline message
'''

MRIM_CS_DELETE_OFFLINE_MESSAGE = 0x101E		# C -> S
'''
	UIDL
'''

MRIM_CS_AUTHORIZE = 0x1020			# C -> S
'''
	LPS user
'''

MRIM_CS_AUTHORIZE_ACK = 0x1021			# S -> C
'''
	LPS user
'''

MRIM_CS_CHANGE_STATUS = 0x1022			# C -> S
'''
	UL new status
'''

MRIM_CS_GET_MPOP_SESSION = 0x1024		# C -> S

########################################
MRIM_CS_GET_MPOP_SESSION_ACK = 0x1025			# S -> C
MRIM_GET_SESSION_FAIL = 0
MRIM_GET_SESSION_SUCCESS = 1
'''
	UL status 
	LPS mpop session
'''
########################################

########################################
MRIM_CS_WP_REQUEST = 0x1029			# C->S
'''
	DWORD field, LPS value
'''
MRIM_CS_WP_REQUEST_PARAM_USER = 0x00
MRIM_CS_WP_REQUEST_PARAM_DOMAIN = 0x01
MRIM_CS_WP_REQUEST_PARAM_NICKNAME = 0x02
MRIM_CS_WP_REQUEST_PARAM_FIRSTNAME = 0x03
MRIM_CS_WP_REQUEST_PARAM_LASTNAME = 0x04
MRIM_CS_WP_REQUEST_PARAM_SEX = 0x05
MRIM_CS_WP_REQUEST_PARAM_BIRTHDAY = 0x06
MRIM_CS_WP_REQUEST_PARAM_DATE1 = 0x07
MRIM_CS_WP_REQUEST_PARAM_DATE2 = 0x08
#!!!!!!!!!!!!!!!!!!!online request param must be at end of request!!!!!!!!!!!!!!!
MRIM_CS_WP_REQUEST_PARAM_ONLINE = 0x09
MRIM_CS_WP_REQUEST_PARAM_STATUS = 0x0a		#we do not used it, yet
MRIM_CS_WP_REQUEST_PARAM_CITY_ID = 0x0b
MRIM_CS_WP_REQUEST_PARAM_ZODIAC = 0x0c
MRIM_CS_WP_REQUEST_PARAM_BIRTHDAY_MONTH = 0x0d
MRIM_CS_WP_REQUEST_PARAM_BIRTHDAY_DAY = 0x0e
MRIM_CS_WP_REQUEST_PARAM_COUNTRY_ID = 0x0f
MRIM_CS_WP_REQUEST_PARAM_MAX = 0x10
########################################

PARAMS_NUMBER_LIMIT = 50
PARAM_VALUE_LENGTH_LIMIT = 64

########################################
MRIM_CS_ANKETA_INFO = 0x1028			# S->C
'''
	DWORD status
'''
MRIM_ANKETA_INFO_STATUS_OK = 1
MRIM_ANKETA_INFO_STATUS_NOUSER = 0
MRIM_ANKETA_INFO_STATUS_DBERR = 2
MRIM_ANKETA_INFO_STATUS_RATELIMERR = 3
'''
	DWORD fields_num				
	DWORD max_rows
	DWORD server_time sec since 1970 (unixtime)
	fields set 				//%fields_num == 0
	values set 				//%fields_num == 0
	LPS value (numbers too)
'''
########################################

#MRIM_CS_MAILBOX_STATUS = 0x1033
#'''
#	DWORD new messages in mailbox
#'''

MRIM_CS_MAILBOX_STATUS = 0x1048			# S -> C
'''
	UL - message number
	LPS - sender
	LPS - subject
	UL - unix_time
	UL - unknown
'''

MRIM_CS_MAILBOX_STATUS_OLD = 0x1033		# S -> C

########################################
MRIM_CS_CONTACT_LIST2 = 0x1037			#S->C
'''
	UL status
'''
GET_CONTACTS_OK = 0x0000
GET_CONTACTS_ERROR = 0x0001
GET_CONTACTS_INTERR = 0x0002
'''
	DWORD status  - if ...OK than this staff:
	DWORD groups number
	mask symbols table:
	's' - lps
	'u' - unsigned long
	'z' - zero terminated string 
	LPS groups fields mask 
	LPS contacts fields mask 
	group fields
	contacts fields
	groups mask 'us' == flags, name
	contact mask 'uussuu' flags, flags, internal flags, status
'''
########################################

MRIM_CS_LOGIN2 = 0x1038				# C -> S

MAX_CLIENT_DESCRIPTION = 256
'''
	LPS login
	LPS password
	DWORD status
	+ statistic packet data: 
		LPS client description //max 256
'''

# Not described in protocol! (mail.ru sucks)
#MRIM_CS_FILE_TRANSFER = 0x1026			# S -> C
MRIM_CS_SMS = 0x1039
'''
	UL - unknown
	LPS - number
	LPS - text
'''
MRIM_CS_SMS_ACK = 0x1040
'''
	UL - status
'''

ZODIAC = {
	'1':'Овен',
	'2':'Телец',
	'3':'Близнецы',
	'4':'Рак',
	'5':'Лев',
	'6':'Дева',
	'7':'Весы',
	'8':'Скорпион',
	'9':'Стрелец',
	'10':'Козерог',
	'11':'Водолей',
	'12':'Рыбы'
}

MONTH = {
	'1':'Январь',
	'2':'Февраль',
	'3':'Март',
	'4':'Апрель',
	'5':'Май',
	'6':'Июнь',
	'7':'Июль',
	'8':'Август',
	'9':'Сентябрь',
	'10':'Октябрь',
	'11':'Ноябрь',
	'12':'Декабрь'
}

COUNTRY = {
	'24':'Россия',
	'123':'Австралия',
	'40':'Австрия',
	'81':'Азербайджан',
	'82':'Армения',
	'340':'Белоруссия',
	'38':'Бельгия',
	'41':'Болгария',
	'45':'Великобритания',
	'44':'Венгрия',
	'46':'Германия',
	'48':'Греция',
	'83':'Грузия',
	'49':'Дания',
	'86':'Израиль',
	'95':'Индия',
	'50':'Ирландия',
	'51':'Исландия',
	'34':'Испания',
	'52':'Италия',
	'84':'Казахстан',
	'138':'Канада',
	'107':'Кипр',
	'92':'Киргизия (Кыргызстан)',
	'76':'Китай',
	'29':'Корея (КНДР)',
	'108':'Корея, республика',
	'53':'Латвия',
	'54':'Литва',
	'59':'Молдавия',
	'60':'Нидерланды',
	'130':'Новая Зеландия',
	'61':'Норвегия',
	'62':'Польша',
	'35':'Португалия',
	'63':'Румыния',
	'139':'США',
	'74':'Сербия и Черногория',
	'65':'Словакия',
	'66':'Словения',
	'91':'Таджикистан',
	'90':'Туркмения',
	'77':'Турция',
	'93':'Узбекистан',
	'39':'Украина',
	'68':'Финляндия',
	'37':'Франция',
	'69':'Хорватия',
	'70':'Чехия',
	'71':'Швейцария',
	'72':'Швеция',
	'73':'Эстония',
	'225':'ЮАР',
	'75':'Япония'
}

CITY = {
	'25':'Москва',
	'293':'Московская область',
	'226':'Санкт-Петербург',
	'257':'Ленинградская область',
	'262':'Агинский Бурятский АО',
	'301':'Адыгея',
	'263':'Алтай (Республика)',
	'264':'Алтайский край',
	'227':'Амурская область',
	'252':'Архангельская область',
	'302':'Астраханская область',
	'237':'Башкортостан',
	'284':'Белгородская область',
	'285':'Брянская область',
	'265':'Бурятия',
	'286':'Владимирская область',
	'303':'Волгоградская область',
	'253':'Вологодская область',
	'287':'Воронежская область',
	'304':'Дагестан',
	'228':'Еврейская АО',
	'288':'Ивановская область',
	'305':'Ингушетия',
	'266':'Иркутская область',
	'306':'Кабардино-Балкария',
	'254':'Калининградская область',
	'307':'Калмыкия',
	'289':'Калужская область',
	'229':'Камчатская область',
	'308':'Карачаево-Черкессия',
	'255':'Карелия',
	'267':'Кемеровская область',
	'238':'Кировская область',
	'256':'Коми',
	'239':'Коми-Пермяцкий АО',
	'230':'Корякский АО',
	'290':'Костромская область',
	'309':'Краснодарский край',
	'268':'Красноярский край',
	'278':'Курганская область',
	'291':'Курская область',
	'292':'Липецкая область',
	'231':'Магаданская область',
	'240':'Марий-Эл',
	'241':'Мордовия',
	'258':'Мурманская область',
	'259':'Ненецкий АО',
	'242':'Нижегородская область',
	'260':'Новгородская область',
	'269':'Новосибирская область',
	'270':'Омская область',
	'243':'Оренбургская область',
	'294':'Орловская область',
	'244':'Пензенская область',
	'245':'Пермская область',
	'232':'Приморский край',
	'261':'Псковская область',
	'310':'Ростовская область',
	'295':'Рязанская область',
	'246':'Самарская область',
	'247':'Саратовская область',
	'233':'Саха (Якутия)',
	'234':'Сахалинская область',
	'279':'Свердловская область',
	'311':'Северная Осетия - Алания',
	'296':'Смоленская область',
	'312':'Ставропольский край',
	'271':'Таймырский АО',
	'297':'Тамбовская область',
	'248':'Татарстан',
	'298':'Тверская область',
	'272':'Томская область',
	'299':'Тульская область',
	'273':'Тыва',
	'280':'Тюменская область',
	'249':'Удмуртия',
	'250':'Ульяновская область',
	'274':'Усть-Ордынский Бурят. АО',
	'235':'Хабаровский край',
	'275':'Хакасия',
	'281':'Ханты-Мансийский АО',
	'282':'Челябинская область',
	'313':'Чечня',
	'276':'Читинская область',
	'251':'Чувашия',
	'236':'Чукотский АО',
	'277':'Эвенкийский АО',
	'283':'Ямало-Ненецкий АО',
	'300':'Ярославская область'
}
