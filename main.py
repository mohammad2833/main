import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler
import os
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')  # خواندن توکن از متغیر محیطی
if not TOKEN:
    raise ValueError("لطفاً توکن ربات را در TELEGRAM_BOT_TOKEN تنظیم کنید!")
    
)
import pandas as pd
from datetime import datetime
from jdatetime import datetime as jdt
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from PIL import Image
import requests
from io import BytesIO
import sqlite3
import logging

# تنظیمات لاگ‌گیری
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# وضعیت‌های مکالمه
(NAME, FAMILY, PHONE, LOCATION_START, CONFIRM_END, TYPE_SERVICE, 
 AMOUNT_MANUAL, PAYMENT_TYPE, PHOTO_UPLOAD, AMOUNT_RECEIVED,
 CLIENT_NAME, CLIENT_PHONE, DESCRIPTION, EVENT_DESC, EVENT_TIME) = range(15)

# دایرکتوری اصلی و تنظیمات دیتابیس
BASE_DIR = 'services'
os.makedirs(BASE_DIR, exist_ok=True)
DB_PATH = os.path.join(BASE_DIR, 'services.db')

# توابع کمکی
def jalali_now():
    return jdt.now().strftime("%Y/%m/%d %H:%M")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # جدول رانندگان
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS drivers (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        family TEXT,
        phone TEXT,
        username TEXT
    )
    ''')
    
    # جدول سرویس‌ها
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        start_time TEXT,
        end_time TEXT,
        service_type TEXT,
        calculated_amount INTEGER,
        received_amount INTEGER,
        bonus INTEGER,
        discount INTEGER,
        client_name TEXT,
        client_phone TEXT,
        description TEXT,
        FOREIGN KEY(user_id) REFERENCES drivers(user_id)
    ''')
    
    conn.commit()
    conn.close()

