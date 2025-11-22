import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta
import random
import string
import os
import logging
import sys
import traceback
import yaml
import json
from collections import defaultdict

# Настройка логирования с явной кодировкой UTF-8
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Форматтер для логов
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Логирование в файл
file_handler = logging.FileHandler("bot.log", encoding='utf-8')
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

# Логирование в консоль с поддержкой UTF-8
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.DEBUG)
logger.addHandler(console_handler)

# Создание папки для хранения файлов
FILES_DIR = "files"
TICKETS_DIR = "tickets"
if not os.path.exists(FILES_DIR):
    os.makedirs(FILES_DIR)
    logger.info(f"Создана директория для файлов: {FILES_DIR}")
if not os.path.exists(TICKETS_DIR):
    os.makedirs(TICKETS_DIR)
    logger.info(f"Создана директория для тикетов: {TICKETS_DIR}")

# Токен бота
TOKEN = "8019657134:AAE_QXtPBzDK39011hPaLr7EQGt0cy2GN3A"
bot = telebot.TeleBot(TOKEN)

# Юзернейм владельца и его chat_id
OWNER_USERNAME = "@fastingd0xing"
OWNER_CHAT_ID = 6664176084

# ID канала для подписки
CHANNEL_ID = "@neocore_dev"

# Пороговые значения для спама
SPAM_MESSAGE_LIMIT = 120
SPAM_TIME_WINDOW = 60  # 1 минута в секундах
SPAM_NOTIFICATION_INTERVAL = 15  # Уведомлять о бане раз в 5 сообщений

# Словарь для отслеживания сообщений пользователей
message_counts = defaultdict(list)

# Словарь для отслеживания количества сообщений от заблокированных пользователей
blocked_user_message_counts = defaultdict(int)

# Подключение к базе данных SQLite
try:
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    logger.info("Успешное подключение к базе данных SQLite")
except Exception as e:
    logger.error(f"Ошибка подключения к базе данных: {e}\n{traceback.format_exc()}")
    sys.exit(1)

