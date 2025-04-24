import os
import json
from functools import wraps
from datetime import datetime
from os import makedirs

from telegram import Update, ForceReply, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, \
    CallbackContext

#Настройки
DATA_FILE = 'db.json'
PHOTO_DIR = 'photos'
ALLOWED_USERS = [379415631,111]


#Состояние диалога
WAITING_FOR_NUMBER, WAITING_FOR_PHOTO = range(2)

#Интерфейс кнопок
MAIN_MENU = ReplyKeyboardMarkup(
    [
        ['Какой номер сейчас ищем?','Последний номер'],
        ['Все номера', 'Добавить номер']
    ],
    resize_keyboard=True
)

#Подготовка
if not os.path.exists(PHOTO_DIR):
    os.makedirs(PHOTO_DIR)

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump({'current_number':1}, f)

#Утилиты
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
        return await func(update, context)
    return wrapper


#Команды и кнопки
@allowed_user_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Привет! Это персональный бот для сбора. \n Сейчас нужен номер: {get_current_number():03d}",
        reply_markup = MAIN_MENU
    )

@allowed_user_only
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    current_number = get_current_number()

    if text == "Какой номер сейчас ищем?":
        await update.message.reply_text(f"📌 Сейчас нужен номер: {current_number:03d}")
        return None

    elif text == "Последний номер":
        if current_number == 1:
            await update.message.reply_text("❗ Пока нет ни одного номера.")
            return None
        else:
            path = get_photo_path(current_number - 1)
            if os.path.exists(path):
                await update.message.reply_photo(photo=open(path, 'rb'), caption=f"Последний номер: {current_number-1:03d}")
                return None
            else:
                await update.message.reply_text("⚠️ Фотография последнего номера не найдена.")
                return None

    elif text == "Все номера":
        photos = get_all_photos()
        if not photos:
            await update.message.reply_text("📂 Пока нет ни одного фото.")
            return None
        else:
            for file in photos:
                path = os.path.join(PHOTO_DIR, file)
                await update.message.reply_photo(photo=open(path, 'rb'), caption=f"Номер: {file[:3]}")


# --- Добавление номера (номер → фото) ---

# --- Начало добавления номера ---
@allowed_user_only
async def begin_add_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 Введи номер, который хочешь добавить:")
    return WAITING_FOR_NUMBER

# --- Получение номера от пользователя ---
@allowed_user_only
async def handle_add_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("⚠️ Введи только цифры (например: 007)")
        return WAITING_FOR_NUMBER

    context.user_data["submitted_number"] = int(text)
    await update.message.reply_text("📷 Теперь пришли фото этого номера")
    return WAITING_FOR_PHOTO

# --- Получение фото ---
@allowed_user_only
async def handle_add_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    submitted_number = context.user_data.get("submitted_number")
    if not submitted_number:
        await update.message.reply_text("⚠️ Сначала введи номер")
        return ConversationHandler.END

    photo_file = await update.message.photo[-1].get_file()
    file_path = get_photo_path(submitted_number)
    await photo_file.download_to_drive(file_path)

    current = get_current_number()
    if submitted_number == current:
        next_number = current + 1
        set_current_number(next_number)

        # Рассылаем уведомление остальным
        for user_id in ALLOWED_USERS:
            if user_id != update.effective_user.id:
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"✅ Найден номер {submitted_number:03d}\n➡️ Теперь ищем {next_number:03d}"
                    )
                except Exception as e:
                    print(f"Не удалось отправить сообщение {user_id}: {e}")

    await update.message.reply_text(f"✅ Номер {submitted_number:03d} добавлен", reply_markup=MAIN_MENU)
    return ConversationHandler.END

# --- Запуск ---
def main():
    TOKEN = os.getenv("BOT_TOKEN")  # ← вставь сюда токен
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(MessageHandler(
        filters.Regex("^(Какой номер сейчас ищем\\?|Последний номер|Все номера)$"),
        handle_buttons
    ))

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Добавить номер$"), begin_add_number)],
        states={
            WAITING_FOR_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_number)],
            WAITING_FOR_PHOTO: [MessageHandler(filters.PHOTO, handle_add_photo)],
        },
        fallbacks=[]
    )
    app.add_handler(conv)

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()


