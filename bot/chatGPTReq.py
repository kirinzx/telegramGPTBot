import logging
from config import getSetting
import python_socks
import async_timeout
import socks
import configparser
from telethon import TelegramClient, events
import asyncio
from asyncio import Queue
import threading
class ChatGPTTG:
    phoneNumber = None
    app_id = None
    app_hash = None
    proxy = None
    client: TelegramClient | None = None
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.message_queue = Queue()
        self.answer_future = None
    def start(self):
        thread = threading.Thread(target=self.__start,name='chatGPT_Thread')
        thread.start()
    def __setData(self):
        config = configparser.ConfigParser()
        config.read('config.ini', encoding='utf-8')
        self.phoneNumber = config.get('TGACC','phoneNumber')
        self.app_id = config.get('TGACC','app_id')
        self.app_hash = config.get('TGACC','app_hash')
        tmpProxy = config.get('TGACC','proxy_ip_port_login_pass').split(':')
        if not '-' in tmpProxy and '' not in tmpProxy:
            self.proxy = (python_socks.ProxyType.SOCKS5,tmpProxy[0],tmpProxy[1],True,tmpProxy[2],tmpProxy[3])
    def __setClient(self):
        if self.app_hash and self.app_id and self.phoneNumber:
            if self.proxy:
                self.client = TelegramClient(session=f"mainSession/{self.phoneNumber}", api_id=int(self.app_id), api_hash=self.app_hash, proxy=self.proxy,app_version="4.0",system_version="IOS 14",device_model="iPhone 14",loop=self.loop)
            else:
                self.client = TelegramClient(session=f"mainSession/{self.phoneNumber}", api_id=int(self.app_id), api_hash=self.app_hash, app_version="4.0",system_version="IOS 14",device_model="iPhone 14",loop=self.loop)
            
            async def getAnswer(event):
                self.answer_future.set_result(event.raw_text)

            self.client.add_event_handler(getAnswer,events.NewMessage(chats=['vitaliy_chatGPT_bot']))
            
            self.client.start()
            self.client.loop.run_forever()
    def __start(self):
        asyncio.set_event_loop(self.loop)
        self.__setData()
        asyncio.ensure_future(self.process_messages())
        self.__setClient()


    async def stop(self):
        if self.client:
            await self.client.disconnect()
    

    async def req(self,message):
        await self.message_queue.put(message)

        # Ждем, пока получим ответ
        answer = await self.answer_future
        return answer
    
    async def process_messages(self):
        while True:
            message = await self.message_queue.get()
            prompt = getSetting('chatgptrequest').replace('$$', message)
            await self.client.send_message('vitaliy_chatGPT_bot', prompt)
            self.answer_future = self.loop.create_future()