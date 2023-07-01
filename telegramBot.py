from aiogram import Bot, Dispatcher, executor, types
from aiogram.types.reply_keyboard import ReplyKeyboardMarkup
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import aiosqlite
import os

storage = MemoryStorage()
bot = Bot(token=os.environ.get("API_TOKEN"))
dp = Dispatcher(bot,storage=storage)

keyboardMenu = ReplyKeyboardMarkup()
keyboardMenu.add("На главную")
keyboardMain = ReplyKeyboardMarkup(keyboard=[
    ["Посмотреть добавленные аккаунты","Добавить аккаунт"],
    ["Как я работаю?"]
],resize_keyboard=True)


class Form(StatesGroup):
    nickname = State()
    app_id = State()
    app_hash = State()

@dp.message_handler(commands="start")
async def start(message:types.Message):
    await message.answer(text="Выберите опцию",reply_markup=keyboardMain)

@dp.message_handler(Text(equals="Посмотреть добавленные аккаунты"))
async def getAccounts(message:types.Message):
    async with aiosqlite.connect("accounts.db") as db:
        async with db.execute("SELECT nickname FROM users;") as cursor:
            accounts = await cursor.fetchall()
    if len(accounts) > 0:
        accountsStr = "\n".join([nickname[0] for nickname in accounts])
        await message.answer(text=accountsStr,reply_markup=keyboardMenu)
    else:
        await message.answer(text="Аккаунтов нет...",reply_markup=keyboardMenu)

@dp.message_handler(Text(equals="Добавить аккаунт"))
async def addAccount(message:types.Message):
    await Form.nickname.set()
    await message.answer(text="Напишите никнейм для аккаунт:",reply_markup=keyboardMenu)

@dp.message_handler(Text(equals="Как я работаю?"))
async def getHelp(message:types.Message):
    await message.answer(text="Добавьте аккаунты и я начну комментировать их посты:",reply_markup=keyboardMenu)

@dp.message_handler(Text(equals="На главную"))
async def goHome(message:types.Message):
    await message.answer(text="Выберите опцию",reply_markup=keyboardMain)

@dp.message_handler(state=Form.nickname)
async def process_nickname(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['nickname'] = message.text

    await Form.next()
    await message.reply("Напишите app_id")

@dp.message_handler(state=Form.app_id)
async def process_app_id(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['app_id'] = message.text

    await Form.next()
    await message.reply("Напишите app_hash")

@dp.message_handler(state=Form.app_hash)
async def process_app_hash(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['app_hash'] = message.text
        user = (data["nickname"],data["app_id"],data["app_hash"])
        try:
            async with aiosqlite.connect("accounts.db")as db:
                await db.execute("INSERT INTO users (nickname,app_id,app_hash) VALUES(?,?,?);",user)
                await db.commit()
            await message.answer("Готово!Выберите опцию",reply_markup=keyboardMain,)
        except aiosqlite.IntegrityError as error:
            await message.answer("Ошибка!Аккаунт с таким никнеймом уже существует!",reply_markup=keyboardMain)
        
    await state.finish()

def main():
    executor.start_polling(dp)