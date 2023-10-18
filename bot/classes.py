import aiosqlite
import threading
from aiogram import Dispatcher, types
from aiogram.types import CallbackQuery
from itertools import islice
from typing import Iterable, Any, Iterator, Callable, Coroutine
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State
from aiogram.dispatcher import FSMContext
from telethon import TelegramClient, events, errors
import asyncio
import random
from chatGPTReq import req
from config import getSetting
import python_socks
import async_timeout
import socks
import logging

class User:
    def __init__(self,phoneNumber,app_id,app_hash,ip,port,login,password):
        self.phoneNumber = phoneNumber
        self.app_id = app_id
        self.app_hash = app_hash
        self.ip = ip
        self.port = port
        self.login = login
        self.password = password

class Paginator:
    def __init__(
            self,
            data: types.InlineKeyboardMarkup |
                  Iterable[types.InlineKeyboardButton] |
                  Iterable[Iterable[types.InlineKeyboardButton]]
            ,
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
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[*_list_current_page, paginations])

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


class UserChecking:
    def __init__(self,session, app_id, app_hash,ip,port,login,password):
        self.session = session
        self.event = threading.Event()
        self.app_id = app_id
        self.app_hash = app_hash
        if ip != "-" and port != "-" and login != "-" and password != "-":
            self.proxy = (python_socks.ProxyType.SOCKS5,ip,port,True,login,password)
        else:
            self.proxy = None
        self.channels = []
        self.thread = threading.Thread(target=self.setClient, args=(self.session, self.app_id, self.app_hash),
                                       name=f"user_{self.session}-Thread")
        self.thread.start()
    async def getChannels(self):
        while True:
            tmpDialogs = []
            tmpDialogsIds = []
            try:
                for dialog in await self.client.get_dialogs():
                    if dialog.is_channel:
                        tmpDialogs.append(dialog)
                        tmpDialogsIds.append(dialog.id)
                for i in range(len(tmpDialogsIds)):
                    if not tmpDialogsIds[i] in self.channels:
                        self.channels.append(tmpDialogsIds[i])
                        await self.checkPosts(tmpDialogs[i])
                for channel in self.channels:
                    if not channel in tmpDialogsIds:
                        self.channels.remove(channel)
            except Exception as e:
                logging.info(f'Error!{e}')
            await asyncio.sleep(10)

    async def checkPosts(self, channel):
        @self.client.on(events.NewMessage(chats=channel.id))
        async def handler(event: events.NewMessage.Event):
            if channel.id in self.channels:
                try:
                    chance = getSetting('chanceToComment')
                    if random.random() <= float(int(chance) / 100):
                        message = await req(event.text)
                        minSymbols = getSetting('minSymbols')
                        if len(message) >= int(minSymbols):

                            async with aiosqlite.connect("accounts.db")as db:
                                async with db.execute("SELECT hyperlink FROM users WHERE phoneNumber = ?;",(self.session,))as cur:
                                    hyperlink = await cur.fetchone()
                            if hyperlink[0] != "-":
                                textToInsert = f'<a href="{hyperlink[0]}">Смотреть тут</a>'
                                message = "<span>" + message + "</span>" + f"\n{textToInsert}"
                            downtimeToWait = getSetting('downtimeToWait')
                            upTimeToWait = getSetting('uptimeToWait')
                            logging.info('sending a message')
                            await asyncio.sleep(random.randint(int(downtimeToWait),int(upTimeToWait)))
                            await self.client.send_message(entity=channel, message=message, comment_to=event,parse_mode = "html")
                            try:
                                channelEntity = await self.client.get_entity(event.chat_id)
                                if channelEntity.username:
                                    channelName = channelEntity.username
                                else:
                                    channelName = channelEntity.usernames[0]
                                post = f't.me/{channelName}/{event.message.id}'
                                channelName = '@' + channelName
                                comment = message
                                async with aiosqlite.connect('accounts.db')as db:
                                    await db.execute("INSERT INTO comments(nickname, channel, comment, post) VALUES(?,?,?,?);",(self.session, channelName, comment, post))
                                    await db.commit()
                            except Exception as e:
                                logging.info(f'Error!{e}')
                except Exception as e:
                    logging.info(f'Error!{e}')
            else:
                return

    def setClient(self,session, app_id, app_hash):
        loop = asyncio.SelectorEventLoop()
        asyncio.set_event_loop(loop)
        if self.proxy:
            self.client = TelegramClient(session=f"sessions/{session}", api_id=int(app_id), api_hash=app_hash, loop=loop, proxy=self.proxy,app_version="4.0",system_version="IOS 14",device_model="iPhone 14")
        else:
            self.client = TelegramClient(session=f"sessions/{session}", api_id=int(app_id), api_hash=app_hash, loop=loop, app_version="4.0",system_version="IOS 14",device_model="iPhone 14")
        self.client.start()
        self.client.loop.run_until_complete(self.getChannels())

    def stop(self):
        self.client.disconnect()
        self.thread.join()