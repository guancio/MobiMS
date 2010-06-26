import socket
import btsocket
import scriptext
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import sys

messaging_handle = scriptext.load('Service.Messaging', 'IMessaging')

class ImapConversation():
   def __init__(self, conn):
      self.__conn = conn
      self.__selectedFolder = None
      
   def handle(self):
      res = self.hHelo()
      try:
         while res:
            opId, op, args = self.readMsg()
            print opId, op, args
            if not hasattr(self, "h" + op[0] + op[1:].lower()):
               res = False
            else:
               res = getattr(self, "h" + op[0] + op[1:].lower())(opId, args)
         print "EXIT CONNECTION"
         self.__conn.close()
      except:
         print "Unexpected error:", sys.exc_info()
         self.__conn.close()
         return

   def readMsg(self):
      res = self.__conn.recv(1024)
      res = res.split()
      return (res[0], res[1], res[2:])
      
   def hHelo(self, opId=None, args=None):
      self.__conn.send("* OK Guancio IMAP-Sms server server ready\r\n")
      return True

   def hCapability(self, opId, args):
      self.__conn.send("* CAPABILITY IMAP4 IMAP4rev1 AUTH=PLAIN\r\n%s OK CAPABILITY Completed\r\n" % opId)
      return True

   def hLogin(self, opId, args):
      if args[0] != "guancio" and args[1] != '"guancio"':
         return False
      self.__conn.send("%s OK User logged in\r\n" % opId)
      return True

   def hList(self, opId, args):
      path = args[0]
      pattern = args[1]
      if pattern == '""' and path == '""':
         conn.send('* LIST (\Noselect) "/" ""\r\n%s OK Completed\r\n' % opId)
         return True
      elif path == '""' and ( pattern == '"*"' or pattern == '"%"'):
         res = '* LIST (\Noinferiors) "/" "INBOX"\r\n'
         res += "%s OK Completed\r\n" % opId
         conn.send(res)
         return True
      print "pattern %s and path %s not supported" % (pattern, path)
      return False

   def hSelect(self, opId, args):
      path = args[0]
      if path != "INBOX":
         print "path %s not valid, folder not found" % path
         return False
      self.__selectedFolder = "INBOX"
      return self.hExamine(opId, args)

   def hExamine(self, opId, args):
      path = args[0]
      if path != "INBOX":
         print "path %s not valid, folder not found" % path
         return False
      messages = self.__getMessages()
      unseen = [m for m in messages if  m["Unread"]]
      recent = messages
      res = "* FLAGS (\\Seen)\r\n"
      res+= "* OK [PERMANENTFLAGS (\\Seen \\*)]\r\n"
      res+= "* %d EXISTS\r\n" % len(messages)
      res+= "* %d RECENT\r\n" % len(recent)
      res+= "* OK [UNSEEN %d]\r\n" % len(unseen)
      res+= "* OK [UIDVALIDITY 1]\r\n"
      if len(unseen) > 0:
         res+= "* OK [UIDNEXT %d]\r\n" % min([m["MessageId"] for m in unseen])
      res+= "%s OK [READ-WRITE] Completed\r\n""" % opId
      self.__conn.send(res)
      return True

   def hFetch(self, opId, args):
      print args
      startId, endId = map(int, args[0].split(":"))
      op, param = args[1:]
      messages = self.__getMessages()
      counter = 1
      res = ""
      for m in messages:
         res += "* %s FETCH (FLAGS (%s) UID %d)\r\n" % \
                (counter, "\Seen" if not m["Unread"] else "", m["MessageId"])
         counter += 1
      res += "%s OK Completed\r\n" % opId
      self.__conn.send(res)
      return True

   def hUid(self, opId, args):
      op = args[0]
      if op == 'FETCH':
         return self.__uidFetch(opId, args[1:])
      if op == 'STORE':
         return self.__uidStore(opId, args[1:])
      print "ERROR OP %s not supported into UID" % op
      return False
      
   def __uidStore(self, opId, args):
      msg_pattern, op, param = args
      new_status = None
      if op == "-FLAGS":
         new_status = u'Unread'
      elif op == "+FLAGS":
         new_status = u'Read'
      if new_status is None:
         print "ERROR OP %s not supported into UID-STORE" % op
         return False
      if param != "(\Seen)":
         print "ERROR PARAM %s not supported into UID-STORE %s" % (param, op)
         return False
      #Manage Deleted
      msg_sequences = msg_pattern.split(",")
      msg_sequences = [s.split(":") for s in msg_sequences]
      for s in msg_sequences:
         seq = []
         if len(s) == 1:
            seq.append(int(s[0]))
         else:
            seq += range(int(s[0]), int(s[1])+1)
         for s1 in seq:
            messaging_handle.call('ChangeStatus', {'MessageId': s1, 'Status': new_status})
      self.__conn.send("%s OK Completed\r\n" % opId)
      return True

   def __uidFetch(self, opId, args):
      msg_id,param = args
      if not param == '(BODY.PEEK[])':
         print "ERROR PARAM %s not supported into UID" % param
         return False
      msg_id = int(msg_id)
      msg = self.__getMessage(msg_id)
      if msg is None:
         print "ERROR MSG %d not found by UID, size " % msg_id
         return False
      m_msg = None
      if msg["MessageType"] == "SMS":
         m_msg = MIMEText(msg["BodyText"].encode('ascii', 'replace'))
      elif msg["MessageType"] == "MMS":
         m_msg = MIMEMultipart("")
         for attach in msg["AttachmentList"]:
            data = file_h.read()
            inner = MIMEApplication(data)
            inner.add_header("x-type", attach["MimeType"])
            m_msg.attach(inner)
      else:
         m_msg = MIMEText("")
      m_msg.add_header("Message-ID", "%d@n97imap" % msg_id)
      m_msg.add_header("From", '"%s"' % msg["Sender"].encode('ascii', 'replace'))
      m_msg.add_header("Subject", msg["Subject"].encode('ascii', 'replace'))

      m_msg.add_header("Date", msg["Time"].strftime("%a, %d %b %Y %H:%M:%S +0000"))
      m_msg.add_header("To", '"Roberto Guanciale"')
      res = m_msg.as_string()
      cmd  = "* %d FETCH (UID %d BODY[] {%d}\r\n" % (msg_id, msg_id, len(res))
      cmd += res + "\r\n"
      cmd += "%s OK Completed\r\n" % opId
      self.__conn.send(cmd)
      return True

   def hLogout(self, opId, args):
      return False

   def __getMessages(self):
      if not self.__selectedFolder == "INBOX":
         print "Folder %s not supported" % folder["path"]
         return []
      sms_iter = messaging_handle.call('GetList', {'Type': u'Inbox'})
      res = []
      for sms in sms_iter:
         if sms["MessageType"] == "SMS":
            res.append(sms)
      return res

   def __getMessage(self, msg_id):
      if not self.__selectedFolder == "INBOX":
         print "Folder %s not supported" % folder["path"]
         return []
      sms_iter = messaging_handle.call('GetList', {'Type': u'Inbox', 'Filter': {'MessageId': msg_id}})
      res = [sms for sms in sms_iter]
      if len(res) == 0:
         return None
      return res[0]


s=btsocket.socket(btsocket.AF_BT, btsocket.SOCK_STREAM)
port = btsocket.bt_rfcomm_get_available_server_channel(s)
s.bind(("", port))
print port
btsocket.set_security(s, btsocket.AUTH)
s.listen(1)

# HOST = ''                 # Symbolic name meaning all available interfaces
# PORT = 14310
# s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# s.bind((HOST, PORT))
# s.listen(1)

running = True
while running:
   conn, addr = s.accept()
   ImapConversation(conn).handle()
   running = False
s.close()

