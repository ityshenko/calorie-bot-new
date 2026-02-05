#!/usr/bin/env python3
import os
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)

# Настройки
TOKEN = os.getenv('BOT_TOKEN')
RAILWAY_URL = os.getenv('RAILWAY_STATIC_URL')

# Создаем Flask и бота
app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

# Ваши обработчики команд (добавьте свои)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Бот работает на Railway! 🚂')

# Настройка обработчиков
application.add_handler(CommandHandler("start", start))

# Веб-сервер для Railway
@app.route('/')
def home():
    return "Bot is running"

@app.route('/health')
def health():
    return "OK", 200

# Вебхук для Telegram
@app.post(f'/{TOKEN}')
async def webhook():
    json_data = await request.get_json()
    update = Update.de_json(json_data, application.bot)
    await application.update_queue.put(update)
    return 'OK'

async def main():
    # Настраиваем вебхук в Railway
    if RAILWAY_URL:
        await application.bot.set_webhook(f'https://{RAILWAY_URL}/{TOKEN}')
        print(f"✅ Вебхук установлен")
    
    # Или polling локально
    else:
        print("🤖 Запускаем polling")
        await application.run_polling()

if __name__ == '__main__':
    import asyncio
    # Запускаем Flask в отдельном потоке
    from threading import Thread
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080))), daemon=True).start()
    
    # Запускаем бота
    asyncio.run(main())