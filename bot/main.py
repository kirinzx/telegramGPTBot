from telegramBot import main as tgMain
import threading
import sqlite3
from classes import MessageSender
import logging
import asyncio


def main():
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.new_event_loop()
    lock = asyncio.Lock()
    tgBot = threading.Thread(
        target=tgMain, name="tgBot-Thread", args=(loop, lock))
    tgBot.start()
    con = sqlite3.connect("accounts.db")
    cur = con.cursor()
    cur.execute(
        'CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, phoneNumber TEXT NOT NULL UNIQUE, app_id TEXT NOT NULL\
        UNIQUE, app_hash TEXT NOT NULL UNIQUE, message TEXT, chatgpt INTEGER NOT NULL, hyperlink TEXT, IP TEXT, PORT INTEGER, login TEXT, password TEXT);')
    cur.execute(
        "CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY, phoneNumber TEXT NOT NULL UNIQUE, adminId TEXT NOT NULL UNIQUE);"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS comments(id INTEGER PRIMARY KEY, phone_number TEXT NOT NULL, comment TEXT NOT NULL, post TEXT NOT NULL);"
    )
    con.commit()
    for row in cur.execute("SELECT phoneNumber, app_id, app_hash, message, chatgpt, hyperlink, IP, PORT, login, password FROM users"):
        MessageSender(row[0], row[1], row[2], row[3],
                      row[4], row[5], row[6], row[7], row[8], row[9], loop, lock)
    con.close()
    tgBot.join()


if __name__ == "__main__":
    main()
