import telegramBot
import checkUsers
import threading
import sqlite3

def main():
    con = sqlite3.connect("accounts.db")
    cur = con.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS users(id integer PRIMARY KEY, phoneNumber text NOT NULL UNIQUE, app_id text NOT NULL UNIQUE, app_hash text NOT NULL UNIQUE);")
    con.commit()
    con.close()
    tgBot = threading.Thread(target=telegramBot.main)
    commenting = threading.Thread(target=checkUsers.main)
    tgBot.start()
    commenting.start()
    tgBot.join()
    commenting.join()

if __name__ == "__main__":
    main()