import e32
import appuifw

# import sys
# sys.path.append(u"E:/data/python")

# from phone_smtp import SmtpServer

e32.ao_yield()

class MobiMSApp:
    def __init__(self):
        self.lock = e32.Ao_lock()
        self.old_title = appuifw.app.title
        appuifw.app.title = u"MobiMS"
        self.exit_flag = False
        appuifw.app.exit_key_handler = self.abort
        self.data = []
        
        appuifw.app.body = appuifw.Text(u"Loading...\n")
        
        self.menu_start_smtp = (u"Start SMTP", self.handle_start_smtp)
        self.menu_stop_smtp = (u"Stop SMTP", self.handle_stop_smtp)
        self.menu_abort = (u"Exit", self.abort)

        self._smtp = None
        self.messages = []

        appuifw.app.menu = [self.menu_abort]
        # First call to refresh() will fill in the menu.

    def initialize(self):
        #SMTP server ready to start
        self._smtp = SmtpServer()
        self._smtp.subscribe(self)
        self._smtp.start()
        self.notify()

    # Set up callback for change notifications.
    def loop(self):
        try:
            self.lock.wait()
            while not self.exit_flag:
                self.refresh()
                self.lock.wait()
        finally:
            #close SMTP
            pass

    def close(self):
        appuifw.app.menu = []
        appuifw.app.body = None
        appuifw.app.exit_key_handler = None
        appuifw.app.title = self.old_title

    def abort(self):
        # Exit-key handler.
        self.exit_flag = True
        self.notify()

    def notify(self):
        self.lock.signal()

    def refresh(self):
        appuifw.app.menu = []
        if self._smtp is not None:
            if self._smtp.running:
                appuifw.app.menu += [self.menu_stop_smtp]
            if self._smtp.ready and not self._smtp.running:
                appuifw.app.menu += [self.menu_start_smtp]
        while self.messages != []:
            appuifw.app.body.add(u"%s\n" % self.messages[0])
            self.messages = self.messages[1:]

        appuifw.app.menu += [self.menu_abort]

    def handle_start_smtp(self):
        if self._smtp is not None and \
           self._smtp.ready and \
           not self._smtp.running:
            self._smtp.startServer()

    def handle_stop_smtp(self):
        if self._smtp is not None and \
           self._smtp.running:
            self._smtp.stopServer()

def main():
    app = MobiMSApp()
    try:
        app.initialize()
        app.loop()
    finally:
        app.close()

import socket
import sys
import base64
import email
import btsocket
import scriptext
import e32
import threading

class SmtpConversation(object):
    def handle(self):
        try:
            while res:
                op, args = self.__readOp()
                print op, args
                if not hasattr(self, "h" + op[0] + op[1:].lower()):
                    print "Operation %s not supported" % op
                    res = False
                else:
                    res = getattr(self, "h" + op[0] + op[1:].lower())(args)
            print "EXIT CONNECTION"
            self.__conn.close()
        except:
            print "Unexpected error:", sys.exc_info()
            self.__conn.close()
            return

    def __readLine(self):
        found = self.__buffer.find("\r\n")
        while found < 0:
            self.__buffer += self.__conn.recv(1024)
            found = self.__buffer.find("\r\n")
        res = self.__buffer[:found+2]
        self.__buffer = self.__buffer[found+2:]
        return res

    def __readOp(self):
        res = self.__readLine()
        res = res.split()
        return (res[0], res[1:])

    def hEhlo(self, args):
        self.__conn.send("250-localhost\r\n")
        self.__conn.send("250 AUTH LOGIN PLAIN\r\n")
        return True

    def hAuth(self, args):
        method = args[0]
        auth = args[1]
        if method != "PLAIN":
            print "Authentication Method %s not supported" % method
            return False
        auth = base64.decodestring(auth).split("\0")
        if len(auth) != 3:
            print "Authentication failed"
            return False
        if auth[1] != "guancio" and auth[2] != "guancio":
            print "Authentication failed"
            return False
        self.__conn.send("235 Authentication successful\r\n")
        return True

    def hMail(self, args):
        self.__curr_mail = {}
        self.__curr_mail["FROM"] = args[0].split(":")[1]
        self.__curr_mail["TO"] = []
        self.__curr_mail["DATA"] = ""
        self.__conn.send("250 Ok\r\n")
        return True

    def hRcpt(self, args):
        flag, mail = args[0].split(":")
        if flag == "TO":
            self.__curr_mail["TO"].append(mail[1:-1])
        else:
            print "RCPT %s not supported" % flag
            return False
        self.__conn.send("250 Ok\r\n")
        return True

    def hData(self, args):
        self.__conn.send("354 End data with <CR><LF>.<CR><LF>\r\n")
        line = self.__readLine()
        while line != ".\r\n":
            self.__curr_mail["DATA"] += line
            line = self.__readLine()
        print "END DATA"
        msg = email.message_from_string(self.__curr_mail["DATA"])
        print self.__curr_mail["TO"]
        if msg.is_multipart() :
            print "Mail format not supported"
            self.__curr_mail = None
            self.__conn.send("451 Requested action aborted: error in processing\r\n")
            return False
        for number in self.__curr_mail["TO"]:
            messaging_handle.call('Send',
                                  {'MessageType': u'SMS',
                                   'To': u'%s' % number,
                                   'BodyText': u'%s' % msg.get_payload()})
        self.__conn.send("250 sent %d SMS\r\n" % len(self.__curr_mail["TO"]))
        self.__curr_mail = None
        return True

    def hQuit(self, args):
        self.__conn.send("221 Bye\r\n")
        return False

