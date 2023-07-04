import telegramBot
import checkUsers
import threading

if __name__ == "__main__":
    tgBot = threading.Thread(target=telegramBot.main)
    commenting = threading.Thread(target=checkUsers.main)
    tgBot.start()
    commenting.start()
    tgBot.join()
    commenting.join()