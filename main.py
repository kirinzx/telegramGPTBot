import telegramBot
import threading
import sqlite3
from checkUsers import getUsersClient

def main():
    userThreads = []
    tgBot = threading.Thread(target=telegramBot.main,name="tgBot-Thread")

    con = sqlite3.connect("accounts.db")
    cur = con.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS users(id integer PRIMARY KEY, phoneNumber text NOT NULL UNIQUE, app_id text NOT NULL UNIQUE, app_hash text NOT NULL UNIQUE);")
    con.commit()
    for row in cur.execute("SELECT phoneNumber,app_id,app_hash FROM users"):
        userThreads.append(threading.Thread(target=getUsersClient, args=(row[0], row[1], row[2]),name=f"user_{row[0]}-Thread"))
    con.close()

    for thread in userThreads:
        thread.start()
    tgBot.start()
    for thread in userThreads:
        thread.join()
    tgBot.join()
if __name__ == "__main__":
    main()