import python_socks
import async_timeout
import socks
import configparser

BOT_TOKEN = ""

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
def setReqUser(user):
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    config.set('TGACC','phoneNumber',user.phoneNumber)
    config.set('TGACC','app_id',user.app_id)
    config.set('TGACC','app_hash',user.app_hash)
    config.set('TGACC','proxy_ip_port_login_pass',':'.join([user.ip,user.port,user.login,user.password]))
    with open('config.ini','w',encoding='utf-8')as file:
        config.write(file)