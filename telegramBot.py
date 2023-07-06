import asyncio
import threading

from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.types.inline_keyboard import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from telethon import TelegramClient
from classes import User, Paginator
from checkUsers import getUsersClient
import aiosqlite
import os

storage = MemoryStorage()
bot = Bot(token=os.environ.get("API_TOKEN"))
dp = Dispatcher(bot,storage=storage)

keyboardCancel = ReplyKeyboardMarkup(keyboard=[
    ["Отменить"],
])
keyboardMain = ReplyKeyboardMarkup(keyboard=[
    ["Посмотреть добавленные аккаунты","Добавить аккаунт"],
    ["Как я работаю?"]
],resize_keyboard=True)

client = None
user = None

class UserForm(StatesGroup):
    phoneNumber = State()
    app_id = State()
    app_hash = State()

class AccessCodeForm(StatesGroup):
    code = State()
@dp.message_handler(commands="start")
async def start(message:types.Message):
    await message.answer(text="Выберите опцию",reply_markup=keyboardMain)

@dp.message_handler(Text(equals="Посмотреть добавленные аккаунты"))
async def getAccounts(message:types.Message):
    # try:
    async with aiosqlite.connect("accounts.db") as db:
        async with db.execute("SELECT phoneNumber FROM users;") as cursor:
            accounts = await cursor.fetchall()
    if len(accounts) > 0:
        accountsButtons = InlineKeyboardMarkup()
        for account in accounts:
            accountsButtons.add(InlineKeyboardButton(text=str(account[0]),callback_data=\
                f"view {str(account[0])}"),InlineKeyboardButton(text="Удалить",callback_data=f"Удалить {str(account[0])}"))
        paginator = Paginator(accountsButtons,size=5,dp=dp)
        await message.answer(text="Добавленные аккаунты. Чтобы удалить, нажмите на кнопку удаления",reply_markup=paginator())
    else:
        await message.answer(text="Аккаунтов нет...",reply_markup=keyboardMain)
    # except:
    #     await message.answer("Непридвиденная ошибка!", reply_markup=keyboardMain)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('Удалить'))
async def proccess_callback_deleteUser(callback_query: types.CallbackQuery):
    userToDelete = callback_query.data.split(" ")[-1]
    try:
        async with aiosqlite.connect("accounts.db") as db:
            await db.execute("DELETE FROM users WHERE phoneNumber=?;",(userToDelete,))
            await db.commit()
        for thread in threading.enumerate():
            if f"user_{userToDelete}-Thread" in thread.name:
                pass
        await bot.send_message(callback_query.from_user.id,text=f"Готово! Пользователь {userToDelete} удалён!",reply_markup=keyboardMain)
    except:
         await bot.send_message(callback_query.from_user.id,text="Непридвиденная ошибка!", reply_markup=keyboardMain)

@dp.message_handler(Text(equals="Добавить аккаунт"))
async def addAccount(message:types.Message):
    await UserForm.phoneNumber.set()
    await message.answer(text="Напишите номер телефона(с кодом страны)",reply_markup=keyboardCancel)

@dp.message_handler(Text(equals="Как я работаю?"))
async def getHelp(message:types.Message):
    await message.answer(text="""
    Вы добавляете аккаунт, и я от лица вашего аккаунта начинаю комментировать все новые посты во всех каналах, на которые подписан акккаунт.\n
    Что нужно для того, чтобы добавить аккаунт?
    1. Номер телефона\n
    2. API_ID и API_HASH. Как их получить? Заходим на сайт https://my.telegram.org/. Это официаьный сайт телеграма. В нём мы создаемновое приложение, после получаем API_ID и API_HASH.\n
    3. Доступ к телеграм аккаунту. Вам на аккаунт придет код, необходимый для работы.\n
    Вот и все! Теперь я начинаю комментировать....
    """,reply_markup=keyboardMain)

@dp.message_handler(Text(equals="На главную"))
async def goHome(message:types.Message):
    await message.answer(text="Выберите опцию",reply_markup=keyboardMain)

@dp.message_handler(state='*', commands='Отменить')
@dp.message_handler(Text(equals='Отменить'), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.finish()
    await message.reply('Отменено', reply_markup=keyboardMain)

@dp.message_handler(state=UserForm.phoneNumber)
async def process_nickname(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['phoneNumber'] = message.text

    await UserForm.next()
    await message.reply("Напишите api_id",reply_markup=keyboardCancel)

@dp.message_handler(state=UserForm.app_id)
async def process_app_id(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['app_id'] = message.text

    await UserForm.next()
    await message.reply("Напишите api_hash",reply_markup=keyboardCancel)

@dp.message_handler(state=UserForm.app_hash)
async def process_app_hash(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['app_hash'] = message.text
        global client, user
        user = User(data["phoneNumber"], data["app_id"], data["app_hash"])
    try:
        client = TelegramClient(session=f'sessions/{user.phoneNumber}', api_id=int(user.app_id),
                                api_hash=str(user.app_hash))
        await client.connect()
        if not await client.is_user_authorized():
            await client.send_code_request(phone=data["phoneNumber"])
            await message.answer("Введите код, который пришел вам в телеграм", reply_markup=keyboardCancel)
            await state.finish()
            await AccessCodeForm.code.set()
        else:
            await saveUser(message,state)
    except:
        try:
            await os.remove(f"sessions/{user.phoneNumber}.session")
        except:
            pass
        await message.answer("Непридвиденная ошибка!", reply_markup=keyboardMain)
        await state.finish()
@dp.message_handler(state=AccessCodeForm.code)
async def process_code(message: types.Message, state: FSMContext):
    global user
    try:
        await client.sign_in(user.phoneNumber,message.text)
        await saveUser(message, state)
    except:
        try:
            await os.remove(f"sessions/{user.phoneNumber}.session")
        except:
            pass
        await message.answer("Непридвиденная ошибка!", reply_markup=keyboardMain)
        await state.finish()

async def saveUser(message: types.Message,state: FSMContext):
    try:
        async with aiosqlite.connect("accounts.db") as db:
            await db.execute("INSERT INTO users (phoneNumber,app_id,app_hash) VALUES(?,?,?);",
                             (user.phoneNumber, user.app_id, user.app_hash))
            await db.commit()
        await client.disconnect()
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, startCheckingNewUser, user.phoneNumber, user.app_id, user.app_hash)
        await message.answer("Готово!", reply_markup=keyboardMain)
        await state.finish()
    except aiosqlite.IntegrityError:
        try:
            await os.remove(f"sessions/{user.phoneNumber}.session")
        except:
            pass
        await message.answer("Ошибка!Аккаунт с такими данными уже существует!", reply_markup=keyboardMain)
        await state.finish()

def startCheckingNewUser(phoneNumber,app_id,app_hash):
    thread = threading.Thread(target=getUsersClient, args=(phoneNumber, app_id, app_hash))
    thread.start()
    thread.join()


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    executor.start_polling(dp)
