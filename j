from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import os
import pandas as pd
from datetime import datetime
from jdatetime import datetime as jdt
from apscheduler.schedulers.background import BackgroundScheduler
from PIL import Image
import requests
from io import BytesIO

# توکن ربات
TOKEN = '8008850402:AAG9SS8l-MuwJphP1DvcQMWi8-snStav6gc'

# وضعیت‌های سرویس
(NAME, FAMILY, PHONE,
 LOCATION_START, CONFIRM_END,
 TYPE_SERVICE, AMOUNT_MANUAL,
 PAYMENT_TYPE, PHOTO_UPLOAD, AMOUNT_RECEIVED,
 CLIENT_NAME, CLIENT_PHONE, DESCRIPTION,
 EVENT_DESC, EVENT_TIME) = range(14)

# دایرکتوری اصلی
BASE_DIR = 'خدمات'
os.makedirs(BASE_DIR, exist_ok=True)

# فایل‌های اکسل
USERS_FILE = os.path.join(BASE_DIR, 'رانندگان.xlsx')
SERVICES_FILE = os.path.join(BASE_DIR, 'سرویس_ها.xlsx')

# تاریخ شمسی
def jalali_now():
    return jdt.now().strftime("%Y/%m/%d %H:%M")

def gregorian_to_jalali(dt):
    return jdt.fromgregorian(datetime=dt).strftime("%Y/%m/%d %H:%M")

def create_service_folder(user_data):
    name = user_data.get('name', 'کاربر')
    user_id = user_data.get('user_id', 'ناشناس')
    folder_name = f"{name}_{user_id}"
    folder_path = os.path.join(BASE_DIR, folder_name)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path

def save_service_data(data):
    df = pd.DataFrame([data])
    if not os.path.exists(SERVICES_FILE):
        df.to_excel(SERVICES_FILE, index=False)
    else:
        with pd.ExcelWriter(SERVICES_FILE, mode='a', engine='openpyxl', if_sheet_exists='append') as writer:
            df.to_excel(writer, index=False, header=not os.path.exists(SERVICES_FILE))

# دستور /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = {
        'user_id': user.id,
        'name': user.first_name,
        'username': user.username or ''
    }
    context.user_data.update(user_data)

    if os.path.exists(USERS_FILE):
        try:
            df_users = pd.read_excel(USERS_FILE)
            if user.id in df_users.values:
                await show_main_menu(update, context)
                return ConversationHandler.END
        except Exception:
            pass

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
    if not phone.startswith("09") or len(phone) != 11 or not phone.isdigit():
        await update.message.reply_text("شماره تماس نامعتبر است.")
        return PHONE

    context.user_data['phone'] = phone

    data = {
        'کد کاربر': [context.user_data['user_id']],
        'نام': [context.user_data['name']],
        'نام خانوادگی': [context.user_data['family']],
        'شماره تماس': [phone]
    }
    df = pd.DataFrame(data)

    if not os.path.exists(USERS_FILE):
        df.to_excel(USERS_FILE, index=False)
    else:
        with pd.ExcelWriter(USERS_FILE, mode='a', engine='openpyxl', if_sheet_exists='append') as writer:
            df.to_excel(writer, index=False, header=False)

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
    name = context.user_data.get('name', 'کاربر')
    await update.message.reply_text(f"به منوی اصلی خوش آمدید {name} جان!", reply_markup=reply_markup)

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
    await update.message.reply_text("⏰ شروع سرویس ثبت شد.")
    context.user_data['start_time'] = datetime.now()
    context.user_data['jalali_start'] = jalali_now()
    keyboard = [[InlineKeyboardButton("🔚 پایان سرویس", callback_data='end_service')]]
    await update.message.reply_text("برای پایان سرویس دکمه زیر را بزنید.", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def end_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⚠️ مطمئن هستید؟ [بله] [خیر]")
    keyboard = [[InlineKeyboardButton("✅ بله", callback_data='confirm_end'), InlineKeyboardButton("❌ خیر", callback_data='cancel_end')]]
    await query.message.reply_text("آیا مطمئن هستید؟", reply_markup=InlineKeyboardMarkup(keyboard))
    return CONFIRM_END

async def confirm_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['end_time'] = datetime.now()
    context.user_data['jalali_end'] = jalali_now()
    if update.message and update.message.location:
        loc = update.message.location
        context.user_data['location_end'] = (loc.latitude, loc.longitude)
    await query.message.reply_text("نوع سرویس را انتخاب کنید:", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("⏰ ساعتی", callback_data='type_hourly')],
        [InlineKeyboardButton("📦 پروژه‌ای", callback_data='type_project')]
    ]))
    return TYPE_SERVICE

async def type_hourly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    start = context.user_data['start_time']
    end = context.user_data['end_time']
    duration_minutes = (end - start).seconds // 60
    fixed = 3_000_000
    hourly = 12_000_000
    total = fixed + (duration_minutes // 60) * hourly
    context.user_data['service_type'] = "ساعتی"
    context.user_data['amount_calculated'] = total
    context.user_data['duration_minutes'] = duration_minutes
    await query.message.reply_text(f"💰 مبلغ محاسبه‌شده: {total:,} ریال\nنوع پرداخت را انتخاب کنید:")
    await query.message.reply_text("گزینه‌ها:", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 کارتخوان", callback_data='payment_card_reader')],
        [InlineKeyboardButton("🏧 کارت به کارت", callback_data='payment_bank_transfer')],
        [InlineKeyboardButton("💵 نقدی", callback_data='payment_cash')],
        [InlineKeyboardButton("赊 نسیه", callback_data='payment_credit')]
    ]))
    return PAYMENT_TYPE

