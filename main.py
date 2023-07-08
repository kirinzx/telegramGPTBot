import telegramBot
import threading
import sqlite3
from classes import UserChecking
from typing import List

usersToCheck : List[UserChecking] = []

def main():
    tgBot = threading.Thread(target=telegramBot.main,name="tgBot-Thread")
    tgBot.start()
    con = sqlite3.connect("accounts.db")
    cur = con.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, phoneNumber TEXT NOT NULL UNIQUE, app_id TEXT NOT NULL UNIQUE, app_hash TEXT NOT NULL UNIQUE);")
    cur.execute(
        "CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY, phoneNumber TEXT NOT NULL UNIQUE, adminId TEXT NOT NULL UNIQUE)"
    )
    con.commit()
    for row in cur.execute("SELECT phoneNumber,app_id,app_hash FROM users"):
        usersToCheck.append(UserChecking(row[0],row[1],row[2]))
    con.close()
    tgBot.join()

if __name__ == "__main__":
    main()