def save_driver(user_data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT OR REPLACE INTO drivers (user_id, name, family, phone, username)
    VALUES (?, ?, ?, ?, ?)
    ''', (
        user_data['user_id'],
        user_data['name'],
        user_data['family'],
        user_data['phone'],
        user_data.get('username', '')
    ))
    
    conn.commit()
    conn.close()

def save_service(service_data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO services (
        user_id, start_time, end_time, service_type,
        calculated_amount, received_amount, bonus,
        discount, client_name, client_phone, description
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        service_data['user_id'],
        service_data['start_time'],
        service_data['end_time'],
        service_data['service_type'],
        service_data.get('calculated_amount', 0),
        service_data.get('received_amount', 0),
        service_data.get('bonus', 0),
        service_data.get('discount', 0),
        service_data.get('client_name', ''),
        service_data.get('client_phone', ''),
        service_data.get('description', '')
    ))
    
    conn.commit()
    conn.close()

# دستور /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = {
        'user_id': user.id,
        'name': user.first_name,
        'username': user.username or ''
    }
    context.user_data.update(user_data)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT 1 FROM drivers WHERE user_id = ?', (user.id,))
    exists = cursor.fetchone()
    conn.close()
    
    if exists:
        await show_main_menu(update, context)
        return ConversationHandler.END
    
    await update.message.reply_text("سلام! لطفاً نام خود را وارد کنید:")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text.strip()
    await update.message.reply_text("نام خانوادگی خود را وارد کنید:")
    return FAMILY

async def get_family(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['family'] = update.message.text.strip()
    await update.message.reply_text("شماره تماس خود را با فرمت 09... وارد کنید:")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not (phone.startswith("09") and len(phone) == 11 and phone.isdigit()):
        await update.message.reply_text("شماره تماس نامعتبر است. لطفاً شماره را با فرمت 09123456789 وارد کنید.")
        return PHONE
    
    context.user_data['phone'] = phone
    save_driver(context.user_data)
    await show_main_menu(update, context)
    return ConversationHandler.END

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🟢 سرویس جدید", callback_data='new_service')],
        [InlineKeyboardButton("📊 گزارش‌ها", callback_data='reports')],
        [InlineKeyboardButton("📝 ثبت سرویس دستی", callback_data='manual_service')],
        [InlineKeyboardButton("🗓️ ثبت رویداد", callback_data='event_register')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(
            f"به منوی اصلی خوش آمدید {context.user_data.get('name', 'کاربر')} جان!",
            reply_markup=reply_markup
        )
    else:
        await update.callback_query.edit_message_text(
            f"به منوی اصلی خوش آمدید {context.user_data.get('name', 'کاربر')} جان!",
            reply_markup=reply_markup
        )

# --- سرویس جدید ---
async def new_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📍 لطفاً موقعیت شروع سرویس را ارسال کنید (اختیاری).")
    return LOCATION_START

async def location_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location:
        loc = update.message.location
        context.user_data['location_start'] = (loc.latitude, loc.longitude)
    
    context.user_data['start_time'] = datetime.now()
    context.user_data['jalali_start'] = jalali_now()
    
    keyboard = [[InlineKeyboardButton("🔚 پایان سرویس", callback_data='end_service')]]
    await update.message.reply_text(
        "⏰ شروع سرویس ثبت شد. برای پایان سرویس دکمه زیر را بزنید.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

async def end_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✅ بله", callback_data='confirm_end')],
        [InlineKeyboardButton("❌ خیر", callback_data='cancel_end')]
    ]
    await query.edit_message_text(
        "⚠️ آیا مطمئن هستید می‌خواهید سرویس را پایان دهید؟",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONFIRM_END

async def confirm_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['end_time'] = datetime.now()
    context.user_data['jalali_end'] = jalali_now()
    
    if update.message and update.message.location:
        loc = update.message.location
        context.user_data['location_end'] = (loc.latitude, loc.longitude)
    
    keyboard = [
        [InlineKeyboardButton("⏰ ساعتی", callback_data='type_hourly')],
        [InlineKeyboardButton("📦 پروژه‌ای", callback_data='type_project')]
    ]
    await query.edit_message_text(
        "نوع سرویس را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return TYPE_SERVICE

async def type_hourly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    start = context.user_data['start_time']
    end = context.user_data['end_time']
    duration_minutes = (end - start).seconds // 60
    
    fixed = 3_000_000  # هزینه ثابت
    hourly = 12_000_000  # هزینه ساعتی
    total = fixed + (duration_minutes // 60) * hourly
    
    context.user_data.update({
        'service_type': "ساعتی",
        'amount_calculated': total,
        'duration_minutes': duration_minutes
    })
    
    keyboard = [
        [InlineKeyboardButton("💳 کارتخوان", callback_data='payment_card_reader')],
        [InlineKeyboardButton("🏧 کارت به کارت", callback_data='payment_bank_transfer')],
        [InlineKeyboardButton("💵 نقدی", callback_data='payment_cash')],
        [InlineKeyboardButton("赊 نسیه", callback_data='payment_credit')]
    ]
    
    await query.edit_message_text(
        f"💰 مبلغ محاسبه‌شده: {total:,} ریال\n\nنوع پرداخت را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PAYMENT_TYPE

async def payment_card_reader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['payment_type'] = "کارتخوان"
    await query.edit_message_text("📸 لطفاً تصویر رسید را بارگذاری کنید.")
    return PHOTO_UPLOAD

async def photo_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    
    # در Render سیستم فایل موقت است، پس تصویر را در حافظه نگه می‌داریم
    photo_bytes = BytesIO()
    await file.download_to_memory(out=photo_bytes)
    context.user_data['photo_bytes'] = photo_bytes.getvalue()
    
    await update.message.reply_text("✅ رسید دریافت شد.\n💰 مبلغ دریافتی را به ریال وارد کنید:")
    return AMOUNT_RECEIVED

async def amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text.replace(',', '').strip())
        calculated = context.user_data.get('amount_calculated', 0)
        
        context.user_data.update({
            'amount_received': amount,
            'bonus': max(amount - calculated, 0),
            'discount': max(calculated - amount, 0)
        })
        
        await update.message.reply_text("👨‍💼 نام یا نام خانوادگی کارفرما را وارد کنید:")
        return CLIENT_NAME
    except ValueError:
        await update.message.reply_text("⚠️ لطفاً یک عدد معتبر وارد کنید.")
        return AMOUNT_RECEIVED

async def client_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['client_name'] = update.message.text
    await update.message.reply_text("📞 شماره تماس کارفرما را وارد کنید:")
    return CLIENT_PHONE

async def client_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not (phone.startswith("09") and len(phone) == 11 and phone.isdigit()):
        await update.message.reply_text("شماره تماس نامعتبر است. لطفاً شماره را با فرمت 09123456789 وارد کنید.")
        return CLIENT_PHONE
    
    context.user_data['client_phone'] = phone
    await update.message.reply_text("📝 توضیحات سرویس را وارد کنید:")
    return DESCRIPTION

async def description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['description'] = update.message.text
    
    # ذخیره اطلاعات در دیتابیس
    service_data = {
        'user_id': context.user_data['user_id'],
        'start_time': context.user_data['jalali_start'],
        'end_time': context.user_data['jalali_end'],
        'service_type': context.user_data['service_type'],
        'calculated_amount': context.user_data.get('amount_calculated', 0),
        'received_amount': context.user_data.get('amount_received', 0),
        'bonus': context.user_data.get('bonus', 0),
        'discount': context.user_data.get('discount', 0),
        'client_name': context.user_data.get('client_name', ''),
        'client_phone': context.user_data.get('client_phone', ''),
        'description': context.user_data.get('description', '')
    }
    
    save_service(service_data)
    
    await update.message.reply_text(
        f"✅ سرویس با موفقیت ثبت شد!\n"
        f"نوع سرویس: {context.user_data['service_type']}\n"
        f"مدت زمان: {context.user_data.get('duration_minutes', 0)} دقیقه"
    )
    
    await show_main_menu(update, context)
    return ConversationHandler.END

# --- گزارش‌ها ---
async def reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📅 روزانه", callback_data='report_daily')],
        [InlineKeyboardButton("📆 هفتگی", callback_data='report_weekly')],
        [InlineKeyboardButton("🗓️ ماهانه", callback_data='report_monthly')],
        [InlineKeyboardButton("🔍 دلخواه", callback_data='report_custom')]
    ]
    
    await query.edit_message_text(
        "📌 نوع گزارش را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

# --- مدیریت خطاها ---
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    
    if update.message:
        await update.message.reply_text(
            "⚠️ خطایی رخ داد. لطفاً دوباره امتحان کنید یا با پشتیبانی تماس بگیرید."
        )
    else:
        await update.callback_query.edit_message_text(
            "⚠️ خطایی رخ داد. لطفاً دوباره امتحان کنید."
        )

# --- تنظیمات اصلی ربات ---
def main():
    # اطمینان از وجود دیتابیس
    init_db()
    
    # ساخت نمونه ربات
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("لطفاً توکن ربات را در متغیر محیطی TELEGRAM_BOT_TOKEN تنظیم کنید!")
    
    app = ApplicationBuilder().token(token).build()
    
    # مدیریت مکالمه ثبت نام
    registration_conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            FAMILY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_family)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)]
        },
        fallbacks=[]
    )
    
    # مدیریت مکالمه سرویس جدید
    service_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_service, pattern='new_service')],
        states={
            LOCATION_START: [MessageHandler(filters.LOCATION, location_start)],
            CONFIRM_END: [CallbackQueryHandler(confirm_end, pattern='confirm_end')],
            TYPE_SERVICE: [CallbackQueryHandler(type_hourly, pattern='type_hourly')],
            PAYMENT_TYPE: [CallbackQueryHandler(payment_card_reader, pattern='payment_card_reader')],
            PHOTO_UPLOAD: [MessageHandler(filters.PHOTO, photo_upload)],
            AMOUNT_RECEIVED: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount_received)],
            CLIENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, client_name)],
            CLIENT_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, client_phone)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, description)]
        },
        fallbacks=[]
    )
    
    # اضافه کردن هندلرها
    app.add_handler(registration_conv)
    app.add_handler(service_conv)
    app.add_handler(CallbackQueryHandler(reports, pattern='reports'))
    app.add_handler(CallbackQueryHandler(show_main_menu, pattern='cancel_end'))
    app.add_error_handler(error_handler)
    
    # راه‌اندازی ربات
    logger.info("ربات در حال راه‌اندازی...")
    app.run_polling()

if __name__ == '__main__':
    main()