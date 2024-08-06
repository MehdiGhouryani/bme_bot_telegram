import sqlite3
import os
from dotenv import load_dotenv
from keyboards_medical import KeyboardsManager
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes , MessageHandler,filters, CallbackQueryHandler
from telegram import KeyboardButton,ReplyKeyboardMarkup ,InlineKeyboardMarkup
from callback_map import *
import logging
# from telegraph import Telegraph


load_dotenv()
token=os.getenv('Token')
db_name="medical_device.db"


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s',level=logging.INFO)







async def start(update:Update , context:ContextTypes.DEFAULT_TYPE):
    # chat_id = update.effective_chat.id  
    user_id =update.message.from_user.id
    username =update.effective_user.username

    print(f'USER : {username}    ID : {user_id}')
    await save_user(user_id,username)
    CHANNEL_USERNAME ='@studentsbme'
    try:
        member =await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME,user_id=user_id)
        print(f"user {user_id} status in {CHANNEL_USERNAME} : {member.status}")
        if member.status not in ['member','administrator','creator']:

            keyboard= [
                [InlineKeyboardButton('عضویت در کانال',url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
                [InlineKeyboardButton("عضو شدم ✅",callback_data='check_membership')]
            ]
            reply_markup=InlineKeyboardMarkup(keyboard)
            await update.message.reply_text('برای استفاده از ربات باید عضو کانال باشی',reply_markup=reply_markup)
        else:
            keyboard = [
                [KeyboardButton("تجهیزات پزشکی  🩺"),]
                ,[KeyboardButton("سنسور ها و قطعات")]
                ,[KeyboardButton("درخواست و پیشنهاد 📝")]
            
            # ,KeyboardButton("فرصت های شغلی 👨‍⚕")]
            ]
    
            reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True) 
            await update.message.reply_text(f"  لطفا یکی از گزینه‌ها را انتخاب کنید :",reply_markup=reply_markup) 
            

    except Exception as e:
        print(f"Error cheking membership : {e}")
        await update.message.reply_text(' مشکلی بوجود اومده ! دوباره تلاش کن')
   


async def save_user(user_id,username):
    connection = sqlite3.connect('users.db')
    cursor = connection.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                      (user_id INTEGER PRIMARY KEY,
                       username TEXT)''')
    
    cursor.execute('INSERT OR REPLACE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    connection.commit()
    connection.close()



async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    CHANNEL_USERNAME = '@studentsbme'

    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            # Send a confirmation message to the user
            await query.answer("عضویت شما تایید شد.")
            await query.delete_message()
            keyboard = [
            [KeyboardButton("درخواست و پیشنهاد 📝"),KeyboardButton("تجهیزات پزشکی  🩺"),]
            ]
    
            reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True) 
            await context.bot.send_message(f"  لطفا یکی از گزینه‌ها را انتخاب کنید :",reply_markup=reply_markup) 

        else:
            await query.answer("شما هنوز عضو کانال نشده‌اید.")
            
    except Exception as e:
        print(f"Error checking membership: {e}")
        await query.answer("خطا در بررسی عضویت.")







pages = {
    "Temperature_Sensor": "https://telegra.ph/سنسور-دما---Temperature-Sensor-08-06-3",
    "Pressure_Sensor": "https://telegra.ph/سنسور-فشار---Pressure-Sensor-08-06-2",
    "HeartRate_Sensor": "https://telegra.ph/سنسور-ضربان-قلب---Heart-Rate-Sensor-08-06-2",
    "Oxygen_Sensor": "https://telegra.ph/سنسور-اکسیژن---Oxygen-Sensor-08-06",
    "Motion_Sensor":"https://telegra.ph/سنسور-حرکتی---Motion-Sensor-08-06",
    "ECG_Sensor":"https://telegra.ph/سنسور-نوار-قلب---ECG-Sensor-08-06",
    "Humidity":"https://telegra.ph/سنسور-دما-و-رطوبت---Temperature-and-Humidity-Sensor-08-06",
    "Level_Sensor":"https://telegra.ph/سنسور-سطح---Level-Sensor-08-06",
    "Gas_Sensor":"https://telegra.ph/سنسور-گاز---Gas-Sensor-08-06",
    "Optical_Sensor":"https://telegra.ph/سنسور-نوری---Optical-Sensor-08-06",   
    }


async def Button_click(update:Update , context:ContextTypes.DEFAULT_TYPE) :
    text= update.message.text   
    user =update.message.from_user
    user_message =update.message.text
    username=user.username
    user_id=user.id
    full_name =user.full_name
    chat_id=update.effective_message.id
    message_id=update.message.message_id
    ADMIN_CHAT_ID='1717599240'
 
    if text == "تجهیزات پزشکی  🩺":

        reply_markup = InlineKeyboardMarkup(main_keyboard)
        await update.message.reply_text(text='یک گزینه را انتخاب کنید : ', reply_markup= reply_markup)


    elif text == "درخواست و پیشنهاد 📝":
        
        context.user_data['awaiting_request'] = True
        await update.message.reply_text('''
سلام مهندس🙂
 خوشحال می‌شیم پیشنهادات و ایده‌های خودت رو درباره ربات با ما به اشتراک بذارید.

لطفاً پیشنهادات خودتون رو همین‌جا بنویسید و ارسال کنید :

''')
    elif context.user_data.get('awaiting_request'):
        # ارسال پیام به ادمین
        admin_message = (
            f"پیشنهاد جدید از سمت {full_name} دریافت شد!\n"
            f"نام کاربری: @{username}\n"
            f"آیدی کاربر: {user_id}\n"
            f"متن پیشنهاد: {user_message}"
        )
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_message)

        # ارسال پیام تایید به کاربر
        await update.message.reply_text('ممنون از پیشنهادتون! ما اون رو بررسی خواهیم کرد.')

        # غیرفعال کردن حالت انتظار
        context.user_data['awaiting_request'] = False

    elif text == "سنسور ها و قطعات":
        buttons=[
            [KeyboardButton("سنسورها"),KeyboardButton("قطعات الکترونیکی")]
        ]
        
        reply_markup=ReplyKeyboardMarkup(buttons,resize_keyboard=True) 
        await context.bot.edit_message_reply_markup(chat_id=chat_id,message_id=message_id,reply_markup=reply_markup)
    
    elif text == "سنسور ها":

        buttons = [
        [InlineKeyboardButton("سنسور دما", url=pages["Temperature_Sensor"])],
        [InlineKeyboardButton("سنسور فشار", url=pages["Pressure_Sensor"])],
        [InlineKeyboardButton("سنسور ضربان قلب", url=pages["HeartRate_Sensor"])],
        [InlineKeyboardButton("سنسور اکسیژن", url=pages["Oxygen_Sensor"])],
        [InlineKeyboardButton("سنسور حرکتی", url=pages["Motion_Sensor"])],
        [InlineKeyboardButton("سنسور نوار قلب", url=pages["ECG_Sensor"])],
        [InlineKeyboardButton("سنسور دما و رطوبت", url=pages["Humidity"])],
        [InlineKeyboardButton("سنسور سطح", url=pages["Level_Sensor"])],  
        [InlineKeyboardButton("سنسور گاز", url=pages["Gas_Sensor"])],
        [InlineKeyboardButton("سنسور نوری", url=pages["Optical_Sensor"])],
        ]

        reply_markup = InlineKeyboardMarkup(buttons)

        # ارسال پیام
        context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)


    # elif text == "قطعات الکترونیکی":
    #     buttons = [
    #     [InlineKeyboardButton("", url=pages[""])],


    #     ]


    elif text =='تعداد کاربران فعال':

        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        await update.message.reply_text(f'تعداد کاربران ربات تا به این لحظه : {count} نفر')
        conn.close()



#     if text == 'سنسور ها و قطعات':
#         await send_event(update,context)   
    
    # elif text == "فرصت های شغلی 👨‍⚕":
    #     await send_job(update)









class_callback_map = callback_map()
callback_map_diagnostic = class_callback_map.callback_map_diagnostic()
callback_map_therapeutic = class_callback_map.callback_map_therapeutic()
callback_map_monitoring = class_callback_map.callback_map_monitoring()

combined_callback_map = {}
combined_callback_map.update(callback_map_diagnostic)
combined_callback_map.update(callback_map_therapeutic)
combined_callback_map.update(callback_map_monitoring)



keyboards_manager = KeyboardsManager()

# دسته‌بندی‌های اصلی
main_keyboard = keyboards_manager.get_keyboard_main_categories()

# دسته‌بندی‌های مختلف
categories = {
    'diagnostic': [
        'diagnostic', 'imaging_devices', 'laboratory_devices',
        'cardiac_devices', 'neurological_devices',
        'pulmonary_devices', 'gastrointestinal_devices',
        'ent_diagnostic_devices', 'ophthalmic_diagnostic_devices'
    ],
    'therapeutic': [
        'therapeutic', 'surgical', 'orthopedic_therapeutic_equipment', 'cardiovascular_therapeutic_equipment',
        'respiratory', 'other_therapeutic'
    ],
    'monitoring': [
        'monitoring','cardiac_monitors',
        'fetal_maternal_monitors', 'fetal_monitors',
        'blood_glucose_monitors'
    ],
    'general_medical': [
        'general_medical', 'hospital_equipment', 'hospital_beds', 'sterilizers',
        'medical_trolleys', 'emergency_equipment'
    ],
    'rehabilitation_and_support': [
        'rehabilitation_and_support', 'rehabilitation', 'patient_support_equipment'
    ],
    'specialized_equipment': [
        'specialized_equipment', 'cardiovascular_equipment', 'neurology_equipment',
        'orthopedic_equipment', 'obstetrics_and_gynecology_equipment',
        'ent_equipment', 'dental_equipment', 'dermatology_equipment'
    ],
    'home_care_equipment': [
        'home_care_equipment', 'daily_care_equipment', 'home_respiratory_equipment'
    ]
}

# ایجاد کیبوردها برای هر دسته‌بندی
for category, subcategories in categories.items():
    for subcategory in subcategories:
        globals()[f"keyboard_{subcategory}"] = getattr(keyboards_manager, f"get_keyboard_{subcategory}")()
        




# دیکشنری برای کیبوردها
keyboard_map = {
    'diagnostic_equipment': keyboard_diagnostic,
    'therapeutic_equipment': keyboard_therapeutic,
    'monitoring_equipment': keyboard_monitoring,
    'general_medical_equipment': keyboard_general_medical,
    'support_rehabilitation_equipment': keyboard_rehabilitation_and_support,
    'specialized_equipment': keyboard_specialized_equipment,
    'home_care_equipment': keyboard_home_care_equipment,

    'imaging_devices': keyboard_imaging_devices,
    'laboratory_devices': keyboard_laboratory_devices,
    'cardiac_devices': keyboard_cardiac_devices,
    'neurological_devices': keyboard_neurological_devices,
    'pulmonary_devices': keyboard_pulmonary_devices,
    'gastrointestinal_devices': keyboard_gastrointestinal_devices,
    'ent_diagnostic_devices': keyboard_ent_diagnostic_devices,
    'ophthalmic_diagnostic_devices': keyboard_ophthalmic_diagnostic_devices,
    'surgical_equipment': keyboard_surgical,
    'orthopedic_therapeutic_equipment': keyboard_orthopedic_therapeutic_equipment,
    'cardiovascular_therapeutic_equipment': keyboard_cardiovascular_therapeutic_equipment,
    'respiratory_equipment': keyboard_respiratory,
    'other_therapeutic_equipment': keyboard_other_therapeutic,
    'vital_signs_monitors': keyboard_cardiac_monitors,
    'cardiac_monitors': keyboard_cardiac_monitors,
   
    'fetal_maternal_monitors': keyboard_fetal_maternal_monitors,
    'fetal_monitors': keyboard_fetal_monitors,
    'blood_glucose_monitors': keyboard_blood_glucose_monitors,
    
    'hospital_equipment': keyboard_hospital_equipment,
    'emergency_equipment': keyboard_emergency_equipment,
    'rehabilitation_equipment': keyboard_rehabilitation,
    'patient_support': keyboard_patient_support_equipment,
    'cardiovascular_equipment': keyboard_cardiovascular_equipment,
    'neurology_equipment': keyboard_neurology_equipment,
    'orthopedic_equipment': keyboard_orthopedic_equipment,
    'obstetrics_and_gynecology_equipment': keyboard_obstetrics_and_gynecology_equipment,
    'ent_equipment': keyboard_ent_equipment,
    'dental_equipment': keyboard_dental_equipment,
    'dermatology_equipment': keyboard_dermatology_equipment,
    'daily_care_equipment': keyboard_daily_care_equipment,
    'home_respiratory_equipment': keyboard_home_respiratory_equipment,
}











async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # user_id = update.message.from_user.id
    query = update.callback_query
    data = query.data
    chat_id = update.effective_chat.id

    connection = sqlite3.connect(db_name)
    cursor = connection.cursor()
    
    if data in combined_callback_map:
      await combined_callback_map[data](data,update, context)

    elif data in keyboard_map:
        reply_markup = InlineKeyboardMarkup(keyboard_map[data])
        await query.edit_message_reply_markup(reply_markup=reply_markup)



    elif ':' in data:
        device, action = data.split(':')
        keyboard_menu =([
            [InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types'), InlineKeyboardButton('معرفی دستگاه', callback_data=f'{device}:definition')],
            [InlineKeyboardButton('ساختار و اجزاء دستگاه', callback_data=f'{device}:structure')],
            [InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation'),InlineKeyboardButton(' تکنولوژی‌های مشابه', callback_data=f'{device}:related_technologies')],
            [InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'), InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data=category)],
        ])
        reply_markup_menu =InlineKeyboardMarkup(keyboard_menu)

        
        keyboard_definition =([
            [InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types')],
            [InlineKeyboardButton('ساختار و اجزاء دستگاه', callback_data=f'{device}:structure')],
            [InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation'),InlineKeyboardButton(' تکنولوژی‌های مشابه', callback_data=f'{device}:related_technologies')],
            [InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'), InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data=category)],
        ])
        reply_markup_definition =InlineKeyboardMarkup(keyboard_definition)


        


        if action == 'definition':
            cursor.execute(f"SELECT definition FROM information WHERE name = '{device}'")
            device_info = cursor.fetchone()[0]

            cursor.execute(f"SELECT photo FROM information WHERE name = '{device}'")
            device_photo = cursor.fetchone()[0]
            
            await query.delete_message()
            await context.bot.send_photo(chat_id=chat_id,caption=device_info,photo=device_photo,parse_mode='Markdown',reply_markup=reply_markup_definition)
        else:
            print('----------')

        
        if action == 'types':
            cursor.execute(f"SELECT types FROM information WHERE name = '{device}'")
            device_info = cursor.fetchone()[0]
            try:
                await query.edit_message_text(text = device_info,parse_mode='Markdown',reply_markup=reply_markup_menu)
            except:    
                await query.delete_message()
                await context.bot.send_message(chat_id=chat_id,text = device_info,parse_mode='Markdown',reply_markup=reply_markup_menu)

        elif action == 'structure':
            cursor.execute(f"SELECT structure FROM information WHERE name = '{device}'")
            device_info = cursor.fetchone()[0]
            try:
                await query.edit_message_text(text = device_info,parse_mode='Markdown',reply_markup=reply_markup_menu)
            except:    
                await query.delete_message()
                await context.bot.send_message(chat_id=chat_id,text = device_info,parse_mode='Markdown',reply_markup=reply_markup_menu)

        elif action == 'operation':
            cursor.execute(f"SELECT operation FROM information WHERE name = '{device}'")
            device_info = cursor.fetchone()[0]
            try:
                await query.edit_message_text(text = device_info,parse_mode='Markdown',reply_markup=reply_markup_menu)
            except:    
                await query.delete_message()
                await context.bot.send_message(chat_id=chat_id,text = device_info,parse_mode='Markdown',reply_markup=reply_markup_menu)

        elif action == 'advantages_disadvantages':
            cursor.execute(f"SELECT advantages_disadvantages FROM information WHERE name = '{device}'")
            device_info = cursor.fetchone()[0]
            try:
                await query.edit_message_text(text = device_info,parse_mode='Markdown',reply_markup=reply_markup_menu)
            except:    
                await query.delete_message()
                await context.bot.send_message(chat_id=chat_id,text = device_info,parse_mode='Markdown',reply_markup=reply_markup_menu)

        elif action == 'safety':
            cursor.execute(f"SELECT safety FROM information WHERE name = '{device}'")
            device_info = cursor.fetchone()[0]
            try:
                await query.edit_message_text(text = device_info,parse_mode='Markdown',reply_markup=reply_markup_menu)
            except:    
                await query.delete_message()
                await context.bot.send_message(chat_id=chat_id,text = device_info,parse_mode='Markdown',reply_markup=reply_markup_menu)

        elif action == 'related_technologies':
            cursor.execute(f"SELECT related_technologies FROM information WHERE name = '{device}'")
            device_info = cursor.fetchone()[0]
            try:
                await query.edit_message_text(text = device_info,parse_mode='Markdown',reply_markup=reply_markup_menu)
            except:    
                await query.delete_message()
                await context.bot.send_message(chat_id=chat_id,text = device_info,parse_mode='Markdown',reply_markup=reply_markup_menu)

        cursor.close()

        
 
    elif data == 'back_to_main':
        reply_markup = InlineKeyboardMarkup(main_keyboard)
        await query.edit_message_reply_markup(reply_markup=reply_markup)
    
    elif data == 'check_membership':
        await check_membership(update,context)
    else:
        await query.answer("مثل اینکه این بخش اماده نشده هنوز  ")








def main():
    app = Application.builder().token(token).build()

    start_handler = CommandHandler("start",start)
    Buttun_handler =MessageHandler(filters.TEXT & ~filters.COMMAND ,Button_click)

    app.add_handler(start_handler)
    app.add_handler(Buttun_handler)
    app.add_handler(CallbackQueryHandler(callback_handler))

    app.run_polling()

if __name__=="__main__":
    main()
