from twisted.internet import protocol, reactor, inotify, epollreactor
from twisted.python import filepath
from twisted.protocols import basic

import sys
import select
import os
import zipfile
import tty
import termios

import hash
import time
import ast


HOST = '127.0.0.1'
# HOST = '128.143.69.241'
PORT = 3240

"""
TODO (ignore if not jyo):
0. upload directories (remember directories are recursive)
1. Read for a user-config file, that contains the directory. If empty, create/watch new directory and
add it to the user-config file (for future uses)

2. Upon startup, read through the local directory and synchronize (how exactly? discuss with team)
3. Server Side: Keep track of "last_modified" file

4. (unsure if this is needed) Set up active (upload/dl) and inactive states. This might be needed to make sure that a client isn't 
trying to upload a file as it's downloading
"""

class TSClntProtocol(basic.LineReceiver):
    delimiter = '\n'
    def __init__(self):
        self.allowed = False
        self.user = None
        self.passwordGuess = False
        self.newPassword = False
        self.notifier = inotify.INotify()
        self.notifier.startReading()
        # prompt for directory if doesn't exit

        # Future Implementation: Nested Directory monitor
        # self.notifier.watch(filepath.FilePath("Data/"), callbacks=[self.notify])
        # self.input = True
        self.dir = "Data/"
        os.chdir(self.dir)
        self.input_text = ""
        self.serverFileMap = None
        self.userFileMap = None

    def sendData(self,args):
        """
        Our own method, does NOT override anything in base class.
        Get data from keyboard and send to the server.
        """
        if len(args) > 1:
            fname=os.path.basename(args[1])
        # CODE HERE IS NOT USED. SO I COMMENTED IT TO NOT CAUSE CONFUSION
        #if currently trying to guess current password to make change
        # if len(args) == 1 and args[0] == "current-pass":
        #     guess = raw_input("current password:")
        #     data = "pw-guess " + guess+'\n'
        #     self.transport.write(data)
        #     # self.passwordGuess = False
        # # if guessed password is correct as for new password
        # elif len(args) == 1 and args[0] == "new-pass":
        #     newPw = raw_input("new password:")
        #     data = "new-pw " + newPw+'\n'
        #     self.transport.write(data)
        #     # self.newPassword = False

        if len(args) == 2 and args[0] == "upload-request":
            try:
                file_path = args[1]
                print file_path
                size = os.path.getsize(file_path)
                print size
                last_modified = time.ctime(os.path.getmtime(file_path))
                print last_modified
                with open(file_path) as f:
                    hashedContents = hash.sha256_file(f)
                # string = "upload-request "+fname+","+str(size)+","+last_modified+","+file_path+","+hashedContents+"\n"
                # print string
                self.transport.write("upload-request "+fname+","+str(size)+","+last_modified+
                    ","+file_path+","+hashedContents+"\n")

            except Exception, e:
                print "upload-request error:",e
                 
        elif len(args)== 2 and args[0] == "upload":
            try:
                print "fname:",fname
                print "args[1]:",args[1]
                file_path = args[1]
                size = os.path.getsize(file_path)
                last_modified = time.ctime(os.path.getmtime(file_path))
                with open(file_path) as f:
                    hashedContents = hash.sha256_file(f)

                # Check if upload is required
                # if file_path in self.userFileMap and hashedContents == self.userFileMap[file_path][1]:
                #     pass
                # else:
                if os.path.isdir(args[1]):
                    fname = fname+".zip"
                    self.compress_directory(args[1],fname)
                
                #update my usertoFileMap
                self.userFileMap[file_path] = os.path.getmtime(file_path),hashedContents,size

                self.transport.write("upload "+fname+","+str(size)+","+last_modified+","+file_path+","+hashedContents+",\n")
                self.setRawMode()
                # fname not in the data/ directory
                for chunks in self.file_iterator(fname):
                    self.transport.write(chunks)
                # self.transport.write('/r/n')
                self.setLineMode()
                # time.sleep(10)

                    # self.transport.write("upload "+fname+","+str(size)+","+last_modified+","+file_path+","+hashedContents+"\n")
                    # if os.path.isdir(args[1]):
                    #     fname = fname+".zip"
                    #     self.compress_directory(args[1],fname)
                    # # Compare file with userFileMap
                    # self.transport.write("upload "+fname+","+str(size)+"\n")
                    # #update my usertoFileMap
                    # self.setRawMode()
                    # # fname not in the data/ directory
                    # for chunks in self.file_iterator(fname):
                    #     self.transport.write(chunks)
                    # # self.transport.write('\r\n')
                    # # remove zip (not implemented yet for testing purpose)
                    # self.setLineMode()
            except Exception, e:
                print e,'cannot open', args[1]
        elif len(args) == 1 and args[0] == "synch":
            print "reached here"
            self.transport.write('synch\n')
            self.setRawMode()
        elif len(args)==2 and args[0] == "remove":
            data = "remove "+fname+'\n'
            print data
            self.transport.write(data)
        else:
            pass

    def compress_directory(self,directory,zipname):
      print directory,zipname
      relroot = os.path.abspath(os.path.join(directory, os.pardir))
      with zipfile.ZipFile(zipname, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(directory):
          # add directory 
          z.write(root, os.path.relpath(root, relroot))
          for file in files:
            filename = os.path.join(root, file)
            if os.path.isfile(filename): # regular files only
              arcname = os.path.join(os.path.relpath(root, relroot), file)
              z.write(filename, arcname)

    def file_iterator(self,file, buff_size=4096):
        with open(file, 'rb') as f:
            while True:
                data_buff = f.read(buff_size)
                if data_buff:
                    yield data_buff
                else:
                    break

    def authenticate(self):
        command = raw_input("Enter 1 or 2\n1. Create new User\n2. Login as existing User\n")
        if command == '1':
            user = raw_input("username: ")
            password = raw_input("password: ")
            write_str = "user-create "+user+" "+password+'\n'
            self.transport.write(write_str)
        if command == '2':
            user = raw_input("username: ")
            password = raw_input("password: ")
            self.transport.write("login "+user+" "+password+'\n')
            self.user = user

    def isData(self):
        return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])

    # Non-blocking shell... not working yet! (maybe make a new thread)
    def startShell2(self):

        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())
            print '>'
            # print self.input
            while 1:
                # self.notifier.watch(filepath.FilePath("Data/"), callbacks=[self.notify])
                # print c
                if self.isData():
                    c = sys.stdin.read(1)
                    self.input_text += c  
                    if self.input_text == 'quit':         # x1b is ESC
                        print "I QUIT"
                        self.input_text = ""
                        # break
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    # make this nonblocking (jyo and garbo)
    def startShell(self):
        # print '>'
        # select.select([sys.stdin], [], [])
        # line = sys.stdin.readline()
        # if line:
        #     self.transport.write(line+'\n')
        # else:
        #     sys.exit(0)
        #     self.transport.loseConnection()
        data = raw_input('> ')
        args = data.split(' ')
        if data:
            self.transport.write(data)
        # else:
        #     self.transport.loseConnection() # if no data input, close connection

    def connectionMade(self):
        """ what we'll do when connection first made """
        self.setLineMode()
        self.authenticate()
        # self.startShell()

    # serverFilemap needs size TODO
    def rawDataReceived(self, data):
        self.serverFileMap = None
        str = ""
        # print data
        # maybe add size?
        if data.endswith("}"):
            str = str + data
            # print str
            self.serverFileMap = ast.literal_eval(str)
            self.setLineMode()
            self.updateFiles()
        else:
            str = str + data

    def createUserFileMap(self):
        files = []
        subdirs = []
        # already in current directory
        path = "."
        for root, dirs, filenames in os.walk(path):
            for subdir in dirs:
                subdirs.append(os.path.relpath(os.path.join(root, subdir), path))
            for f in filenames:
                files.append(os.path.relpath(os.path.join(root, f), path))
        index = {}
        for f in files:
            # print f, os.path.join(path, f)
            relative_path = os.path.join(path, f)
            file = open(relative_path)
            index[f] = os.path.getmtime(relative_path), hash.sha256_file(file), os.path.getsize(relative_path)
            file.close()
        self.userFileMap = index

    def updateFiles(self):
        # compare serverFileMap to userFileMap and act accordingly.
        print "UserFileMap:\n",self.userFileMap
        print "serverFileMap:\n",self.serverFileMap

        # file is the relative path
          
        for file in self.userFileMap:
            if file in self.serverFileMap:
                # Checked hashed contents
                if self.userFileMap[file][1] != self.serverFileMap[file][1]:
                    # Check for latest last modified timestamp
                    if self.userFileMap[file][0] > self.serverFileMap[file][0]:
                        self.setLineMode()
                        print "updateFiles:",file
                        self.sendData(['upload',file])
                        # time.sleep(10)
                    else:
                        pass
                        # update userFileMap
                        # self.sendData(['download-request',file])
            else:
                # I can also do upload but the metadata won't get updated to corresponding tables
                self.setLineMode()
                print "updateFiles:",file
                self.sendData(['upload',file])
                # time.sleep(10)

            # self.sendData(['update-tables'])

        # files exclusive in server but not in local
        for file in self.serverFileMap:
            if file not in self.userFileMap:
                pass
                # update userFileMap
                # self.sendData(['download-request',file])

        # After updates, set the serverFileMap to None to be efficient about space
        # self.serverFileMap = None

    def lineReceived(self, data):
        """ what we'll do when our client receives data """
        data = data.strip()
        print data
        if data == "Login Successful! Welcome to OneDir":
            self.allowed = True
            self.notifier.watch(filepath.FilePath(""), callbacks=[self.notify])
            self.createUserFileMap()
            self.sendData(['synch'])
        if data == "Logout Successful":
            self.allowed = False

        if not self.allowed:
            self.authenticate()
        else:
            # #if user asked to change pw, ask for what the current password is
            # if data == "Insert current password.":
            #     # self.passwordGuess = True
            #     self.sendData(['current-pass'])
            # #if user guessed correctly, allow them to change to new password
            # if data == "Insert new password.":
            #     # self.newPassword = True
            #     self.sendData(['new-pass'])
            if data.startswith("upload ready"):
                self.sendData(['upload',data.split('upload ready ')[1]])
            # self.input = True
            # self.startShell()  # let's repeat: get more data to send to server
    def notify(self, ignore, filepath, mask):
        # self.input = False
        print "event %s on %s" % (', '.join(inotify.humanReadableMask(mask)), filepath)
        action = inotify.humanReadableMask(mask)[0]
        # This might break.... depending on the queue of the 
        path = os.path.relpath(filepath.path)
        # path = filepath.path
        print "path:",path
        # Check for swp or temp file
        check = path.endswith('swp') or path.endswith('~') or path.endswith('swx') or '.goutputstream' in path
        if action == 'attrib' or action == "moved_to":
            if not check:

                self.sendData(['upload',path])
        if action == 'delete' or action == 'moved_from':
            if not check:
                self.sendData(['remove',path])

class TSClntFactory(protocol.ClientFactory):
    def startedConnecting(self, connector):
        print 'Starting to connect...'

    def buildProtocol(self, addr):
        print 'Connected.'
        return TSClntProtocol()

    def clientConnectionLost(self, connector, reason):
        print 'Lost connection.  Reason:', reason

    def clientConnectionFailed(self, connector, reason):
        print 'Connection failed. Reason:', reason

def handleLostFailed1(reason):
    print 'Connection closed, lost or failed.  Reason:', reason
    reactor.stop()

factory = TSClntFactory()
# epollreactor.install()
reactor.connectTCP(HOST, PORT, factory)
reactor.run()
