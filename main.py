from telegramBot import main as tgMain
import threading
import sqlite3
from classes import UserChecking
from typing import List
import logging

#Чтобы поменять время ожидания, изменяйте файл timeToWait.txt. Первая строка - нижняя граница, Вторая строка - верхняя граница времени.
#Например, мы хотим, чтобы было время ожидания от 3.5 до 6 минут.
#Тогда переводим это все в секунды и 210(3.5 * 60) пишем вместо 120, а 360(6*60) вместо 300.

usersToCheck : List[UserChecking] = []

def main():
    tgBot = threading.Thread(target=tgMain,name="tgBot-Thread")
    tgBot.start()
    con = sqlite3.connect("accounts.db")
    cur = con.cursor()
    cur.execute(
        'CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, phoneNumber TEXT NOT NULL UNIQUE, app_id TEXT NOT NULL UNIQUE, app_hash TEXT NOT NULL UNIQUE, IP TEXT, PORT INTEGER, login TEXT, password TEXT, hyperlink TEXT default "-");')
    cur.execute(
        "CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY, phoneNumber TEXT NOT NULL UNIQUE, adminId TEXT NOT NULL UNIQUE)"
    )
    con.commit()
    for row in cur.execute("SELECT phoneNumber,app_id,app_hash,IP,PORT,login,password FROM users"):
        usersToCheck.append(UserChecking(row[0],row[1],row[2],row[3],row[4],row[5],row[6]))
    con.close()
    tgBot.join()

if __name__ == "__main__":
    main()