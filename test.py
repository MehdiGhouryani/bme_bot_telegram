# دیکشنری برای کیبوردها
keyboard_map = {
    'diagnostic_equipment': keyboard_diagnostic,
    'therapeutic_equipment': keyboard_therapeutic,
    'monitoring_equipment': keyboard_monitoring,
    'general_medical_equipment': keyboard_general_medical,
    'support_rehabilitation_equipment': keyboard_rehabilitation_and_support,
    'specialized_equipment': keyboard_specialized_equipment,
    'home_care_equipment': keyboard_home_care_equipment,
    'medical_imaging': keyboard_medical_imaging,
    'laboratory_equipment': keyboard_laboratory_equipment,
    'cardiac_diagnostic_equipment': keyboard_cardiac_diagnostic_equipment,
    'neurological_diagnostic_equipment': keyboard_neurological_diagnostic_equipment,
    'pulmonary_diagnostic_equipment': keyboard_pulmonary_diagnostic_equipment,
    'gastrointestinal_diagnostic_equipment': keyboard_gastrointestinal_diagnostic_equipment,
    'ent_diagnostic_equipment': keyboard_ent_diagnostic_equipment,
    'ophthalmic_diagnostic_equipment': keyboard_ophthalmic_diagnostic_equipment,
    'surgical_equipment': keyboard_surgical,
    'orthopedic_equipment': keyboard_orthopedic,
    'cardiovascular_equipment': keyboard_cardiovascular,
    'respiratory_equipment': keyboard_respiratory,
    'other_therapeutic_equipment': keyboard_other_therapeutic,
    'vital_signs_monitors': keyboard_vital_signs_monitors,
    'cardiac_monitors': keyboard_cardiac_monitors,
    'pulse_oximeters': keyboard_pulse_oximeters,
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

# دیکشنری برای اطلاعات پایگاه داده
info_map = {
    'definition': 'definition',
    'types': 'types',
    'structure': 'structure',
    'operation': 'operation',
    'advantages_disadvantages': 'advantages_disadvantages',
    'safety': 'safety',
    'related_technologies': 'related_technologies'
}

async def fetch_and_send_info(action: str, device: str, query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    column = info_map.get(action)
    if column:
        async with sqlite3.connect(db_name) as connection:
            cursor = connection.cursor()
            cursor.execute(f"SELECT {column} FROM information WHERE name = ?", (device,))
            device_info = cursor.fetchone()[0]
        await query.delete_message()
        await context.bot.send_message(
            chat_id=chat_id,
            text=device_info,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('بازگشت', callback_data=device)]])
        )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    query = update.callback_query
    data = query.data
    chat_id = update.message.chat_id

    if data in keyboard_map:
        reply_markup = InlineKeyboardMarkup(keyboard_map[data])
        await query.edit_message_reply_markup(reply_markup=reply_markup)

    elif ':' in data:
        device, action = data.split(':')
        await fetch_and_send_info(action, device, query, context, chat_id)

    elif data == 'back_to_main':
        reply_markup = InlineKeyboardMarkup(main_keyboard)
        await query.edit_message_reply_markup(reply_markup=reply_markup)

    else:
        await query.answer("دستور نامعتبر است.")















        from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Callback query handler function
async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    CHANNEL_USERNAME = '@studentsbme'

    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            # Send a confirmation message to the user
            await query.answer("عضویت شما تایید شد.")
            await query.message.reply_text("عضویت شما تایید شد! اکنون می‌توانید از ربات استفاده کنید.")
            await query.message.delete()  # حذف پیام اینلاین قبلی
        else:
            await query.answer("شما هنوز عضو کانال نشده‌اید.")
            await query.message.reply_text("برای استفاده از ربات باید عضو کانال شوید.")
    except Exception as e:
        print(f"Error checking membership: {e}")
        await query.answer("خطا در بررسی عضویت.")

# Main function to set up the bot
async def main():
    app = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_membership, pattern='check_membership'))

    await app.run_polling()

if name == "main":
    import asyncio
    asyncio.run(main())