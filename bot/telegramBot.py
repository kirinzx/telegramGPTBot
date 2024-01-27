import asyncio
import logging
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
from classes import User, Paginator, MessageSender, senders, bot
from config import getSetting, setSetting
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
dp = Dispatcher(bot, storage=storage)

keyboardCancel = ReplyKeyboardMarkup(keyboard=[
    ["Отменить"],
])

keyboardMain = ReplyKeyboardMarkup(keyboard=[
    [r'Добавить "админа"', "Добавить аккаунт для комментирования"],
    ["Как я работаю?", 'Изменить настройки', 'Получить отчет'],
    [r'Посмотреть "админов"', "Посмотреть добавленные аккаунты"],
], resize_keyboard=True)

keyboardSettings = ReplyKeyboardMarkup(keyboard=[
    ["Изменить шанс комментирования", "Изменить время ожидания",
        "Изменить чат/канал для получения сообщений"],
    ['Изменить запрос к chatgpt', 'Изменить api ключ openai',
        "Изменить прокси для запроса к chatgpt"],
    ['Назад']
], resize_keyboard=True)

client: TelegramClient = None
user: User = None
phoneNumber = None
lock = None


@dp.message_handler(commands="start")
async def start(message: types.Message):
    downtimeToWait = getSetting('downTimeToWait')
    upTimeToWait = getSetting('upTimeToWait')
    prompt = getSetting('chatgptrequest')
    chance = getSetting("chanceToComment")
    proxy = getSetting("proxy")
    await message.answer(
        text=f"Ваше текущее время ожидания: от {round(int(downtimeToWait) / 60,1)} мин. до {round(int(upTimeToWait) / 60,2)} мин.\nВаш шанс оставить комментарий: {chance}%.\nВаш запрос к chatgpt: {prompt}\nВаш прокси: {proxy}",
        reply_markup=keyboardMain
    )


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


@dp.message_handler(Text(equals='Назад'))
async def getBack(message: types.Message):
    await message.answer(text='Выберите необходимую опцию', reply_markup=keyboardMain)


@dp.message_handler(Text(equals='Получить отчет'))
async def sendReport(message: types.Message):
    async with aiosqlite.connect('accounts.db')as db:
        async with db.execute('SELECT phone_number, comment, post from comments')as cur:
            comments = await cur.fetchall()
            comments.insert(
                0, ('Номер телефона', 'Комментарий', 'Пост'))

    thread = threading.Thread(target=sendExcel, args=(
        comments, asyncio.get_event_loop(), message.from_id))

    thread.start()


def sendExcel(data, botLoop, chat_id):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    excel = openpyxl.Workbook()
    sheet = excel.active
    for item in data:
        sheet.append(item)
    excelBytes = io.BytesIO()
    excel.save(excelBytes)
    excelBytes.seek(0)
    botLoop.create_task(bot.send_document(
        chat_id, types.InputFile(excelBytes, filename='отчет.xlsx')))


@dp.message_handler(Text(equals="Изменить прокси для запроса к chatgpt"))
async def change_proxy_for_gpt(message: types.Message):
    await ProxyForm.proxy.set()
    await message.answer(text='Напишите данные от HTTP прокси в формате ЛОГИН:ПАРОЛЬ@IP:ПОРТ', reply_markup=keyboardCancel)


@dp.message_handler(state=ProxyForm.proxy)
async def process_proxy(message: types.Message, state: FSMContext):
    setSetting('proxy', message.text.strip())
    await message.answer(text='Готово!', reply_markup=keyboardMain)


@dp.message_handler(Text(equals="Изменить чат/канал для получения сообщений"))
async def change_channel_to_grab(message: types.Message):
    await ChatForm.chat.set()
    await message.answer('Напишите ссылку(пригласительную или другую) на чат/канал или его id', reply_markup=keyboardCancel)


@dp.message_handler(state=ChatForm.chat)
async def process_chat(message: types.Message, state: FSMContext):
    chat = message.text.strip()
    setSetting('tgstat_chat', chat)
    for sender in senders:
        sender.chat = chat
        await sender.set_chat_entity()

    await state.finish()
    await message.answer('Готово!', reply_markup=keyboardMain)


