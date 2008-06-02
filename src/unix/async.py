try:
    import epoll as select
except ImportError:
    import select
import socket
import heapq
import time
import os
import sys
import weakref
from errno import EALREADY, EINPROGRESS, EWOULDBLOCK, ECONNRESET, \
     ENOTCONN, ESHUTDOWN, EINTR, EISCONN, errorcode

FLAGS = select.POLLIN | select.POLLPRI | select.POLLERR | select.POLLHUP | select.POLLNVAL

try:
    socket_map
except NameError:
    socket_map = {}

try:
    pollster
except NameError:
    pollster = select.poll()

try:
    timers
except NameError:
    timers = []

class ExitNow(Exception):
    pass

def ticks():
    return os.times()[4]

def readwrite(obj, flags):
    try:
        if flags & (select.POLLIN | select.POLLPRI):
            obj.handle_read_event()
        if flags & select.POLLOUT:
            obj.handle_write_event()
        if flags & (select.POLLERR | select.POLLHUP | select.POLLNVAL):
            obj.handle_expt_event()
    except ExitNow:
        raise
    except:
        obj.handle_error()

def poll(timeout=0.0):
    timeout = int(timeout*1000)
    try:
        nfds = pollster.poll(timeout)
    except select.error, err:
        if err[0] != EINTR:
            raise
        nfds = []
    for fd, flags in nfds:
        obj = socket_map.get(fd)
        if obj:
            readwrite(obj, flags)

def loop(timeout=30.0, use_poll=True):
    maxtimeout = timeout
    while socket_map:
        poll(timeout)
        timeout = process_timers(maxtimeout)

class dispatcher:

    debug = False
    connected = False
    accepting = False
    closing = False
    addr = None
    timerref = 0

    def __init__(self, sock=None):
        self.timers = {}
        if sock:
            self.set_socket(sock)
            self.socket.setblocking(0)
            self.connected = True
            try:
                self.addr = sock.getpeername()
            except socket.error:
                pass
        else:
            self.socket = None

    def __repr__(self):
        status = [self.__class__.__module__+"."+self.__class__.__name__]
        if self.accepting and self.addr:
            status.append('listening')
        elif self.connected:
            status.append('connected')
        if self.addr is not None:
            try:
                status.append('%s:%d' % self.addr)
            except TypeError:
                status.append(repr(self.addr))
        return '<%s at %s>' % (' '.join(status), id(self))

    def add_channel(self):
        socket_map[self._fileno] = self
        pollster.register(self._fileno, FLAGS | select.POLLOUT)

    def del_channel(self):
        fd = self._fileno
        if socket_map.has_key(fd):
            del socket_map[fd]
            pollster.unregister(fd)
        self._fileno = None

    def create_socket(self, family, type):
        self.family_and_type = family, type
        self.socket = socket.socket(family, type)
        self.socket.setblocking(0)
        self._fileno = self.socket.fileno()
        self.add_channel()

    def set_socket(self, sock):
        self.socket = sock
        self._fileno = sock.fileno()
        self.add_channel()

    def set_reuse_addr(self):
        try:
            self.socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR,
                self.socket.getsockopt(socket.SOL_SOCKET,
                                       socket.SO_REUSEADDR) | 1
                )
        except socket.error:
            pass

    def gettref(self):
        dispatcher.timerref += 1
        return dispatcher.timerref

    def set_timer(self, pause, msg):
        tref = self.gettref()
        stoptime = ticks() + pause
        objref = weakref.ref(self)
        heapq.heappush(timers, (stoptime, tref, objref))
        self.timers[tref] = (stoptime, msg)
        return tref

    def cancel_timer(self, tref):
        try:
            del self.timers[tref]
        except KeyError:
            pass

    def listen(self, num):
        self.accepting = True
        if os.name == 'nt' and num > 5:
            num = 1
        return self.socket.listen(num)

    def bind(self, addr):
        self.addr = addr
        return self.socket.bind(addr)

    def async_connect(self, address):
        self.connected = False
        err = self.socket.connect_ex(address)
        # XXX Should interpret Winsock return values
        if err in (EINPROGRESS, EALREADY, EWOULDBLOCK):
            return
        if err in (0, EISCONN):
            self.addr = address
            self.connected = True
            self.handle_connect()
        else:
            raise socket.error, (err, errorcode[err])

    def accept(self):
        # XXX can return either an address pair or None
        try:
            conn, addr = self.socket.accept()
            return conn, addr
        except socket.error, why:
            if why[0] == EWOULDBLOCK:
                pass
            else:
                raise

    def async_send(self, data):
        try:
            result = self.socket.send(data)
            return result
        except socket.error, why:
            if why[0] == EWOULDBLOCK:
                return 0
            else:
                raise
            return 0

    def recv(self, buffer_size):
        try:
            data = self.socket.recv(buffer_size)
            if not data:
                # a closed connection is indicated by signaling
                # a read condition, and having recv() return 0.
                self.handle_close()
                return ''
            else:
                return data
        except socket.error, why:
            # winsock sometimes throws ENOTCONN
            if why[0] in [ECONNRESET, ENOTCONN, ESHUTDOWN]:
                self.handle_close()
                return ''
            else:
                raise

    def close(self):
        self.del_channel()
        self.timers = {}
        self.socket.close()

    # cheap inheritance, used to pass all other attribute
    # references to the underlying socket object.
    def __getattr__(self, attr):
        return getattr(self.socket, attr)

    # log and log_info may be overridden to provide more sophisticated
    # logging and warning methods. In general, log is for 'hit' logging
    # and 'log_info' is for informational, warning and error logging.

    def log(self, message):
        sys.stderr.write('log: %s\n' % str(message))

    def log_info(self, message, type='info'):
        if __debug__ or type != 'info':
            print '%s: %s' % (type, message)

    def handle_read_event(self):
        if self.accepting:
            # for an accepting socket, getting a read implies
            # that we are connected
            if not self.connected:
                self.connected = True
            self.handle_accept()
        elif not self.connected:
            self.handle_connect()
            self.connected = True
            self.handle_read()
        else:
            self.handle_read()

    def handle_write_event(self):
        # getting a write implies that we are connected
        if not self.connected:
            self.handle_connect()
            self.connected = True
        self.handle_write()

    def handle_expt_event(self):
        self.handle_expt()

    def handle_timer_event(self, tref):
        msg = self.timers.pop(tref)[1]
        self.handle_timer(tref, msg)

    def handle_error(self):
        nil, t, v, tbinfo = compact_traceback()

        # sometimes a user repr method will crash.
        try:
            self_repr = repr(self)
        except:
            self_repr = '<__repr__(self) failed for object at %0x>' % id(self)

        self.log_info(
            'uncaptured python exception, closing channel %s (%s:%s %s)' % (
                self_repr,
                t,
                v,
                tbinfo
                ),
            'error'
            )
        self.close()

    def handle_expt(self):
        self.log_info('unhandled exception', 'warning')

    def handle_read(self):
        self.log_info('unhandled read event', 'warning')

    def handle_write(self):
        self.log_info('unhandled write event', 'warning')

    def handle_connect(self):
        self.log_info('unhandled connect event', 'warning')

    def handle_accept(self):
        self.log_info('unhandled accept event', 'warning')

    def handle_close(self):
        self.log_info('unhandled close event', 'warning')
        self.close()

    def handle_timer(self, tref, msg):
        self.log_info('unhandled timer event', 'warning')

