import socket
from bluetooth import *
from threading import *

HOST = ''                 # Symbolic name meaning all available interfaces
PORT = 25000
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind((HOST, PORT))
s.listen(1)

conn, addr = s.accept()

try:
    s1=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s1.connect(("mail.netfarm.it", 25))

    class Server(Thread):
        def run(self):
            while True:
                res = s1.recv(2048)
                if len(res) == 0:
                    break
                print res
                conn.send(res)
    Server().start()
                
    while True:
        op = conn.recv(12000)
        if len(op) == 0:
            break
        print op
        s1.send(op)

except:
   print "Unexpected error:", sys.exc_info()[0]
   if conn is not None:
      conn.close()
   s.close()
   raise
s.close()
