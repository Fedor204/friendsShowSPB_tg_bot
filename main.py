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
    setup_command,
    handle_message
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging. INFO
)
logger = logging.getLogger(__name__)


def init_managers():
    """Инициализация начальных менеджеров при старте бота"""
    logger.info("Проверка начальных менеджеров...")

    # Получаем список всех менеджеров из БД
    existing_managers = db.get_all_managers()
    existing_usernames = [username for _, username in existing_managers]

    logger.info(f"Текущие менеджеры в БД: {existing_usernames}")
    logger.info(f"Начальные менеджеры из конфига: {INITIAL_MANAGERS}")

    # Если в БД нет менеджеров - это первый запуск
    if not existing_managers:
        logger. info("База данных пуста.  Менеджеры должны выполнить команду /setup")
    else:
        logger.info(f"В базе уже есть {len(existing_managers)} менеджер(ов)")


async def post_init(application: Application):
    """Инициализация после запуска бота"""
    bot = application.bot
    bot_info = await bot.get_me()
    logger.info(f"Бот запущен:  @{bot_info.username}")

    # Инициализируем менеджеров
    init_managers()

    logger.info("Бот готов к работе!")


def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("setup", setup_command))
    application.add_handler(CommandHandler("add_manager", add_manager_command))
    application.add_handler(CommandHandler("remove_manager", remove_manager_command))
    application.add_handler(CommandHandler("list_managers", list_managers_command))

    # Обработчик всех текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота
    logger.info("Бот запускается...")
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()