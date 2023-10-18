import openai
from config import getSetting

async def req(post):
    try:
        openai.api_key = getSetting('openai_api_key')
        prompt = getSetting('chatGPTRequest')
        request = prompt.replace("$$",str(post).strip(),1)
        response = await openai.ChatCompletion.acreate(model="gpt-3.5-turbo",messages=[{"role":"user","content":request}])
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(e)
        return None