import numpy as np
import yfinance as yf
from tradingview_ta import TA_Handler, Interval, Exchange
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import logging
import time
import threading

# Replace with your own Telegram Bot token
TELEGRAM_BOT_TOKEN = '7107415911:AAGWjZlYEkfIHbUS6f9lqe6HEy5ijGcpIBw'
CHAT_ID = '1006163916'  # Replace with your chat ID

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
company_symbols = []  # List of companies to analyze
intervals = [Interval.INTERVAL_15_MINUTES, Interval.INTERVAL_30_MINUTES, Interval.INTERVAL_1_HOUR, Interval.INTERVAL_4_HOURS, Interval.INTERVAL_1_DAY]
bot_active = False
company_entry_allowed = False
analyzing_thread = None

# Function to send a message via the Telegram bot
async def send_telegram_message(context: CallbackContext, chat_id: int, message: str):
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')

# Function to fetch data from TradingView
def fetch_tradingview_data(symbol: str, interval: Interval):
    handler = TA_Handler(
        symbol=symbol,
        screener="america",
        exchange="NASDAQ",  # Adjust for different exchanges as needed
        interval=interval
    )
    analysis = handler.get_analysis()
    return analysis

# Function to fetch data from Yahoo Finance
def fetch_yahoo_data(symbol: str):
    ticker = yf.Ticker(symbol)
    data = ticker.history(period="1d")
    return data

# Function to analyze data and generate signals
def analyze_data(symbol: str):
    messages = []
    for interval in intervals:
        try:
            analysis = fetch_tradingview_data(symbol, interval)
            close_price = analysis.indicators["close"]
            recommendation = analysis.summary["RECOMMENDATION"]
            entry_price = close_price  # Adjust this based on your strategies
            exit_price = entry_price * 1.05  # Example exit price strategy

            if recommendation != "NEUTRAL":
                messages.append(f"<b>{symbol} ({interval})</b>: {recommendation}\nسعر الدخول: {entry_price}\nسعر الخروج: {exit_price}")

        except Exception as e:
            logger.error(f"Error analyzing {symbol} for interval {interval}: {e}")
            messages.append(f"خطأ في تحليل {symbol} للفاصل {interval}: {e}")

    return messages

# Start command handler
async def start(update, context: CallbackContext):
    chat_id = update.effective_chat.id
    welcome_message = """
    مرحبًا بك في روبوت تحليل الأسهم! هنا الأوامر المتاحة:
    - /start_bot : بدء التحليل
    - /stop_bot : إيقاف التحليل
    - /enter_company : إضافة شركة للتحليل
    - /finish_company : إيقاف تحليل شركة معينة
    - /view_report : عرض تقرير الإشارة لجميع الشركات
    """
    await context.bot.send_message(chat_id=chat_id, text=welcome_message, parse_mode='HTML')

# Start the bot command
async def start_bot(update, context: CallbackContext):
    global bot_active, company_entry_allowed, analyzing_thread
    chat_id = update.effective_chat.id

    if not bot_active:
        bot_active = True
        company_entry_allowed = True
        await send_telegram_message(context, chat_id, "تم بدء الروبوت. يمكنك الآن إدخال رموز الشركات للتحليل.")
        analyzing_thread = threading.Thread(target=start_analysis, args=(chat_id, context), daemon=True)
        analyzing_thread.start()

# Stop the bot command
async def stop_bot(update, context: CallbackContext):
    global bot_active, company_entry_allowed
    chat_id = update.effective_chat.id

    if bot_active:
        bot_active = False
        company_entry_allowed = False
        await send_telegram_message(context, chat_id, "تم إيقاف الروبوت. توقف التحليل.")

# Enter a company command
async def enter_company(update, context: CallbackContext):
    global bot_active, company_entry_allowed
    chat_id = update.effective_chat.id

    if bot_active:
        company_entry_allowed = True
        await context.bot.send_message(chat_id=chat_id, text="يرجى إرسال رمز الشركة للتحليل.")
    else:
        await context.bot.send_message(chat_id=chat_id, text="الروبوت غير نشط. يرجى بدء الروبوت أولاً.")

# Finish company command
async def finish_company(update, context: CallbackContext):
    global bot_active
    chat_id = update.effective_chat.id

    if bot_active:
        await context.bot.send_message(chat_id=chat_id, text="يرجى إرسال اسم الشركة التي ترغب في إيقاف تحليلها.")
    else:
        await context.bot.send_message(chat_id=chat_id, text="الروبوت غير نشط. يرجى بدء الروبوت أولاً.")

# View report command
async def view_report(update, context: CallbackContext):
    chat_id = update.effective_chat.id

    if not company_symbols:
        await send_telegram_message(context, chat_id, "لم يتم إدخال أي شركات. يرجى إدخال رمز الشركة أولاً.")
        return

    for symbol in company_symbols:
        signals = analyze_data(symbol)
        if signals:
            for signal in signals:
                await send_telegram_message(context, chat_id, signal)
        else:
            await send_telegram_message(context, chat_id, f"لا توجد إشارات لـ {symbol}. يتم مواصلة التحليل.")

# Handle text messages (used to add or stop analyzing a company)
async def handle_message(update, context: CallbackContext):
    global company_entry_allowed

    if bot_active:
        if company_entry_allowed:
            company_symbols.append(update.message.text.upper())
            await update.message.reply_text(f"تمت إضافة {update.message.text.upper()} إلى قائمة التحليل.")
        else:
            await update.message.reply_text("يرجى استخدام /enter_company قبل إدخال رمز الشركة.")
    else:
        await update.message.reply_text("الروبوت غير نشط. يرجى استخدام /start_bot أولاً.")

# Start the analysis process
def start_analysis(chat_id: int, context: CallbackContext):
    while bot_active:
        if company_symbols:
            for symbol in company_symbols:
                signals = analyze_data(symbol)
                if signals:
                    for signal in signals:
                        context.application.create_task(send_telegram_message(context, chat_id, signal))
                else:
                    context.application.create_task(send_telegram_message(context, chat_id, f"لا توجد إشارات لـ {symbol}. يتم مواصلة التحليل."))
        else:
            context.application.create_task(send_telegram_message(context, chat_id, "لم يتم إدخال أي شركات للتحليل."))
        time.sleep(3600)  # Wait for an hour before the next check

def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('start_bot', start_bot))
    application.add_handler(CommandHandler('stop_bot', stop_bot))
    application.add_handler(CommandHandler('enter_company', enter_company))
    application.add_handler(CommandHandler('finish_company', finish_company))
    application.add_handler(CommandHandler('view_report', view_report))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()
