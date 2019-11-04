import json
import logging
import os
from typing import List

import httpx
import telegram
from pynamodb.attributes import NumberAttribute, UnicodeAttribute
from pynamodb.models import Model

logger = logging.getLogger()
if logger.handlers:
    for handler in logger.handlers:
        logger.removeHandler(handler)
logging.basicConfig(level=logging.INFO)

OK_RESPONSE = {
    "statusCode": 200,
    "headers": {"Content-Type": "application/json"},
    "body": json.dumps("ok"),
}
ERROR_RESPONSE = {"statusCode": 400, "body": json.dumps("Oops, something went wrong!")}

BOT_USERMAME = os.environ.get("BOT_USERMAME")

url = "https://en.wikipedia.org/api/rest_v1/page/random/summary"


class ChatModel(Model):
    id = NumberAttribute(hash_key=True)
    hour = NumberAttribute()

    class Meta:
        table_name = "chats"
        region = "eu-west-3"
        aws_access_key_id = os.environ.get("AWS_ACCESS")
        aws_secret_access_key = os.environ.get("AWS_SECRET")


def configure_telegram():
    """
    Configures the bot with a Telegram Token.
    Returns a bot instance.
    """

    telegram_token = os.environ.get("TELEGRAM_TOKEN")
    if not telegram_token:
        logger.error("The TELEGRAM_TOKEN must be set")
        raise NotImplementedError

    return telegram.Bot(telegram_token)


bot = configure_telegram()


def handler(event, context) -> dict:

    logger.info(f"Event: {event}")

    update = telegram.Update.de_json(json.loads(event.get("body")), bot)
    chat_id = update.effective_message.chat.id if update.effective_message else None

    text = update.effective_message.text

    if text in ["/start", f"/start@{BOT_USERMAME}"]:
        start(chat_id)
    elif text in ["/stop", f"/stop@{BOT_USERMAME}"]:
        stop(chat_id)
    elif text in ["/article", f"/article@{BOT_USERMAME}"]:
        article(chat_id)

    return OK_RESPONSE


def daily(event, context) -> dict:
    article = get_random_article_url()
    chats = get_chats()

    for chat in chats:
        bot.send_message(chat_id=chat.id, text=article)

    return OK_RESPONSE


def start(chat_id: int) -> None:
    text = (
        "I will send you a random article every day at 8PM, to stop "
        "this send /stop. If you want a random article now send "
        "/article"
    )

    save_chat_id(chat_id)

    bot.send_message(chat_id=chat_id, text=text)


def stop(chat_id: int) -> None:
    delete_chat_id(chat_id)
    bot.send_message(chat_id=chat_id, text="Stopped!")


def article(chat_id: int):
    article = get_random_article_url()
    bot.send_message(chat_id=chat_id, text=article)


def get_random_article_url() -> str:
    response = httpx.get(url)
    return response.json()["content_urls"]["desktop"]["page"]


def get_chats() -> List[ChatModel]:
    return ChatModel.scan()


def save_chat_id(chat_id: int) -> None:
    if not ChatModel.count(chat_id):
        ChatModel(chat_id, hour=19).save()


def delete_chat_id(chat_id: int) -> None:
    chats = ChatModel.query(chat_id)
    for chat in chats:
        chat.delete()
