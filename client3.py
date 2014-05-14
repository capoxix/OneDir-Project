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
#HOST = '192.168.1.156'
PORT = 3240



class TSClntProtocol(basic.LineReceiver):
    delimiter = '\n'
    def __init__(self):
        self.allowed = False
        self.user = None
        self.passwordGuess = False
        self.newPassword = False
        self.notifier = inotify.INotify()
        self.notifier.startReading()

        self.dir = "Onedir/"
        os.chdir(self.dir)
        self.input_text = ""
        self.serverFileMap = None
        self.userFileMap = None
        self.fileDownload_flag = False
        self.curr_file_handle = None
        self.curr_file_name = None



    def sendData(self,args):

        print args
        if len(args) > 1:
            fname=os.path.basename(args[1])


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
                string = "upload-request "+fname+","+str(size)+","+last_modified+","+file_path+","+hashedContents+"\n"
                print string
                self.transport.write("upload-request "+fname+","+str(size)+","+last_modified+
                    ","+file_path+","+hashedContents+"\n")
            except Exception, e:
                print "upload-request error:",e
                 
        elif len(args)== 2 and args[0] == "upload":
            try:
                print "fname:",fname
                print "args[1]:",args[1]
                size = os.path.getsize(args[1])

                if os.path.isdir(args[1]):
                    fname = fname+".zip"
                    self.compress_directory(args[1],fname)

                self.transport.write("upload "+fname+","+str(size)+","+args[1]+',\n')
                # update my usertoFileMap
                self.setRawMode()
                for chunks in self.file_iterator(fname):
                    self.transport.write(chunks)
                self.setLineMode()
            except Exception, e:
                print "Client:senData:upload:",e
        if len(args) == 3 and args[0] == "download":
            try:
                file_path = args[1]
                size = args[2]
                self.transport.write("download "+file_path+","+str(size)+",\n")
            except Exception, e:
                print "Client:senData:download:",e
        elif len(args) == 1 and args[0] == "synch":
            print "readched here"
            self.transport.write('synch\n')
            self.setRawMode()
        elif len(args)==2 and args[0] == "remove":
            data = "remove "+args[1]+'\n'
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
        command = raw_input("Enter 1, 2, or 3\n1. Create new User\n2. Login as existing User\n3. Change user password\n")
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
        if command == '3':
            user = raw_input("username:")
            password = raw_input ("current password:")
            newPw = raw_input ("new password:")
            write_str = "change-pw "+user+" "+password+" "+newPw+'\n'
            self.transport.write(write_str)


    def isData(self):
        return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])


    def connectionMade(self):
        """ what we'll do when connection first made """
        self.setLineMode()
        self.authenticate()


        
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
            check = file.endswith('swp') or file.endswith('~') or file.endswith('swx') or '.goutputstream' in file
            if file in self.serverFileMap:
                # Checked hashed content
                if self.userFileMap[file][1] != self.serverFileMap[file][1] and not check:
                    # Check for latest last modified timestamp
                    print "type: self.userFileMap[file][0]  self.serverFileMap[file][0]",type(self.userFileMap[file][0]) ,type(self.serverFileMap[file][0])
                    if self.userFileMap[file][0] > self.serverFileMap[file][0]:
                        print "updateFiles:",file
                        self.sendData(['upload-request',file])
            else:
                if not check:
                    print "updateFiles:",file
                    self.sendData(['upload-request',file])

        # files exclusive in server but not in local
        for file in self.serverFileMap:
            check = file.endswith('swp') or file.endswith('~') or file.endswith('swx') or '.goutputstream' in file
            if file not in self.userFileMap and not check:
                print "update to userfileMap"
                size = self.serverFileMap[file][2]
                print "size:",size
                self.sendData(['download',file,size])
            else:
                if self.userFileMap[file][1] != self.serverFileMap[file][1] and not check:
                    if self.userFileMap[file][0] < self.serverFileMap[file][0]:
                        size = self.serverFileMap[file][2]
                        print "size:",size
                        self.sendData(['download',file,size])

        self.notifier.watch(filepath.FilePath(""), callbacks=[self.notify])



        # After updates, set the serverFileMap to None to be efficient about space
        self.serverFileMap = None
        

    def lineReceived(self, data):
        """ what we'll do when our client receives data """
        data = data.strip()
        print data
        if data == "Login Successful! Welcome to OneDir":
            self.allowed = True
            self.createUserFileMap()
            self.sendData(['synch'])
            # self.notifier.watch(filepath.FilePath(""), callbacks=[self.notify])
                        
        if data == "Logout Successful":
            self.allowed = False

        if not self.allowed:
            self.authenticate()
        else:
            args = data.split(" ",1)
            if data.startswith("upload ready"):
                self.sendData(['upload',data.split('upload ready ')[1]])
            elif args[0] == "download-request":
                params = args[1].split(",")
                fname = params[0]
                # last_modified = params[1]
                hashedContents = params[1]
                size = params[2]

                if fname in self.userFileMap:
                    if hashedContents != self.userFileMap[fname][1]:
                        self.sendData(['download',fname, size])
                else:
                    self.sendData(["download",fname, size])
            elif args[0] == "download":
                params = args[1].split(",")
                fname = params[0]
                size = params[1]

            
                self.fileDownload_flag = True
                self.curr_file_name = fname
                self.curr_file_size = int(size)
                self.setRawMode()
            elif args[0] == "remove":
                print "client:remove:",args[1]
                print self.userFileMap
                if os.path.isfile(args[1]):
                    del self.userFileMap[args[1]]
                    os.unlink(args[1])

    # Receive any files or database structures
    def rawDataReceived(self, data):
        if self.fileDownload_flag: 
            if not self.curr_file_handle:
                self.curr_file_handle = open(self.curr_file_name, 'wb')
                self.byte_counter = 0

            self.byte_counter += len(data)

            
            print "types:",type(self.curr_file_size),type(self.byte_counter)
            if self.curr_file_size > self.byte_counter:
              print "file_size > byte_counter", self.curr_file_size,self.byte_counter
              self.curr_file_handle.write(data)
            elif self.curr_file_size == self.byte_counter:
              self.curr_file_handle.write(data)
              print "file_size == byte_counter"
              self.curr_file_handle.close()
              with open(self.curr_file_name) as f: 
                self.userFileMap[self.curr_file_name] = os.path.getmtime(self.curr_file_name),hash.sha256_file(f),os.path.getsize(self.curr_file_name)
              self.setLineMode()
              self.curr_file_handle = None
            else:
              endChunk = data[self.curr_file_size - self.byte_counter:]
              print "next:",endChunk

              self.curr_file_handle.write(data[:self.curr_file_size - self.byte_counter])
              self.curr_file_handle.close()
              self.curr_file_handle = None
              with open(self.curr_file_name) as f: 
                self.userFileMap[self.curr_file_name] = os.path.getmtime(self.curr_file_name),hash.sha256_file(f),os.path.getsize(self.curr_file_name)

              # For next command (upload or download)
              args = endChunk.split(" ",1)
              command = args[0]
              if command == 'download': 
                params = args[1].split(",",2)
                file_path = params[0]
                size = params[1]

                print "curr_file_size:",size

                self.curr_file_size = int(size)
                self.curr_file_name = file_path
                # file_withpath = os.path.join(self.user_dir,self.curr_file_name)

                self.curr_file_handle = open(self.curr_file_name, 'wb')
                self.byte_counter = 0
                nextChunk = params[2][1:]
                print "next:",nextChunk

                self.curr_file_handle.write(nextChunk)
                self.byte_counter += len(nextChunk)
                print "compare: ",self.curr_file_size,self.byte_counter
                if self.curr_file_size == self.byte_counter:
                  self.curr_file_handle.close()
                  self.curr_file_handle = None
                  with open(self.curr_file_name) as f: 
                    self.userFileMap[self.curr_file_name] = os.path.getmtime(self.curr_file_name),hash.sha256_file(f),os.path.getsize(self.curr_file_name)                  
                  self.setLineMode()
        else:
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

    def notify(self, ignore, filepath, mask):
        # self.input = False
        print "event %s on %s" % (', '.join(inotify.humanReadableMask(mask)), filepath)
        action = inotify.humanReadableMask(mask)[0]
        # This might break.... depending on the queue of the 
        path = os.path.relpath(filepath.path)
        # Check for swp or temp file
        check = path.endswith('swp') or path.endswith('~') or path.endswith('swx') or '.goutputstream' in path
        # update userfilemap
        if action == 'attrib' or action == "moved_to":
            if not check:
                self.sendData(['upload-request',path])
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
reactor.connectTCP(HOST, PORT, factory)
reactor.run()
