import asyncio
import threading

import aiohttp
from middlewares import AdminMiddleware
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.types.inline_keyboard import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from telethon import TelegramClient
from classes import User, Paginator, UserChecking
from config import BOT_TOKEN, getSetting, setSetting
from states import *
import telethon
import aiosqlite
import os
import python_socks
import async_timeout
import socks
import configparser
import openpyxl
import io

storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot,storage=storage)

keyboardCancel = ReplyKeyboardMarkup(keyboard=[
    ["Отменить"],
])

keyboardMain = ReplyKeyboardMarkup(keyboard=[
    [r'Добавить "админа"',"Добавить аккаунт для комментирования"],
    ["Как я работаю?",'Изменить настройки','Получить отчет'],
    [r'Посмотреть "админов"',"Посмотреть добавленные аккаунты"],
],resize_keyboard=True)

keyboardSettings = ReplyKeyboardMarkup(keyboard=[
    ["Изменить шанс комментирования","Изменить время ожидания","Изменить запрос к chatgpt"],
    ["Изменить минимальное кол-во символов в комментарии",'Изменить/удалить гиперссылку'],
    ['Изменить API ключ',"Изменить прокси для запроса к chatgpt"],
    ['Назад']
], resize_keyboard=True)

client : TelegramClient = None
user : User = None
phoneNumber = None


@dp.message_handler(commands="start")
async def start(message:types.Message):
    downtimeToWait = getSetting('downTimeToWait')
    upTimeToWait = getSetting('upTimeToWait')
    prompt = getSetting("chatGPTRequest")
    chance = getSetting("chanceToComment")
    minSymbols = getSetting("minSymbols")
    await message.answer(text=f"Выберите опцию.\nВаше текущее время ожидания: от {round(int(downtimeToWait) / 60,1)} мин. до {round(int(upTimeToWait) / 60,2)} мин.\nВаш запрос к chatgpt выглядит так($$ - это текст поста):\n{prompt}\n\nВаш шанс оставить комментарий: {chance}%\nМинимальное кол-во символов в комментарии: {minSymbols}",reply_markup=keyboardMain)

@dp.message_handler(Text(equals='Отменить'), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.finish()
    await message.reply('Отменено', reply_markup=keyboardMain)

@dp.message_handler(Text(equals='Изменить настройки'))
async def getSettings(message: types.Message):
    await message.answer(text='Выберите необходимую опцию', reply_markup=keyboardSettings)

@dp.message_handler(Text(equals="Изменить прокси для запроса к chatgpt"))
async def change_proxy_for_gpt(message: types.Message):
    await ProxyForm.proxy.set()
    await message.answer(text='Напишите данные от HTTP прокси в формате ЛОГИН:ПАРОЛЬ@IP:ПОРТ', reply_markup=keyboardCancel)


@dp.message_handler(state=ProxyForm.proxy)
async def process_proxy(message: types.Message, state: FSMContext):
    setSetting('proxy', message.text.strip())
    await message.answer(text='Готово!', reply_markup=keyboardMain)

@dp.message_handler(Text(equals='Назад'))
async def getBack(message: types.Message):
    await message.answer(text='Выберите необходимую опцию', reply_markup=keyboardMain)

@dp.message_handler(Text(equals="Изменить шанс комментирования"))
async def changeChance_start(message: types.Message):
    await ChanceForm.chance.set()
    await message.answer(text="Напишите шанс комментирования в процентах, но без знака процента. Пример: 50. Важно! Число процентов не должно превышать 100 и быть меньше 0",reply_markup=keyboardCancel)

@dp.message_handler(state=ChanceForm.chance)
async def process_chance(message: types.Message, state: FSMContext):
    chance = message.text.strip()
    try:
        if chance.isdigit():
            if 0 <= int(chance) <= 100:
                setSetting('chanceToComment',chance)
                await message.answer(text="Готово!",reply_markup=keyboardMain)
            else:
                await message.answer(text="Некорректные данные!",reply_markup=keyboardMain)
        else:
            await message.answer(text="Некорректные данные!",reply_markup=keyboardMain)
    except:
        await message.answer(text="Непредвиденная ошибка!",reply_markup=keyboardMain)
    finally:
        await state.finish()

@dp.message_handler(Text(equals="Изменить/удалить гиперссылку"))
async def changeHyperlink(message: types.Message):
    async with aiosqlite.connect("accounts.db")as db:
        async with db.execute("SELECT phoneNumber,hyperlink FROM users;")as cur:
            accounts = await cur.fetchall()
    if len(accounts) > 0:
        accountsButtons = InlineKeyboardMarkup()
        for account in accounts:
            if account[1] == "-":
                accountsButtons.add(InlineKeyboardButton(text=str(account[0]), callback_data=f"view {account[0]}"),
                                  InlineKeyboardButton(text="-", callback_data=f"view {account[1]}"),
                                  InlineKeyboardButton(text="Добавить", callback_data=f"Добавить гиперссылку {account[0]}"))
            else:
                accountsButtons.add(InlineKeyboardButton(text=str(account[0]), callback_data=f"view {account[0]}"),
                                  InlineKeyboardButton(text=str(account[1]),callback_data=f"view {account[1]}"),
                                  InlineKeyboardButton(text="Изменить", callback_data=f"Добавить гиперссылку {account[0]}"))
        paginator = Paginator(accountsButtons, size=5, dp=dp)
        await message.answer(text="Ваши аккаунты и иъ гиперссылки",reply_markup=paginator())
    else:
        await message.answer(text="Аккаунтов нет..",reply_markup=keyboardMain)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('Добавить гиперссылку'))
