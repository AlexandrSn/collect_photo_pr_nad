import os
import json
from functools import wraps
from datetime import datetime
from os import makedirs
from telegram import Update, ForceReply, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackContext
from flask import Flask, request
import logging

# Инициализация логирования
logging.basicConfig(level=logging.INFO)

# Создание Flask-приложения
app = Flask(__name__)

@app.route('/')
def home():
    return "I'm alive!"  # Это отвечает на запросы от UptimeRobot

# Настройки
DATA_FILE = 'db.json'
PHOTO_DIR = 'photos'

ALLOWED_USERS = []
for key, value in os.environ.items():
    if key.startswith("user_"):
        user_id = int(value)
        ALLOWED_USERS.append(user_id)

TOKEN = os.getenv("BOT_TOKEN")
print(TOKEN[:5])
print(ALLOWED_USERS)

# Состояние диалога
WAITING_FOR_NUMBER, WAITING_FOR_PHOTO = range(2)

# Интерфейс кнопок
MAIN_MENU = ReplyKeyboardMarkup(
    [
        ['Какой номер сейчас ищем?', 'Последний номер'],
        ['Все номера', 'Добавить номер']
    ],
    resize_keyboard=True
)

# Подготовка
if not os.path.exists(PHOTO_DIR):
    os.makedirs(PHOTO_DIR)

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump({'current_number': 1}, f)

# Утилиты
def get_current_number():
    with open(DATA_FILE) as f:
        return json.load(f)['current_number']

def set_current_number(num):
    with open(DATA_FILE, 'w') as f:
        json.dump({"current_number": num}, f)

def get_photo_path(number):
    return os.path.join(PHOTO_DIR, f"{number:03d}.jpg")

def get_all_photos():
    return sorted(
        [
            f for f in os.listdir(PHOTO_DIR)
            if f.endswith('.jpg')
        ]
    )

def is_allowed(user_id):
    return user_id in ALLOWED_USERS

def allowed_user_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not is_allowed(user_id):
            await update.message.reply_text("⛔ У тебя нет доступа к этому боту.")
            print('User_id: ', update.message.from_user.id)
            return ConversationHandler.END
