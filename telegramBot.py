import asyncio
import threading

from middlewares import AdminMiddleware
from main import usersToCheck
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.types.inline_keyboard import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from telethon import TelegramClient
from classes import User, Paginator, UserChecking
import aiosqlite
import os

storage = MemoryStorage()
bot = Bot(token=os.environ.get("API_TOKEN"))
dp = Dispatcher(bot,storage=storage)

keyboardCancel = ReplyKeyboardMarkup(keyboard=[
    ["Отменить"],
])

keyboardMain = ReplyKeyboardMarkup(keyboard=[
    [r'Добавить "админа"',"Добавить аккаунт для комментирования"],
    ["Как я работаю?"],
    [r'Посмотреть "админов"',"Посмотреть добавленные аккаунты"]
],resize_keyboard=True)

client : TelegramClient = None
user : User = None


class AdminForm(StatesGroup):
    phoneNumberAdmin = State()
    adminId = State()
class UserForm(StatesGroup):
    phoneNumber = State()
    app_id = State()
    app_hash = State()

class AccessCodeForm(StatesGroup):
    code = State()

@dp.message_handler(commands="start")
async def start(message:types.Message):
    await message.answer(text="Выберите опцию.",reply_markup=keyboardMain)

@dp.message_handler(Text(equals='Отменить'), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.finish()
    await message.reply('Отменено', reply_markup=keyboardMain)
@dp.message_handler(Text(equals=r'Посмотреть "админов"'))
async def getAdmins(message:types.Message):
    async with aiosqlite.connect("accounts.db")as db:
        async with db.execute("SELECT phoneNumber,adminId FROM admins;")as cur:
            admins = await cur.fetchall()
    if len(admins) > 0:
        adminsButtons = InlineKeyboardMarkup()
        for admin in admins:
            adminsButtons.add(InlineKeyboardButton(text=str(admin[0]), callback_data=f"view {admin[0]}"),
                              InlineKeyboardButton(text=str(admin[1]),callback_data=f"view {admin[1]}"),
                              InlineKeyboardButton(text="Удалить", callback_data=f"Удалить админа {str(admin[0])}"))
        paginator = Paginator(adminsButtons, size=5, dp=dp)
        await message.answer(text="Добавленные админы. Чтобы удалить, нажмите на кнопку удаления",reply_markup=paginator())
    else:
        await message.answer(text="Админов нет...", reply_markup=keyboardMain)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('Удалить админа'))
async def proccess_callback_deleteAdmin(callback_query: types.CallbackQuery):
    adminToDelete = callback_query.data.split(" ")[-1]
    try:
        async with aiosqlite.connect("accounts.db") as db:
            await db.execute("DELETE FROM admins WHERE phoneNumber=?;", (adminToDelete,))
            await db.commit()
        await removeSessionFile(adminToDelete)

        await bot.send_message(callback_query.from_user.id, text=f"Готово! Админ {adminToDelete} удалён!",
                               reply_markup=keyboardMain)
    except:
        await bot.send_message(callback_query.from_user.id, text="Непридвиденная ошибка!", reply_markup=keyboardMain)

@dp.message_handler(Text(equals='Добавить "админа"'))
async def addAdmin(message:types.Message):
    await AdminForm.phoneNumberAdmin.set()
    await message.answer("Напишите номер телефона(с кодом страны)",reply_markup=keyboardCancel)
