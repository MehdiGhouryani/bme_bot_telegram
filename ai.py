from telegram import Update
from telegram.ext import Application,CommandHandler,filters,MessageHandler,ContextTypes
import google.generativeai as genai
from telegram.constants import ParseMode

genai.configure(api_key="AIzaSyCEVrQ9LA0LM9qMgxKfj8ZzJE2Ktmu7K6I")
model = genai.GenerativeModel("gemini-1.5-flash")

bot_TK = "7715332342:AAFqctg0XVQzxYGHkXNYyXb6U9FlRRjijuA"





async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        replyText = update.message.reply_to_message.text
        try:
            response = model.generate_content(f"""سلام.

سوال زیر مربوط به یک کاربر رشته مهندسی پزشکی است. لطفاً پاسخ را به صورت تخصصی و در عین حال به زبان عامیانه و روان فارسی ارائه دهید و از نوشتن مطالب اضافی خودداری کن.\n\n{replyText}""")
            
            # اطمینان از اینکه response.text یک رشته است
            await update.message.reply_text(str(response.text), parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            error_message = f"خطا در تولید محتوا: {str(e)}"
            await update.message.reply_text(error_message, parse_mode=ParseMode.MARKDOWN)