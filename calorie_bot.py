#!/usr/bin/env python3
import os
import logging
import sqlite3
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ConversationHandler, ContextTypes, filters
)

# 🔐 ПОЛУЧАЕМ ТОКЕН ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ (БЕЗОПАСНО!)
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    logging.error("❌ Токен не найден! Установите переменную BOT_TOKEN")
    exit(1)

# Настройка логов
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Этапы разговора
WEIGHT, HEIGHT, AGE, GENDER, MAIN = range(5)

# База продуктов (калории на 100г)
FOODS = {
    "гречка": 343,
    "рис": 130,
    "курица": 165,
    "яйцо": 157,
    "банан": 89,
    "яблоко": 52,
    "творог": 121,
    "хлеб": 247,
    "картофель": 77,
    "помидор": 18,
    "огурец": 15,
    "сыр": 402,
    "молоко": 52,
    "йогурт": 59,
}

class SimpleCalorieBot:
    def __init__(self):
        self.init_database()
    
    def init_database(self):
        """Создаем простую базу данных"""
        try:
            self.conn = sqlite3.connect('calories.db')
            self.cursor = self.conn.cursor()
            
            # Таблица пользователей
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    weight REAL,
                    height REAL,
                    age INTEGER,
                    gender TEXT,
                    daily_goal INTEGER
                )
            ''')
            
            # Таблица еды
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS meals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    food TEXT,
                    calories INTEGER,
                    grams INTEGER,
                    date TEXT
                )
            ''')
            
            self.conn.commit()
            logger.info("✅ База данных инициализирована")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}")
    
    def save_user(self, user_id, weight, height, age, gender):
        """Сохраняем пользователя и считаем норму"""
        try:
            if gender == 'мужской':
                daily_goal = int(10 * weight + 6.25 * height - 5 * age + 5) * 1.2
            else:
                daily_goal = int(10 * weight + 6.25 * height - 5 * age - 161) * 1.2
            
            self.cursor.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, weight, height, age, gender, daily_goal)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, weight, height, age, gender, daily_goal))
            
            self.conn.commit()
            logger.info(f"✅ Пользователь {user_id} сохранён, норма: {daily_goal}")
            return daily_goal
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения пользователя: {e}")
            return 2000  # Значение по умолчанию
    
    def add_food(self, user_id, food, grams):
        """Добавляем еду"""
        try:
            if food in FOODS:
                calories = int((FOODS[food] * grams) / 100)
                today = datetime.now().strftime('%Y-%m-%d')
                
                self.cursor.execute('''
                    INSERT INTO meals (user_id, food, calories, grams, date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, food, calories, grams, today))
                
                self.conn.commit()
                logger.info(f"✅ Добавлена еда: {food} {grams}г ({calories} ккал)")
                return calories
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка добавления еды: {e}")
            return None
    
    def get_today_total(self, user_id):
        """Считаем калории за сегодня"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            self.cursor.execute('''
                SELECT SUM(calories) FROM meals 
                WHERE user_id=? AND date=?
            ''', (user_id, today))
            
            result = self.cursor.fetchone()
            return result[0] if result[0] else 0
        except Exception as e:
            logger.error(f"❌ Ошибка получения калорий: {e}")
            return 0
    
    def get_goal(self, user_id):
        """Получаем дневную норму"""
        try:
            self.cursor.execute('SELECT daily_goal FROM users WHERE user_id=?', (user_id,))
            result = self.cursor.fetchone()
            return result[0] if result else 2000
        except Exception as e:
            logger.error(f"❌ Ошибка получения нормы: {e}")
            return 2000
    
    def get_month_stats(self, user_id):
        """Статистика за месяц"""
        try:
            month = datetime.now().strftime('%Y-%m')
            
            self.cursor.execute('''
                SELECT date, SUM(calories) FROM meals 
                WHERE user_id=? AND strftime('%Y-%m', date)=?
                GROUP BY date
                ORDER BY date
            ''', (user_id, month))
            
            return self.cursor.fetchall()
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return []

# Создаем бота
bot = SimpleCalorieBot()

# ========== ФУНКЦИИ БОТА ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинаем диалог"""
    user_id = update.effective_user.id
    
    # Проверяем, есть ли пользователь в БД
    try:
        bot.cursor.execute('SELECT weight FROM users WHERE user_id=?', (user_id,))
        user_exists = bot.cursor.fetchone()
        
        if user_exists:
            # Пользователь уже зарегистрирован
            await update.message.reply_text(
                "👋 С возвращением! Выберите действие:\n"
                "📝 Добавить еду\n"
                "📊 Статистика\n"
                "⚙️ Изменить данные",
                reply_markup=ReplyKeyboardMarkup(
                    [["📝 Добавить еду", "📊 Статистика"], ["⚙️ Изменить данные"]],
                    resize_keyboard=True
                )
            )
            return MAIN
    except Exception as e:
        logger.error(f"Ошибка проверки пользователя: {e}")
    
    # Новый пользователь
    await update.message.reply_text(
        "🍏 Привет! Я помогу тебе считать калории.\n"
        "Для начала давай узнаем твои данные.\n"
        "Сколько ты весишь (в кг)?"
    )
    return WEIGHT

async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем вес"""
    try:
        weight = float(update.message.text)
        if weight < 20 or weight > 300:
            await update.message.reply_text("❌ Неверный вес! Введи число от 20 до 300 кг:")
            return WEIGHT
        
        context.user_data['weight'] = weight
        await update.message.reply_text("📏 Какой у тебя рост (в см)?")
        return HEIGHT
    except ValueError:
        await update.message.reply_text("❌ Введи число, например: 70.5")
        return WEIGHT

async def get_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем рост"""
    try:
        height = float(update.message.text)
        if height < 50 or height > 250:
            await update.message.reply_text("❌ Неверный рост! Введи число от 50 до 250 см:")
            return HEIGHT
        
        context.user_data['height'] = height
        await update.message.reply_text("🎂 Сколько тебе лет?")
        return AGE
    except ValueError:
        await update.message.reply_text("❌ Введи число, например: 175")
        return HEIGHT

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем возраст"""
    try:
        age = int(update.message.text)
        if age < 10 or age > 120:
            await update.message.reply_text("❌ Неверный возраст! Введи число от 10 до 120:")
            return AGE
        
        context.user_data['age'] = age
        await update.message.reply_text(
            "👤 Выбери пол:\n"
            "мужской\n"
            "женский",
            reply_markup=ReplyKeyboardMarkup(
                [["мужской", "женский"]],
                resize_keyboard=True
            )
        )
        return GENDER
    except ValueError:
        await update.message.reply_text("❌ Введи целое число, например: 25")
        return AGE

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем пол"""
    gender = update.message.text.lower()
    if gender not in ['мужской', 'женский']:
        await update.message.reply_text("❌ Выбери 'мужской' или 'женский'")
        return GENDER
    
    # Сохраняем пользователя
    user_id = update.effective_user.id
    weight = context.user_data.get('weight')
    height = context.user_data.get('height')
    age = context.user_data.get('age')
    
    daily_goal = bot.save_user(user_id, weight, height, age, gender)
    
    await update.message.reply_text(
        f"✅ Отлично! Твоя дневная норма: {daily_goal} ккал\n\n"
        "Что хочешь сделать?",
        reply_markup=ReplyKeyboardMarkup(
            [["📝 Добавить еду", "📊 Статистика"], ["⚙️ Изменить данные"]],
            resize_keyboard=True
        )
    )
    return MAIN

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню"""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "📝 Добавить еду":
        # Показываем список продуктов
        food_list = "\n".join([f"• {food}" for food in FOODS.keys()])
        await update.message.reply_text(
            f"🍎 Выбери продукт из списка:\n\n{food_list}\n\n"
            "Или напиши название продукта:"
        )
        return 'CHOOSE_FOOD'
    
    elif text == "📊 Статистика":
        today_total = bot.get_today_total(user_id)
        goal = bot.get_goal(user_id)
        remaining = max(0, goal - today_total)
        
        stats = bot.get_month_stats(user_id)
        stats_text = ""
        if stats:
            stats_text = "\n\n📅 За этот месяц:\n"
            for date, calories in stats[:7]:  # Последние 7 дней
                stats_text += f"{date}: {calories} ккал\n"
        
        await update.message.reply_text(
            f"📊 Сегодня ты съел(а): {today_total} ккал\n"
            f"🎯 Цель на день: {goal} ккал\n"
            f"📉 Осталось: {remaining} ккал"
            f"{stats_text}"
        )
        return MAIN
    
    elif text == "⚙️ Изменить данные":
        await update.message.reply_text("✏️ Введи новый вес (в кг):")
        return WEIGHT
    
    else:
        await update.message.reply_text("Выбери действие из меню:")
        return MAIN

async def choose_food(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор продукта"""
    food = update.message.text.lower()
    
    if food not in FOODS:
        await update.message.reply_text("❌ Такого продукта нет в базе. Попробуй другой:")
        return 'CHOOSE_FOOD'
    
    context.user_data['selected_food'] = food
    await update.message.reply_text(f"🍎 {food.capitalize()}. Сколько грамм?")
    return 'GET_GRAMS'

async def get_grams(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем количество грамм"""
    try:
        grams = int(update.message.text)
        if grams <= 0 or grams > 5000:
            await update.message.reply_text("❌ Введи количество от 1 до 5000 грамм:")
            return 'GET_GRAMS'
        
        user_id = update.effective_user.id
        food = context.user_data.get('selected_food')
        
        calories = bot.add_food(user_id, food, grams)
        
        if calories:
            today_total = bot.get_today_total(user_id)
            goal = bot.get_goal(user_id)
            
            await update.message.reply_text(
                f"✅ Добавлено: {food} - {grams}г ({calories} ккал)\n\n"
                f"📊 Всего за сегодня: {today_total} / {goal} ккал\n\n"
                "Что дальше?",
                reply_markup=ReplyKeyboardMarkup(
                    [["📝 Добавить еду", "📊 Статистика"], ["⚙️ Изменить данные"]],
                    resize_keyboard=True
                )
            )
            return MAIN
        else:
            await update.message.reply_text("❌ Ошибка добавления. Попробуй еще раз:")
            return 'CHOOSE_FOOD'
            
    except ValueError:
        await update.message.reply_text("❌ Введи число, например: 150")
        return 'GET_GRAMS'

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь"""
    await update.message.reply_text(
        "🍏 CalorieBot - Помощь:\n\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать это сообщение\n"
        "/cancel - Отменить текущее действие\n\n"
        "Бот помогает считать калории и следить за питанием!"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена"""
    await update.message.reply_text(
        "Действие отменено. Используй /start чтобы начать заново.",
        reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
    )
    return ConversationHandler.END

# ========== ЗАПУСК БОТА ==========
def main():
    """Главная функция запуска"""
    try:
        application = Application.builder().token(TOKEN).build()
        
        # Настраиваем диалог
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start)],
            states={
                WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)],
                HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_height)],
                AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
                GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gender)],
                MAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu)],
                'CHOOSE_FOOD': [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_food)],
                'GET_GRAMS': [MessageHandler(filters.TEXT & ~filters.COMMAND, get_grams)],
            },
            fallbacks=[CommandHandler('cancel', cancel)],
        )
        
        # Добавляем обработчики
        application.add_handler(conv_handler)
        application.add_handler(CommandHandler('help', help_command))
        
        # Запускаем polling
        logger.info("🤖 Бот запускается...")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")

if __name__ == '__main__':
    main()