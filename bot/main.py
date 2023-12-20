from telegramBot import main as tgMain
import threading
import sqlite3
from classes import UserChecking
from typing import List
import logging

usersToCheck: List[UserChecking] = []


def main():
    logging.basicConfig(level=logging.INFO)
    tgBot = threading.Thread(target=tgMain, name="tgBot-Thread")
    tgBot.start()
    con = sqlite3.connect("accounts.db")
    cur = con.cursor()
    cur.execute(
        'CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, phoneNumber TEXT NOT NULL UNIQUE, app_id TEXT NOT NULL UNIQUE, app_hash TEXT NOT NULL UNIQUE, IP TEXT, PORT INTEGER, login TEXT, password TEXT, hyperlink TEXT default "-");')
    cur.execute(
        "CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY, phoneNumber TEXT NOT NULL UNIQUE, adminId TEXT NOT NULL UNIQUE);"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS comments(id INTEGER PRIMARY KEY, nickname TEXT NOT NULL, channel TEXT NOT NULL, comment TEXT NOT NULL, post TEXT NOT NULL);"
    )
    con.commit()
    for row in cur.execute("SELECT phoneNumber,app_id,app_hash,IP,PORT,login,password FROM users"):
        usersToCheck.append(UserChecking(
            row[0], row[1], row[2], row[3], row[4], row[5], row[6]))
    con.close()
    create_admins()
    tgBot.join()


def create_admins():
    con = sqlite3.connect('accounts.db')
    cur = con.cursor()
    with open('admins.txt') as file:
        admins = file.readlines()
        for i in range(len(admins)):
            admins[i] = admins[i].split(' ')
        cur.executemany(
            "INSERT OR IGNORE INTO admins(phoneNumber, adminId) VALUES (?,?);", admins)
        con.commit()
        con.close()


if __name__ == "__main__":
    main()
