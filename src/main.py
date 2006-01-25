#!/usr/bin/python

import transport
import config
import signal
import urllib2
import time
import sys
import traceback
import utils

conf = config.Config()

while 1:
	try:
		xmpp_con = transport.XMPPTransport(conf.name,conf.disconame,conf.server,conf.port,conf.passwd)
		print "Connecting to XMPP server..."
		xmpp_con.run()
	except KeyboardInterrupt:
		xmpp_con.stop()
		sys.exit(0)
	except:
		traceback.print_exc()
		print "Connection to server lost"
		print "Try to reconnect over 5 seconds"
		try:
			xmpp_con.stop(notify=False)
			del xmpp_con
		except:
			traceback.print_exc()
			pass
		time.sleep(5)
