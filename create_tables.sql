DROP TABLE IF EXISTS UserInfo;
CREATE TABLE UserInfo (userID text, password text, numFiles int, totalSize int);

DROP TABLE IF EXISTS Synch;
CREATE TABLE Synch (userID text, fileName int, action text, timeStamp text);
