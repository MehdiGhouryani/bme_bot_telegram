
import os
from telegram import Update
from telegram.ext import ContextTypes



class get_photo:
   
    async def dawnload_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
        photo = update.message.photo[-1]

        photo_file = await context.bot.get_file(photo)

        photo_path = os.path.join('images', photo_file.file_unique_id + '.jpg')
 

        if not os.path.exists('images'):
            os.makedirs('images')

        with open(photo_path, 'wb') as f:
            await photo_file.download_to_memory(f)

        await context.bot.send_message(chat_id=update.effective_chat.id, text='عکس ذخیره شد .')

        return photo_path
