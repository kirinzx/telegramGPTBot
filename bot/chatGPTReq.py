from openai import AsyncOpenAI
from config import getSetting
import httpx

async def req(post):
    try:
        proxy = getSetting('proxy')
        if proxy:
            openai = AsyncOpenAI(
                api_key = getSetting('openai_api_key'),
                http_client=httpx.AsyncClient(
                    proxies="http://" + getSetting('proxy'),
                )
            )
        else:
            openai = AsyncOpenAI(
                api_key=getSetting('openai_api_key')
            )
        prompt = getSetting('chatGPTRequest')
        request = prompt.replace("$$",str(post).strip(),1)
        response = await openai.ChatCompletion.acreate(model="gpt-3.5-turbo",messages=[{"role":"user","content":request}])
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(e)
        return None