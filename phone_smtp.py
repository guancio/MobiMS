import sys
import base64
import email


class SmtpService():
    def __init__(self):
        pass

class SmsService(SmtpService):
    def __init__(self):
        import scriptext
        self.__messaging_handle = scriptext.load('Service.Messaging', 'iMessaging')
    def self(self, msg, addresses):
        for addr in addresses:
            self.__messaging_handle.call('Send',
                                         {'MessageType': u'SMS',
                                          'To': u'%s' % addr,
                                          'BodyText': u'%s' % msg.get_payload()})
        return 0

class FsService(SmtpService):
    def __init__(self):
        pass
    def send(self, msg, addresses):
        import time
        for addr in addresses:
            f = open("/tmp/%d.%s" % (time.time(), addr), "w")
            f.write(msg.as_string())
            f.close()

class SmtpConversation(object):
    def __init__(self, conn, server):
        self.__conn = conn
        self.__buffer = ""
        self.__curr_mail = None
        self.__server = server

    def handle(self):
        res = self.hHelo()
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

    def hHelo(self):
        self.__conn.send("220 localhost MobiMS (Symbian)\r\n")
        return True

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
        self.__server.get_service().send(msg, self.__curr_mail['TO'])
        self.__conn.send("250 sent %d SMS\r\n" % len(self.__curr_mail["TO"]))
        self.__curr_mail = None
        return True

    def hQuit(self, args):
        self.__conn.send("221 Bye\r\n")
        return False

class SmtpServer:
    BT, WIFI = range(2)
    SMS, FS = range(2)

    def __init__(self, method, service):
        self.__method = method
        if self.__method == SmtpServer.BT:
            import btsocket
            self.__sock_pkg = btsocket
        if self.__method == SmtpServer.WIFI:
            import socket
            self.__sock_pkg = socket

        self.__service = None
        if service == SmtpServer.SMS:
            self.__service = SmsService()
        elif service == SmtpServer.FS:
            self.__service = FsService()

    def run(self):
        s = None
        if self.__method == SmtpServer.WIFI:
            s = self.__sock_pkg.socket(self.__sock_pkg.AF_INET, self.__sock_pkg.SOCK_STREAM)
            s.setsockopt(self.__sock_pkg.SOL_SOCKET, self.__sock_pkg.SO_REUSEADDR, 1)
            s.bind(('', 25000))
        if self.__method == SmtpServer.BT:
            s=self.__sock_pkg.socket(self.__sock_pkg.AF_BT, self.__sock_pkg.SOCK_STREAM)
            port = self.__sock_pkg.bt_rfcomm_get_available_server_channel(s)
            s.bind(("", port))
            print port
            self.__sock_pkg.set_security(s, self.__sock_pkg.AUTH)
        s.listen(1)

        running = True
        while running:
            conn, addr = s.accept()
            SmtpConversation(conn, self).handle()
            running = False
        s.close()

    def get_service(self):
        return self.__service

method = SmtpServer.BT
service = SmtpServer.SMS
for arg in sys.argv:
    if arg == "--bt":
        method = SmtpServer.BT
    elif arg == "--wifi":
        method = SmtpServer.WIFI
    elif arg == "--sms":
        service = SmtpServer.SMS
    elif arg == "--fs":
        service = SmtpServer.FS

server = SmtpServer(method, service)
server.run()
