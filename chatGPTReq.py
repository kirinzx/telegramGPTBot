import os
import openai

async def req(post):
    try:
        openai.api_key = os.environ.get("OPENAI_KEY")
        request = f"""
        Представь, что ты пользователь соц. сети и ты видишь такой пост:{post}.
        Прокомментируй его, используя максимум 10 слов, но не используя эти слова: промо,реклама,акция,скидка,распродажа,купон,бесплатно,рекламная,порно,секс,канал,паблик,источник,подпишись.
        Смотри внимательно на контекст, если идет речь об игре, пиши об игре, если идет речь о фильмах, сериалах, книгах, то пиши про них.
        """
        response = await openai.ChatCompletion.acreate(model="gpt-3.5-turbo",messages=[{"role":"user","content":request}])
        return response.choices[0].message.content.strip()
    except:
        return None