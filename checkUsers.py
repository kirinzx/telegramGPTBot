from telethon import TelegramClient
import asyncio
from telethon import events
from chatGPTReq import req
import random
import sqlite3
import threading

def startParsing(session,app_id,app_hash):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TelegramClient(session=f"sessions/{session}", api_id=int(app_id), api_hash=app_hash,loop=loop)
    client.loop.run_until_complete(getChannels(client))
    return client

async def getChannels(client):
    async with client:
        for dialog in await client.get_dialogs():
            if dialog.is_channel:
                await checkPosts(client, dialog)


async def checkPosts(client:TelegramClient,channel):
    @client.on(events.NewMessage(chats=channel.id))
    async def handler(event):
        message = await req(event.text)
        if message:
            try:
                await asyncio.sleep(random.randint(120,300))
                await client.send_message(entity=channel,message=message,comment_to=event)
            except:
                pass


def getUsersClient(session,app_id,app_hash):
    client = startParsing(session,app_id,app_hash)
    client.start()
    client.run_until_disconnected()
