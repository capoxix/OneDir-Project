import json
from twisted.internet.protocol import Protocol, Factory 
from twisted.internet import reactor, inotify
from twisted.python import filepath
from time import ctime, time
import time
import os
from twisted.protocols import basic

from twisted.enterprise import adbapi
import datetime
import hash
import hashlib

class Server(basic.LineReceiver):
  delimiter = '\n'
  def __init__(self, factory):
    self.factory = factory
    self.activeFile = []
    self.auth = False
    self.clnt = None
    self.user = None
    self.curr_file_name = None
    self.curr_file_handle = None
    self.notifier = inotify.INotify()
    self.notifier.startReading()
    self.dbpool = adbapi.ConnectionPool("sqlite3", "tables.db")


  # TODO: advanced feature. Make sure userToFileMap is synched with Serverfiles/ directory
  def connectionMade(self):
    self.factory.numProtocols += 1
    self.clnt = self.transport.getPeer().host
    self.setLineMode()
    print '...connected from:', self.clnt
    print 'protocol number: ', self.factory.numProtocols
  
  # Close the connection to database?
  def connectionLost(self, reason):
    self.factory.numProtocols -= 1

  def notify(self, ignore, filepath, mask):
    print "event %s on %s" % (', '.join(inotify.humanReadableMask(mask)), filepath)
    action = inotify.humanReadableMask(mask)[0]
    path = filepath.path
    rel_path = str(path.split(self.user_dir+"/")[1])
    # # Check for swp or temp file
    check = path.endswith('swp') or path.endswith('~') or path.endswith('swx') or '.goutputstream' in path
    if action == 'modify': #or action == 'attrib':
      if not check:
        print "modify:", rel_path
        self.sendData(['download-request',path])
    if action == 'delete' or action == 'moved_from':
      if not check:
        print "delete:", rel_path
        self.sendData(['remove',rel_path])

  def sendData(self,args):
    if len(args) == 2 and args[0] == "download-request":
      try:
        # send hash,last_modified, and size
        # send the relative path
        file_path = args[1]
        size = os.path.getsize(file_path)
        with open(file_path) as f:
          hashedContent = hash.sha256_file(f)
        rel_path = str(file_path.split(self.user_dir+"/")[1])

        self.transport.write("download-request "+rel_path+","+hashedContent+","+str(size)+"\n")
      except Exception, e:
        print "SendData:download-request error:",e
    if len(args) == 2 and args[0] == "remove":
      # send hash,last_modified, and size
      # send the relative path
      file_path = args[1]
      self.transport.write("remove "+file_path+"\n")

  def lineReceived(self, data):
    data = data.strip()
    args = data.split(" ",1)
    print data,self.auth
    print self.user

    if not self.auth:
      username = args[1].split(" ")[0]
      password = args[1].split(" ")[1]
      hashedPw = hashlib.md5(password).hexdigest()

      if len(args) == 2 and args[0] == "login":
        data = self.dbpool.runQuery("select * from UserInfo where userID =? and password=?;",(username,hashedPw))
        data.addCallback(self.verifyUser)
        self.user = username

      elif len(args) == 2 and args[0] == "user-create":
        self.factory.user_list[username] = hashedPw
        self.createUser(username,hashedPw)
        self.transport.write("User Created Successfully. Now you can login to OneDir!\n")
        print self.factory.user_list
      elif len(args) == 2 and args[0] == "change-pw":
        currentPWGuess = hashedPw
        pwChangeTo = args[1].split(" ")[2]
        hashedpwChangeTo = hashlib.md5(pwChangeTo).hexdigest()
        print "username:",username
        print "currentPWGuess:",password
        print "pwChangeTo:",pwChangeTo 
        data = self.dbpool.runQuery("select * from UserInfo where userID = '" + username + "';")
        print "after query, going to changePW!!!!"
        data.addCallback(self.changePW,username, currentPWGuess, hashedpwChangeTo)  
      else:
        self.transport.write("Invalid Login Arguments\n")
    else:
      #if args[0] == "update-table" and len(args)== 2:
      if args[0] == "upload-request" and len(args) == 2:
        params = args[1].split(",")
        fname = params[0]
        size = params[1]
        last_modified = params[2]
        file_path = params[3]
        hashedContent = params[4]
        
        sql_command = "select * from %s where fileName = '%s';" % (self.user, fname) 
        data = self.dbpool.runQuery(sql_command)
        print "entering Compare File!"
        data.addCallback(self.compareFile, fname, size, last_modified, file_path, hashedContent)


      elif args[0] == "upload" and len(args) >= 2:
        # fname=os.path.basename(args[1])
        
        self.transport.write("Uploading "+args[1]+"..."+'\n')
        
        params = args[1].split(",")
        self.curr_file_size = int(params[1])
        self.curr_file_name = params[2]
        print "server:lineReceived:upload",params[2]


        self.notifier.ignore(filepath.FilePath(self.user_dir))

        self.setRawMode()

      # SYNCH
      elif args[0] == "synch" and len(args) == 1:
        data = self.dbpool.runQuery("select filePath,lastModified,HashedContent,fileSize from "+self.user+";")
        self.setRawMode()
        data.addCallback(self.sendUserData)
      elif args[0] == "download" and len(args) == 2:
        try:
          params = args[1].split(",")
          file_path = params[0]
          file_size = int(params[1])
          print "file_path",file_path
          self.transport.write("download "+file_path+","+str(file_size)+",\n")
          self.setRawMode()
          file_path = self.user_dir +"/"+file_path 
          for chunks in self.file_iterator(file_path):
            self.transport.write(chunks)
          self.setLineMode()
        except Exception,e:
          print "Server:lineReceived:download",e

      elif args[0] == "remove" and len(args) == 2:
        
        file_path = os.path.join(self.user_dir,args[1])
        print "Server:lineReceived:remove:", self.user_dir, args[1], file_path, os.getcwd()

        if os.path.isfile(file_path):
          self.transport.write("Removing "+args[1]+"...\n")
          filesize = os.path.getsize(file_path)
          self.remove_data(self.user_dir, args[1])


        #Updating Synch
          print "updating UserInfo, server:lineReceived"
          sql_commandU = "update UserInfo set numFiles = numFiles-1, totalSize = totalSize -"+str(filesize) +" where userID = '"+self.user+"';"
          
          self.dbpool.runQuery(sql_commandU)

          sql_command = "delete from %s where fileName = '%s';" % (self.user, args[1])
          self.dbpool.runQuery(sql_command)
        else:
          print "no such file"
          self.transport.write("No such file or directory: "+args[1]+'\n')
      elif len(args) == 1 and args[0] == "ls":
        self.displayfiles(self.user)
      elif args[0] == "logout":
        self.transport.write("Logout Successful\n")
        self.auth = False

      else:
        self.transport.write("Invalid Command!\n")

  def rawDataReceived(self, data):
    # Make sure you close the file handle
    # filename should be the relative path of file from the directory
    filename = self.curr_file_name
    file_withpath = os.path.join(self.user_dir,filename)

    if not self.curr_file_handle:
      print "opening file",file_withpath
      self.curr_file_handle = open(file_withpath, 'wb')
      self.byte_counter = 0

    self.byte_counter += len(data)

    print "types:",type(self.curr_file_size),type(self.byte_counter)
    if self.curr_file_size > self.byte_counter:
      print "file_size > byte_counter"
      self.curr_file_handle.write(data)
    elif self.curr_file_size == self.byte_counter:
      print "file_size == byte_counter"
      self.curr_file_handle.write(data)
      self.notifier.watch(filepath.FilePath(self.user_dir), callbacks=[self.notify])
      self.curr_file_handle.close()
      self.setLineMode()
      self.curr_file_handle = None
    else:
      print "file_size < byte_counter"

      endChunk = data[self.curr_file_size - self.byte_counter:]

      self.curr_file_handle.write(data[:self.curr_file_size - self.byte_counter])
      self.notifier.watch(filepath.FilePath(self.user_dir), callbacks=[self.notify])

      self.curr_file_handle.close()
      # turn off
      self.notifier.ignore(filepath.FilePath(self.user_dir))
      self.curr_file_handle = None


      # For next command (upload or download)
      args = endChunk.split(" ",1)
      command = args[0]
      if command == 'upload': 
        params = args[1].split(",",3)
        fname = params[0]
        size = params[1]
        file_path = params[2]

        print "curr_file_size:",size

        self.curr_file_size = int(size)
        self.curr_file_name = file_path
        file_withpath = os.path.join(self.user_dir,self.curr_file_name)

        self.curr_file_handle = open(file_withpath,'wb')
        self.byte_counter = 0
        nextChunk = params[3][1:]
        # print "next:",nextChunk

        self.curr_file_handle.write(nextChunk)
        self.byte_counter += len(nextChunk)
        print "compare: ",self.curr_file_size,self.byte_counter
        if self.curr_file_size == self.byte_counter:
          self.notifier.watch(filepath.FilePath(self.user_dir), callbacks=[self.notify])
          self.curr_file_handle.close()
          self.curr_file_handle = None
          self.setLineMode()
      if command == 'download':
        pass

  def file_iterator(self,file, buff_size=4096):
    with open(file, 'rb') as f:
        while True:
            data_buff = f.read(buff_size)
            if data_buff:
                yield data_buff
            else:
                break

  # TODO: Put the timestamp with the file (too lazy)
  def displayfiles(self,user):
    self.transport.write("Files:\n")
    if user in self.factory.userToFileMap:
      for file in self.factory.userToFileMap[user]:
        self.transport.write(file.split('_')[1])

  def remove_data(self, path, filename):
    file_withpath = os.path.join(path, filename)
    try:
      if os.path.isfile(file_withpath):
        os.unlink(file_withpath)
    except Exception, e:
        print e

  # DATABASE functions

  def sendUserData(self,dbFile):
    dict = {}
    for i in range(len(dbFile)):
      dict[str(dbFile[i][0])] = time.mktime(time.strptime(dbFile[i][1])), str(dbFile[i][2]), int(dbFile[i][3])
    print "serverFileMap: ",str(dict)
    self.transport.write(str(dict))

    self.setLineMode()

  # Should be empty if not found in table UserInfo
  def verifyUser(self, user):
    if user:
      self.user = user[0][0]
      self.user_dir = self.factory.workDir+self.user
      self.auth = True
      self.factory.user_list[self.user]=user[0][1]
      self.notifier.watch(filepath.FilePath(self.user_dir), callbacks=[self.notify])
      self.transport.write("Login Successful! Welcome to OneDir\n")
    else:
      self.transport.write("Invalid Login Arguments\n")
  
  # TODO: Incomplete, check if user already exists
  def createUser(self, username,password):
    # create table for user
    self.dbpool.runQuery("CREATE TABLE "+username+" (fileName text, fileSize text, "+
      "lastModified text, filePath text, HashedContent text);")
    # inser the user and pw into UserInfo (changed table name from 'Admin')
    self.dbpool.runQuery("insert into UserInfo (userID,password,numFiles,totalSize) Values (?,?,?,?);", (username, password,0,0))
    self.user_dir = self.factory.workDir+username
    os.mkdir(self.user_dir)
  def getHashedConent(self, user,filename):
    pass


  def changePW(self,member,user, pwGuess,newPw):

    if member:
      username = str(member[0][0])
      password = str(member[0][1])

      if pwGuess == password:
        self.transport.write("Sucessfully changed " + username + "'s password!\n")
        self.dbpool.runQuery("UPDATE UserInfo SET password =? WHERE userID =?;",(newPw,username))
        
      else: 
        self.transport.write("Invalid current password!\n")
    else:
      self.transport.write(user + " does not exist!\n")

  def updateUser(self,fileName,fileSize,timeStamp,filePath,hashedFileContents):
    #I believe time in timeStamp is the last modified
    self.dbpool.runQuery("INSERT INTO "+self.user+" (fileName, fileSize, timeStamp, filePath, hashedFileContents)" 
      +" Values (?,?,?,?,?)",(fileName, fileSize, timeStamp, filePath ,hashedFileContents))


  def compareFile(self,dbFile,fname, size, last_modified, file_path, hashedContent):
    print "Compare File\n"
    print "dfile: ",dbFile
    if dbFile:
      db_fileName = dbFile[0][0]
      db_size = dbFile[0][1]  #size in server/database
      db_last_modified = dbFile[0][2]
      path = dbFile[0][3]
      db_hashContent = dbFile[0][4]
      # TODO: update synchist, and update userinfo 
      if hashedContent != db_hashContent:
        # need to add an if statement to compare last modified time?
        # if last_modified > db_last_modified:
        
        self.dbpool.runQuery("update "+ self.user+" SET lastModified = ?, HashedContent = ?, fileSize = ? "
          +"WHERE fileName = ?",(last_modified,hashedContent,size,db_fileName))
        
        current_time = ctime()
        print "updating Synch \n"
        print db_fileName,time
        self.dbpool.runQuery("INSERT INTO Synch (userID, fileName, action, timeStamp)" 
          +" Values (?,?,?,?)",(self.user,db_fileName, 'receiving', current_time))
        sizeChange = int(size) - int(db_size)
        print "sizeChange:",sizeChange
        sql_commandU = "update UserInfo set numFiles = numFiles, totalSize = totalSize +"+str(sizeChange) +" where userID = '"+self.user+"';"
          
        self.dbpool.runQuery(sql_commandU)

        self.transport.write("upload ready "+file_path+"\n")

    else:

      self.dbpool.runQuery("insert into "+self.user+" (fileName,fileSize,lastModified,filePath,HashedContent) Values (?,?,?,?,?);", 
        (fname,size,last_modified,file_path,hashedContent))

      current_time = ctime()
      self.dbpool.runQuery("INSERT INTO Synch (userID, fileName, action, timeStamp)" 
          +" Values (?,?,?,?)",(self.user,fname,'receiving', current_time))
      print "going to UserInfo!!" 

      sql_commandU = "update UserInfo set numFiles = numFiles + 1, totalSize = totalSize +"+size +" where userID = '"+self.user+"';"
      self.dbpool.runQuery(sql_commandU)
      print "after UserInfo!"
      self.transport.write("upload ready "+file_path+"\n")

  #[Garbo]

  def getSize(self, removeSize):
    if removeSize:
      filesize = removeSize[0][0]

      userinfo = self.dbpool.runQuery("select numFiles,totalSize from UserInfo where userID = '"+self.user+"';")
      userinfo.addCallback(self.updateUserInfo,-1,0,int(filesize))

class ServerFactory(Factory):

  def __init__(self):
    self.numProtocols = 0
    self.fileToUserMap = {} #Maybe need it for future?
    self.userToFileMap = {}
    self.workDir = "Serverfiles/"

    #get user list from an actual text file where we can keep track of users info [JSON format].
    # f = open('userList.txt', 'r')
    # dictionary = json.load(f)
    # f.close()

    self.user_list = {}

  def buildProtocol(self, addr):
    return Server(self)

reactor.listenTCP(3240, ServerFactory())
reactor.run()

"""

"""


