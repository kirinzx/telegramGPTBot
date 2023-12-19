import asyncio
import logging
from openai import AsyncOpenAI
from config import getSetting
import httpx


async def req(post):
    try:
        proxy = getSetting('proxy')
        if proxy:
            client = AsyncOpenAI(
                api_key=getSetting('openai_api_key'),
                http_client=httpx.AsyncClient(
                    proxies="http://" + getSetting('proxy'),
                )
            )
        else:
            client = AsyncOpenAI(api_key=getSetting('openai_api_key'))
        prompt = getSetting('chatgptrequest')
        request = prompt.replace("$$", str(post).strip(), 1)
        response = await client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": request}])
        return response.choices[0].message.content.strip().replace('"', '')
    except Exception as e:
        logging.info(f"Error in chatgpt req. {e}")
        return None