# Создание таблиц в базе данных
try:
    with conn:
        cursor = conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                name TEXT,
                reg_date TEXT,
                role TEXT,
                is_blocked INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS keys (
                key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_value TEXT UNIQUE,
                file_name TEXT,
                is_activated INTEGER DEFAULT 0,
                activated_by INTEGER,
                activation_date TEXT
            );
            CREATE TABLE IF NOT EXISTS ideas (
                idea_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                idea_text TEXT,
                submission_date TEXT
            );
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                status TEXT DEFAULT 'open',
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS ticket_messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                user_id INTEGER,
                message_text TEXT,
                sent_at TEXT,
                is_admin BOOLEAN DEFAULT 0
            );
        """)
        conn.commit()
        logger.info("Таблицы в базе данных успешно созданы или уже существуют")
except Exception as e:
    logger.error(f"Ошибка создания таблиц в базе данных: {e}\n{traceback.format_exc()}")
    sys.exit(1)

# Словарь для хранения состояний пользователей
user_states = {}

# Загрузка списка администраторов из admins.yml
def load_admins():
    try:
        default_admins = ['@GabriDev1337', '@by_lod1x']
        if os.path.exists("admins.yml"):
            with open("admins.yml", "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                admins = data.get("admins", []) if data else []
                admins = list(set(default_admins + admins))  # Добавляем обязательных и убираем дубликаты
                logger.info(f"Загружены администраторы из admins.yml: {admins}")
                return admins
        else:
            logger.warning("Файл admins.yml не найден, используются обязательные администраторы")
            return default_admins
    except Exception as e:
        logger.error(f"Ошибка загрузки admins.yml: {e}\n{traceback.format_exc()}")
        return default_admins

ADMINS = load_admins()

# Функция загрузки данных пользователей из users.yml
def load_users_yml():
    try:
        if os.path.exists("users.yml"):
            with open("users.yml", "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                users = data.get("users", {}) if data else {}
                logger.info(f"Загружены данные пользователей из users.yml: {len(users)} записей")
                return users
        else:
            logger.warning("Файл users.yml не найден, создается пустой")
            return {}
    except Exception as e:
        logger.error(f"Ошибка загрузки users.yml: {e}\n{traceback.format_exc()}")
        return {}

# Функция сохранения данных пользователей в users.yml
def save_users_yml(users_data):
    try:
        with open("users.yml", "w", encoding="utf-8") as f:
            yaml.safe_dump({"users": users_data}, f, allow_unicode=True)
        logger.info("Данные пользователей сохранены в users.yml")
    except Exception as e:
        logger.error(f"Ошибка сохранения users.yml: {e}\n{traceback.format_exc()}")

# Функция генерации случайного ключа
def generate_random_key():
    try:
        chars = string.ascii_uppercase + string.digits
        key = f"NeoCore-{'-'.join(''.join(random.choices(chars, k=5)) for _ in range(3))}"
        logger.info(f"Сгенерирован ключ: {key}")
        return key
    except Exception as e:
        logger.error(f"Ошибка генерации ключа: {e}\n{traceback.format_exc()}")
        raise

# Создание главного меню
def create_main_menu():
    try:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("⚙️ Профиль"))
        markup.add(types.KeyboardButton("🔑 Активировать ключ"))
        markup.add(types.KeyboardButton("📊 История активаций"))
        markup.add(types.KeyboardButton("💡Идеи"))
        markup.add(types.KeyboardButton("📞 Тех.Поддержка"))
        markup.add(types.KeyboardButton("📖 Правила"))
        logger.info("Создано главное меню")
        return markup
    except Exception as e:
        logger.error(f"Ошибка создания главного меню: {e}\n{traceback.format_exc()}")
        raise

# Создание меню админ-панели
def create_admin_menu():
    try:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("🔑 Добавить ключ"))
        markup.add(types.KeyboardButton("⚰️ Заблокировать пользователя"))
        markup.add(types.KeyboardButton("🔓 Разблокировать пользователя"))
        markup.add(types.KeyboardButton("📢 Объявление"))
        markup.add(types.KeyboardButton("⚙️ Информация"))
        markup.add(types.KeyboardButton("📞 Тикеты"))
        markup.add(types.KeyboardButton("Отменить ввод"))
        logger.info("Создано меню админ-панели")
        return markup
    except Exception as e:
        logger.error(f"Ошибка создания меню админ-панели: {e}\n{traceback.format_exc()}")
        raise

# Создание кнопки отмены
def create_cancel_button():
    try:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("Отменить ввод"))
        logger.info("Создана кнопка отмены")
        return markup
    except Exception as e:
        logger.error(f"Ошибка создания кнопки отмены: {e}\n{traceback.format_exc()}")
        raise

# Создание клавиатуры для тикета
def create_ticket_keyboard():
    try:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("Закрыть тикет"))
        markup.add(types.KeyboardButton("Отменить ввод"))
        return markup
    except Exception as e:
        logger.error(f"Ошибка создания клавиатуры для тикета: {e}\n{traceback.format_exc()}")
        raise

# Проверка подписки на канал
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_ID, user_id).status
        is_sub = status in ['member', 'administrator', 'creator']
        logger.info(f"Проверка подписки user_id {user_id}: {'Подписан' if is_sub else 'Не подписан'}")
        return is_sub
    except Exception as e:
        logger.error(f"Ошибка проверки подписки для user_id {user_id}: {e}\n{traceback.format_exc()}")
        return False

# Проверка блокировки пользователя
def is_blocked(user_id):
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            is_blocked = result[0] == 1 if result else False
            logger.info(f"Проверка блокировки user_id {user_id}: {'Заблокирован' if is_blocked else 'Не заблокирован'}")
            return is_blocked
    except Exception as e:
        logger.error(f"Ошибка проверки блокировки для user_id {user_id}: {e}\n{traceback.format_exc()}")
        return False

# Проверка, является ли пользователь администратором
def is_admin(user_id, username):
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT role, username FROM users WHERE user_id = ?", (user_id,))
            user_data = cursor.fetchone()
            is_admin_user = user_data and (user_data[0] == "Администрация" or user_data[1] in ADMINS or user_id == OWNER_CHAT_ID)
            logger.info(f"Проверка админ-прав для user_id {user_id} ({username}): {'Админ' if is_admin_user else 'Не админ'}")
            return is_admin_user
    except Exception as e:
        logger.error(f"Ошибка проверки админ-прав для user_id {user_id}: {e}\n{traceback.format_exc()}")
        return False

# Регистрация нового пользователя
def register_user(user_id, username, name):
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            if not cursor.fetchone():
                role = "Администрация" if username in ADMINS else "Пользователь"
                reg_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO users (user_id, username, name, reg_date, role) VALUES (?, ?, ?, ?, ?)",
                              (user_id, username, name, reg_date, role))
                conn.commit()
                logger.info(f"Зарегистрирован новый пользователь: user_id={user_id}, username={username}, role={role}")
                
                # Обновляем users.yml
                users_data = load_users_yml()
                users_data[str(user_id)] = {
                    "user_id": user_id,
                    "username": username,
                    "name": name,
                    "reg_date": reg_date,
                    "role": role,
                    "is_blocked": 0,
                    "activated_keys": 0
                }
                save_users_yml(users_data)
            else:
                logger.info(f"Пользователь user_id={user_id}, username={username} уже зарегистрирован")
    except Exception as e:
        logger.error(f"Ошибка регистрации пользователя user_id {user_id}: {e}\n{traceback.format_exc()}")
        raise

# Функция для сохранения тикета в JSON
def save_ticket_to_json(ticket_id, user_id, message_text, created_at, status='open', messages=None):
    try:
        ticket_data = {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "created_at": created_at,
            "status": status,
            "messages": messages or [{"user_id": user_id, "text": message_text, "sent_at": created_at, "is_admin": False}]
        }
        ticket_path = os.path.join(TICKETS_DIR, f"{ticket_id}.json")
        with open(ticket_path, "w", encoding="utf-8") as f:
            json.dump(ticket_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Тикет #{ticket_id} сохранен в {ticket_path}")
    except Exception as e:
        logger.error(f"Ошибка сохранения тикета #{ticket_id} в JSON: {e}\n{traceback.format_exc()}")

# Функция для обновления тикета в JSON
def update_ticket_in_json(ticket_id, message_text, user_id, is_admin=False):
    try:
        ticket_path = os.path.join(TICKETS_DIR, f"{ticket_id}.json")
        if os.path.exists(ticket_path):
            with open(ticket_path, "r", encoding="utf-8") as f:
                ticket_data = json.load(f)
            ticket_data["messages"].append({
                "user_id": user_id,
                "text": message_text,
                "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "is_admin": is_admin
            })
            with open(ticket_path, "w", encoding="utf-8") as f:
                json.dump(ticket_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Тикет #{ticket_id} обновлен в {ticket_path}")
        else:
            logger.error(f"Файл тикета #{ticket_id} не найден")
    except Exception as e:
        logger.error(f"Ошибка обновления тикета #{ticket_id} в JSON: {e}\n{traceback.format_exc()}")

# Функция для обновления статуса тикета в JSON
def update_ticket_status_in_json(ticket_id, status):
    try:
        ticket_path = os.path.join(TICKETS_DIR, f"{ticket_id}.json")
        if os.path.exists(ticket_path):
            with open(ticket_path, "r", encoding="utf-8") as f:
                ticket_data = json.load(f)
            ticket_data["status"] = status
            with open(ticket_path, "w", encoding="utf-8") as f:
                json.dump(ticket_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Статус тикета #{ticket_id} обновлен в {ticket_path}: {status}")
    except Exception as e:
        logger.error(f"Ошибка обновления статуса тикета #{ticket_id} в JSON: {e}\n{traceback.format_exc()}")

# Функция проверки спама
def check_spam(user_id, username):
    try:
        current_time = datetime.now()
        message_counts[user_id].append(current_time)
        
        # Удаляем сообщения старше SPAM_TIME_WINDOW
        message_counts[user_id] = [t for t in message_counts[user_id] if (current_time - t).total_seconds() <= SPAM_TIME_WINDOW]
        
        # Проверяем, превышает ли количество сообщений лимит
        if len(message_counts[user_id]) > SPAM_MESSAGE_LIMIT:
            with conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (user_id,))
                conn.commit()
            
            # Обновляем users.yml
            users_data = load_users_yml()
            user_key = str(user_id)
            if user_key in users_data:
                users_data[user_key]["is_blocked"] = 1
            save_users_yml(users_data)
            
            logger.warning(f"Пользователь {user_id} ({username}) заблокирован за спам: {len(message_counts[user_id])} сообщений за {SPAM_TIME_WINDOW} секунд")
            bot.send_message(user_id, "❌ Вы были заблокированы за спам! Обжаловать наказание: @GabriDev1337")
            
            # Уведомляем админов
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users WHERE role = 'Администрация'")
                admins = cursor.fetchall()
            for admin in admins:
                bot.send_message(admin[0], f"Пользователь {username} заблокирован за спам: отправил {len(message_counts[user_id])} сообщений за минуту.")
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки спама для user_id {user_id}: {e}\n{traceback.format_exc()}")
        return False

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    try:
        user_id = message.from_user.id
        username = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
        name = message.from_user.first_name
        
        logger.info(f"Пользователь {user_id} ({username}) запустил команду /start")
        
        # Проверка спама
        if check_spam(user_id, username):
            return
        
        if is_blocked(user_id):
            blocked_user_message_counts[user_id] += 1
            if blocked_user_message_counts[user_id] % SPAM_NOTIFICATION_INTERVAL == 0:
                bot.send_message(user_id, "❌ Вы были заблокированы в боте! Обжаловать наказание: @GabriDev1337")
            return
        
        register_user(user_id, username, name)
        
        if is_subscribed(user_id):
            bot.send_message(message.chat.id, 
                            f"Привет! Дорогой {name}, ты попал\n"
                            "В Официальный бот студии NeoCore!✅\n"
                            "\n"
                            "Спасибо что зашёл в бота и подписался на нас🎆\n"
                            "В канале ты можешь увидеть много ключей, для бота, и новые обновления. Приятного получения кодов!\n",
                            reply_markup=create_main_menu())
            logger.info(f"Пользователь {user_id} успешно начал работу с ботом")
        else:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📌Подписаться", url="https://t.me/neocore_dev"))
            markup.add(types.InlineKeyboardButton("✅ Проверить подписку", callback_data="check_subscription"))
            bot.send_message(message.chat.id, "Для начала работы подпишись", reply_markup=markup)
            logger.info(f"Пользователь {user_id} не подписан, предложена подписка")
    except Exception as e:
        logger.error(f"Ошибка в обработчике /start для user_id {user_id}: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# Обработчик команды /admin
@bot.message_handler(commands=['admin'])
def admin_command(message):
    try:
        user_id = message.from_user.id
        username = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
        
        logger.info(f"Пользователь {user_id} ({username}) запросил команду /admin")
        
        # Проверка спама
        if check_spam(user_id, username):
            return
        
        if is_blocked(user_id):
            blocked_user_message_counts[user_id] += 1
            if blocked_user_message_counts[user_id] % SPAM_NOTIFICATION_INTERVAL == 0:
                bot.send_message(message.chat.id, "❌ Вы были заблокированы в боте! Обжаловать наказание: @GabriDev1337")
            return
            
        if is_admin(user_id, username):
            bot.send_message(message.chat.id, "🔒 Вы попали в админ панель, что хотите сделать?",
                            reply_markup=create_admin_menu())
            logger.info(f"Пользователь {user_id} вошел в админ-панель")
        else:
            bot.send_message(message.chat.id, "❌ У вас нет прав", reply_markup=create_main_menu())
            logger.warning(f"Пользователь {user_id} попытался войти в админ-панель без прав")
    except Exception as e:
        logger.error(f"Ошибка в обработчике команды /admin для user_id {user_id}: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# Обработчик кнопки "Тикеты" в админ-панели
@bot.message_handler(func=lambda message: message.text == "📞 Тикеты")
def view_tickets(message):
    try:
        user_id = message.from_user.id
        username = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
        
        logger.info(f"Админ {user_id} ({username}) запросил просмотр тикетов")
        
        # Проверка спама
        if check_spam(user_id, username):
            return
        
        if is_blocked(user_id):
            blocked_user_message_counts[user_id] += 1
            if blocked_user_message_counts[user_id] % SPAM_NOTIFICATION_INTERVAL == 0:
                bot.send_message(message.chat.id, "❌ Вы были заблокированы в боте! Обжаловать наказание: @GabriDev1337")
            return
            
        if is_admin(user_id, username):
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT ticket_id, user_id, status, created_at FROM tickets WHERE status = 'open'")
                tickets = cursor.fetchall()
            if not tickets:
                bot.send_message(message.chat.id, "Нет открытых тикетов.", reply_markup=create_admin_menu())
                return
            
            for ticket in tickets:
                ticket_id, ticket_user_id, status, created_at = ticket
                with conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT username FROM users WHERE user_id = ?", (ticket_user_id,))
                    user_data = cursor.fetchone()
                ticket_username = user_data[0] if user_data else "Неизвестный пользователь"
                
                ticket_path = os.path.join(TICKETS_DIR, f"{ticket_id}.json")
                if os.path.exists(ticket_path):
                    with open(ticket_path, "r", encoding="utf-8") as f:
                        ticket_data = json.load(f)
                    messages = ticket_data["messages"]
                    response = f"Тикет #{ticket_id} от {ticket_username} ({created_at}, Статус: {status})\n\n"
                    for msg in messages:
                        msg_username = ticket_username if not msg["is_admin"] else "Администратор"
                        response += f"{msg_username} ({msg['sent_at']}): {msg['text']}\n"
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("Ответить", callback_data=f"reply_ticket_{ticket_id}"))
                    markup.add(types.InlineKeyboardButton("Закрыть", callback_data=f"close_ticket_{ticket_id}"))
                    markup.add(types.InlineKeyboardButton("Удалить", callback_data=f"delete_ticket_{ticket_id}"))
                    bot.send_message(message.chat.id, response, reply_markup=markup)
                else:
                    bot.send_message(message.chat.id, f"Тикет #{ticket_id} существует, но файл не найден.", reply_markup=create_admin_menu())
            logger.info(f"Админ {user_id} просмотрел открытые тикеты")
        else:
            bot.send_message(message.chat.id, "❌ У вас нет прав", reply_markup=create_main_menu())
    except Exception as e:
        logger.error(f"Ошибка в обработчике просмотра тикетов для user_id {user_id}: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# Обработчик инлайн-кнопок
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    try:
        user_id = call.from_user.id
        username = f"@{call.from_user.username}" if call.from_user.username else "Без юзернейма"
        
        logger.info(f"Пользователь {user_id} ({username}) нажал инлайн-кнопку: {call.data}")
        
        # Проверка спама
        if check_spam(user_id, username):
            return
        
        if is_blocked(user_id):
            blocked_user_message_counts[user_id] += 1
            if blocked_user_message_counts[user_id] % SPAM_NOTIFICATION_INTERVAL == 0:
                bot.send_message(call.message.chat.id, "❌ Вы были заблокированы в боте! Обжаловать наказание: @GabriDev1337")
            return
        
        if call.data == "check_subscription":
            if is_subscribed(user_id):
                bot.send_message(call.message.chat.id, 
                               f"Привет, {call.from_user.first_name}, ты попал в телеграм бота сквада \"NeoCore\". "
                               "Тут ты можешь активировать ключ, связаться с тех поддержкой и не только!",
                               reply_markup=create_main_menu())
                logger.info(f"Пользователь {user_id} успешно проверил подписку")
            else:
                bot.answer_callback_query(call.id, "Вы не подписаны на канал!")
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("📌Подписаться", url="https://t.me/NeoCore_dev_bot"))
                markup.add(types.InlineKeyboardButton("✅ Проверить подписку", callback_data="check_subscription"))
                bot.send_message(call.message.chat.id, "Для начала работы подпишись", reply_markup=markup)
                logger.info(f"Пользователь {user_id} не подписан на канал")
        elif call.data.startswith("reply_ticket_"):
            if not is_admin(user_id, username):
                bot.answer_callback_query(call.id, "У вас нет прав.")
                return
            ticket_id = call.data.split("_")[-1]
            user_states[user_id] = f"waiting_for_reply_{ticket_id}"
            bot.send_message(call.message.chat.id, "Введите ваш ответ для этого тикета:", reply_markup=create_cancel_button())
            bot.answer_callback_query(call.id, "Подготовьтесь к отправке ответа.")
        elif call.data.startswith("close_ticket_"):
            if not is_admin(user_id, username):
                bot.answer_callback_query(call.id, "У вас нет прав.")
                return
            ticket_id = call.data.split("_")[-1]
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT status, user_id FROM tickets WHERE ticket_id = ?", (ticket_id,))
                ticket_data = cursor.fetchone()
            if ticket_data and ticket_data[0] == 'open':
                with conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE tickets SET status = 'closed' WHERE ticket_id = ?", (ticket_id,))
                    conn.commit()
                update_ticket_status_in_json(ticket_id, 'closed')
                bot.send_message(ticket_data[1], f"Ваш тикет #{ticket_id} закрыт администратором.", reply_markup=create_main_menu())
                user_states.pop(ticket_data[1], None)
                with conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT user_id FROM users WHERE role = 'Администрация'")
                    admins = cursor.fetchall()
                for admin in admins:
                    if admin[0] != user_id:
                        bot.send_message(admin[0], f"Тикет #{ticket_id} закрыт администратором {username}.")
                bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
                bot.answer_callback_query(call.id, "Тикет закрыт.")
            else:
                bot.answer_callback_query(call.id, "Тикет уже закрыт или не существует.")
        elif call.data.startswith("delete_ticket_"):
            if not is_admin(user_id, username):
                bot.answer_callback_query(call.id, "У вас нет прав.")
                return
            ticket_id = call.data.split("_")[-1]
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM tickets WHERE ticket_id = ?", (ticket_id,))
                ticket_data = cursor.fetchone()
            if ticket_data:
                user_ticket_id = ticket_data[0]
                with conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM tickets WHERE ticket_id = ?", (ticket_id,))
                    cursor.execute("DELETE FROM ticket_messages WHERE ticket_id = ?", (ticket_id,))
                    conn.commit()
                ticket_path = os.path.join(TICKETS_DIR, f"{ticket_id}.json")
                if os.path.exists(ticket_path):
                    os.remove(ticket_path)
                bot.send_message(user_ticket_id, f"Ваш тикет #{ticket_id} был удален администратором.", reply_markup=create_main_menu())
                user_states.pop(user_ticket_id, None)
                with conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT user_id FROM users WHERE role = 'Администрация'")
                    admins = cursor.fetchall()
                for admin in admins:
                    if admin[0] != user_id:
                        bot.send_message(admin[0], f"Тикет #{ticket_id} удален администратором {username}.")
                bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
                bot.answer_callback_query(call.id, "Тикет удален.")
            else:
                bot.answer_callback_query(call.id, "Тикет не существует.")
        elif call.data.startswith("unblock_"):
            if not is_admin(user_id, username):
                bot.answer_callback_query(call.id, "У вас нет прав.")
                return
            unblock_username = call.data.split("_")[1]
            with conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET is_blocked = 0 WHERE username = ?", (unblock_username,))
                conn.commit()
            
            # Обновляем users.yml
            users_data = load_users_yml()
            for user_key, user_data in users_data.items():
                if user_data["username"] == unblock_username:
                    users_data[user_key]["is_blocked"] = 0
                    break
            save_users_yml(users_data)
            
            bot.answer_callback_query(call.id, f"Пользователь {unblock_username} разблокирован.")
            try:
                with conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT user_id FROM users WHERE username = ?", (unblock_username,))
                    unblocked_user = cursor.fetchone()
                if unblocked_user:
                    bot.send_message(unblocked_user[0], "✅ Вы были разблокированы в боте!")
                    blocked_user_message_counts.pop(unblocked_user[0], None)  # Сбрасываем счетчик сообщений
            except Exception as e:
                logger.error(f"Ошибка отправки сообщения о разблокировке {unblock_username}: {e}\n{traceback.format_exc()}")
            logger.info(f"Админ {user_id} разблокировал пользователя {unblock_username}")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    except Exception as e:
        logger.error(f"Ошибка в обработчике инлайн-кнопок для user_id {user_id}: {e}\n{traceback.format_exc()}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.")

# Обработчик кнопки "Профиль"
@bot.message_handler(func=lambda message: message.text == "⚙️ Профиль")
def profile(message):
    try:
        user_id = message.from_user.id
        username = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
        
        logger.info(f"Пользователь {user_id} ({username}) запросил профиль")
        
        # Проверка спама
        if check_spam(user_id, username):
            return
        
        if is_blocked(user_id):
            blocked_user_message_counts[user_id] += 1
            if blocked_user_message_counts[user_id] % SPAM_NOTIFICATION_INTERVAL == 0:
                bot.send_message(message.chat.id, "❌ Вы были заблокированы в боте! Обжаловать наказание: @GabriDev1337")
            return
            
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, username, reg_date, role FROM users WHERE user_id = ?", (user_id,))
            user_data = cursor.fetchone()
        
        if not user_data:
            logger.warning(f"Пользователь user_id={user_id} не найден в базе данных, повторная регистрация")
            register_user(user_id, username, message.from_user.first_name)
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name, username, reg_date, role FROM users WHERE user_id = ?", (user_id,))
                user_data = cursor.fetchone()
        
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM keys WHERE activated_by = ? AND is_activated = 1", (user_id,))
            key_count = cursor.fetchone()[0]
        
        bot.send_message(message.chat.id, 
                        f"Твоё имя: {user_data[0]}\n"
                        f"Твой юзернейм: {user_data[1]}\n"
                        f"Зарегистрированы: {user_data[2]}\n"
                        f"Активировано ключей: {key_count}\n"
                        f"Роль: {user_data[3]}",
                        reply_markup=create_main_menu())
    except Exception as e:
        logger.error(f"Ошибка в обработчике профиля для user_id {user_id}: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# Обработчик кнопки "Активировать ключ"
@bot.message_handler(func=lambda message: message.text == "🔑 Активировать ключ")
def activate_key(message):
    try:
        user_id = message.from_user.id
        username = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
        
        logger.info(f"Пользователь {user_id} ({username}) запросил активацию ключа")
        
        # Проверка спама
        if check_spam(user_id, username):
            return
        
        if is_blocked(user_id):
            blocked_user_message_counts[user_id] += 1
            if blocked_user_message_counts[user_id] % SPAM_NOTIFICATION_INTERVAL == 0:
                bot.send_message(message.chat.id, "❌ Вы были заблокированы в боте! Обжаловать наказание: @GabriDev1337")
            return
            
        user_states[message.from_user.id] = "waiting_for_key"
        bot.send_message(message.chat.id, 
                        "❗️ Введите ключ в формате NeoCore-XXXXX-XXXXX-XXXXX:",
                        reply_markup=create_cancel_button())
    except Exception as e:
        logger.error(f"Ошибка в обработчике активации ключа для user_id {user_id}: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# Обработчик кнопки "История активаций"
@bot.message_handler(func=lambda message: message.text == "📊 История активаций")
def activation_history(message):
    try:
        user_id = message.from_user.id
        username = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
        
        logger.info(f"Пользователь {user_id} ({username}) запросил историю активаций")
        
        # Проверка спама
        if check_spam(user_id, username):
            return
        
        if is_blocked(user_id):
            blocked_user_message_counts[user_id] += 1
            if blocked_user_message_counts[user_id] % SPAM_NOTIFICATION_INTERVAL == 0:
                bot.send_message(message.chat.id, "❌ Вы были заблокированы в боте! Обжаловать наказание: @GabriDev1337")
            return
            
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT file_name, activation_date, key_value FROM keys WHERE activated_by = ? AND is_activated = 1", 
                          (user_id,))
            activations = cursor.fetchall()
        
        if not activations:
            bot.send_message(message.chat.id, "🔗 Ваша история активаций:\nПусто", 
                            reply_markup=create_main_menu())
        else:
            response = "🔗 Ваша история активаций:\n\n"
            for activation in activations:
                response += f"Файл: {activation[0]}\n"
                response += f"Дата активации: {activation[1]}\n"
                response += f"Ключ по которому активировали: {activation[2]}\n\n"
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("Назад"))
            bot.send_message(message.chat.id, response, reply_markup=markup)
    except Exception as e:
        logger.error(f"Ошибка в обработчике истории активаций для user_id {user_id}: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# Обработчик кнопки "Идеи"
@bot.message_handler(func=lambda message: message.text == "💡Идеи")
def submit_idea(message):
    try:
        user_id = message.from_user.id
        username = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
        
        logger.info(f"Пользователь {user_id} ({username}) запросил отправку идеи")
        
        # Проверка спама
        if check_spam(user_id, username):
            return
        
        if is_blocked(user_id):
            blocked_user_message_counts[user_id] += 1
            if blocked_user_message_counts[user_id] % SPAM_NOTIFICATION_INTERVAL == 0:
                bot.send_message(message.chat.id, "❌ Вы были заблокированы в боте! Обжаловать наказание: @GabriDev1337")
            return
            
        user_states[message.from_user.id] = "waiting_for_idea"
        bot.send_message(message.chat.id,
                        "💡 Напишите вашу идею для улучшения бота (макс. 500 символов):\n\n"
                        "• Опишите предложение кратко и по делу\n"
                        "• Укажите, как это должно работать\n\n"
                        "Лучшие идеи будут реализованы!",
                        reply_markup=create_cancel_button())
    except Exception as e:
        logger.error(f"Ошибка в обработчике идей для user_id {user_id}: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# Обработчик кнопки "Тех.Поддержка"
@bot.message_handler(func=lambda message: message.text == "📞 Тех.Поддержка")
def support(message):
    try:
        user_id = message.from_user.id
        username = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
        
        logger.info(f"Пользователь {user_id} ({username}) запросил тех. поддержку")
        
        # Проверка спама
        if check_spam(user_id, username):
            return
        
        if is_blocked(user_id):
            blocked_user_message_counts[user_id] += 1
            if blocked_user_message_counts[user_id] % SPAM_NOTIFICATION_INTERVAL == 0:
                bot.send_message(message.chat.id, "❌ Вы были заблокированы в боте! Обжаловать наказание: @GabriDev1337")
            return
        
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticket_id FROM tickets WHERE user_id = ? AND status = 'open'", (user_id,))
            existing_ticket = cursor.fetchone()
        if existing_ticket:
            ticket_id = existing_ticket[0]
            user_states[user_id] = {"state": "in_ticket", "ticket_id": ticket_id}
            bot.send_message(message.chat.id, 
                            f"У вас уже открыт тикет #{ticket_id}. Вы можете отправить дополнительное сообщение или закрыть тикет.",
                            reply_markup=create_ticket_keyboard())
        else:
            user_states[user_id] = "waiting_for_support_message"
            bot.send_message(message.chat.id, 
                            "📞 Напишите ваше обращение в тех. поддержку:",
                            reply_markup=create_cancel_button())
    except Exception as e:
        logger.error(f"Ошибка в обработчике тех. поддержки для user_id {user_id}: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# Обработчик кнопки "Правила"
@bot.message_handler(func=lambda message: message.text == "📖 Правила")
def rules(message):
    try:
        user_id = message.from_user.id
        username = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
        
        logger.info(f"Пользователь {user_id} ({username}) запросил правила")
        
        # Проверка спама
        if check_spam(user_id, username):
            return
        
        if is_blocked(user_id):
            blocked_user_message_counts[user_id] += 1
            if blocked_user_message_counts[user_id] % SPAM_NOTIFICATION_INTERVAL == 0:
                bot.send_message(message.chat.id, "❌ Вы были заблокированы в боте! Обжаловать наказание: @GabriDev1337")
            return
            
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("Назад"))
        bot.send_message(message.chat.id,
                        "💎 Правила использования бота\n\n"
                        "1) 🚫 Нельзя распространять полученные файлы\n"
                        "2) 🛑 Перепродажа и передача ключей запрещена\n"
                        "3) 🔒Мой личный бот » @NeoCore_dev_bot Один ключ = одна активация на аккаунт\n"
                        "4) 📞 Вопросы — через поддержку\n"
                        "5) ⚡️ Активация = согласие с правилами\n"
                        "6) 🎯 Используйте контент только в личных целях\n"
                        "7) 💎 Мы отвечаем за качество\n\n"
                        "⚠️ Нарушение ведет к немедленной блокировке.",
                        reply_markup=markup)
    except Exception as e:
        logger.error(f"Ошибка в обработчике правил для user_id {user_id}: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# Обработчик кнопки "Добавить ключ" в админ-панели
@bot.message_handler(func=lambda message: message.text == "🔑 Добавить ключ")
def add_key(message):
    try:
        user_id = message.from_user.id
        username = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
        
        logger.info(f"Админ {user_id} ({username}) запросил добавление ключа")
        
        # Проверка спама
        if check_spam(user_id, username):
            return
        
        if is_blocked(user_id):
            blocked_user_message_counts[user_id] += 1
            if blocked_user_message_counts[user_id] % SPAM_NOTIFICATION_INTERVAL == 0:
                bot.send_message(message.chat.id, "❌ Вы были заблокированы в боте! Обжаловать наказание: @GabriDev1337")
            return
            
        if is_admin(user_id, username):
            user_states[message.from_user.id] = "waiting_for_file"
            bot.send_message(message.chat.id, 
                            "🔗 Скиньте файл который будет выдавать при активации ключа",
                            reply_markup=create_cancel_button())
        else:
            bot.send_message(message.chat.id, "❌ У вас нет прав", reply_markup=create_main_menu())
    except Exception as e:
        logger.error(f"Ошибка в обработчике добавления ключа для user_id {user_id}: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# Обработчик кнопки "Заблокировать пользователя" в админ-панели
@bot.message_handler(func=lambda message: message.text == "⚰️ Заблокировать пользователя")
def block_user(message):
    try:
        user_id = message.from_user.id
        username = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
        
        logger.info(f"Админ {user_id} ({username}) запросил блокировку пользователя")
        
        # Проверка спама
        if check_spam(user_id, username):
            return
        
        if is_blocked(user_id):
            blocked_user_message_counts[user_id] += 1
            if blocked_user_message_counts[user_id] % SPAM_NOTIFICATION_INTERVAL == 0:
                bot.send_message(message.chat.id, "❌ Вы были заблокированы в боте! Обжаловать наказание: @GabriDev1337")
            return
            
        if is_admin(user_id, username):
            user_states[message.from_user.id] = "waiting_for_block_username"
            bot.send_message(message.chat.id, 
                            "🛠 Скиньте юзернейм пользователя которого нужно заблокировать",
                            reply_markup=create_cancel_button())
        else:
            bot.send_message(message.chat.id, "❌ У вас нет прав", reply_markup=create_main_menu())
    except Exception as e:
        logger.error(f"Ошибка в обработчике блокировки пользователя для user_id {user_id}: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# Обработчик кнопки "Разблокировать пользователя" в админ-панели
@bot.message_handler(func=lambda message: message.text == "🔓 Разблокировать пользователя")
def unblock_user(message):
    try:
        user_id = message.from_user.id
        username = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
        
        logger.info(f"Админ {user_id} ({username}) запросил разблокировку пользователя")
        
        # Проверка спама
        if check_spam(user_id, username):
            return
        
        if is_blocked(user_id):
            blocked_user_message_counts[user_id] += 1
            if blocked_user_message_counts[user_id] % SPAM_NOTIFICATION_INTERVAL == 0:
                bot.send_message(message.chat.id, "❌ Вы были заблокированы в боте! Обжаловать наказание: @GabriDev1337")
            return
            
        if is_admin(user_id, username):
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT username FROM users WHERE is_blocked = 1")
                blocked_users = cursor.fetchall()
            if not blocked_users:
                bot.send_message(message.chat.id, "Нет заблокированных пользователей.", reply_markup=create_admin_menu())
                return
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            for blocked in blocked_users:
                markup.add(types.InlineKeyboardButton(blocked[0], callback_data=f"unblock_{blocked[0]}"))
            bot.send_message(message.chat.id, "Выберите пользователя для разблокировки:", reply_markup=markup)
        else:
            bot.send_message(message.chat.id, "❌ У вас нет прав", reply_markup=create_main_menu())
    except Exception as e:
        logger.error(f"Ошибка в обработчике разблокировки пользователя для user_id {user_id}: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# Обработчик кнопки "Объявление" в админ-панели
@bot.message_handler(func=lambda message: message.text == "📢 Объявление")
def announcement(message):
    try:
        user_id = message.from_user.id
        username = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
        
        logger.info(f"Админ {user_id} ({username}) запросил создание объявления")
        
        # Проверка спама
        if check_spam(user_id, username):
            return
        
        if is_blocked(user_id):
            blocked_user_message_counts[user_id] += 1
            if blocked_user_message_counts[user_id] % SPAM_NOTIFICATION_INTERVAL == 0:
                bot.send_message(message.chat.id, "❌ Вы были заблокированы в боте! Обжаловать наказание: @GabriDev1337")
            return
            
        if is_admin(user_id, username):
            user_states[message.from_user.id] = "waiting_for_announcement"
            bot.send_message(message.chat.id, 
                            "📢 Введите текст объявления, который будет отправлен всем пользователям:",
                            reply_markup=create_cancel_button())
        else:
            bot.send_message(message.chat.id, "❌ У вас нет прав", reply_markup=create_main_menu())
    except Exception as e:
        logger.error(f"Ошибка в обработчике объявления для user_id {user_id}: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# Обработчик кнопки "Информация" в админ-панели
@bot.message_handler(func=lambda message: message.text == "⚙️ Информация")
def admin_info(message):
    try:
        user_id = message.from_user.id
        username = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
        
        logger.info(f"Админ {user_id} ({username}) запросил информацию")
        
        # Проверка спама
        if check_spam(user_id, username):
            return
        
        if is_blocked(user_id):
            blocked_user_message_counts[user_id] += 1
            if blocked_user_message_counts[user_id] % SPAM_NOTIFICATION_INTERVAL == 0:
                bot.send_message(message.chat.id, "❌ Вы были заблокированы в боте! Обжаловать наказание: @GabriDev1337")
            return
            
        if is_admin(user_id, username):
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users")
                total_users = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'Администрация'")
                admin_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM keys")
                total_keys = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM keys WHERE is_activated = 1")
                activated_keys = cursor.fetchone()[0]
            
            bot.send_message(message.chat.id,
                            f"👤 Пользователей: {total_users - admin_count}\n"
                            f"⚙️ Админов: {len(ADMINS)}\n"
                            f"📌 Всего: {total_users}\n\n"
                            f"🔑 Всего Ключей создано: {total_keys}\n"
                            f"❗️ Всего Ключей активировано: {activated_keys}",
                            reply_markup=create_admin_menu())
        else:
            bot.send_message(message.chat.id, "❌ У вас нет прав", reply_markup=create_main_menu())
    except Exception as e:
        logger.error(f"Ошибка в обработчике информации для user_id {user_id}: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# Обработчик загруженных файлов
@bot.message_handler(content_types=['document'])
def handle_document(message):
    try:
        user_id = message.from_user.id
        username = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
        
        logger.info(f"Пользователь {user_id} ({username}) загрузил документ: {message.document.file_name}")
        
        # Проверка спама
        if check_spam(user_id, username):
            return
        
        if is_blocked(user_id):
            blocked_user_message_counts[user_id] += 1
            if blocked_user_message_counts[user_id] % SPAM_NOTIFICATION_INTERVAL == 0:
                bot.send_message(message.chat.id, "❌ Вы были заблокированы в боте! Обжаловать наказание: @GabriDev1337")
            return
            
        if user_states.get(message.from_user.id) == "waiting_for_file":
            if is_admin(user_id, username):
                file_info = bot.get_file(message.document.file_id)
                file_name = message.document.file_name
                file_path = os.path.join(FILES_DIR, file_name)
                
                # Скачивание файла
                downloaded_file = bot.download_file(file_info.file_path)
                with open(file_path, 'wb') as new_file:
                    new_file.write(downloaded_file)
                logger.info(f"Файл сохранен: {file_path}")
                
                user_states[message.from_user.id] = {"state": "waiting_for_key_count", "file_path": file_path}
                bot.send_message(message.chat.id, 
                               "❗️Какое количество ключей вы хотите создать (до 10)",
                               reply_markup=create_cancel_button())
    except Exception as e:
        logger.error(f"Ошибка в обработчике документов для user_id {user_id}: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# Обработчик текстовых сообщений
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        user_id = message.from_user.id
        username = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
        text = message.text
        
        logger.info(f"Пользователь {user_id} ({username}) отправил сообщение: {text}")
        
        # Проверка спама
        if check_spam(user_id, username):
            return
        
        if is_blocked(user_id):
            blocked_user_message_counts[user_id] += 1
            if blocked_user_message_counts[user_id] % SPAM_NOTIFICATION_INTERVAL == 0:
                bot.send_message(message.chat.id, "❌ Вы были заблокированы в боте! Обжаловать наказание: @GabriDev1337")
            return
            
        state = user_states.get(user_id)
        
        if text == "Отменить ввод" or text == "Назад":
            user_states.pop(user_id, None)
            bot.send_message(message.chat.id, "Действие отменено", reply_markup=create_main_menu())
            return
        
        if state == "waiting_for_key":
            key = text
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT key_id, file_name FROM keys WHERE key_value = ? AND is_activated = 0", (key,))
                key_data = cursor.fetchone()
            
            if key_data:
                file_path = os.path.join(FILES_DIR, key_data[1])
                if os.path.exists(file_path):
                    with conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE keys SET is_activated = 1, activated_by = ?, activation_date = ? WHERE key_id = ?",
                                     (user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), key_data[0]))
                        conn.commit()
                    
                    # Обновляем количество активированных ключей в users.yml
                    users_data = load_users_yml()
                    user_key = str(user_id)
                    if user_key in users_data:
                        users_data[user_key]["activated_keys"] += 1
                    else:
                        users_data[user_key] = {
                            "user_id": user_id,
                            "username": username,
                            "name": message.from_user.first_name,
                            "reg_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "role": "Пользователь",
                            "is_blocked": 0,
                            "activated_keys": 1
                        }
                    save_users_yml(users_data)
                    
                    with open(file_path, 'rb') as file:
                        bot.send_document(message.chat.id, file, caption="✅ Ключ успешно активирован! Вот ваш файл:")
                    bot.send_message(message.chat.id, "Файл отправлен!", reply_markup=create_main_menu())
                    logger.info(f"Пользователь {user_id} активировал ключ: {key} и получил файл: {file_path}")
                else:
                    bot.send_message(message.chat.id, "❌ Файл не найден на сервере. Обратитесь в поддержку: @GabriDev1337",
                                   reply_markup=create_main_menu())
                    logger.error(f"Файл {file_path} не найден для ключа {key}")
            else:
                bot.send_message(message.chat.id, "❌ Неверный или уже использованный ключ",
                               reply_markup=create_main_menu())
                logger.warning(f"Пользователь {user_id} попытался активировать неверный ключ: {key}")
            user_states.pop(user_id, None)
        
        elif state == "waiting_for_idea":
            if len(text) > 500:
                bot.send_message(message.chat.id, "❌ Идея слишком длинная (макс. 500 символов)",
                               reply_markup=create_cancel_button())
                logger.warning(f"Пользователь {user_id} отправил слишком длинную идею")
            else:
                with conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO ideas (user_id, idea_text, submission_date) VALUES (?, ?, ?)",
                                 (user_id, text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                try:
                    bot.send_message(OWNER_CHAT_ID, f"Новая идея от {username}:\n{text}")
                except Exception as e:
                    logger.error(f"Ошибка отправки идеи владельцу: {e}\n{traceback.format_exc()}")
                    bot.send_message(message.chat.id, "⚠️ Идея сохранена, но не удалось уведомить владельца")
                bot.send_message(message.chat.id, "✅ Идея отправлена!", reply_markup=create_main_menu())
                logger.info(f"Пользователь {user_id} отправил идею: {text}")
                user_states.pop(user_id, None)
        
        elif state == "waiting_for_announcement":
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users WHERE is_blocked = 0")
                users = cursor.fetchall()
            success_count = 0
            fail_count = 0
            for user in users:
                try:
                    bot.send_message(user[0], f"📢 Объявление:\n\n{text}")
                    success_count += 1
                except Exception as e:
                    logger.error(f"Ошибка отправки объявления пользователю {user[0]}: {e}")
                    fail_count += 1
            bot.send_message(message.chat.id, 
                           f"✅ Объявление отправлено {success_count} пользователям. Не удалось отправить {fail_count} пользователям.",
                           reply_markup=create_admin_menu())
            logger.info(f"Админ {user_id} отправил объявление: {text}")
            user_states.pop(user_id, None)
        
        elif isinstance(state, dict) and state.get("state") == "waiting_for_key_count":
            try:
                count = int(text)
                if count > 10 or count < 1:
                    raise ValueError
                keys = [generate_random_key() for _ in range(count)]
                response = f"✅ Успешно создано {count} ключей, вот они:\n\n"
                file_name = os.path.basename(state["file_path"])
                with conn:
                    cursor = conn.cursor()
                    for key in keys:
                        cursor.execute("INSERT INTO keys (key_value, file_name) VALUES (?, ?)",
                                     (key, file_name))
                        response += f"{key}\n"
                    conn.commit()
                response += f"\n🔗 Файл: {file_name}\n Бот: @NeoCoreBot"
                bot.send_message(message.chat.id, response, reply_markup=create_admin_menu())
                logger.info(f"Админ {user_id} создал {count} ключей для файла {file_name}")
                user_states.pop(user_id, None)
            except Exception as e:
                bot.send_message(message.chat.id, "❌ Введите число от 1 до 10",
                               reply_markup=create_cancel_button())
                logger.error(f"Ошибка при создании ключей для user_id {user_id}: {e}\n{traceback.format_exc()}")
        
        elif state == "waiting_for_block_username":
            username_to_block = text
            with conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET is_blocked = 1 WHERE username = ?", (username_to_block,))
                conn.commit()
            
            # Обновляем users.yml
            users_data = load_users_yml()
            for user_key, user_data in users_data.items():
                if user_data["username"] == username_to_block:
                    users_data[user_key]["is_blocked"] = 1
                    break
            save_users_yml(users_data)
            
            bot.send_message(message.chat.id, 
                           f"✅ Вы успешно заблокировали пользователя {username_to_block}",
                           reply_markup=create_admin_menu())
            try:
                with conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT user_id FROM users WHERE username = ?", (username_to_block,))
                    blocked_user = cursor.fetchone()
                if blocked_user:
                    bot.send_message(blocked_user[0], "❌ Вы были заблокированы в боте! Обжаловать наказание: @GabriDev1337")
                else:
                    bot.send_message(message.chat.id, "⚠️ Пользователь не найден в базе данных")
            except Exception as e:
                bot.send_message(message.chat.id, "⚠️ Не удалось отправить сообщение пользователю, возможно, он не начинал общение с ботом")
                logger.error(f"Ошибка отправки сообщения о блокировке {username_to_block}: {e}\n{traceback.format_exc()}")
            logger.info(f"Админ {user_id} заблокировал пользователя {username_to_block}")
            user_states.pop(user_id, None)
        
        elif state == "waiting_for_support_message":
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO tickets (user_id, created_at) VALUES (?, ?)",
                              (user_id, created_at))
                conn.commit()
                ticket_id = cursor.lastrowid
                cursor.execute("INSERT INTO ticket_messages (ticket_id, user_id, message_text, sent_at, is_admin) VALUES (?, ?, ?, ?, ?)",
                              (ticket_id, user_id, text, created_at, False))
                conn.commit()
            save_ticket_to_json(ticket_id, user_id, text, created_at)
            user_states[user_id] = {"state": "in_ticket", "ticket_id": ticket_id}
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users WHERE role = 'Администрация'")
                admins = cursor.fetchall()
            for admin in admins:
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("Ответить", callback_data=f"reply_ticket_{ticket_id}"))
                markup.add(types.InlineKeyboardButton("Закрыть", callback_data=f"close_ticket_{ticket_id}"))
                markup.add(types.InlineKeyboardButton("Удалить", callback_data=f"delete_ticket_{ticket_id}"))
                bot.send_message(admin[0], f"Новый тикет #{ticket_id} от {username}:\n{text}", reply_markup=markup)
            bot.send_message(user_id, "✅ Обращение отправлено. Вы можете отправить дополнительные сообщения или закрыть тикет.", reply_markup=create_ticket_keyboard())
        
        elif isinstance(state, dict) and state["state"] == "in_ticket":
            ticket_id = state["ticket_id"]
            if text == "Закрыть тикет":
                with conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE tickets SET status = 'closed' WHERE ticket_id = ?", (ticket_id,))
                    conn.commit()
                update_ticket_status_in_json(ticket_id, 'closed')
                bot.send_message(user_id, f"Тикет #{ticket_id} закрыт.", reply_markup=create_main_menu())
                user_states.pop(user_id, None)
                with conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT user_id FROM users WHERE role = 'Администрация'")
                    admins = cursor.fetchall()
                for admin in admins:
                    bot.send_message(admin[0], f"Пользователь {username} закрыл тикет #{ticket_id}.")
            else:
                with conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT status FROM tickets WHERE ticket_id = ?", (ticket_id,))
                    status = cursor.fetchone()[0]
                if status == 'open':
                    with conn:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO ticket_messages (ticket_id, user_id, message_text, sent_at, is_admin) VALUES (?, ?, ?, ?, ?)",
                                      (ticket_id, user_id, text, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), False))
                        conn.commit()
                    update_ticket_in_json(ticket_id, text, user_id, is_admin=False)
                    with conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT user_id FROM users WHERE role = 'Администрация'")
                        admins = cursor.fetchall()
                    for admin in admins:
                        markup = types.InlineKeyboardMarkup()
                        markup.add(types.InlineKeyboardButton("Ответить", callback_data=f"reply_ticket_{ticket_id}"))
                        markup.add(types.InlineKeyboardButton("Закрыть", callback_data=f"close_ticket_{ticket_id}"))
                        markup.add(types.InlineKeyboardButton("Удалить", callback_data=f"delete_ticket_{ticket_id}"))
                        bot.send_message(admin[0], f"Сообщение в тикет #{ticket_id} от {username}:\n{text}", reply_markup=markup)
                    bot.send_message(user_id, "Сообщение отправлено в поддержку.", reply_markup=create_ticket_keyboard())
                else:
                    bot.send_message(user_id, "Тикет закрыт. Откройте новый, если нужно.", reply_markup=create_main_menu())
                    user_states.pop(user_id, None)
        
        elif isinstance(state, str) and state.startswith("waiting_for_reply_"):
            ticket_id = state.split("_")[-1]
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT status, user_id FROM tickets WHERE ticket_id = ?", (ticket_id,))
                ticket_data = cursor.fetchone()
            if ticket_data and ticket_data[0] == 'open':
                with conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO ticket_messages (ticket_id, user_id, message_text, sent_at, is_admin) VALUES (?, ?, ?, ?, ?)",
                                  (ticket_id, user_id, text, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), True))
                    conn.commit()
                update_ticket_in_json(ticket_id, text, user_id, is_admin=True)
                bot.send_message(ticket_data[1], f"Ответ от поддержки:\n{text}")
                bot.send_message(user_id, "Ответ отправлен пользователю.", reply_markup=create_admin_menu())
                user_states.pop(user_id, None)
            else:
                bot.send_message(user_id, "Тикет уже закрыт или не существует.", reply_markup=create_admin_menu())
                user_states.pop(user_id, None)
        
        else:
            bot.send_message(message.chat.id, "❌ Неизвестная команда", reply_markup=create_main_menu())
            logger.info(f"Пользователь {user_id} отправил неизвестную команду: {text}")
    except Exception as e:
        logger.error(f"Ошибка в обработчике текстовых сообщений для user_id {user_id}: {e}\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

# Запуск бота
try:
    logger.info("Бот запущен")
    bot.polling()
except Exception as e:
    logger.error(f"Критическая ошибка при запуске бота: {e}\n{traceback.format_exc()}")
    sys.exit(1)