class dispatcher_with_send(dispatcher):

    def __init__(self, sock=None):
        dispatcher.__init__(self, sock)
        self.out_buffer = ''

    def initiate_send(self):
        num_sent = 0
        num_sent = dispatcher.async_send(self, self.out_buffer)
        self.out_buffer = self.out_buffer[num_sent:]
        if self.out_buffer:
            pollster.register(self._fileno, FLAGS | select.POLLOUT)
        else:
            pollster.register(self._fileno, FLAGS)

    def handle_write(self):
        self.initiate_send()

    def async_send(self, data):
        if self.debug:
            self.log_info('sending %s' % repr(data))
        self.out_buffer = self.out_buffer + data
        self.initiate_send()

# ---------------------------------------------------------------------------
# timers processing
# ---------------------------------------------------------------------------
PRECISION = 0.01

def process_timers(maxtimeout):
    while timers:
        stoptime = timers[0][0]
        now = ticks()
        if now >= stoptime:
            stoptime, tref, objref = heapq.heappop(timers)
            obj = objref()
            if obj and obj.timers.has_key(tref):
                try:
                    obj.handle_timer_event(tref)
                except ExitNow:
                    raise
                except:
                    obj.handle_error()
        else:
            timeout = max(PRECISION, stoptime-now)
            return min(timeout, maxtimeout)
    return maxtimeout

def compact_traceback():
    t, v, tb = sys.exc_info()
    tbinfo = []
    assert tb # Must have a traceback
    while tb:
        tbinfo.append((
            tb.tb_frame.f_code.co_filename,
            tb.tb_frame.f_code.co_name,
            str(tb.tb_lineno)
            ))
        tb = tb.tb_next

    # just to be safe
    del tb

    file, function, line = tbinfo[-1]
    info = ' '.join(['[%s|%s|%s]' % x for x in tbinfo])
    return (file, function, line), t, v, info

def close_all():
    for obj in socket_map.values():
        obj.close()
