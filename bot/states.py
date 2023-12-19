from aiogram.dispatcher.filters.state import State, StatesGroup


class AdminForm(StatesGroup):
    phoneNumberAdmin = State()
    adminId = State()


class UserForm(StatesGroup):
    phoneNumber = State()
    app_id = State()
    app_hash = State()
    message = State()
    chatgpt = State()
    hyperlink = State()
    proxy = State()
    code = State()
    password = State()


class ChanceForm(StatesGroup):
    chance = State()


class TimeToWaitForm(StatesGroup):
    timeLowRange = State()
    timeHighRange = State()


class OpenAIKeyForm(StatesGroup):
    key = State()


class ChatGPTRequestForm(StatesGroup):
    request = State()


class HyperlinkForm(StatesGroup):
    hyperlink = State()


class MessageForm(StatesGroup):
    message = State()


class ProxyForm(StatesGroup):
    proxy = State()


class ChatForm(StatesGroup):
    chat = State()
