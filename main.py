import sqlite3
import os
from dotenv import load_dotenv
from func_db import *
from keyboards_medical import KeyboardsManager
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes , MessageHandler,filters, CallbackQueryHandler
from telegram import KeyboardButton,ReplyKeyboardMarkup ,InlineKeyboardMarkup
from equipments import *
from callback_map import callback_map
import logging


load_dotenv()
token=os.getenv('Token')


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
        'diagnostic', 'medical_imaging', 'laboratory_equipment',
        'cardiac_diagnostic_equipment', 'neurological_diagnostic_equipment',
        'pulmonary_diagnostic_equipment', 'gastrointestinal_diagnostic_equipment',
        'ent_diagnostic_equipment', 'ophthalmic_diagnostic_equipment'
    ],
    'therapeutic': [
        'therapeutic', 'surgical', 'orthopedic', 'cardiovascular',
        'respiratory', 'other_therapeutic'
    ],
    'monitoring': [
        'monitoring', 'vital_signs_monitors', 'cardiac_monitors',
        'pulse_oximeters', 'fetal_maternal_monitors', 'fetal_monitors',
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
        









db_name="medical_device.db"





logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s',level=logging.INFO)

async def start(update:Update , context:ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id  
    user_id =update.message.from_user.id
    print('start')
    CHANNEL_USERNAME ='@studentsbme'
    try:
        member =await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME,user_id=user_id)
        print(f"user {user_id} status in {CHANNEL_USERNAME} : {member.status}")
        if member.status not in ['member','administrator','creator']:

            keyboard= [
                [InlineKeyboardButton('عضویت در کانال',url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
                [[InlineKeyboardButton("عضو شدم ✅",callback_data='check_membership')]]
            ]
            reply_markup=InlineKeyboardMarkup(keyboard)
            await update.message.reply_text('برای استفاده از ربات باید عضو کانال باشی',reply_markup=reply_markup)
        else:
            keyboard = [
            [KeyboardButton("درخواست و پیشنهاد 📝"),KeyboardButton("آموزش 📚"),]
            # ,[KeyboardButton("رویداد ها 🗓"),KeyboardButton("فرصت های شغلی 👨‍⚕")]
            ]
    
            reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True) 
            await update.message.reply_text(f"  لطفا یکی از گزینه‌ها را انتخاب کنید :",reply_markup=reply_markup) 


    except Exception as e:
        print(f"Error cheking membership : {e}")
        await update.message.reply_text('مشکلی بوجود اومده ! دوباره تلاش کن')
   



async def handle_chat_member_update(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.chat_member.new_chat_member.status =='left':
        chat_id =update.effective_chat.id
        user_id =update.chat_member.new_chat_member.user.id
        async for message in context.bot.get_chat_administrators(chat_id):
            if message.from_user.id == user_id:
                await context.bot.delete_message(chat_id=chat_id,message_id=message.message_id)


async def Button_click(update:Update , context:ContextTypes.DEFAULT_TYPE) :
    text= update.message.text   
#     if text == 'رویداد ها 🗓':
#         await send_event(update,context)   
    
    if text == "آموزش 📚":
        await send_tutorials(update,context)

    
    elif text == "درخواست و پیشنهاد 📝":
        await send_request(update,context)

    # elif text == "فرصت های شغلی 👨‍⚕":
    #     await send_job(update)









async def callback_handler(update: Update , context:ContextTypes.DEFAULT_TYPE) :
    user_id =update.message.from_user.id
    chat_id=update.effective_chat.id

    query = update.callback_query
    data = query.data
  
    CHANNEL_USERNAME ='@studentsbme'
    print('callback_handler is  started')

    try:
        member =await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME,user_id=user_id)
        print(f"user(use in callback_data) {user_id} status in {CHANNEL_USERNAME} : {member.status}")
        if member.status not in ['member','administrator','creator']:
            await start(update,context)
        else:

            if data in combined_callback_map:
                await combined_callback_map[data](data,update, context)

            elif ':' in data:
            
                device,action =data.split(':')

                connection = sqlite3.connect(db_name)
                cursor = connection.cursor()


                if action == 'definition':
                    cursor.execute(f"SELECT definition FROM information WHERE name = '{device}'")
                    device_info = cursor.fetchone()[0]

                    cursor.execute(f"SELECT photo FROM information WHERE name = '{device}'")
                    device_photo = cursor.fetchone()[0]

                    await query.delete_message()
                    await context.bot.send_photo(chat_id=chat_id,caption=device_info,photo=device_photo,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('بازگشت  ',callback_data=f'{device}')]]))
                else :
                    print(" button not is definition")

                if action == 'types':
                    cursor.execute(f"SELECT types FROM information WHERE name = '{device}'")
                    device_info = cursor.fetchone()[0]
                elif action == 'structure':
                    cursor.execute(f"SELECT structure FROM information WHERE name = '{device}'")
                    device_info = cursor.fetchone()[0]
                elif action == 'operation':
                    cursor.execute(f"SELECT operation FROM information WHERE name = '{device}'")
                    device_info = cursor.fetchone()[0]
                elif action == 'advantages_disadvantages':
                    cursor.execute(f"SELECT advantages_disadvantages FROM information WHERE name = '{device}'")
                    device_info = cursor.fetchone()[0]
                elif action == 'safety':
                    cursor.execute(f"SELECT safety FROM information WHERE name = '{device}'")
                    device_info = cursor.fetchone()[0]
                elif action == 'related_technologies':
                    cursor.execute(f"SELECT related_technologies FROM information WHERE name = '{device}'")
                    device_info = cursor.fetchone()[0]
                await query.delete_message()
                await context.bot.send_message(chat_id=chat_id,text = device_info,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('بازگشت  ',callback_data=f'{device}')]]))



            elif data == 'back_to_main':
                reply_markup = InlineKeyboardMarkup(main_keyboard)
                await query.edit_message_reply_markup(reply_markup=reply_markup)






        # main_categories

            elif data in {'diagnostic_equipment' }:

                reply_markup = InlineKeyboardMarkup(keyboard_diagnostic)
                await query.edit_message_reply_markup(reply_markup=reply_markup)



            elif data in {'therapeutic_equipment'} :

                reply_markup = InlineKeyboardMarkup(keyboard_therapeutic)
                await query.edit_message_reply_markup(reply_markup=reply_markup)



            elif data in {'monitoring_equipment'}:
            
                reply_markup = InlineKeyboardMarkup(keyboard_monitoring)
                await query.edit_message_reply_markup(reply_markup=reply_markup)



            elif data in {'general_medical_equipment'}:
            
                reply_markup = InlineKeyboardMarkup(keyboard_general_medical)
                await query.edit_message_reply_markup(reply_markup=reply_markup)



            elif data in {'support_rehabilitation_equipment'}:
            
                reply_markup = InlineKeyboardMarkup(keyboard_rehabilitation_and_support)
                await query.edit_message_reply_markup(reply_markup=reply_markup)



            elif data in {'specialized_equipment'}:
            
                reply_markup = InlineKeyboardMarkup(keyboard_specialized_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)



            elif data in {'home_care_equipment'}:
            
                reply_markup = InlineKeyboardMarkup(keyboard_home_care_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)









        # diagnostic


            elif data == 'medical_imaging':
            
                reply_markup = InlineKeyboardMarkup(keyboard_medical_imaging)
                await query.edit_message_reply_markup(reply_markup=reply_markup)




            elif data == 'laboratory_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_laboratory_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)


            elif data == 'cardiac_diagnostic_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_cardiac_diagnostic_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)



            elif data == 'neurological_diagnostic_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_neurological_diagnostic_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)



            elif data == 'pulmonary_diagnostic_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_pulmonary_diagnostic_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)




            elif data == 'gastrointestinal_diagnostic_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_gastrointestinal_diagnostic_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)




            elif data == 'ent_diagnostic_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_ent_diagnostic_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)




            elif data == 'ophthalmic_diagnostic_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_ophthalmic_diagnostic_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)












        # therapeutic

            elif data == 'surgical_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_surgical)
                await query.edit_message_reply_markup(reply_markup=reply_markup)




            elif data == 'orthopedic_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_orthopedic)
                await query.edit_message_reply_markup(reply_markup=reply_markup)




            elif data == 'cardiovascular_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_cardiovascular)
                await query.edit_message_reply_markup(reply_markup=reply_markup)




            elif data == 'respiratory_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_respiratory)
                await query.edit_message_reply_markup(reply_markup=reply_markup)



            elif data == 'other_therapeutic_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_other_therapeutic)
                await query.edit_message_reply_markup(reply_markup=reply_markup)












        # monitoring

            elif data == 'vital_signs_monitors':
            
                reply_markup = InlineKeyboardMarkup(keyboard_vital_signs_monitors)
                await query.edit_message_reply_markup(reply_markup=reply_markup)


            elif data == 'cardiac_monitors':
                reply_markup = InlineKeyboardMarkup(keyboard_cardiac_monitors)
                await query.edit_message_reply_markup(reply_markup=reply_markup)

            elif data == 'pulse_oximeters':
                reply_markup = InlineKeyboardMarkup(keyboard_pulse_oximeters)
                await query.edit_message_reply_markup(reply_markup=reply_markup)





            elif data == 'fetal_maternal_monitors':
            
                reply_markup = InlineKeyboardMarkup(keyboard_fetal_maternal_monitors)
                await query.edit_message_reply_markup(reply_markup=reply_markup)

            elif data == 'fetal_monitors':
                reply_markup = InlineKeyboardMarkup(keyboard_fetal_monitors)
                await query.edit_message_reply_markup(reply_markup=reply_markup)


            elif data == 'blood_glucose_monitors':
            
                reply_markup = InlineKeyboardMarkup(keyboard_blood_glucose_monitors)
                await query.edit_message_reply_markup(reply_markup=reply_markup)











        # general


            elif data == 'hospital_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_hospital_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)




            elif data == 'emergency_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_emergency_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)












        # rehabilitation

            elif data == 'rehabilitation_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_rehabilitation)
                await query.edit_message_reply_markup(reply_markup=reply_markup)




            elif data == 'patient_support':
            
                reply_markup = InlineKeyboardMarkup(keyboard_patient_support)
                await query.edit_message_reply_markup(reply_markup=reply_markup)












        # specialized

            elif data == 'cardiovascular_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_cardiovascular_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)




            elif data == 'neurology_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_neurology_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)



            elif data == 'orthopedic_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_orthopedic_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)




            elif data == 'obstetrics_and_gynecology_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_obstetrics_and_gynecology_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)




            elif data == 'ent_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_ent_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)




            elif data == 'dental_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_dental_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)




            elif data == 'dermatology_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_dermatology_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)













        # home_care


            elif data == 'daily_care_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_daily_care_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)




            elif data == 'home_respiratory_equipment':
            
                reply_markup = InlineKeyboardMarkup(keyboard_home_respiratory_equipment)
                await query.edit_message_reply_markup(reply_markup=reply_markup)





    except Exception as e:
        print(f"Error cheking membership : {e}")
        await update.message.reply_text('مشکلی بوجود اومده ! دوباره تلاش کن')
   



   




























async def send_tutorials(update: Update, context: ContextTypes.DEFAULT_TYPE):
   
    reply_markup = InlineKeyboardMarkup(main_keyboard)
   
    await update.message.reply_text(text='یک گزینه را انتخاب کنید : ', reply_markup= reply_markup)
    



async def send_request(update:Update , context : ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,text="درخواستی که داری رو بگو :",reply_to_message_id=update.effective_message.id)

    if len(update.message.text)>12 :
        user_id = update.message.from_user.id
        user_request = update.message.text
        #Forwarad to admin

        await context.bot.send_message(chat_id='1717599240',text=f"new request from user {user_id}:{user_request}")




# def send_job(update:Update , context : ContextTypes.DEFAULT_TYPE):




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
