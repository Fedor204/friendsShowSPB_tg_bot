"""
Обработчики сообщений бота
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from database import db
from config import AUTO_REPLIES, MANAGER_COMMANDS, WELCOME_MESSAGE, INITIAL_MANAGERS
import re


def normalize_text(text: str) -> str:
    """Нормализация текста для лучшего поиска"""
    text = text.lower()
    text = text.replace('ё', 'е')
    # Убираем знаки препинания
    text = re.sub(r'[^\w\s]', ' ', text)
    # Убираем множественные пробелы
    text = re.sub(r'\s+', ' ', text)
    return text. strip()


def extract_word_roots(text: str) -> set:
    """Извлекает корни слов (первые 4-5 символов значимых слов)"""
    words = text.split()
    roots = set()

    # Стоп-слова, которые игнорируем
    stop_words = {'это', 'для', 'как', 'что', 'где', 'когда', 'можно', 'нужно',
                  'есть', 'или', 'про', 'чем', 'будет', 'быть', 'был', 'была',
                  'если', 'уже', 'еще', 'ещё', 'все', 'вся', 'ваш', 'наш', 'мой'}

    for word in words:
        if len(word) > 3 and word not in stop_words:
            # Берем первые 4 символа как корень
            roots.add(word[:4])
            if len(word) > 5:
                roots.add(word[: 5])

    return roots


def calculate_match_score(message_text: str, keywords: list) -> float:
    """
    Вычисляет степень совпадения сообщения с ключевыми словами
    Возвращает оценку от 0 до 1
    """
    message_normalized = normalize_text(message_text)
    message_roots = extract_word_roots(message_normalized)

    max_score = 0

    for keyword in keywords:
        keyword_normalized = normalize_text(keyword)
        score = 0

        # 1. Точное вхождение фразы - максимальная оценка
        if keyword_normalized in message_normalized:
            score = 1.0

        # 2. Все слова ключа есть в сообщении
        elif all(word in message_normalized for word in keyword_normalized. split()):
            score = 0.9

        # 3. Проверка по корням слов
        else:
            keyword_roots = extract_word_roots(keyword_normalized)
            if keyword_roots:
                matching_roots = message_roots.intersection(keyword_roots)
                score = len(matching_roots) / len(keyword_roots)

        max_score = max(max_score, score)

    return max_score


def find_auto_reply(message_text: str, threshold: float = 0.5) -> str:
    """
    Ищет подходящий автоответ по ключевым словам
    threshold - минимальный порог совпадения (0.5 = 50%)
    """
    best_match = None
    best_score = 0

    for reply_item in AUTO_REPLIES:
        keywords = reply_item["keywords"]
        score = calculate_match_score(message_text, keywords)

        if score > best_score:
            best_score = score
            best_match = reply_item

    # Возвращаем ответ только если оценка выше порога
    if best_score >= threshold:
        return best_match["answer"]

    return None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user

    # АВТОМАТИЧЕСКИ добавляем начальных менеджеров при первом /start
    if user.username and user.username in INITIAL_MANAGERS:
        if not db.is_manager(user.id):
            db.add_manager(user.id, user.username)
            await update. message.reply_text(
                f"✅ Вы автоматически добавлены как менеджер!\n\n"
                f"👋 Добро пожаловать, менеджер {user.first_name}!\n\n{MANAGER_COMMANDS}"
            )
            return

    if db.is_manager(user.id):
        await update.message.reply_text(
            f"👋 Добро пожаловать, менеджер {user.first_name}!\n\n{MANAGER_COMMANDS}"
        )
    else:
        # Отправляем приветственное сообщение с именем пользователя
        welcome_text = WELCOME_MESSAGE. format(first_name=user. first_name or "друг")
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.HTML
        )


async def add_manager_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить нового менеджера (только для менеджеров)"""
    user = update.effective_user

    if not db.is_manager(user. id):
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return

    if not context.args or len(context.args) != 1:
        await update.message. reply_text("❌ Использование: /add_manager @username")
        return

    username = context.args[0].lstrip("@")

    # Проверяем, есть ли уже такой менеджер
    managers = db.get_all_managers()
    for manager_id, manager_username in managers:
        if manager_username == username:
            await update.message. reply_text(f"⚠️ Менеджер @{username} уже добавлен!")
            return

    await update.message.reply_text(
        f"⚠️ Попросите @{username} написать боту команду /start, "
        f"затем повторите команду /add_manager @{username}"
    )


