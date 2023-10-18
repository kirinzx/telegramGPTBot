import python_socks
import async_timeout
import socks
import configparser

BOT_TOKEN = "6632322739:AAGQLzCz2Opxx2DxKzfJ-FcSZXqz-_LnPt8"

def getSetting(settingName):
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    return config.get('Settings',settingName)

def setSetting(settingName, value):
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    config.set('Settings',settingName,value)
    with open('config.ini','w',encoding='utf-8')as file:
        config.write(file)