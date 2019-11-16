import json
import logging
import os

import httpx
import telegram
from pynamodb.attributes import NumberAttribute, BooleanAttribute
from pynamodb.models import Model
from pynamodb.pagination import ResultIterator

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

BOT_USERNAME = os.environ.get("BOT_USERNAME")


class ChatModel(Model):
    id = NumberAttribute(hash_key=True)
    hour = NumberAttribute(default=19)
    daily = BooleanAttribute(default=True)

    class Meta:
        table_name = os.environ['DYNAMODB_TABLE']
        region = os.environ['REGION']
        host = os.environ['DYNAMODB_HOST']


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
    article_url = get_random_article_url()
    chats = get_daily_chats()

    for chat in chats:
        bot.send_message(chat_id=chat.id, text=article_url)

    return OK_RESPONSE


def start(chat_id: int) -> None:
    save_chat_id(chat_id)

    text = (
        "I will send you a random article every day at 8PM, to stop "
        "this send /stop. If you want a random article now send "
        "/article"
    )

    bot.send_message(chat_id=chat_id, text=text)


class AlreadyStoped(Exception):
    pass


def stop(chat_id: int) -> None:
    try:
        stop_chat_id(chat_id)
    except AlreadyStoped:
        text = "You are already unsubscribed"
    else:
        text = (
            "I will no longer send you a daily article, to activate it again"
            "send /start"
        )

    bot.send_message(chat_id=chat_id, text=text)


def article(chat_id: int):
    article_url = get_random_article_url()
    bot.send_message(chat_id=chat_id, text=article_url)


def get_random_article_url() -> str:
    response = httpx.get("https://en.wikipedia.org/api/rest_v1/page/random/summary")
    return response.json()["content_urls"]["desktop"]["page"]


def get_daily_chats() -> "ResultIterator[ChatModel]":
    return ChatModel.scan(ChatModel.daily == True)


def save_chat_id(chat_id: int) -> None:
    try:
        chat = ChatModel.get(chat_id)
    except ChatModel.DoesNotExist:
        ChatModel(chat_id).save()
    else:
        chat.daily = True
        chat.save()


def stop_chat_id(chat_id: int) -> None:
    try:
        chat = ChatModel.get(chat_id)
    except ChatModel.DoesNotExist:
        pass
    else:
        if not chat.daily:
            raise AlreadyStoped

        chat.daily = False
        chat.save()
