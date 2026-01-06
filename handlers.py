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
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text. strip()


def extract_word_roots(text: str) -> set:
    """Извлекает корни слов"""
    words = text.split()
    roots = set()

    stop_words = {'это', 'для', 'как', 'что', 'где', 'когда', 'можно', 'нужно',
                  'есть', 'или', 'про', 'чем', 'будет', 'быть', 'был', 'была',
                  'если', 'уже', 'еще', 'ещё', 'все', 'вся', 'ваш', 'наш', 'мой'}

    for word in words:
        if len(word) > 3 and word not in stop_words:
            roots.add(word[: 4])
            if len(word) > 5:
                roots.add(word[: 5])

    return roots


def calculate_match_score(message_text: str, keywords: list) -> float:
    """Вычисляет степень совпадения сообщения с ключевыми словами"""
    message_normalized = normalize_text(message_text)
    message_roots = extract_word_roots(message_normalized)

    max_score = 0

    for keyword in keywords:
        keyword_normalized = normalize_text(keyword)
        score = 0

        if keyword_normalized in message_normalized:
            score = 1.0
        elif all(word in message_normalized for word in keyword_normalized. split()):
            score = 0.9
        else:
            keyword_roots = extract_word_roots(keyword_normalized)
            if keyword_roots:
                matching_roots = message_roots. intersection(keyword_roots)
                score = len(matching_roots) / len(keyword_roots)

        max_score = max(max_score, score)

    return max_score


def find_auto_reply(message_text: str, threshold: float = 0.4) -> str:
    """Ищет подходящий автоответ по ключевым словам"""
    best_match = None
    best_score = 0

    for reply_item in AUTO_REPLIES:
        keywords = reply_item["keywords"]
        score = calculate_match_score(message_text, keywords)

        if score > best_score:
            best_score = score
            best_match = reply_item

    if best_score >= threshold:
        return best_match["answer"]

    return None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user

    # Автоматически добавляем начальных менеджеров при первом /start
    if user.username and user.username in INITIAL_MANAGERS:
        if not db.is_manager(user.id):
            success = db.add_manager(user.id, user.username)
            if success:
                await update.message.reply_text(
                    f"✅ Вы автоматически добавлены как менеджер!\n\n"
                    f"👋 Добро пожаловать, {user.first_name}!\n\n{MANAGER_COMMANDS}"
                )
                return

    # Если уже менеджер
    if db.is_manager(user.id):
        await update.message. reply_text(
            f"👋 С возвращением, {user.first_name}!\n\n{MANAGER_COMMANDS}"
        )
    else:
        # Обычный пользователь
        welcome_text = WELCOME_MESSAGE.format(first_name=user.first_name or "друг")
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.HTML
        )


async def add_manager_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить нового менеджера - УПРОЩЕННАЯ ВЕРСИЯ"""
    user = update.effective_user

    # Проверяем права
    if not db.is_manager(user.id):
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return

    # Проверяем аргументы
    if not context.args or len(context.args) != 1:
        await update.message. reply_text(
            "❌ Использование:   /add_manager @username\n\n"
            "Попросите пользователя СНАЧАЛА написать боту /start, затем добавьте его."
        )
        return

    new_username = context.args[0]. lstrip("@")

    # Проверяем, уже есть?
    managers = db.get_all_managers()
    for manager_id, manager_username in managers:
        if manager_username == new_username:
            await update.message.reply_text(f"⚠️ @{new_username} уже является менеджером!")
            return

    # Ищем пользователя в истории сообщений (если писал боту)
    # Пока просто показываем инструкцию
    await update.message.reply_text(
        f"📝 Чтобы добавить @{new_username} как менеджера:\n\n"
        f"1️⃣ Попросите @{new_username} написать боту команду:   /request_manager\n"
        f"2️⃣ Вы получите уведомление с кнопкой подтверждения\n"
        f"3️⃣ Нажмите кнопку - готово!"
    )


async def request_manager_command(update: Update, context:  ContextTypes.DEFAULT_TYPE):
    """Запрос на получение прав менеджера"""
    user = update.effective_user

    # Проверяем что у пользователя есть username
    if not user.username:
        await update.message.reply_text(
            "❌ У вас не установлен username в Telegram.\n\n"
            "Установите его:  Settings → Edit Profile → Username\n"
            "Затем попробуйте снова."
        )
        return

    # Проверяем, уже менеджер?
    if db.is_manager(user.id):
        await update.message. reply_text(f"✅ Вы уже менеджер!\n\n{MANAGER_COMMANDS}")
        return

    # Отправляем всем текущим менеджерам запрос
    managers = db. get_all_managers()

    if not managers:
        await update. message.reply_text(
            "⚠️ В системе пока нет менеджеров.  Обратитесь к администратору."
        )
        return

    request_message = (
        f"🔔 <b>Запрос на добавление менеджера</b>\n\n"
        f"👤 Пользователь:  {user.first_name or 'Неизвестно'}"
    )
    if user.last_name:
        request_message += f" {user.last_name}"
    request_message += f"\n📝 Username: @{user.username}\n🆔 ID: <code>{user.id}</code>\n\n"
    request_message += f"Чтобы добавить, выполните команду:\n<code>/approve_manager {user.id} {user.username}</code>"

    sent_count = 0
    for manager_id, _ in managers:
        try:
            await context.bot.send_message(
                chat_id=manager_id,
                text=request_message,
                parse_mode=ParseMode. HTML
            )
            sent_count += 1
        except Exception as e:
            print(f"Ошибка отправки менеджеру {manager_id}: {e}")

    if sent_count > 0:
        await update. message.reply_text(
            "✅ Ваш запрос отправлен менеджерам!\n"
            "Ожидайте подтверждения."
        )
    else:
        await update. message.reply_text(
            "⚠️ Не удалось отправить запрос.  Попробуйте позже."
        )


async def approve_manager_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Одобрить запрос на добавление менеджера"""
    user = update.effective_user

    # Проверяем права
    if not db.is_manager(user.id):
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return

    # Проверяем аргументы
    if not context.args or len(context.args) != 2:
        await update. message.reply_text(
            "❌ Использование:   /approve_manager USER_ID USERNAME"
        )
        return

    try:
        new_user_id = int(context.args[0])
        new_username = context.args[1].lstrip("@")
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Неверный формат.  Проверьте команду.")
        return

    # Проверяем, уже менеджер?
    if db.is_manager(new_user_id):
        await update.message.reply_text(f"⚠️ @{new_username} уже менеджер!")
        return

    # Добавляем
    success = db.add_manager(new_user_id, new_username)

    if success:
        # Уведомляем менеджера
        await update.message.reply_text(
            f"✅ @{new_username} успешно добавлен как менеджер!"
        )

        # Уведомляем нового менеджера
        try:
            await context.bot. send_message(
                chat_id=new_user_id,
                text=f"🎉 Поздравляем!  Вы назначены менеджером.\n\n{MANAGER_COMMANDS}"
            )
        except:
            pass
    else:
        await update. message.reply_text("❌ Ошибка при добавлении менеджера.")


