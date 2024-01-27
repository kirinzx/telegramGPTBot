import aiosqlite
from itertools import islice
from typing import Iterable, Any, Iterator, Callable, Coroutine, List
from telethon import TelegramClient, events, functions
import telethon
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State
from aiogram.dispatcher import FSMContext
from aiogram import Dispatcher, types, Bot
from aiogram.types import CallbackQuery
import asyncio
import random
from config import getSetting
import python_socks
import async_timeout
import socks
import logging
from chatGPTReq import req


class User:
    def __init__(self, phoneNumber, app_id, app_hash, message=None, chatgpt=False, hyperlink=None, proxy_ip=None, proxy_port=None, proxy_login=None, proxy_password=None):
        self.phoneNumber = phoneNumber
        self.app_id = app_id
        self.app_hash = app_hash
        self.message = message
        self.chatgpt = chatgpt
        self.hyperlink = hyperlink
        self.proxy_ip = proxy_ip
        self.proxy_port = proxy_port
        self.proxy_login = proxy_login
        self.proxy_password = proxy_password


class Paginator:
    def __init__(
            self,
            data: types.InlineKeyboardMarkup |
        Iterable[types.InlineKeyboardButton] |
        Iterable[Iterable[types.InlineKeyboardButton]],
            state: State = None,
            callback_startswith: str = 'page_',
            size: int = 8,
            page_separator: str = '/',
            dp: Dispatcher = None
    ):
        """
        Example: paginator = Paginator(data=kb, size=5)

        :param data: An iterable object that stores an InlineKeyboardButton.
        :param callback_startswith: What should callback_data begin with in handler pagination. Default = 'page_'.
        :param size: Number of lines per page. Default = 8.
        :param state: Current state.
        :param page_separator: Separator for page numbers. Default = '/'.
        """
        self.dp = dp
        self.page_separator = page_separator
        self._state = state
        self._size = size
        self._startswith = callback_startswith
        if isinstance(data, types.InlineKeyboardMarkup):
            self._list_kb = list(
                self._chunk(
                    it=data.inline_keyboard,
                    size=self._size
                )
            )
        elif isinstance(data, Iterable):
            self._list_kb = list(
                self._chunk(
                    it=data,
                    size=self._size
                )
            )
        else:
            raise ValueError(f'{data} is not valid data')

    """
    Class for pagination's in aiogram inline keyboards
    """

    def __call__(
            self,
            current_page=0,
            *args,
            **kwargs
    ) -> types.InlineKeyboardMarkup:
        """
        Example:

        await message.answer(
            text='Some menu',
            reply_markup=paginator()
        )

        :return: InlineKeyboardMarkup
        """
        _list_current_page = self._list_kb[current_page]

        paginations = self._get_paginator(
            counts=len(self._list_kb),
            page=current_page,
            page_separator=self.page_separator,
            startswith=self._startswith
        )
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[*_list_current_page, paginations])

        # keyboard.add(_list_current_page)
        # keyboard.row(paginations)
        # keyboard.adjust(3)

        if self.dp:
            self.paginator_handler()

        return keyboard

    @staticmethod
    def _get_page(call: types.CallbackQuery) -> int:
        """
        :param call: CallbackQuery in paginator handler.
        :return: Current page.
        """
        return int(call.data[-1])

    @staticmethod
    def _chunk(it, size) -> Iterator[tuple[Any, ...]]:
        """
        :param it: Source iterable object.
        :param size: Chunk size.
        :return: Iterator chunks pages.
        """
        it = iter(it)
        return iter(lambda: tuple(islice(it, size)), ())

    @staticmethod
    def _get_paginator(
            counts: int,
            page: int,
            page_separator: str = '/',
            startswith: str = 'page_'
    ) -> list[types.InlineKeyboardButton]:
        """
        :param counts: Counts total buttons.
        :param page: Current page.
        :param page_separator: Separator for page numbers. Default = '/'.
        :return: Page control line buttons.
        """
        counts -= 1

        paginations = []

        if page > 0:
            paginations.append(
                types.InlineKeyboardButton(
                    text='⏮️️',
                    callback_data=f'{startswith}0'
                )
            )
            paginations.append(
                types.InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'{startswith}{page - 1}'
                ),
            )
        paginations.append(
            types.InlineKeyboardButton(
                text=f'{page + 1}{page_separator}{counts + 1}',
                callback_data='pass'
            ),
        )
        if counts > page:
            paginations.append(
                types.InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'{startswith}{page + 1}'
                )
            )
            paginations.append(
                types.InlineKeyboardButton(
                    text='⏭️',
                    callback_data=f'{startswith}{counts}'
                )
            )
        return paginations

    def paginator_handler(self) -> tuple[Callable[[CallbackQuery, FSMContext], Coroutine[Any, Any, None]], Text]:
        """
        Example:

        args, kwargs = paginator.paginator_handler()

        dp.register_callback_query_handler(*args, **kwargs)

        :return: Data for register handler pagination.
        """

        async def _page(call: types.CallbackQuery, state: FSMContext):
            page = self._get_page(call)

            await call.message.edit_reply_markup(
                reply_markup=self.__call__(
                    current_page=page
                )
            )
            await state.update_data({f'last_page_{self._startswith}': page})

        if not self.dp:
            return \
                (_page, Text(startswith=self._startswith))
        else:
            self.dp.register_callback_query_handler(
                _page,
                Text(startswith=self._startswith),
            )