async def callback_process_changeHyperlink(callback_query: types.CallbackQuery):
    global phoneNumber
    phoneNumber = callback_query.data.split()[-1]
    await HyperlinkForm.hyperlink.set()
    await bot.send_message(chat_id=callback_query.from_user.id,text="Напишите ссылку. Если хотите удалить, то напишите прочерк(-)",reply_markup=keyboardCancel)

@dp.message_handler(state=HyperlinkForm.hyperlink)
async def process_hyperlink(message: types.Message, state: FSMContext):
    global phoneNumber
    hyperlink = message.text.strip()
    if hyperlink != "-":
        async with aiosqlite.connect("accounts.db")as db:
            await db.execute("UPDATE users SET hyperlink = ? WHERE phoneNumber = ?;",(hyperlink,phoneNumber))
            await db.commit()
    else:
        async with aiosqlite.connect("accounts.db")as db:
            await db.execute('UPDATE users SET hyperlink = "-" WHERE phoneNumber = ?;',(phoneNumber,))
            await db.commit()
    phoneNumber = None
    await state.finish()
    await message.answer(text="Готово!",reply_markup=keyboardMain)


@dp.message_handler(Text(equals='Получить отчет'))
async def sendReport(message: types.Message):
    async with aiosqlite.connect('accounts.db')as db:
        async with db.execute('SELECT nickname, channel, comment, post from comments')as cur:
            comments = await cur.fetchall()
            comments.insert(0, ('Номер телефона', 'Канал', 'Комментарий', 'Пост'))
    thread = threading.Thread(target=sendExcel,args=(comments,asyncio.get_event_loop(),message.from_id))
    thread.start()

def sendExcel(data,botLoop, chat_id):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    excel = openpyxl.Workbook()
    sheet = excel.active
    for item in data:
        sheet.append(item)
    excelBytes = io.BytesIO()
    excel.save(excelBytes)
    excelBytes.seek(0)
    botLoop.create_task(bot.send_document(chat_id, types.InputFile(excelBytes, filename='отчет.xlsx')))

@dp.message_handler(Text(equals="Изменить запрос к chatgpt"))
async def changeRequest_start(message: types.Message):
    await RequestForm.request.set()
    await message.answer(text='Напишите желаемый запрос к chatgpt. ОБЯЗАТЕЛЬНО! Где должен быть текст поста, поставьте эти символы - "$$"(без кавычек). При отсутствии этих символов, изменение не будет выполнено',reply_markup=keyboardCancel)