@dp.message_handler(state=AdminForm.phoneNumberAdmin)
async def proccess_phoneNumberAdmin(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['phoneNumberAdmin'] = message.text.strip()
    await AdminForm.next()
    await message.reply("Напишите id аккаунта",reply_markup=keyboardCancel)

@dp.message_handler(state=AdminForm.adminId)
async def proccess_adminId(message:types.Message,state:FSMContext):
    async with state.proxy() as data:
        data['adminId'] = message.text.strip()

    async with aiosqlite.connect("accounts.db")as db:
        try:
            await db.execute("INSERT INTO admins(phoneNumber,adminId) VALUES(?,?);",(data["phoneNumberAdmin"],data["adminId"]))
            await db.commit()
            await state.finish()
            await message.reply("Готово!", reply_markup=keyboardMain)
        except aiosqlite.IntegrityError:
            await state.finish()
            await message.reply("Админ с такими данными уже сущетсвует!",reply_markup=keyboardMain)



@dp.message_handler(Text(equals="Посмотреть добавленные аккаунты"))
async def getAccounts(message:types.Message):
    try:
        async with aiosqlite.connect("accounts.db") as db:
            async with db.execute("SELECT phoneNumber FROM users;") as cursor:
                accounts = await cursor.fetchall()
        if len(accounts) > 0:
            accountsButtons = InlineKeyboardMarkup()
            for account in accounts:
                accountsButtons.add(InlineKeyboardButton(text=str(account[0]),callback_data=\
                    f"view {str(account[0])}"),InlineKeyboardButton(text="Удалить",callback_data=f"Удалить аккаунт{str(account[0])}"))
            paginator = Paginator(accountsButtons,size=5,dp=dp)
            await message.answer(text="Добавленные аккаунты. Чтобы удалить, нажмите на кнопку удаления",reply_markup=paginator())
        else:
            await message.answer(text="Аккаунтов нет...",reply_markup=keyboardMain)
    except:
        await message.answer("Непридвиденная ошибка!", reply_markup=keyboardMain)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('Удалить аккаунт'))
async def proccess_callback_deleteUser(callback_query: types.CallbackQuery):
    userToDelete = callback_query.data.split(" ")[-1]
    try:
        for i in range(len(usersToCheck)):
            if usersToCheck[i].session == userToDelete:
                usersToCheck[i].stop()
                del usersToCheck[i]
                break
        async with aiosqlite.connect("accounts.db") as db:
            await db.execute("DELETE FROM users WHERE phoneNumber=?;",(userToDelete,))
            await db.commit()
        await removeSessionFile(userToDelete)

        await bot.send_message(callback_query.from_user.id,text=f"Готово! Пользователь {userToDelete} удалён!",reply_markup=keyboardMain)
    except:
         await bot.send_message(callback_query.from_user.id,text="Непридвиденная ошибка!", reply_markup=keyboardMain)

@dp.message_handler(Text(equals="Добавить аккаунт для комментирования"))
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

@dp.message_handler(state=UserForm.phoneNumber)
async def process_nickname(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['phoneNumber'] = message.text.strip()

    await UserForm.next()
    await message.reply("Напишите api_id",reply_markup=keyboardCancel)

@dp.message_handler(state=UserForm.app_id)
async def process_app_id(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['app_id'] = message.text.strip()

    await UserForm.next()
    await message.reply("Напишите api_hash",reply_markup=keyboardCancel)

@dp.message_handler(state=UserForm.app_hash)
async def process_app_hash(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['app_hash'] = message.text.strip()
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
        await removeSessionFile(user.phoneNumber)
        await message.answer("Непридвиденная ошибка!", reply_markup=keyboardMain)
        await state.finish()
@dp.message_handler(state=AccessCodeForm.code)
async def process_code(message: types.Message, state: FSMContext):
    global user
    try:
        await client.sign_in(user.phoneNumber,message.text.strip())
        await saveUser(message, state)
    except:
        await removeSessionFile(user.phoneNumber)
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
        await removeSessionFile(user.phoneNumber)
        await message.answer("Ошибка!Аккаунт с такими данными уже существует!", reply_markup=keyboardMain)
        await state.finish()

def startCheckingNewUser(phoneNumber,app_id,app_hash):
    usersToCheck.append(UserChecking(phoneNumber,app_id, app_hash))

async def removeSessionFile(sessionName):
    try:
        os.remove(f"sessions/{sessionName}.session")
    except:
        pass
def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    dp.middleware.setup(AdminMiddleware())
    executor.start_polling(dp)