@dp.message_handler(Text(equals="Изменить запрос к chatgpt"))
async def changeRequest_start(message: types.Message):
    await ChatGPTRequestForm.request.set()
    await message.answer(text='Напишите желаемый запрос к chatgpt. ОБЯЗАТЕЛЬНО! Где должен быть текст поста, поставьте эти символы - "$$"(без кавычек). При отсутствии этих символов, изменение не будет выполнено', reply_markup=keyboardCancel)


@dp.message_handler(state=ChatGPTRequestForm.request)
async def process_request(message: types.Message, state: FSMContext):
    request = message.text.strip()
    if request.find("$$") != -1:
        setSetting("chatgptrequest", request)
        await message.answer(text='Готово!', reply_markup=keyboardMain)
    else:
        await message.answer(text='Ошибка! Символы "$$" не найдены', reply_markup=keyboardMain)
    await state.finish()


@dp.message_handler(Text(equals='Изменить api ключ openai'))
async def changeApiKey(message: types.Message):
    await OpenAIKeyForm.key.set()
    await message.answer(text='Напишите новый апи ключ', reply_markup=keyboardCancel)


@dp.message_handler(state=OpenAIKeyForm.key)
async def process_api_key(message: types.Message, state: FSMContext):
    await state.finish()
    key = message.text.strip()
    setSetting('openai_api_key', key)
    await message.answer(text='Готово!', reply_markup=keyboardMain)


@dp.message_handler(Text(equals="Изменить шанс комментирования"))
async def changeChance_start(message: types.Message):
    await ChanceForm.chance.set()
    await message.answer(text="Напишите шанс комментирования в процентах, но без знака процента. Пример: 50. Важно! Число процентов не должно превышать 100 и быть меньше 0", reply_markup=keyboardCancel)


@dp.message_handler(state=ChanceForm.chance)
async def process_chance(message: types.Message, state: FSMContext):
    chance = message.text.strip()
    try:
        if chance.isdigit():
            if 0 <= int(chance) <= 100:
                setSetting('chanceToComment', chance)
                await message.answer(text="Готово!", reply_markup=keyboardMain)
            else:
                await message.answer(text="Некорректные данные!", reply_markup=keyboardMain)
        else:
            await message.answer(text="Некорректные данные!", reply_markup=keyboardMain)
    except:
        await message.answer(text="Непредвиденная ошибка!", reply_markup=keyboardMain)
    finally:
        await state.finish()


@dp.message_handler(Text(equals='Получить отчет'))
async def sendReport(message: types.Message):
    try:
        async with aiosqlite.connect('accounts.db')as db:
            async with db.execute('SELECT nickname, channel, comment, post from comments')as cur:
                comments = await cur.fetchall()
                comments.insert(
                    0, ('Номер телефона', 'Канал', 'Комментарий', 'Пост'))
        thread = threading.Thread(target=sendExcel, args=(
            comments, asyncio.get_event_loop(), message.from_id))
        thread.start()
    except Exception as e:
        await message.answer(text="Непридвиденная ошибка", reply_markup=keyboardMain)
        logging.info(f'Error in user settings. {e}')


def sendExcel(data, botLoop, chat_id):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    excel = openpyxl.Workbook()
    sheet = excel.active
    for item in data:
        sheet.append(item)
    excelBytes = io.BytesIO()
    excel.save(excelBytes)
    excelBytes.seek(0)
    botLoop.create_task(bot.send_document(
        chat_id, types.InputFile(excelBytes, filename='отчет.xlsx')))


@dp.message_handler(Text(equals="Изменить время ожидания"))
async def timeChange_start(message: types.Message):
    await TimeToWaitForm.timeLowRange.set()
    await message.answer(text="Напишите нижнюю границу времени в минутах. Если пишите нецелое кол-во минут, то пишите через точку(например, 2.5)", reply_markup=keyboardCancel)


