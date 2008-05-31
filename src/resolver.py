import threading
import time
import socket
import random
import Queue

try:
	qbox
except NameError:
	qbox = Queue.Queue(0)

try:
    addrs
except NameError:
    addrs = {}

def gethostbyname(name):
	try:
		return random.choice(addrs[name])
	except KeyError:
		qbox.put_nowait(name)
	except:
		pass
	return name

def resolver():
	global addrs
	while 1:
		try:
			newname = qbox.get(True, 600)
		except Queue.Empty:
			newname = None
		if newname:
			addrs[newname] = []
		for name in addrs.keys():
			try:
				res = socket.gethostbyname_ex(name)
				addrs[name] = res[2]
			except:
				pass

def start(names=[]):
	T = threading.Thread(target=resolver, name='resolver')
	T.setDaemon(True)
	T.start()
	for name in names:
		gethostbyname(name)