# HOST = ''
# PORT = 25000
# s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
# s.bind((HOST, PORT))
# s.listen(1)

import select

class SmtpServer(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.ready = False
        self.running = False
        self.port = None
        self.messaging_handle = None
        self.__subscriber = None
        self.__operation = None
        self.__connection = None
        self.__serv_sock = None
        self.__buffer = ""
        self.__curr_mail = None

    def subscribe(self, subscriber):
        self.__subscriber = subscriber

    def startServer(self):
        self.__operation = "START"
        self.__lock.signal()

    def stopServer(self):
        self.__operation = "STOP"
        self.__lock.signal()

    def _hStart(self):
        self.__sock_serv=btsocket.socket(btsocket.AF_BT, btsocket.SOCK_STREAM)
        self.port = btsocket.bt_rfcomm_get_available_server_channel(self.__sock_serv)
        self.__sock_serv.bind(("", self.port))
        btsocket.set_security(self.__sock_serv, btsocket.AUTH)
        self.__sock_serv.listen(1)

        self.running = True
        self.__subscriber.messages.append("SMTP Server Started")
        self.__subscriber.notify()

        self.__operation = "REACCEPT"
        self.__lock.signal()

    def _hReAccept(self):
        def handleAccept(p):
            native_socket,addr = p
            self.__connection=btsocket._socketobject(native_socket,
                                                   self.__sock_serv)
            self.__subscriber.messages.append(repr(self.__connection))
            self.__subscriber.notify()
            self.__operation = "ACCEPTED"
            self.__lock.signal()
        
        self.__sock_serv.accept(handleAccept)
        self.__subscriber.messages.append("SMTP Server Accepting Connection")
        self.__subscriber.notify()

    def _hAccepted(self):
        self.__subscriber.messages.append("SMTP Server Accepted Connection")
        self.__subscriber.notify()

        self.__connection.send("220 localhost MobiMS (Symbian)\r\n")
        
        self.__operation = "CLOSECONN"
        self.__lock.signal()

    def _hStop(self):
        # va fatto anche l'unbind
        self.__sock_serv.close()
        self.__sock_serv = None
        self.running = False
        self.__subscriber.messages.append("SMTP Server Stopped")
        self.__subscriber.notify()

    def _hCloseConn(self):
        self.__connection.close()
        self.__connection = None
        self.__subscriber.messages.append("SMTP Server Closed Connection")
        self.__subscriber.notify()

        self.__operation = "REACCEPT"
        self.__lock.signal()
        

    def run(self):
        self.__connection = None
        self.__lock = e32.Ao_lock()
        self.messaging_handle = scriptext.load('Service.Messaging', 'IMessaging')
        self.ready = True
        self.__subscriber.messages.append("SMTP Server Ready")
        self.__subscriber.notify()
        
        while True:
            self.__lock.wait()
            self.__subscriber.messages.append(self.__operation)
            self.__subscriber.notify()
            if self.__operation == "QUIT":
                self._hQuit()
            elif self.__operation == "START":
                self._hStart()
            elif  self.__operation == "ACCEPTED":
                self._hAccepted()
            elif self.__operation == "STOP":
                self._hStop()
            elif self.__operation == "CLOSECONN":
                self._hCloseConn()
            elif self.__operation == "REACCEPT":
                self._hReAccept()
            
            #SmtpConversation(conn).handle()
            #conn.close()

if __name__ == "__main__":
    main()