@dp.message_handler(state=TimeToWaitForm.timeLowRange)
async def process_timeLowRange(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data["timeLowRange"] = message.text.strip()
    await TimeToWaitForm.next()
    await message.reply(text="Напишите верхнюю границу времени в минутах. Если пишите нецелое кол-во минут, то пишите через точку(например, 2.5)", reply_markup=keyboardCancel)


@dp.message_handler(state=TimeToWaitForm.timeHighRange)
async def process_timeHighRange(message: types.Message, state: FSMContext):
    try:
        async with state.proxy() as data:
            tmp1 = float(data["timeLowRange"])
            tmp2 = float(message.text.strip())
        if tmp1 <= tmp2:
            setSetting('downTimeToWait', f"{int(tmp1 * 60)}")
            setSetting('upTimeToWait', f"{int(tmp2 * 60)}")
            await message.reply(text=f"Готово!Ваше текущее ожидание: от {tmp1} мин. до {tmp2} мин.", reply_markup=keyboardMain)
        else:
            await message.reply(text="Ошибка! Ваша нижняя граница больше верхней. Повторите снова", reply_markup=keyboardMain)
    except:
        await message.reply(text="Непридвиденная ошибка", reply_markup=keyboardMain)
    finally:
        await state.finish()


@dp.message_handler(Text(equals=r'Посмотреть "админов"'))
async def getAdmins(message: types.Message):
    try:
        async with aiosqlite.connect("accounts.db")as db:
            async with db.execute("SELECT phoneNumber,adminId FROM admins;")as cur:
                admins = await cur.fetchall()
        if len(admins) > 0:
            adminsButtons = InlineKeyboardMarkup()
            for admin in admins:
                if admin[1] == str(message.from_user.id):
                    adminsButtons.add(InlineKeyboardButton(text=str(admin[0]), callback_data=f"view {admin[0]}"),
                                      InlineKeyboardButton(
                        text=str(admin[1]), callback_data=f"view {admin[1]}"),
                        InlineKeyboardButton(text="-", callback_data=f"fake-delete {admin[0]}"))
                else:
                    adminsButtons.add(InlineKeyboardButton(text=str(admin[0]), callback_data=f"view {admin[0]}"),
                                      InlineKeyboardButton(
                        text=str(admin[1]), callback_data=f"view {admin[1]}"),
                        InlineKeyboardButton(text="Удалить", callback_data=f"Удалить админа {admin[0]}"))
            paginator = Paginator(adminsButtons, size=5, dp=dp)
            await message.answer(text="Добавленные админы. Чтобы удалить, нажмите на кнопку удаления", reply_markup=paginator())
        else:
            await message.answer(text="Админов нет...", reply_markup=keyboardMain)
    except Exception as e:
        await message.answer(text="Непридвиденная ошибка", reply_markup=keyboardMain)
        logging.info(f'Error in user settings. {e}')


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
    except Exception as e:
        await callback_query.message.answer(text="Непридвиденная ошибка", reply_markup=keyboardMain)
        logging.info(f'Error in user settings. {e}')


@dp.message_handler(Text(equals='Добавить "админа"'))
async def addAdmin(message: types.Message):
    await AdminForm.phoneNumberAdmin.set()
    await message.answer("Напишите никнейм для этого аккаунта", reply_markup=keyboardCancel)


@dp.message_handler(state=AdminForm.phoneNumberAdmin)
async def process_phoneNumberAdmin(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['phoneNumberAdmin'] = message.text.strip()
    await AdminForm.next()
    await message.reply("Напишите id аккаунта", reply_markup=keyboardCancel)


@dp.message_handler(state=AdminForm.adminId)
async def process_adminId(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['adminId'] = message.text.strip()

    async with aiosqlite.connect("accounts.db")as db:
        try:
            if data["adminId"].isdigit():
                await db.execute("INSERT INTO admins(phoneNumber,adminId) VALUES(?,?);", (data["phoneNumberAdmin"], data["adminId"]))
                await db.commit()
                await state.finish()
                await message.reply("Готово!", reply_markup=keyboardMain)
            else:
                await message.reply("Некорректные данные!", reply_markup=keyboardMain)
        except aiosqlite.IntegrityError:
            await state.finish()
            await message.reply("Админ с такими данными уже сущетсвует!", reply_markup=keyboardMain)


@dp.message_handler(Text(equals="Посмотреть добавленные аккаунты"))
async def getAccounts(message: types.Message):
    try:
        async with aiosqlite.connect("accounts.db") as db:
            async with db.execute("SELECT phoneNumber FROM users;") as cursor:
                accounts = await cursor.fetchall()
        if len(accounts) > 0:
            accountsButtons = InlineKeyboardMarkup()
            for account in accounts:
                accountsButtons.add(InlineKeyboardButton(text=str(account[0]), callback_data=f"view {str(account[0])}"),
                                    InlineKeyboardButton(text="Настройки", callback_data=f"Настройки аккаунта/{str(account[0])}"), InlineKeyboardButton(
                    text="Удалить", callback_data=f"Удалить аккаунт/{str(account[0])}"))
            paginator = Paginator(accountsButtons, size=5, dp=dp)
            await message.answer(text="Добавленные аккаунты", reply_markup=paginator())
        else:
            await message.answer(text="Аккаунтов нет...", reply_markup=keyboardMain)
    except:
        await message.answer("Непридвиденная ошибка!", reply_markup=keyboardMain)


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('Настройки аккаунта'))
async def process_callback_user_settings(callback_query: types.CallbackQuery):
    try:
        phone_number = callback_query.data.split("/")[-1]
        async with aiosqlite.connect("accounts.db") as db:
            async with db.execute("SELECT message, chatgpt, hyperlink FROM users WHERE phoneNumber=?;", (phone_number,)) as cursor:
                data = await cursor.fetchone()
        dataButtons = InlineKeyboardMarkup()

        dataButtons.add(
            InlineKeyboardButton(
                text='Комментарий', callback_data=f"view {phone_number}"),
            InlineKeyboardButton(
                text=data[0] if data[0] else '-', callback_data=f"view comment/{phone_number}"),
            InlineKeyboardButton(
                text="Изменить", callback_data=f"change comment/{phone_number}")
        )

        if data[1]:
            tmp_btn = InlineKeyboardButton(
                text="Включено", callback_data=f"view1_ {phone_number}")
            action_btn = InlineKeyboardButton(
                text="Выключить", callback_data=f"turn/off/{phone_number}")
        else:
            tmp_btn = InlineKeyboardButton(
                text="Выключено", callback_data=f"view1_ {phone_number}")
            action_btn = InlineKeyboardButton(
                text="Включить", callback_data=f"turn/on/{phone_number}")

        dataButtons.add(
            InlineKeyboardButton(
                text='ChatGPT', callback_data=f"view1 {phone_number}"),
            tmp_btn,
            action_btn
        )

        dataButtons.add(
            InlineKeyboardButton(
                text='Ссылка', callback_data=f"view2 {phone_number}"),
            InlineKeyboardButton(
                text=data[2] if data[2] else '-', callback_data=f"view2_ {phone_number}"),
            InlineKeyboardButton(
                text="Изменить", callback_data=f"change link/{phone_number}")
        )

        await callback_query.message.answer(text=f'Номер телефона просматриваемого аккаунта: {phone_number}', reply_markup=dataButtons)
    except Exception as e:
        await callback_query.message.answer(text="Непридвиденная ошибка", reply_markup=keyboardMain)
        logging.info(f'Error in user settings. {e}')


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('change comment'))
async def process_callback_change_comment(callback_query: types.CallbackQuery):
    await MessageForm.message.set()
    global phoneNumber
    phoneNumber = callback_query.data.split("/")[-1]
    await callback_query.message.answer(text='Напишите комментарий', reply_markup=keyboardCancel)
    await callback_query.message.delete()


@dp.message_handler(state=MessageForm.message)
async def process_callback_message(message: types.Message, state: FSMContext):
    try:
        comment = message.text.strip()
        if comment == '-':
            comment = None
        async with aiosqlite.connect('accounts.db') as db:
            await db.execute("UPDATE users SET message=? WHERE phoneNumber=?", (comment, phoneNumber))
            await db.commit()
        for sender in senders:
            if sender.phone_number == phoneNumber:
                sender.message = comment
                break

        await state.finish()
        await message.answer('Готово!', reply_markup=keyboardMain)
    except Exception as e:
        await message.answer('Непридвиденная ошибка!', reply_markup=keyboardMain)
        logging.info(f'error in cb message {e}')
        await state.finish()


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('turn'))
async def process_callback_change_gpt(callback_query: types.CallbackQuery):
    try:
        data = callback_query.data.split("/")
        phoneNumber = data[-1]
        action = data[-2]
        if action == 'on':
            async with aiosqlite.connect('accounts.db') as db:
                await db.execute("UPDATE users SET chatgpt=? WHERE phoneNumber=?", (True, phoneNumber))
                await db.commit()
            for sender in senders:
                if sender.phone_number == phoneNumber:
                    sender.chagpt = True
                    break
        else:
            async with aiosqlite.connect('accounts.db') as db:
                await db.execute("UPDATE users SET chatgpt=? WHERE phoneNumber=?", (False, phoneNumber))
                await db.commit()
            for sender in senders:
                if sender.phone_number == phoneNumber:
                    sender.chagpt = False
                    break

        await callback_query.message.answer(text='Готово!', reply_markup=keyboardMain)
        await callback_query.message.delete()
    except Exception as e:
        await callback_query.message.answer(text='Непридвиденная ошибка!', reply_markup=keyboardMain)


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('change link'))
async def process_callback_change_link(callback_query: types.CallbackQuery):
    await HyperlinkForm.hyperlink.set()
    global phoneNumber
    phoneNumber = callback_query.data.split("/")[-1]
    await callback_query.message.answer(text='Напишите ссылку', reply_markup=keyboardCancel)
    await callback_query.message.delete()


