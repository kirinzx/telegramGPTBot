import asyncio

from aiogram import Bot, Dispatcher, executor, types
from aiogram.types.reply_keyboard import ReplyKeyboardMarkup
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from telethon import TelegramClient
from classes import User
from checkUsers import getChannels
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
    async with aiosqlite.connect("accounts.db") as db:
        async with db.execute("SELECT phoneNumber FROM users;") as cursor:
            accounts = await cursor.fetchall()
    if len(accounts) > 0:
        accountsStr = "\n".join([nickname[0] for nickname in accounts])
        await message.answer(text=accountsStr,reply_markup=keyboardMain)
    else:
        await message.answer(text="Аккаунтов нет...",reply_markup=keyboardMain)

@dp.message_handler(Text(equals="Добавить аккаунт"))
async def addAccount(message:types.Message):
    await UserForm.phoneNumber.set()
    await message.answer(text="Напишите номер телефона аккаунт(с кодом страны):",reply_markup=keyboardCancel)

@dp.message_handler(Text(equals="Как я работаю?"))
async def getHelp(message:types.Message):
    await message.answer(text="Добавьте аккаунты и я начну комментировать их посты:",reply_markup=keyboardMain)

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
        userTMP = (data["phoneNumber"],data["app_id"],data["app_hash"])
        try:
            async with aiosqlite.connect("accounts.db")as db:
                await db.execute("INSERT INTO users (phoneNumber,app_id,app_hash) VALUES(?,?,?);",userTMP)
                await db.commit()
            global client, user
            user = User(userTMP[0],userTMP[1],userTMP[2])
            client = TelegramClient(session=f'sessions/{data["phoneNumber"]}',api_id=data["app_id"],api_hash=data["app_hash"])
            await client.connect()
            if not await client.is_user_authorized():
                await client.send_code_request(phone=data["phoneNumber"])
                await message.answer("Введите код, который пришел вам в телеграм!",reply_markup=keyboardCancel)
                await state.finish()
                await AccessCodeForm.code.set()
            else:
                await message.answer("Готово!",reply_markup=keyboardMain)
                await state.finish()
        except aiosqlite.IntegrityError:
            await message.answer("Ошибка!Аккаунт с таким никнеймом уже существует!",reply_markup=keyboardMain)
            await state.finish()
@dp.message_handler(state=AccessCodeForm.code)
async def process_code(message: types.Message, state: FSMContext):
    global user
    await client.sign_in(user.phoneNumber,message.text)
    await message.answer("Готово!",reply_markup=keyboardMain)
    await state.finish()
    await getChannels(client)

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    executor.start_polling(dp)