@dp.message_handler(state=RequestForm.request)
async def process_request(message: types.Message, state: FSMContext):
    request = message.text.strip()
    if request.find("$$") != -1:
        setSetting("chatGPTRequest",request)
        await message.answer(text='Готово!',reply_markup=keyboardMain)
    else:
        await message.answer(text='Ошибка! Символы "$$" не найдены',reply_markup=keyboardMain)
    await state.finish()

@dp.message_handler(Text(equals="Изменить время ожидания"))
async def timeChange_start(message: types.Message):
    await TimeToWaitForm.timeLowRange.set()
    await message.answer(text="Напишите нижнюю границу времени в минутах. Если пишите нецелое кол-во минут, то пишите через точку(например, 2.5)",reply_markup=keyboardCancel)

@dp.message_handler(state=TimeToWaitForm.timeLowRange)
async def process_timeLowRange(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data["timeLowRange"] = message.text.strip()
    await TimeToWaitForm.next()
    await message.reply(text="Напишите верхнюю границу времени в минутах. Если пишите нецелое кол-во минут, то пишите через точку(например, 2.5)",reply_markup=keyboardCancel)

@dp.message_handler(state=TimeToWaitForm.timeHighRange)
async def process_timeHighRange(message: types.Message, state: FSMContext):
    try:
        async with state.proxy() as data:
            tmp1 = float(data["timeLowRange"])
            tmp2 = float(message.text.strip())
        if tmp1 <= tmp2:
            setSetting('downTimeToWait',f"{int(tmp1 * 60)}")
            setSetting('upTimeToWait', f"{int(tmp2 * 60)}")
            await message.reply(text=f"Готово!Ваше текущее ожидание: от {tmp1} мин. до {tmp2} мин.",reply_markup=keyboardMain)
        else:
            await message.reply(text="Ошибка! Ваша нижняя граница больше верхней. Повторите снова",reply_markup=keyboardMain)
    except:
        await message.reply(text="Непридвиденная ошибка",reply_markup=keyboardMain)
    finally:
        await state.finish()

@dp.message_handler(Text(equals=r'Посмотреть "админов"'))
async def getAdmins(message:types.Message):
    async with aiosqlite.connect("accounts.db")as db:
        async with db.execute("SELECT phoneNumber,adminId FROM admins;")as cur:
            admins = await cur.fetchall()
    if len(admins) > 0:
        adminsButtons = InlineKeyboardMarkup()
        for admin in admins:
            if admin[1] == str(message.from_user.id):
                adminsButtons.add(InlineKeyboardButton(text=str(admin[0]), callback_data=f"view {admin[0]}"),
                                  InlineKeyboardButton(text=str(admin[1]), callback_data=f"view {admin[1]}"),
                                  InlineKeyboardButton(text="-", callback_data=f"fake-delete {admin[0]}"))
            else:
                adminsButtons.add(InlineKeyboardButton(text=str(admin[0]), callback_data=f"view {admin[0]}"),
                                  InlineKeyboardButton(text=str(admin[1]),callback_data=f"view {admin[1]}"),
                                  InlineKeyboardButton(text="Удалить", callback_data=f"Удалить админа {admin[0]}"))
        paginator = Paginator(adminsButtons, size=5, dp=dp)
        await message.answer(text="Добавленные админы. Чтобы удалить, нажмите на кнопку удаления",reply_markup=paginator())
    else:
        await message.answer(text="Админов нет...", reply_markup=keyboardMain)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('Удалить админа'))
async def process_callback_deleteAdmin(callback_query: types.CallbackQuery):
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
    await message.answer("Напишите никнейм для этого аккаунта",reply_markup=keyboardCancel)

