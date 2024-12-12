from telegram import Update
from telegram.ext import Application,CommandHandler,filters,MessageHandler,ContextTypes
import google.generativeai as genai
from telegram.constants import ParseMode

genai.configure(api_key="AIzaSyCEVrQ9LA0LM9qMgxKfj8ZzJE2Ktmu7K6I")
model = genai.GenerativeModel("gemini-1.5-flash")

bot_TK = "7715332342:AAFqctg0XVQzxYGHkXNYyXb6U9FlRRjijuA"


async def ai_command(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        replyText =update.message.reply_to_message.text
        response = model.generate_content(f"""سلام.
میخام سوال زیر رو به شکل تخصصی پاسخ بدی
مربوط به رشته مهندسی پزشکی است.
دقت کن جواب را فقط مربوط به این سوال زیر بدی و مطلب اضافی ننویسی
در اخر پاسخ را به زبان عامیانه فارسی و روان و قابل فهم ارسال کن\n\n{replyText}""")

        await update.message.reply_text(response.text,parse_mode=ParseMode.MARKDOWN)


def main():
    app = Application.builder().token(bot_TK).build()
    app.add_handler(CommandHandler("ai",ai_command))
    
    app.run_polling()

if __name__ == '__main__':
    main()