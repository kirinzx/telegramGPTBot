from aiogram.dispatcher.filters.state import State, StatesGroup

class AdminForm(StatesGroup):
    phoneNumberAdmin = State()
    adminId = State()

class UserForm(StatesGroup):
    phoneNumber = State()
    app_id = State()
    app_hash = State()
    ip = State()
    port = State()
    proxyLogin = State()
    proxyPassword = State()
    code = State()
    password = State()
    

class TimeToWaitForm(StatesGroup):
    timeLowRange = State()
    timeHighRange = State()

class RequestForm(StatesGroup):
    request = State()

class ChanceForm(StatesGroup):
    chance = State()

class MinSymbolsForm(StatesGroup):
    minSymbols = State()

class HyperlinkForm(StatesGroup):
    hyperlink = State()

class OpenAIKeyForm(StatesGroup):
    api_key = State()

class ProxyForm(StatesGroup):
    proxy = State()