@dp.message_handler(state=AdminForm.phoneNumberAdmin)
async def process_phoneNumberAdmin(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['phoneNumberAdmin'] = message.text.strip()
    await AdminForm.next()
    await message.reply("Напишите id аккаунта",reply_markup=keyboardCancel)

@dp.message_handler(state=AdminForm.adminId)
async def process_adminId(message:types.Message,state:FSMContext):
    async with state.proxy() as data:
        data['adminId'] = message.text.strip()

    async with aiosqlite.connect("accounts.db")as db:
        try:
            if data["adminId"].isdigit():
                await db.execute("INSERT INTO admins(phoneNumber,adminId) VALUES(?,?);",(data["phoneNumberAdmin"],data["adminId"]))
                await db.commit()
                await state.finish()
                await message.reply("Готово!", reply_markup=keyboardMain)
            else:
                await message.reply("Некорректные данные!", reply_markup=keyboardMain)
        except aiosqlite.IntegrityError:
            await state.finish()
            await message.reply("Админ с такими данными уже сущетсвует!",reply_markup=keyboardMain)

@dp.message_handler(Text(equals='Изменить API ключ'))
async def changeApiKey(message: types.Message):
    await OpenAIKeyForm.api_key.set()
    await message.answer(text='Напишите новый апи ключ',reply_markup=keyboardCancel)

@dp.message_handler(state=OpenAIKeyForm.api_key)
async def process_api_key(message: types.Message, state: FSMContext):
    await state.finish()
    key = message.text.strip()
    setSetting('openai_api_key',key)
    await message.answer(text='Готово!',reply_markup=keyboardMain)

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
                    f"view {str(account[0])}"),InlineKeyboardButton(text="Удалить",callback_data=f"Удалить аккаунт {str(account[0])}"))
            paginator = Paginator(accountsButtons,size=5,dp=dp)
            await message.answer(text="Добавленные аккаунты. Чтобы удалить, нажмите на кнопку удаления",reply_markup=paginator())
        else:
            await message.answer(text="Аккаунтов нет...",reply_markup=keyboardMain)
    except:
        await message.answer("Непридвиденная ошибка!", reply_markup=keyboardMain)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('Удалить аккаунт'))
async def process_callback_deleteUser(callback_query: types.CallbackQuery):
    userToDelete = callback_query.data.split(" ")[-1]
    try:
        from main import usersToCheck
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

@dp.message_handler(Text(equals="Изменить минимальное кол-во символов в комментарии"))
async def changeMinSymbols(message: types.Message):
    await MinSymbolsForm.minSymbols.set()
    await message.answer(text="Напишите минимальное кол-во символов в комментарии",reply_markup=keyboardCancel)

@dp.message_handler(state=MinSymbolsForm.minSymbols)
async def process_minSymbols(message: types.Message, state: FSMContext):
    minSymbols = message.text.strip()
    if minSymbols.isdigit():
        if int(minSymbols) >= 0:
            setSetting("minSymbols",minSymbols)
            await message.answer(text="Готово!",reply_markup=keyboardMain)
    else:
        await message.answer(text='Некорректные данные!',reply_markup=keyboardMain)
    await state.finish()

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
    2. API_ID и API_HASH. Как их получить? Заходим на сайт https://my.telegram.org/. Это официаьный сайт телеграма. В нём мы создаем новое приложение, после получаем API_ID и API_HASH.\n
    3. Доступ к телеграм аккаунту. Вам на аккаунт придет код, необходимый для работы.\n
    3.1. По желанию можно добавить прокси. Поддерживается ТОЛЬКО SOCKS5 прокси.
    Вы можете изменить время ожидания перед комментированием, для этого просто нажмите на соответствующую кнопку и введите сначала нижнюю границу (минимальное кол-во минут), потом верхнюю(максимальное кол-во минут)\n
    Кто такие Админы? Это те люди, которые могут пользоваться ботом\n
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
    await UserForm.next()
    await message.reply("Напишите ip от прокси SOCKS5(если не хотите его использовать, то напишите прочерк(-))",reply_markup=keyboardCancel)
        