class InspectableQueue(asyncio.Queue):
    _sentinel = object()
    _next = _sentinel

    async def get(self):
        if self._next is self._sentinel:
            return await super().get()
        value = self._next
        self._next = self._sentinel
        return value

    def get_nowait(self):
        if self._next is self._sentinel:
            return super().get_nowait()
        value = self._next
        self._next = self._sentinel
        return value

    def peek(self, default=_sentinel):
        if self._next is not self._sentinel:
            return self._next
        try:
            self._next = self._sentinel
            value = self._next = super().get_nowait()
        except asyncio.QueueEmpty:
            if default is self._sentinel:
                raise
            return default
        return value

    def empty(self):
        if self._next is not self._sentinel:
            return False
        return super().empty()

    def qsize(self):
        value = super.qsize()
        if self._next is not self._sentinel:
            value += 1
        return value


class MessageSender:
    def __init__(
            self,
            phone_number: str,
            api_id: int | str,
            api_hash: str, message=None,
            chatgpt=False, hyperlink=None,
            proxy_ip=None, proxy_port=None,
            proxy_login=None, proxy_password=None,
            loop=None, lock=None
    ):
        global num_list
        self.phone_number = phone_number
        self.api_id = api_id
        self.api_hash = api_hash
        self.message = message
        self.hyperlink = hyperlink
        self.chagpt = chatgpt
        self.chat = getSetting('tgstat_chat')
        if proxy_ip is not None and proxy_port is not None and proxy_login is not None and proxy_password is not None:
            self.proxy = (python_socks.ProxyType.SOCKS5, proxy_ip,
                          proxy_port, True, proxy_login, proxy_password)
        else:
            self.proxy = None
        self.lock: asyncio.Lock = lock
        self.loop: asyncio.AbstractEventLoop = loop
        senders.append(self)
        if len(num_list.keys()) > 0:
            num_list[self.phone_number] = ""
        else:
            num_list[self.phone_number] = "next"
        self.loop.create_task(self.__set_client())

    async def __set_client(self):
        self.client = TelegramClient(
            session=f'sessions/{self.phone_number}', api_id=int(self.api_id), api_hash=self.api_hash,
            system_version='IOS 14', device_model='iPhone 14', loop=self.loop
        )
        if self.proxy is not None:
            self.client.set_proxy(self.proxy)

        await self.client.start()
        if self.chat:
            await self.set_chat_entity()

    async def set_chat_entity(self):
        self.client.remove_event_handler(self.getmsg)
        chat_entity = await self.client.get_input_entity(self.chat)

        self.client.add_event_handler(
            self.getmsg, events.NewMessage(chats=chat_entity))

    async def stop(self):
        global num_list
        await self.client.disconnect()
        senders.remove(self)
        del num_list[self.phone_number]

    async def getmsg(self, event: telethon.events.NewMessage.Event):
        try:
            link_msg = event.message.message[event.message.message.index(
                't.me'):event.message.message.index('\n\n')]
            link_lst = link_msg.split('/')
            message_id = link_lst.pop(-1)
            link = '/'.join(link_lst)
        except Exception as e:
            logging.info(f'error in getmsg in {self.phone_number}. {e}')
            return

        if not message_id:
            return
        if not link:
            return
        try:
            await self.comment(message_id, link)
        except Exception as e:
            logging.info(f'Error in comment in {self.phone_number}. {e}')

    async def refill_queue(self):
        for sender in senders:
            await senders_queue.put(sender)

    async def text_admins(self, link):
        global bot
        async with aiosqlite.connect('accounts.db')as db:
            async with db.execute("SELECT adminId FROM admins;")as cur:
                admins = await cur.fetchall()

        for admin in admins:
            admin_id = admin[0]
            bot.send_message(int(admin_id),f'Ошибка при комментировании поста: {link}. Номер телефона комментируюего: {self.phone_number}')

    async def comment(self, message_id, link):
        global last_msg_id, num_list
        print(last_msg_id)
        print(message_id)
        keys = list(num_list.keys())
        current_index = keys.index(self.phone_number)
        if self.phone_number == keys[current_index] and num_list[keys[current_index]] == "next" and message_id != last_msg_id['id']:
            print(keys[current_index], 'next')
            last_msg_id['id'] = message_id
        else:
            print(self.phone_number, 'skip')
            return

        print("The next element is: ", end="")

        if current_index < len(keys) - 1:
            next_key = keys[current_index + 1]
            print(next_key)
            print(num_list)
            num_list[keys[current_index]] = ''
            num_list[next_key] = 'next'
            print(num_list)

        else:
            print("No next key found.")
            next_key = keys[0]
            print(next_key)
            print(num_list)
            num_list[keys[current_index]] = ''
            num_list[next_key] = 'next'
            print(num_list)

        chat = await self.client.get_input_entity(link)
        message = await self.client.get_messages(chat, ids=int(message_id))
        if self.message or self.chagpt:
            try:
                await self.client(functions.channels.JoinChannelRequest(chat))
            except:
                pass
        try:
            if self.message:
                await self.text_message(chat, message, link)

            if self.chagpt:
                await self.text_message_via_gpt(chat, message, link)

        except:
            await self.text_admins(link)
            await self.comment(message_id, link)

    async def text_message(self, chat: telethon.types.InputChannel, message: telethon.types.Message, link):
        chance = getSetting('chanceToComment')
        if random.random() <= float(int(chance) / 100):
            downtimeToWait = getSetting('downtimeToWait')
            upTimeToWait = getSetting('uptimeToWait')

            await asyncio.sleep(random.randint(int(downtimeToWait), int(upTimeToWait)))
            await self.client.send_message(chat, self.message, comment_to=message.id, parse_mode='html')
            await self.save_to_db(link)


    async def save_to_db(self, post, message=None):
        if message is None:
            message = self.message
        async with aiosqlite.connect('accounts.db')as db:
            await db.execute("INSERT INTO comments(phone_number, comment, post) VALUES(?,?,?);", (self.phone_number, message, post))
            await db.commit()

    async def text_message_via_gpt(self, chat: telethon.types.InputChannel, message: telethon.types.Message, link):
        chance = getSetting('chanceToComment')
        if random.random() <= float(int(chance) / 100):

            comment = await req(message.message)
            if not comment:
                return

            async with aiosqlite.connect("accounts.db")as db:
                async with db.execute("SELECT hyperlink FROM users WHERE phoneNumber = ?;", (self.phone_number,))as cur:
                    hyperlink = await cur.fetchone()

            if hyperlink[0] is not None:
                textToInsert = f'<a href="{hyperlink[0]}">Смотреть тут</a>'
                comment = "<span>" + comment + \
                    "</span>" + f"\n{textToInsert}"

            downtimeToWait = getSetting('downtimeToWait')
            upTimeToWait = getSetting('uptimeToWait')

            await asyncio.sleep(random.randint(int(downtimeToWait), int(upTimeToWait)))
            await self.client.send_message(entity=chat, message=comment, comment_to=message.id, parse_mode="html")

            await self.save_to_db(link, comment)


senders: List[MessageSender] = []
senders_queue = InspectableQueue()
num_list = {}
last_msg_id = {'id': 0}
bot = Bot(token=getSetting('telegram_bot_token'))