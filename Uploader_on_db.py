import sqlite3
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, filters , ContextTypes,Application
import io
import logging

load_dotenv()
Token = os.getenv('token')


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s',level=logging.INFO)

user_info = {}


db_name = 'medical_device.db'



async def start(update:Update , context:ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_info[chat_id] = {
        'data' : {},
        'state': 'start'
    }
    await context.bot.send_message(chat_id=chat_id,text='نام دستگاه و بفرس')




async def get_device_name(update:Update , context:ContextTypes.DEFAULT_TYPE):
   
    global device_name
    chat_id = update.effective_chat.id
    device_name = update.message.text

    user_info[chat_id]['state']= 'get_device_name'
    user_info[chat_id]['data']['device_name'] = device_name
    print('name')

    await update.message.reply_text(':   تعریف دستگاه')





async def get_device_definition(update:Update , context:ContextTypes.DEFAULT_TYPE):
   
    global device_definition

    chat_id = update.effective_chat.id
    device_definition = update.message.text

    user_info[chat_id]['state']= 'get_device_definition'
    user_info[chat_id]['data']['device_definition'] = device_definition

    print('definiton')

    await update.message.reply_text(':   انواع دستگاه')



async def get_device_types(update:Update , context:ContextTypes.DEFAULT_TYPE):
    
    global device_types
    chat_id = update.effective_chat.id

    device_types = update.message.text

    user_info[chat_id]['state']= 'get_device_types'
    user_info[chat_id]['data']['device_types'] = device_types

    print('types')
    await update.message.reply_text(' :  ساختار و اجزا')


async def get_device_structure(update:Update , context:ContextTypes.DEFAULT_TYPE):
    
    global device_structure
    chat_id = update.effective_chat.id

    device_structure = update.message.text

    user_info[chat_id]['state']= 'get_device_structure'
    user_info[chat_id]['data']['device_structure'] = device_structure

    print('structure')
    await update.message.reply_text(':   نحوه عملکرد')


async def get_device_operation(update:Update , context:ContextTypes.DEFAULT_TYPE):
    
    global device_operation
    chat_id = update.effective_chat.id

    device_operation = update.message.text

    user_info[chat_id]['state']= 'get_device_operation'
    user_info[chat_id]['data']['device_operation'] = device_operation

    print('opration')
    await update.message.reply_text(':    مزایا و معایب')


async def get_device_advantages_disadvantages(update:Update , context:ContextTypes.DEFAULT_TYPE):
    
    global device_advantages_disadvantages
    chat_id = update.effective_chat.id

    device_advantages_disadvantages = update.message.text

    user_info[chat_id]['state']= 'get_device_advantages_disadvantages'
    user_info[chat_id]['data']['device_advantages_disadvantages'] = device_advantages_disadvantages

    print('advantage')
    await update.message.reply_text(':   نکات ایمنی')


async def get_device_safety(update:Update , context:ContextTypes.DEFAULT_TYPE):
    
    global device_safety
    chat_id = update.effective_chat.id

    device_safety = update.message.text

    user_info[chat_id]['state']= 'get_device_safety'
    user_info[chat_id]['data']['device_safety'] = device_safety

    print('safety')
    await update.message.reply_text(':   تکنولوژی‌های مرتبط')


async def get_device_related_technologies(update:Update , context:ContextTypes.DEFAULT_TYPE):
    
    global device_related_technologies
    chat_id = update.effective_chat.id

    device_related_technologies = update.message.text

    user_info[chat_id]['state']= 'get_device_related_technologies'
    user_info[chat_id]['data']['device_related_technologies'] = device_related_technologies

    print('technologies')
    await update.message.reply_text('عکس دستگاه را ارسال کنید.')



async def get_device_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    print('get_device_photo is Start')
    global device_photo_binary
    photo = update.message.photo[-1]
    photo_file = await context.bot.get_file(photo.file_id)
    
    # ذخیره عکس به صورت باینری در متغیر
    device_photo_binary = io.BytesIO()
    
    # دانلود عکس به صورت باینری
    await photo_file.download_to_memory(device_photo_binary)
    
    device_photo_binary.seek(0)
    # print(f'Type of device_photo_binary: {type(device_photo_binary)}, Size: {device_photo_binary.getbuffer().nbytes} bytes')
    print(device_photo_binary.seek(0))
    # user_info[chat_id]['state']= 'get_device_structure'
    photo_data=device_photo_binary.getvalue()
    print(photo_data)
    user_info[chat_id]['data']['device_photo'] = device_photo_binary

    device_name = user_info[chat_id]['data']['device_name'] 

    await save_to_db(device_name,device_definition, device_types,device_structure,device_operation,device_advantages_disadvantages,device_safety,device_related_technologies,photo_data)

    await update.message.reply_text('اطلاعات دستگاه با موفقیت ذخیره شد!')





async def save_to_db(name,definition,types,structure,operation,advantages_disadvantages,safety,related_technologies,photo_data):
    """ذخیره اطلاعات در پایگاه داده SQLite"""
    print('save to database is connected')
    connection = sqlite3.connect(db_name)
    cursor = connection.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS information (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            definition TEXT,
            types TEXT,
            structure TEXT,
            operation TEXT,
            advantages_disadvantages TEXT,
            safety TEXT,
            related_technologies TEXT,
            photo BLOB
        )
    ''')
    

    cursor.execute('INSERT INTO information(name,definition,types,structure,operation,advantages_disadvantages,safety,related_technologies,photo) VALUES (?,?,?,?,?,?,?,?,?)', (name, definition, types,structure,operation,advantages_disadvantages,safety,related_technologies,photo_data))
    connection.commit()
    connection.close()





async def message_handler(update:Update , context:ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    if chat_id not in user_info:
        await start(update, context)

    elif user_info[chat_id]['state'] == 'start':
        await get_device_name(update, context)

    elif user_info[chat_id]['state'] == 'get_device_name':
        await get_device_definition(update, context)

    elif user_info[chat_id]['state'] == 'get_device_definition':
        await get_device_types(update, context)
    
    elif user_info[chat_id]['state'] == 'get_device_types':
        await get_device_structure(update, context)


    elif user_info[chat_id]['state'] == 'get_device_structure':
        await get_device_operation(update, context)


    elif user_info[chat_id]['state'] == 'get_device_operation':
        await get_device_advantages_disadvantages(update, context)


    elif user_info[chat_id]['state'] == 'get_device_advantages_disadvantages':
        await get_device_safety(update, context)


    elif user_info[chat_id]['state'] == 'get_device_safety':
        await get_device_related_technologies(update, context)


    # elif user_info[chat_id]['state'] == 'get_device_related_technologies':
    #     await get_device_photo(update, context)





async def photo_handler(update:Update , context:ContextTypes.DEFAULT_TYPE):
    print('photo handler is start')
    chat_id = update.effective_chat.id

    if chat_id not in user_info:
        await start(update,context)

    elif user_info[chat_id]['state'] == 'get_device_related_technologies':
        await get_device_photo(update, context)




def main():
    app=Application.builder().token(Token).build()
    app.add_handler(CommandHandler('start', start))
    # app.add_handler(CommandHandler('dawnload', get_photo))
    app.add_handler(MessageHandler(filters.TEXT,message_handler))
    app.add_handler(MessageHandler(filters.PHOTO,photo_handler))
 
    app.run_polling()
    print("running . . .")

main()
