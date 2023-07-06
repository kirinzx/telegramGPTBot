import os
import openai

async def req(post):
    #try:
    openai.api_key = os.environ.get("OPENAI_KEY")
    request = f"Прокомментируй этот пост как пользователь, используя максимум 10 слов:{post}."
    response = await openai.ChatCompletion.acreate(model="gpt-3.5-turbo",messages=[{"role":"user","content":request}])
    return response.choices[0].message.content.strip()
    # except:
    #     return None