@dp.message_handler(state=HyperlinkForm.hyperlink)
async def process_callback_hyperlink(message: types.Message, state: FSMContext):
    try:
        async with aiosqlite.connect('accounts.db') as db:
            await db.execute("UPDATE users SET hyperlink=? WHERE phoneNumber=?", (message.text.strip(), phoneNumber))
            await db.commit()
        for sender in senders:
            if sender.phone_number == phoneNumber:
                sender.hyperlink = message.text.strip()
                break
        await state.finish()
        await message.answer('Готово!', reply_markup=keyboardMain)
    except Exception as e:
        await message.answer('Непридвиденная ошибка!', reply_markup=keyboardMain)
        logging.info(f"error in cl link. {e}")
        await state.finish()


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('Удалить аккаунт'))
async def process_callback_deleteUser(callback_query: types.CallbackQuery):
    userToDelete = callback_query.data.split("/")[-1]
    try:
        for sender in senders:
            if sender.phone_number == userToDelete:
                await sender.stop()
                break
        async with aiosqlite.connect("accounts.db") as db:
            await db.execute("DELETE FROM users WHERE phoneNumber=?;", (userToDelete,))
            await db.commit()
        await removeSessionFile(userToDelete)

        await callback_query.message.answer(text=f"Готово! Пользователь {userToDelete} удалён!", reply_markup=keyboardMain)
        await callback_query.message.delete()
    except Exception as e:
        logging.info(f"error in delete user. {e}")
        await callback_query.message.answer(text="Непридвиденная ошибка!", reply_markup=keyboardMain)
        await callback_query.message.delete()


