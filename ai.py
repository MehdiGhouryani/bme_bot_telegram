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

سوال زیر مربوط به یک کاربر رشته مهندسی پزشکی است. لطفاً پاسخ را به صورت تخصصی و در عین حال به زبان عامیانه و روان فارسی ارائه دهید و از نوشتن مطالب اضافی خودداری کن .\n\n{replyText}""")

        await update.message.reply_text(response.text,parse_mode=ParseMode.MARKDOWN)


def main():
    app = Application.builder().token(bot_TK).build()
    app.add_handler(CommandHandler("ai",ai_command))
    
    app.run_polling()

if __name__ == '__main__':
    main()