"""Запуск: python bot.py. Токен хранится в .env рядом с этим файлом."""
import html
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo, MenuButtonWebApp
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from game import Atlas, Game
from wiki import Wikipedia

RULES = (
    "🌍 Играем в города!\n\n"
    "Ты называешь город — я отвечаю городом на его последнюю букву. "
    "Затем твой ход на последнюю букву моего города. Ь, Ъ и Ы пропускаем, Ё = Е. "
    "Повторять города нельзя.\n\n"
    "Пришлю страну, население, фото и Википедию для обоих городов. "
    "Названия пиши по-русски. При совпадении названий выбираю самый населённый город.\n\n"
    "/new — новая игра\n/help — правила\n\nНачинай с любого города!"
)


async def setup(app: Application):
    app.bot_data["atlas"] = Atlas()
    app.bot_data["wiki"] = Wikipedia()
    await app.bot.set_my_commands([
        BotCommand("start", "Начать игру"), BotCommand("new", "Новая игра"),
        BotCommand("help", "Правила игры"), BotCommand("app", "Открыть Mini App"),
    ])
    url = os.getenv("MINI_APP_URL", "").strip()
    if url:
        if not url.startswith("https://"):
            raise ValueError("MINI_APP_URL должен начинаться с https://")
        await app.bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Играть", web_app=WebAppInfo(url=url)))


async def shutdown(app: Application):
    await app.bot_data["wiki"].close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["game"] = Game()
    await update.effective_message.reply_text(RULES)
    if os.getenv("MINI_APP_URL") and update.effective_chat.type == "private":
        await open_app(update, context)


async def open_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = os.getenv("MINI_APP_URL", "").strip()
    if not url:
        await update.effective_message.reply_text("Mini App ещё не подключено. Укажи MINI_APP_URL в .env и перезапусти бота.")
    elif update.effective_chat.type != "private":
        await update.effective_message.reply_text("Открой личный чат со мной и отправь /app, чтобы запустить Mini App.")
    else:
        await update.effective_message.reply_text("🌍 Открой свой атлас путешествий: игра, фото городов, карта и личные рекорды.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Открыть игру", web_app=WebAppInfo(url=url))]]))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(RULES)


async def card(message, city, heading: str, wiki: Wikipedia):
    url, photo = await wiki.get(city)
    population = f"{city.population:,}".replace(",", " ") if city.population else "нет данных"
    caption = (f"{heading}: <b>{html.escape(city.name)}</b>\n"
               f"Страна: {html.escape(city.country)}\n"
               f"Население: {population}\n"
               "Данные: GeoNames (справочная оценка).")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📖 Википедия", url=url)]])
    if photo:
        try:
            await message.reply_photo(photo, caption=caption, parse_mode="HTML", reply_markup=keyboard)
            return
        except TelegramError:
            pass
    await message.reply_text(caption + "\nФото сейчас недоступно.", parse_mode="HTML", reply_markup=keyboard)


async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    game = context.chat_data.setdefault("game", Game())
    if len(message.text) > 100:
        await message.reply_text("Напиши только название города, до 100 символов.")
        return
    try:
        player_city, bot_city = game.move(message.text, context.bot_data["atlas"])
    except ValueError as error:
        await message.reply_text(str(error))
        return
    await card(message, player_city, "📍 Твой город", context.bot_data["wiki"])
    if bot_city:
        await card(message, bot_city, "🤖 Мой город", context.bot_data["wiki"])
        await message.reply_text(f"Тебе на «{game.expected.upper()}»! Ходов: {game.turns}.")
    else:
        await message.reply_text("Ты победил! У меня закончились подходящие города. /new — сыграть ещё.")
        context.chat_data.pop("game", None)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    # Не записываем URL запросов Telegram: они содержат токен.
    logging.getLogger(__name__).warning("Ошибка обработки: %s", type(context.error).__name__)
    if isinstance(update, Update) and update.effective_message:
        try:
            game = context.chat_data.get("game")
            hint = f" Текущая буква: «{game.expected.upper()}»." if game and game.expected else ""
            await update.effective_message.reply_text("Не удалось отправить ответ." + hint + " /new — новая игра.")
        except TelegramError:
            pass


def main():
    load_dotenv(Path(__file__).with_name(".env"))
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or token == "put_your_botfather_token_here":
        raise SystemExit("Укажи TELEGRAM_BOT_TOKEN в файле .env. Инструкция — в README.md.")
    logging.basicConfig(level=logging.WARNING)
    app = (Application.builder().token(token).concurrent_updates(False)
           .post_init(setup).post_shutdown(shutdown).build())
    app.add_handler(CommandHandler(["start", "new"], start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("app", open_app))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, play))
    app.add_error_handler(error_handler)
    print("Бот запущен. Для остановки нажми Ctrl+C.")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
