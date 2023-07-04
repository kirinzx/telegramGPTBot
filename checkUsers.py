from telethon import TelegramClient
import asyncio
from telethon import events
from chatGPTReq import req

def startParsing():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TelegramClient(session=".", api_id=1, api_hash=".",loop=loop)
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
        await client.send_message(entity=channel,message=message,comment_to=event)

def main():
    client = startParsing()
    client.start()
    client.run_until_disconnected()