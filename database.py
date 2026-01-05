"""
Модуль для работы с базой данных
"""

import sqlite3
from typing import List, Optional
from config import DATABASE_NAME, INITIAL_MANAGERS


class Database:
    """Класс для работы с базой данных менеджеров и пользователей"""

    def __init__(self, db_name: str = DATABASE_NAME):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        """Инициализация базы данных"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()

            # Таблица менеджеров
            cursor. execute("""
                CREATE TABLE IF NOT EXISTS managers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    username TEXT UNIQUE NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица для связи сообщений (чтобы отвечать правильному пользователю)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS message_mapping (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    manager_message_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    manager_chat_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица пользователей (отслеживаем первое сообщение)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    first_message_sent BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()

    def add_manager(self, user_id:  int, username: str) -> bool:
        """Добавить менеджера"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn. cursor()
                cursor.execute(
                    "INSERT INTO managers (user_id, username) VALUES (?, ?)",
                    (user_id, username)
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def remove_manager(self, username: str) -> bool:
        """Удалить менеджера"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM managers WHERE username = ?", (username,))
            conn.commit()
            return cursor.rowcount > 0

    def is_manager(self, user_id: int) -> bool:
        """Проверить, является ли пользователь менеджером"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM managers WHERE user_id = ?", (user_id,))
            return cursor.fetchone() is not None

    def get_all_managers(self) -> List[tuple]:
        """Получить всех менеджеров"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username FROM managers")
            return cursor.fetchall()

    def save_message_mapping(self, manager_message_id: int, user_id: int, manager_chat_id: int):
        """Сохранить связь сообщения менеджера с пользователем"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO message_mapping (manager_message_id, user_id, manager_chat_id) VALUES (?, ?, ?)",
                (manager_message_id, user_id, manager_chat_id)
            )
            conn.commit()

    def get_user_by_message(self, manager_message_id:  int, manager_chat_id: int) -> Optional[int]:
        """Получить ID пользователя по сообщению менеджера"""
        with sqlite3.connect(self. db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id FROM message_mapping WHERE manager_message_id = ?  AND manager_chat_id = ? ",
                (manager_message_id, manager_chat_id)
            )
            result = cursor.fetchone()
            return result[0] if result else None

    def is_first_message(self, user_id: int) -> bool:
        """Проверить, первое ли это сообщение от пользователя"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT first_message_sent FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()

            if result is None:
                # Пользователь новый - добавляем его
                cursor.execute("INSERT INTO users (user_id, first_message_sent) VALUES (?, 1)", (user_id,))
                conn.commit()
                return True
            else:
                # Пользователь уже писал
                return False


# Глобальный экземпляр базы данных
db = Database()