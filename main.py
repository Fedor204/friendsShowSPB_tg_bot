"""
Главный файл телеграм-бота
"""

import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from config import BOT_TOKEN, INITIAL_MANAGERS
from database import db
from handlers import (
    start_command,
    add_manager_command,
    remove_manager_command,
    list_managers_command,
    request_manager_command,
    approve_manager_command,
    test_auto_command,
    handle_message
)
import asyncio
from aiohttp import web

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# Простой HTTP сервер для проверки здоровья
async def health_check(request):
    """Эндпоинт для проверки что бот жив"""
    return web.Response(text="OK", status=200)


async def start_health_server():
    """Запуск HTTP сервера для мониторинга"""
    app = web.Application()
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("Health check сервер запущен на порту 8080")


def init_managers():
    """Инициализация начальных менеджеров при старте бота"""
    logger.info("Проверка начальных менеджеров...")
    existing_managers = db.get_all_managers()
    existing_usernames = [username for _, username in existing_managers]
    logger.info(f"Менеджеры в БД: {existing_usernames}")


async def post_init(application: Application):
    """Инициализация после запуска бота"""
    bot = application.bot
    bot_info = await bot.get_me()
    logger.info(f"Бот запущен:   @{bot_info.username}")
    init_managers()

    # Запускаем health check сервер
    asyncio.create_task(start_health_server())

    logger.info("Бот готов к работе!")


def main():
    """Запуск бота"""
    application = Application. builder().token(BOT_TOKEN).post_init(post_init).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("request_manager", request_manager_command))
    application.add_handler(CommandHandler("approve_manager", approve_manager_command))
    application.add_handler(CommandHandler("add_manager", add_manager_command))
    application.add_handler(CommandHandler("remove_manager", remove_manager_command))
    application.add_handler(CommandHandler("list_managers", list_managers_command))
    application.add_handler(CommandHandler("test_auto", test_auto_command))

    # Обработчик всех текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота
    logger.info("Бот запускается...")
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