async def payment_card_reader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['payment_type'] = "کارتخوان"
    await query.message.reply_text("📸 لطفاً تصویر رسید را بارگذاری کنید.")
    return PHOTO_UPLOAD

async def photo_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    user_data = context.user_data
    service_folder = create_service_folder(user_data)
    photo_path = os.path.join(service_folder, f"رسید_{datetime.now().timestamp()}.jpg")
    await file.download_to_drive(photo_path)
    context.user_data['photo_path'] = photo_path
    await update.message.reply_text("✅ رسید دریافت شد.\n💰 مبلغ دریافتی را به ریال وارد کنید:")
    return AMOUNT_RECEIVED

async def amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text.replace(',', '').strip())
        context.user_data['amount_received'] = amount
        diff = amount - context.user_data.get('amount_calculated', 0)
        bonus = diff if diff > 0 else 0
        discount = abs(diff) if diff < 0 else 0
        context.user_data['bonus'] = bonus
        context.user_data['discount'] = discount
        await update.message.reply_text("👨‍💼 نام یا نام خانوادگی کارفرما را وارد کنید:")
        return CLIENT_NAME
    except ValueError:
        await update.message.reply_text("عدد وارد کنید.")
        return AMOUNT_RECEIVED

async def client_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['client_name'] = update.message.text
    await update.message.reply_text("📞 شماره تماس کارفرما را وارد کنید:")
    return CLIENT_PHONE

async def client_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['client_phone'] = update.message.text
    await update.message.reply_text("📝 توضیحات سرویس را وارد کنید:")
    return DESCRIPTION

async def description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['description'] = update.message.text
    data = {
        'کد کاربر': context.user_data['user_id'],
        'زمان شروع': context.user_data['jalali_start'],
        'زمان پایان': context.user_data['jalali_end'],
        'نوع سرویس': context.user_data['service_type'],
        'مبلغ محاسبه‌شده': context.user_data.get('amount_calculated', 0),
        'مبلغ دریافتی': context.user_data.get('amount_received', 0),
        'انعام': context.user_data.get('bonus', 0),
        'تخفیف': context.user_data.get('discount', 0),
        'نام کارفرما': context.user_data.get('client_name', ''),
        'شماره کارفرما': context.user_data.get('client_phone', '')
    }
    save_service_data(data)
    name = context.user_data['name']
    await update.message.reply_text(f"👋 {name} جان، خداقوت!\nورود شما را به ناوگان بین المللی جهان تبریک عرض میکنیم!!!\nنوع سرویس شما: {context.user_data['service_type']}")
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
    await query.message.reply_text("📌 نوع گزارش را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

# --- ثبت دستی سرویس ---
async def manual_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("📅 تاریخ سرویس را به فرمت شمسی وارد کنید (مثال: 1403/08/15):")
    return 100  # DATE_PICK

async def date_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['date_manual'] = update.message.text
    await update.message.reply_text("⏰ ساعت شروع سرویس را وارد کنید (مثال: 09:30):")
    return 101  # TIME_START

async def time_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['time_start'] = update.message.text
    await update.message.reply_text("🔚 ساعت پایان سرویس را وارد کنید (مثال: 11:45):")
    return 102  # TIME_END

async def time_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['time_end'] = update.message.text
    await update.message.reply_text("نوع سرویس را انتخاب کنید:", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("⏰ ساعتی", callback_data='type_hourly_manual')],
        [InlineKeyboardButton("📦 پروژه‌ای", callback_data='type_project_manual')]
    ]))
    return ConversationHandler.END

# --- ثبت رویداد ---
async def event_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("📝 شرح رویداد را وارد کنید:")
    return EVENT_DESC

async def event_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['event_desc'] = update.message.text
    await update.message.reply_text("⏰ زمان یادآوری را وارد کنید (مثال: 14:30):")
    return EVENT_TIME

async def event_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_input = update.message.text.strip()
    now = datetime.now()
    hour, minute = map(int, time_input.split(":"))
    alarm_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    context.user_data['alarm_time'] = alarm_time
    scheduler.add_job(send_event_reminder, 'date', run_date=alarm_time, args=[update, context])
    await update.message.reply_text("✅ یادآوری تنظیم شد.")
    await show_main_menu(update, context)
    return ConversationHandler.END

async def send_event_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = context.job.args[2].user_data.get('event_desc', '')
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"🔔 یادآوری:\n{desc}")

# --- Schedule ---
scheduler = BackgroundScheduler()
scheduler.start()

# --- اجرای ربات ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            FAMILY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_family)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)]
        },
        fallbacks=[]
    )

    new_service_conv = ConversationHandler(
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

    report_handler = CallbackQueryHandler(reports, pattern='reports')
    event_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(event_register, pattern='event_register')],
        states={
            EVENT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, event_desc)],
            EVENT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, event_time)]
        },
        fallbacks=[]
    )

    app.add_handler(conv_handler)
    app.add_handler(new_service_conv)
    app.add_handler(report_handler)
    app.add_handler(event_conversation)

    print("ربات در حال اجرا...")
    app.run_polling()
