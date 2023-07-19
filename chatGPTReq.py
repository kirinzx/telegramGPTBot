from config import OPENAI_API_KEY
import openai
import aiofiles

async def req(post):
    try:
        openai.api_key = OPENAI_API_KEY
        prompt = ""
        async with aiofiles.open("chatGPTRequest.txt",mode="r",encoding="utf-8")as file:
            prompt = await file.read()
        request = prompt.replace("$$",str(post).strip(),1)
        response = await openai.ChatCompletion.acreate(model="gpt-3.5-turbo",messages=[{"role":"user","content":request}])
        return response.choices[0].message.content.strip()
    except:
        return None