async def remove_manager_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить менеджера"""
    user = update.effective_user

    if not db.is_manager(user.id):
        await update. message.reply_text("❌ У вас нет прав для этой команды.")
        return

    if not context.args or len(context.args) != 1:
        await update.message.reply_text("❌ Использование:  /remove_manager @username")
        return

    username = context.args[0].lstrip("@")

    # Защита от удаления себя
    if username == user. username:
        await update.message.reply_text("❌ Вы не можете удалить сами себя!")
        return

    if db.remove_manager(username):
        await update.message. reply_text(f"✅ @{username} удален из менеджеров.")
    else:
        await update.message.reply_text(f"❌ @{username} не найден в списке менеджеров.")


async def list_managers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список всех менеджеров"""
    user = update.effective_user

    if not db. is_manager(user.id):
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return

    managers = db.get_all_managers()

    if not managers:
        await update.message.reply_text(
            "📋 Список менеджеров пуст.\n\n"
            "Начальные менеджеры должны написать боту /start для активации."
        )
        return

    message = "📋 <b>Список менеджеров: </b>\n\n"
    for user_id, username in managers:
        message += f"• @{username}\n   <code>ID: {user_id}</code>\n\n"

    message += f"<i>Всего: {len(managers)}</i>"

    await update.message.reply_text(message, parse_mode=ParseMode.HTML)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех текстовых сообщений"""
    user = update.effective_user
    message = update.message

    # Если сообщение от менеджера
    if db.is_manager(user.id):
        if message.reply_to_message:
            user_id = db.get_user_by_message(
                message.reply_to_message.message_id,
                message.chat_id
            )

            if user_id:
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=message.text
                    )
                    await message.reply_text("✅ Ответ отправлен пользователю")
                except Exception as e:
                    await message.reply_text(f"❌ Ошибка отправки:  {str(e)}")
            else:
                await message.reply_text(
                    "❌ Не удалось найти пользователя.\n"
                    "Убедитесь что отвечаете (Reply) на сообщение от пользователя."
                )
        else:
            await message. reply_text(
                "💡 Чтобы ответить пользователю:\n"
                "Ответьте (Reply) на его сообщение\n\n"
                f"{MANAGER_COMMANDS}"
            )

    # Если сообщение от обычного пользователя
    else:
        is_first = db.is_first_message(user.id)

        auto_reply_text = find_auto_reply(message.text, threshold=0.4)
        auto_reply_sent = False

        if auto_reply_text:
            await message.reply_text(auto_reply_text, parse_mode=ParseMode.HTML)
            auto_reply_sent = True

        # Формируем сообщение для менеджеров
        user_info = f"👤 <b>{'🆕 НОВЫЙ пользователь' if is_first else 'Сообщение от пользователя'}</b>\n\n"
        user_info += f"Имя: {user.first_name or 'Не указано'}"
        if user.last_name:
            user_info += f" {user.last_name}"
        user_info += f"\nUsername:  @{user.username or 'не указан'}"
        user_info += f"\nID: <code>{user. id}</code>"
        user_info += f"\n\n📝 <b>Сообщение: </b>\n{message.text}"

        if auto_reply_sent:
            user_info += "\n\n🤖 <i>Автоматический ответ отправлен</i>"

        # Отправляем всем менеджерам
        managers = db.get_all_managers()

        if not managers:
            await message.reply_text(
                "⚠️ К сожалению, сейчас нет доступных менеджеров.\n"
                "Пожалуйста, попробуйте позже."
            )
            return

        sent_count = 0
        for manager_id, manager_username in managers:
            try:
                sent_message = await context.bot.send_message(
                    chat_id=manager_id,
                    text=user_info,
                    parse_mode=ParseMode. HTML
                )
                db.save_message_mapping(sent_message.message_id, user.id, manager_id)
                sent_count += 1
            except Exception as e:
                print(f"Ошибка отправки менеджеру @{manager_username}: {e}")

        if sent_count == 0:
            await message. reply_text(
                "⚠️ Произошла ошибка при отправке сообщения.\n"
                "Пожалуйста, попробуйте позже."
            )
        elif is_first and not auto_reply_sent:
            await message.reply_text(
                "✅ Ваше сообщение получено!\n"
                "Наши менеджеры ответят вам в ближайшее время."
            )