@dp.message_handler(Text(equals="Добавить аккаунт для комментирования"))
async def addAccount(message: types.Message):
    await UserForm.phoneNumber.set()
    await message.answer(text="Напишите номер телефона(с кодом страны)", reply_markup=keyboardCancel)


@dp.message_handler(Text(equals="Как я работаю?"))
async def getHelp(message: types.Message):
    await message.answer(text="""
    Вы добавляете аккаунт, и я от лица вашего аккаунта начинаю комментировать все новые посты во всех каналах, на которые подписан акккаунт.\n
    Что нужно для того, чтобы добавить аккаунт?
    1. Номер телефона\n
    2. API_ID и API_HASH. Как их получить? Заходим на сайт https://my.telegram.org/. Это официаьный сайт телеграма. В нём мы создаем новое приложение, после получаем API_ID и API_HASH.\n
    3. Доступ к телеграм аккаунту. Вам на аккаунт придет код, необходимый для работы.\n
    3.1. По желанию можно добавить прокси. Поддерживается ТОЛЬКО SOCKS5 прокси.\n
    4. Скидывайте мне ссылки на сообщения и я буду их комментировать\n
    Кто такие Админы? Это те люди, которые могут пользоваться ботом\n
    """, reply_markup=keyboardMain)


@dp.message_handler(state=UserForm.phoneNumber)
async def process_nickname(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['phoneNumber'] = message.text.strip().replace(' ', '')

    await UserForm.next()
    await message.reply("Напишите api_id", reply_markup=keyboardCancel)


@dp.message_handler(state=UserForm.app_id)
async def process_app_id(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['app_id'] = message.text.strip()

    await UserForm.next()
    await message.reply("Напишите api_hash", reply_markup=keyboardCancel)


@dp.message_handler(state=UserForm.app_hash)
async def process_app_hash(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['app_hash'] = message.text.strip()
    await UserForm.next()
    await message.reply("Напишите сообщение, которое нужно отправлять. Если не хотите это использовать, то напишите прочерк(-). Этот параметр можно будет изменить в будущем",
                        reply_markup=keyboardCancel
                        )


@dp.message_handler(state=UserForm.message)
async def process_message(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['message'] = message.html_text if message.text.strip() != '-' else None
    await UserForm.next()
    await message.reply("Напишите, нужно ли использовать chatgpt. Да/Нет. Этот параметр можно будет изменить в будущем",
                        reply_markup=keyboardCancel)


@dp.message_handler(state=UserForm.chatgpt)
async def process_chatgpt(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        answer = message.text.strip().capitalize()
        if answer == 'Да':
            data['chatgpt'] = True
            await UserForm.next()
            await message.reply("Напишите, какую ссылку оставлять в конце сообщения(работает только с chatgpt), если не нужна ссылка, то напишите прочерк(-). Этот параметр можно будет изменить в будущем", reply_markup=keyboardCancel)
        elif answer == 'Нет':
            data['chatgpt'] = False
            await UserForm.next()
            await message.reply("Напишите, какую ссылку оставлять в конце сообщения(работает только с chatgpt), если не нужна ссылка, то напишите прочерк(-). Этот параметр можно будет изменить в будущем", reply_markup=keyboardCancel)
        else:
            await state.finish()
            await message.reply("Ошибка! Ожидался ответ Да/Нет", reply_markup=keyboardMain)


@dp.message_handler(state=UserForm.hyperlink)
async def process_chatgpt(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['hyperlink'] = message.text.strip(
        ) if message.text.strip() != '-' else None
    await UserForm.next()
    await message.reply("Напишите данные от прокси SOCKS5 в формате: ip:port:логин:пароль.\nЕсли он не нужен, то напишите прочерк(-)",
                        reply_markup=keyboardCancel
                        )


@dp.message_handler(state=UserForm.proxy)
async def process_ip(message: types.Message, state: FSMContext):
    global client, user
    try:
        if message.text.strip() != '-':
            arr_proxy = message.text.strip().split(':')
            proxy = (python_socks.ProxyType.SOCKS5,
                     arr_proxy[0], arr_proxy[1], True, arr_proxy[2], arr_proxy[3])

            async with state.proxy() as data:
                user = User(data["phoneNumber"], data["app_id"], data["app_hash"],
                            data['message'], data['chatgpt'], data['hyperlink'], arr_proxy[0], arr_proxy[1], arr_proxy[2], arr_proxy[3]
                            )

            client = TelegramClient(session=f'sessions/{user.phoneNumber}', api_id=int(user.app_id),
                                    api_hash=str(user.app_hash), proxy=proxy, system_version="IOS 14",
                                    device_model="iPhone 14"
                                    )
        else:
            async with state.proxy() as data:
                user = User(data["phoneNumber"], data["app_id"],
                            data["app_hash"], data['message'], data['chatgpt'], data['hyperlink'])

            client = TelegramClient(session=f'sessions/{user.phoneNumber}', api_id=int(user.app_id),
                                    api_hash=str(user.app_hash), system_version="IOS 14",
                                    device_model="iPhone 14"
                                    )

        await client.connect()
        if not await client.is_user_authorized():
            await client.send_code_request(phone=data["phoneNumber"])
            await message.answer("Введите код, который пришел вам в телеграм. ВНИМАНИЕ! Поставьте в любом месте нижнее подчеркивание(_), иначе придется проходить все этапы регистрации опять!", reply_markup=keyboardCancel)
            await UserForm.next()
        else:
            await saveUser(message, state)
    except Exception as e:
        logging.info(f'Error!{e}')
        await removeSessionFile(user.phoneNumber)
        await message.answer("Непридвиденная ошибка!", reply_markup=keyboardMain)
        await state.finish()


@dp.message_handler(state=UserForm.code)
async def process_code(message: types.Message, state: FSMContext):
    global user
    try:
        await client.sign_in(user.phoneNumber, message.text.strip().replace("_", ""))
        await saveUser(message, state)
    except telethon.errors.SessionPasswordNeededError:
        async with state.proxy() as data:
            data["code"] = message.text.strip()
        await UserForm.next()
        await message.answer(text="Введите пароль от 2FA", reply_markup=keyboardCancel)
    except Exception as e:
        logging.info(f'error in code. {e}')
        await removeSessionFile(user.phoneNumber)
        await message.answer("Непридвиденная ошибка!", reply_markup=keyboardMain)
        await state.finish()


@dp.message_handler(state=UserForm.password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text.strip()
    try:
        await client.sign_in(password=password)
        await saveUser(message, state)
    except Exception as e:
        logging.info(f'error in password. {e}')
        await removeSessionFile(user.phoneNumber)
        await state.finish()
        await message.answer("Непридвиденная ошибка!", reply_markup=keyboardMain)


async def saveUser(message: types.Message, state: FSMContext):
    global lock
    try:
        await client.disconnect()
        async with aiosqlite.connect("accounts.db") as db:
            await db.execute("INSERT INTO users (phoneNumber, app_id, app_hash, message, chatgpt, hyperlink, IP, PORT, login, password) VALUES(?,?,?,?,?,?,?,?,?,?);",
                             (
                                 user.phoneNumber, user.app_id, user.app_hash,
                                 user.message, user.chatgpt, user.hyperlink, user.proxy_ip, user.proxy_port,
                                 user.proxy_login, user.proxy_password
                             )
                             )
            await db.commit()

        MessageSender(
            user.phoneNumber, user.app_id, user.app_hash,
            user.message, user.chatgpt, user.hyperlink, user.proxy_ip, user.proxy_port,
            user.proxy_login, user.proxy_password, asyncio.get_event_loop(), lock
        )
        await message.answer("Готово!", reply_markup=keyboardMain)
        await state.finish()
    except aiosqlite.IntegrityError:
        await removeSessionFile(user.phoneNumber)
        await message.answer("Ошибка!Аккаунт с такими данными уже существует!", reply_markup=keyboardMain)
        await state.finish()
    except Exception as e:
        logging.info(f'error in save user {e}')
        await state.finish()
        await message.answer("Непридвиденная ошибка!", reply_markup=keyboardMain)


async def removeSessionFile(sessionName):
    try:
        os.remove(f"sessions/{sessionName}.session")
        os.remove(f"sessions/{sessionName}.session-journal")
    except:
        pass


def main(loop: asyncio.AbstractEventLoop, lock_):
    global lock
    lock = lock_
    asyncio.set_event_loop(loop)
    dp.middleware.setup(AdminMiddleware())

    executor.start_polling(dp, skip_updates=True, loop=loop)
