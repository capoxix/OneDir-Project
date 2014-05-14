from queries import Queries
import sqlite3
import os
import shutil
import hashlib

path = os.getcwd()
path = path+"/Serverfiles"
db = Queries("tables.db", path) #change server_root to root directory?
#change to db= Queries("tables.db", "server_root").
#unpretty
def all_stats():
    print "User ID\tNumber of Files\tTotal File Size"
    for record in db.sql_getalluserstats():
        print "\t".join(map(lambda k: str(k), record))

#unpretty
def user_stats():
    userID = raw_input("Input userID: ")
    print "Password\tNumber of Files\tTotal File Size"
    print "\t".join(map(lambda k: str(k), db.sql_getuserstats(userID)[0]))

#kind of pretty
def total_files_and_sizes():
    tupleh = db.sql_gettotalfileandsize()
    print "Total files = ", tupleh[0]
    print "Total size of files = ", tupleh[1]


#Path finding untested
def remove_user():
    userID = raw_input("Input userID: ")
    print "Remove user's files?"
    print "1: no"
    print "2: yes"
    choice = input()

    if choice == 1:
        db.sql_removeuser(userID)
    elif choice == 2:
        db.sql_removeuser(userID, True)


# No password hashing
# No password confirmation
def change_password():
    userID = raw_input("Input userID: ")
    new_password = raw_input("Input new password: ")

    db.sql_changeuserpassword(userID, hashlib.md5(new_password).hexdigest())


def sync_history():
    print "User ID\tFile Name\tAction\tTimestamp"
    for record in db.sql_getsynchistory():
        print "\t".join(map(lambda k: str(k), record))


def exit():
    quit()


#NOT PERMANENT  FOR TESTING ONLY
def add_user():
    userID = raw_input("Input userID: ")
    password = raw_input("Input password: ")
    numFiles = input("Input number of files: ")
    totalSize = input("Input total size of files: ")
    with sqlite3.connect(db.database) as connection:
        cursor = connection.cursor()
        sql_cmd = "INSERT INTO UserInfo (userID, password, numFiles, totalSize) VALUES (?, ?, ?, ?)"

        cursor.execute(sql_cmd, (userID, password, numFiles, totalSize))

def add_sync_hist():
    userID = raw_input("Input userID: ")
    fileName = raw_input("Input fileName: ")
    sentOrReceived = raw_input("Input whether the file was sent or received: ")
    time = raw_input("Input timestamp: ")
    with sqlite3.connect(db.database) as connection:
        cursor = connection.cursor()
        sql_cmd = "INSERT INTO Synch (userID, fileName, sentOrReceived, time) VALUES (?, ?, ?, ?)"

        cursor.execute(sql_cmd, (userID, fileName, sentOrReceived, time))


def list_users():
    print db.sql_getusers()


case_switch = {
    1: all_stats,
    2: user_stats,
    3: total_files_and_sizes,
    4: remove_user,
    5: change_password,
    6: sync_history,
    7: exit
}


#not pretty
def main():

    while True:
        print "Select Option: "
        print "\t1: all_stats"
        print "\t2: user_stats"
        print "\t3: total_files_and_sizes"
        print "\t4: remove_user"
        print "\t5: change_password"
        print "\t6: sync_history"
        print "\t7: exit"
        command = input()
        action = case_switch[command]
        action()


if __name__ == '__main__':
    main()