@dp.message_handler(state=UserForm.ip)
async def process_ip(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['ip'] = message.text.strip()
    await UserForm.next()
    await message.reply("Напишите порт от прокси SOCKS5(если не хотите его использовать, то напишите прочерк(-))",reply_markup=keyboardCancel)

@dp.message_handler(state=UserForm.port)
async def process_port(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['port'] = message.text.strip()
    await UserForm.next()
    await message.reply("Напишите логин от прокси SOCKS5(если не хотите его использовать, то напишите прочерк(-))",reply_markup=keyboardCancel)

@dp.message_handler(state=UserForm.proxyLogin)
async def process_login(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['login'] = message.text.strip()
    await UserForm.next()
    await message.reply("Напишите пароль от прокси SOCKS5(если не хотите его использовать, то напишите прочерк(-))",reply_markup=keyboardCancel)

@dp.message_handler(state=UserForm.proxyPassword)
async def process_password(message: types.Message, state: FSMContext):
    global client, user
    async with state.proxy() as data:
        user = User(data["phoneNumber"], data["app_id"], data["app_hash"],data['ip'],data['port'],data['login'],message.text.strip())
        proxy = (python_socks.ProxyType.SOCKS5,data['ip'],data['port'],True,data['login'],message.text.strip())
    try:
        if data['ip'] != "-" and data['port'] != "-" and data['login'] != "-" and message.text.strip() != "-":
            client = TelegramClient(session=f'sessions/{user.phoneNumber}', api_id=int(user.app_id),
                                    api_hash=str(user.app_hash),proxy=proxy,app_version="4.0",system_version="IOS 14",device_model="iPhone 14")
        else:
            client = TelegramClient(session=f'sessions/{user.phoneNumber}', api_id=int(user.app_id),
                                    api_hash=str(user.app_hash),app_version="4.0",system_version="IOS 14",device_model="iPhone 14")
        await client.connect()
        if not await client.is_user_authorized():
            await client.send_code_request(phone=data["phoneNumber"])
            await message.answer("Введите код, который пришел вам в телеграм. ВНИМАНИЕ! Поставьте в любом месте нижнее подчеркивание(_), иначе придется проходить все этапы регистрации опять!", reply_markup=keyboardCancel)
            await UserForm.next()
        else:
            await saveUser(message,state)
    except Exception as e:
        print(f'Error!{e}')
        await removeSessionFile(user.phoneNumber)
        await message.answer("Непридвиденная ошибка!", reply_markup=keyboardMain)
        await state.finish()

@dp.message_handler(state=UserForm.code)
async def process_code(message: types.Message, state: FSMContext):
    global user
    try:
        await client.sign_in(user.phoneNumber,message.text.strip().replace("_",""))
        await saveUser(message, state)
    except telethon.errors.SessionPasswordNeededError:
        async with state.proxy() as data:
            data["code"] = message.text.strip()
        await UserForm.next()
        await message.answer(text="Введите пароль от 2FA",reply_markup=keyboardCancel)
    except:
        await removeSessionFile(user.phoneNumber)
        await message.answer("Непридвиденная ошибка!", reply_markup=keyboardMain)
        await state.finish()

@dp.message_handler(state=UserForm.password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text.strip()
    try:
        async with state.proxy() as data:
            await client.sign_in(password=password)
            await saveUser(message,state)
    except:
        await removeSessionFile(user.phoneNumber)
        await state.finish()
        await message.answer("Непридвиденная ошибка!",reply_markup=keyboardMain)

async def saveUser(message: types.Message,state: FSMContext):
    try:
        async with aiosqlite.connect("accounts.db") as db:
            await db.execute("INSERT INTO users (phoneNumber, app_id, app_hash, IP, PORT, login, password) VALUES(?,?,?,?,?,?,?);",
                             (user.phoneNumber, user.app_id, user.app_hash,user.ip,user.port,user.login,user.password))
            await db.commit()
        await client.disconnect()
        from main import usersToCheck
        usersToCheck.append(UserChecking(user.phoneNumber, user.app_id, user.app_hash,user.ip,user.port,user.login,user.password))
        await message.answer("Готово!", reply_markup=keyboardMain)
        await state.finish()
    except aiosqlite.IntegrityError:
        await removeSessionFile(user.phoneNumber)
        await message.answer("Ошибка!Аккаунт с такими данными уже существует!", reply_markup=keyboardMain)
        await state.finish()

async def removeSessionFile(sessionName):
    try:
        os.remove(f"sessions/{sessionName}.session")
    except:
        pass

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    dp.middleware.setup(AdminMiddleware())
    while True:
        try:
            executor.start_polling(dp, skip_updates=True,loop=loop)
        except aiohttp.client_exceptions.ServerDisconnectedError:
            print(f'Server was crashed.Trying to restart..')