async def remove_manager_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить менеджера (только для менеджеров)"""
    user = update. effective_user

    if not db.is_manager(user.id):
        await update. message.reply_text("❌ У вас нет прав для этой команды.")
        return

    if not context.args or len(context.args) != 1:
        await update.message.reply_text("❌ Использование: /remove_manager @username")
        return

    username = context.args[0].lstrip("@")

    if db.remove_manager(username):
        await update.message. reply_text(f"✅ Менеджер @{username} успешно удален.")
    else:
        await update.message.reply_text(f"❌ Менеджер @{username} не найден.")


async def list_managers_command(update: Update, context:  ContextTypes.DEFAULT_TYPE):
    """Показать список всех менеджеров (только для менеджеров)"""
    user = update.effective_user

    if not db.is_manager(user. id):
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return

    managers = db. get_all_managers()

    if not managers:
        await update.message.reply_text("📋 Список менеджеров пуст.")
        return

    message = "📋 Список менеджеров:\n\n"
    for user_id, username in managers:
        message += f"• @{username} (ID: {user_id})\n"

    await update.message.reply_text(message)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех текстовых сообщений"""
    user = update.effective_user
    message = update.message

    # Если сообщение от менеджера
    if db.is_manager(user.id):
        # Проверяем, это ответ на сообщение пользователя?
        if message.reply_to_message:
            # Находим пользователя, которому нужно ответить
            user_id = db.get_user_by_message(
                message.reply_to_message.message_id,
                message.chat_id
            )

            if user_id:
                try:
                    # Отправляем ответ пользователю
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=message.text
                    )
                    await message.reply_text("✅ Ответ отправлен пользователю.")
                except Exception as e:
                    await message.reply_text(f"❌ Ошибка отправки:  {str(e)}")
            else:
                await message.reply_text("❌ Не удалось найти пользователя для ответа.")
        else:
            await message.reply_text(
                "ℹ️ Чтобы ответить пользователю, используйте Reply на его сообщение.\n\n"
                f"{MANAGER_COMMANDS}"
            )

    # Если сообщение от обычного пользователя
    else:
        # Проверяем на ключевые слова для автоответов
        auto_reply_text = find_auto_reply(message.text, threshold=0.4)
        auto_reply_sent = False

        if auto_reply_text:
            await message.reply_text(auto_reply_text, parse_mode=ParseMode.HTML)
            auto_reply_sent = True

        # Формируем сообщение для менеджеров
        user_info = f"👤 Новое сообщение от пользователя:\n\n"
        user_info += f"Имя: {user.first_name or 'Не указано'}"
        if user.last_name:
            user_info += f" {user.last_name}"
        user_info += f"\nUsername: @{user.username or 'не указан'}\n"
        user_info += f"ID: {user.id}\n"
        user_info += f"\n📝 Сообщение:\n{message.text}"

        if auto_reply_sent:
            user_info += "\n\n🤖 Автоматический ответ был отправлен пользователю."

        # Отправляем всем менеджерам
        managers = db.get_all_managers()

        if not managers:
            # Если нет менеджеров в базе, отправляем предупреждение
            await message.reply_text(
                "⚠️ Ваше сообщение получено, но в системе пока нет активных менеджеров.\n"
                "Пожалуйста, попробуйте позже."
            )
            return

        sent_count = 0
        for manager_id, manager_username in managers:
            try:
                sent_message = await context.bot.send_message(
                    chat_id=manager_id,
                    text=user_info
                )
                # Сохраняем связь сообщения с пользователем
                db.save_message_mapping(sent_message.message_id, user.id, manager_id)
                sent_count += 1
            except Exception as e:
                print(f"Ошибка отправки менеджеру @{manager_username}: {e}")

        # Подтверждение пользователю
        if sent_count > 0:
            if not auto_reply_sent:
                await message.reply_text(
                    "✅ Ваше сообщение получено!  Наши менеджеры ответят вам в ближайшее время."
                )
        else:
            await message.reply_text(
                "⚠️ Произошла ошибка при отправке сообщения менеджерам.  Пожалуйста, попробуйте позже."
            )