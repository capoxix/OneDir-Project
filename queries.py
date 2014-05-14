# This file contains pre-constructed SQL queries
# Use: Assuming your database cursor is called cursor, use cursor.execute(sql_getwhatever, (tuple, containing, args))

import sqlite3
import os
import shutil


class Queries:
    def __init__(self, name, server_root):
        self.server_root = server_root 
        if os.path.exists('./' + name):
            self.database = name
        else:
            print 'Given filename does not exist, setting to database to None'
            self.database = None

    def sql_getalluserstats(self):
        """ Returns result of SQL query for getting list of all users, their total files, and total file size """
        with sqlite3.connect(self.database) as connection:
            cursor = connection.cursor()
            sql_cmd = "SELECT userID, numFiles, totalSize FROM UserInfo;"
            cursor.execute(sql_cmd)
            return cursor.fetchall()

    def sql_getuserstats(self, user):
        """ Returns SQL query for getting numFiles and totalSize of one, specified user """
        with sqlite3.connect(self.database) as connection:
            cursor = connection.cursor()
            sql_cmd = "SELECT userID, numFiles, totalSize FROM UserInfo WHERE userID=?;"
            cursor.execute(sql_cmd, (user,))
            return cursor.fetchall()

    def sql_gettotalfileandsize(self):
        """ Returns tuple of (total number of files, total size) """
        with sqlite3.connect(self.database) as connection:
            cursor = connection.cursor()
            sql_cmd = "SELECT numFiles, totalSize FROM UserInfo;"
            cursor.execute(sql_cmd)
            numFiles = 0
            size = 0
            for record in cursor.fetchall():
                numFiles += record[0]
                size += record[1]
            return numFiles, size

    def sql_removeuser(self, user, rmfiles = False):
        """ Deletes specified user, possibly user's files too """
        with sqlite3.connect(self.database) as connection:
            cursor = connection.cursor()
            sql_cmd = "DROP TABLE " + user + " ;"   #changed from old version so that it works
            cursor.execute(sql_cmd)
            sql_cmd = "DELETE FROM UserInfo WHERE userID=?;"
            cursor.execute(sql_cmd, (user,))

            if rmfiles:
                shutil.rmtree(self.server_root + '/' + user)

    def sql_changeuserpassword(self, user, password_hash):
        """ Changes user's password """
        with sqlite3.connect(self.database) as connection:
            cursor = connection.cursor()
            sql_cmd = "UPDATE UserInfo SET password=? WHERE userID=?;"
            cursor.execute(sql_cmd, (password_hash, user))

    def sql_getsynchistory(self):
        """ Selects the entire sync history table"""
        with sqlite3.connect(self.database) as connection:
            cursor = connection.cursor()
            sql_cmd = "SELECT * from Synch"
            cursor.execute(sql_cmd)
            return cursor.fetchall()

    def sql_getusers(self):
        """ Returns list of current users """
        with sqlite3.connect(self.database) as connection:
            cursor = connection.cursor()
            sql_cmd = "SELECT userID FROM UserInfo;"
            cursor.execute(sql_cmd)
            return cursor.fetchall()