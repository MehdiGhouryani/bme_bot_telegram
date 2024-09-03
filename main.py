import sqlite3
import os
from dotenv import load_dotenv
from keyboards_medical import KeyboardsManager
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes , MessageHandler,filters, CallbackQueryHandler
from telegram import KeyboardButton,ReplyKeyboardMarkup ,InlineKeyboardMarkup,InlineKeyboardButton
from callback_map import callback_map
import logging
from sympy import symbols, diff, integrate,sympify


load_dotenv()
token=os.getenv('Token')
db_name="medical_device.db"
ADMIN_CHAT_ID=['1717599240','686724429']

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s',level=logging.INFO)
logger = logging.getLogger(__name__)




async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id  
    user_id = update.message.from_user.id
    username = update.effective_user.username

    print(f'USER : {username}    ID : {user_id}')
    await save_user(user_id, username, chat_id)
    GROUP_CHAT_ID = '@chat_studentsbme'

    try:
        member = await context.bot.get_chat_member(chat_id=GROUP_CHAT_ID, user_id=user_id)
        print(f"user {user_id} status in group {GROUP_CHAT_ID} : {member.status}")
        if member.status not in ['member', 'administrator', 'creator']:

            keyboard = [
                [InlineKeyboardButton('عضویت در گروه', url=f"https://t.me/joinchat/{GROUP_CHAT_ID[1:]}")],
                [InlineKeyboardButton("عضو شدم ✅", callback_data='check_membership')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text('''
برای استفاده از ربات باید عضو گروه باشی
اگه عضو شدی دوباره /start کن.
''', reply_markup=reply_markup)
        else:
            keyboard = [
                [KeyboardButton("آموزش"),],
                [KeyboardButton("حل مسأله ریاضیات")],
                [KeyboardButton("سوالات متداول")],
                [KeyboardButton("درخواست و پیشنهاد 📝")],
            ]
    
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True) 
            await update.message.reply_text("لطفا یکی از گزینه‌ها را انتخاب کنید:", reply_markup=reply_markup) 
            
    except Exception as e:
        print(f"Error checking membership: {e}")
        await update.message.reply_text('مشکلی بوجود اومده! دوباره تلاش کن.')
   



async def save_user(user_id,username,chat_id):
    connection = sqlite3.connect('users.db')
    cursor = connection.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                      (user_id INTEGER PRIMARY KEY,
                       username TEXT,
                       chat_id TEXT)''')
    
    cursor.execute('INSERT OR REPLACE INTO users (user_id, username,chat_id) VALUES (?, ?,?)', (user_id, username,chat_id))
    connection.commit()
    connection.close()



async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    GROUP_CHAT_ID = '@chat_studentsbme'

    try:
        member = await context.bot.get_chat_member(chat_id=GROUP_CHAT_ID, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            # ارسال پیام تایید
            await query.answer("عضویت شما تایید شد.")
            await query.delete_message()
            keyboard = [
                [KeyboardButton("آموزش"),],
                [KeyboardButton("حل مسأله ریاضیات")],
                [KeyboardButton("سوالات متداول")],
                [KeyboardButton("درخواست و پیشنهاد 📝")],
            ]
    
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True) 
            await context.bot.send_message(chat_id=user_id, text="لطفا یکی از گزینه‌ها را انتخاب کنید:", reply_markup=reply_markup) 

        else:
            await query.answer("شما هنوز عضو گروه نشده‌اید.")
            
    except Exception as e:
        print(f"Error checking membership: {e}")
        await query.answer("خطا در بررسی عضویت.")


question_page1=(
"\n\n"
"💠برای مشاهده پاسخ هر سوال روی آن کلیک کنید :\n\n"
"[1. مهندسی پزشکی چیست؟](https://telegra.ph/مهندسی-پزشکی-چیست-08-20)\n\n\n"


"[2. چه گرایش‌هایی در رشته مهندسی پزشکی وجود دارد؟](https://telegra.ph/انواع-گرایش-در-مهندسی-پزشکی-08-20)\n\n"
"[🔻برای مشاهده پادکست مربوط به انواع گرایش در مهندسی پزشکی کلیک کنید](https://t.me/studentsbme/6)\n\n\n"


"[3. مهندسی پزشکی چه ارتباطی با رشته‌های دیگر مثل پزشکی، بیولوژی، کامپیوتر، و ... دارد؟](https://telegra.ph/ارتباط-با-دیگر-رشته-ها-08-20)\n\n\n"


"[4. مهندسی پزشکی چه نقشی در ارتقا سلامت جامعه ایفا می‌کند؟](https://telegra.ph/مهندسی-پزشکی-و-سلامت-08-20)\n\n\n"


"[5. مهارت‌های اصلی مورد نیاز برای یک مهندس پزشکی چیست؟](https://telegra.ph/مهارت-های-مورد-نیاز-08-20)\n\n\n"



"[6. چه مشاغلی در رشته مهندسی پزشکی وجود دارد؟](https://telegra.ph/مشاغل-مختلف-مهندسی-پزشکی-08-20)\n\n"
"[🔻برای مشاهده پادکست مربوط به انواع مشاغل در مهندسی پزشکی کلیک کنید](https://t.me/studentsbme/189)\n\n\n"


"[7. در کدام گرایش‌های مهندسی پزشکی (بیوالکتریک، بیومکانیک، بیومتریال) تقاضای بیشتری در بازار کار وجود دارد؟](https://telegra.ph/بازار-کار-08-20)\n\n\n" 


"[8. با بررسی بازار کار، محیط کاری در خارج یا داخل کشور بیشتر و بهتر است؟چرا؟](https://telegra.ph/ایران-یا-خارج-08-20)\n\n\n"


"[9. اپلای چیست؟ مدارک مورد نیاز آن چیست؟](https://telegra.ph/چطور-Apply-کنیم-08-20)\n\n\n"


"[10. مقاله نویسی چیست؟ میزان اهمیت ان برای اپلای و رزومه چگونه است؟](https://telegra.ph/مقاله-نویسی-08-21)\n\n\n"

"---"

)


question_page2 = (
"\n\n"
"💠برای مشاهده پاسخ هر سوال روی آن کلیک کنید :\n\n"

"[11. مهندس پزشک در بیمارستان چه چالش هایی دارد؟](https://t.me/studentsbme/189)\n\n\n"

"[12. طرح چیست؟ نحوه ثبت نام و شرایطش چگونه است؟](https://t.me/studentsbme/56)\n\n\n"

"[14. چه دانشگاه‌ها و مراکز آموزشی در ایران رشته مهندسی پزشکی ارائه می‌دهند؟](https://t.me/studentsbme/82)\n\n\n"

"[15. استخدام های دولتی رشته مهندسی پزشکی چگونه است؟ (شرایط و نحوه گزینش)](https://t.me/studentsbme/258)\n\n\n"

"[16. کار آموزی در شرکت یا بیمارستان بهتر است؟چرا؟](https://telegra.ph/کارآموزی-کجا-بهتره-08-21)\n\n\n"

"[17. عضویت در انجمن متخصصین تجهیزات پزشکی کشور چگونه است؟](https://t.me/studentsbme/27)\n\n\n"

"[18. در طول تحصیل در مقاطع کارشناسی و ارشد مهندسی پزشکی، چه دروسی ارائه می‌شوند و سرفصل‌های این دروس شامل چه موضوعاتی هستند؟]\n"
"['بررسی دروس و سر فصل های 'دوره کارشناسی](https://t.me/studentsbme/30)\n"
"['بررسی دروس و سر فصل های 'دوره کارشناسی ارشد](https://t.me/studentsbme/104)\n\n"


"---"
)



pages_sensors = {
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

pages_components={
    "Microcontroller":"https://telegra.ph/میکروکنترلر-Microcontroller-08-07",  
    "Amplifier": "https://telegra.ph/آی‌سی-تقویت‌کننده-Operational-Amplifier-08-07",
    "ADC": "https://telegra.ph/آی‌سی-آنالوگ-به-دیجیتال-ADC-08-07",
    "DAC": "https://telegra.ph/آی‌سی-دیجیتال-به-آنالوگ-DAC-08-07",
    "Transistor": "https://telegra.ph/ترانزیستور-Transistor-08-07",
    "Diode": "https://telegra.ph/دیود-Diode-08-07",
    "Resistor": "https://telegra.ph/مقاومت-Resistor-08-07",
    "Capacitor": "https://telegra.ph/خازن-Capacitor-08-07",
    "Potentiometer": "https://telegra.ph/پتانسیومتر-Potentiometer-08-07",
    "Voltage-Regulator": "https://telegra.ph/مبدل-ولتاژ-Voltage-Regulator-08-07",
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
    ADMIN_CHAT_ID=['1717599240','686724429']



    if text =='آموزش':
        buttons=[
        [KeyboardButton("تجهیزات پزشکی  🩺"),KeyboardButton("سنسور ها و قطعات")],
        [KeyboardButton('بازگشت به صفحه قبل  ⬅️')]
        ]
    
        reply_markup=ReplyKeyboardMarkup(buttons,resize_keyboard=True) 
        await update.message.reply_text('  لطفا یکی از گزینه‌ها را انتخاب کنید :',reply_markup=reply_markup)

    elif text == "تجهیزات پزشکی  🩺":

        reply_markup = InlineKeyboardMarkup(main_keyboard)
        await update.message.reply_text(text='یک گزینه را انتخاب کنید : ', reply_markup= reply_markup)


    elif text == "سنسور ها و قطعات":
        buttons=[
            [KeyboardButton("سنسورها"),KeyboardButton("قطعات الکترونیکی")],
            [KeyboardButton('بازگشت به صفحه قبل ⬅️')]
        ]
        
        reply_markup=ReplyKeyboardMarkup(buttons,resize_keyboard=True) 
        await update.message.reply_text('  لطفا یکی از گزینه‌ها را انتخاب کنید :',reply_markup=reply_markup)
    
    elif text == "سنسورها":

        buttons = [
        [InlineKeyboardButton("سنسور دما", url=pages_sensors["Temperature_Sensor"])],
        [InlineKeyboardButton("سنسور فشار", url=pages_sensors["Pressure_Sensor"])],
        [InlineKeyboardButton("سنسور ضربان قلب", url=pages_sensors["HeartRate_Sensor"])],
        [InlineKeyboardButton("سنسور اکسیژن", url=pages_sensors["Oxygen_Sensor"])],
        [InlineKeyboardButton("سنسور حرکتی", url=pages_sensors["Motion_Sensor"])],
        [InlineKeyboardButton("سنسور نوار قلب", url=pages_sensors["ECG_Sensor"])],
        [InlineKeyboardButton("سنسور دما و رطوبت", url=pages_sensors["Humidity"])],
        [InlineKeyboardButton("سنسور سطح", url=pages_sensors["Level_Sensor"])],  
        [InlineKeyboardButton("سنسور گاز", url=pages_sensors["Gas_Sensor"])],
        [InlineKeyboardButton("سنسور نوری", url=pages_sensors["Optical_Sensor"])],
        ]

        reply_markup = InlineKeyboardMarkup(buttons)

        # ارسال پیام

        await update.message.reply_text(text='یک گزینه را انتخاب کنید : ', reply_markup= reply_markup)

    elif text == "قطعات الکترونیکی":
        buttons = [
        [InlineKeyboardButton("میکروکنترلر", url=pages_components["Microcontroller"]),InlineKeyboardButton("تقویت‌کننده", url=pages_components["Amplifier"])],
        [InlineKeyboardButton("ADC", url=pages_components["ADC"]),InlineKeyboardButton("DAC", url=pages_components["DAC"])],
        [InlineKeyboardButton("ترانزیستور", url=pages_components["Transistor"]),InlineKeyboardButton("مقاومت", url=pages_components["Resistor"])],
        [InlineKeyboardButton("دیود", url=pages_components["Diode"]),InlineKeyboardButton("خازن", url=pages_components["Capacitor"])],
        [InlineKeyboardButton("پتانسیومتر", url=pages_components["Potentiometer"]),InlineKeyboardButton("مبدل-ولتاژ-", url=pages_components["Voltage-Regulator"])],
        ]

        reply_markup = InlineKeyboardMarkup(buttons)

        # ارسال پیام

        await update.message.reply_text(text='یک گزینه را انتخاب کنید : ', reply_markup= reply_markup)


    elif text == "حل مسأله ریاضیات":  # if برای شروع اولین شرط

        keyboard = [
            [KeyboardButton("مشتق‌گیری 📈"), KeyboardButton("انتگرال‌گیری ∫")],
            [KeyboardButton("مشتقات جزئی ∂"), KeyboardButton("انتگرال چندگانه ∬")],

            [KeyboardButton('بازگشت به صفحه قبل  ⬅️')]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text('لطفاً یک گزینه را انتخاب کنید:', reply_markup=reply_markup)
    elif text == "مشتق‌گیری 📈":
        await update.message.reply_text("لطفاً تابع خود را برای مشتق‌گیری وارد کنید:")
        context.user_data['operation'] = 'derivative'

    elif context.user_data.get('operation') == 'derivative':
        text = (
            text.replace('√', 'sqrt') 
                .replace('π', 'pi')   
                .replace('^', '')   
                .replace(' ', '')   
                .lower()          
        )
        x = symbols('x')
        try:
            function = sympify(text) 
            derivative = diff(function, x)
            await update.message.reply_text(f"مشتق تابع:\n\n {derivative}")
            print('-- MOSHTAGH --')
        except Exception as e:
            await update.message.reply_text("خطا در محاسبه مشتق. لطفاً تابع را به درستی وارد کنید.")
        context.user_data['operation'] = None

    elif text == "انتگرال‌گیری ∫":
        buttons = [
            [KeyboardButton("انتگرال نامعین"), KeyboardButton("انتگرال معین")],
            [KeyboardButton("برو به صفحه قبل⬅️")]
        ]
        reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        await update.message.reply_text("لطفاً نوع انتگرال را انتخاب کنید:", reply_markup=reply_markup)

    elif text == "انتگرال نامعین":
        await update.message.reply_text("لطفاً تابع خود را برای انتگرال نامعین وارد کنید:")
        context.user_data['operation'] = 'indefinite_integral'

    elif text == "انتگرال معین":
        await update.message.reply_text("لطفاً تابع خود را برای انتگرال معین وارد کنید:")
        context.user_data['operation'] = 'definite_integral'

    elif context.user_data.get('operation') == 'indefinite_integral':
        text = (
            text.replace('√', 'sqrt')  
                .replace('π', 'pi')   
                .replace('^', '')    
                .replace(' ', '')   
                .lower()             
        )

        x = symbols('x')
        try:
            function = sympify(text)
            indefinite_integral = integrate(function, x)
            await update.message.reply_text(f"انتگرال نامعین تابع:\n\n {indefinite_integral}+ C")
            print('-- ANTEGRAL 1 --')

        except Exception as e:
            await update.message.reply_text("خطا در محاسبه انتگرال. لطفاً تابع را به درستی وارد کنید.")
        context.user_data['operation'] = None

    elif context.user_data.get('operation') == 'definite_integral':
        text = (
            text.replace('√', 'sqrt') 
                .replace('π', 'pi')   
                .replace('^', '')   
                .replace(' ', '')   
                .lower()          
        )
 
        context.user_data['function'] = text
        context.user_data['operation'] = 'enter_limits'
        await update.message.reply_text("لطفاً حدود انتگرال را به صورت a, b وارد کنید:")

    elif context.user_data.get('operation') == 'enter_limits':
        text = (
            text.replace('√', 'sqrt') 
                .replace('π', 'pi')
                .replace('-π','-pi')   
                .replace('^', '')   
                .replace(' ', '')     
                .lower()          
        )

        try:
            x = symbols('x')
            limits = list(map(lambda limit:sympify(limit), text.split(',')))
            function = sympify(context.user_data.get('function'))
            definite_integral = integrate(function, (x, limits[0], limits[1]))
            print('-- ANTEGRAL 2 --')
            await update.message.reply_text(f"انتگرال معین تابع بین {limits[0]} و {limits[1]}:\n\n {definite_integral}")

        except Exception as e:
            await update.message.reply_text("خطا در محاسبه انتگرال معین. لطفاً تابع و حدود را به درستی وارد کنید.")
        context.user_data['operation'] = None
        


    elif text == "مشتقات جزئی ∂":
        await update.message.reply_text("لطفاً تابع خود را برای مشتق جزئی وارد کنید:")
        context.user_data['operation'] = 'partial_derivative'

    elif context.user_data.get('operation') == 'partial_derivative':
        text = (
            text.replace('√', 'sqrt')  
                .replace('π', 'pi')   
                .replace('^', '')    
                .replace(' ', '')   
                .lower()             
        )

        x, y = symbols('x y')
        try:
            function = sympify(text)
            partial_derivative_x = diff(function, x)
            partial_derivative_y = diff(function, y)
            await update.message.reply_text(f"مشتق جزئی تابع نسبت به x:\n\n {partial_derivative_x}\n\nمشتق جزئی تابع نسبت به y:\n\n {partial_derivative_y}")
            print('-- PARTIAL DERIVATIVE --')
        except Exception as e:
            await update.message.reply_text("خطا در محاسبه مشتق جزئی. لطفاً تابع را به درستی وارد کنید.")
        context.user_data['operation'] = None



    elif text == "انتگرال چندگانه ∬":
        await update.message.reply_text("لطفاً تابع خود را برای انتگرال چندگانه وارد کنید:")
        context.user_data['operation'] = 'multiple_integral'

    elif context.user_data.get('operation') == 'multiple_integral':
        text = (
            text.replace('√', 'sqrt')  
                .replace('π', 'pi')   
                .replace('^', '')    
                .replace(' ', '')   
                .lower()             
        )

        x, y = symbols('x y')
        try:
            function = sympify(text)
            multiple_integral = integrate(integrate(function, x), y)
            await update.message.reply_text(f"انتگرال چندگانه تابع:\n\n {multiple_integral}")
            print('-- MULTIPLE INTEGRAL --')
        except Exception as e:
            await update.message.reply_text("خطا در محاسبه انتگرال چندگانه. لطفاً تابع را به درستی وارد کنید.")
        context.user_data['operation'] = None



    
    elif text=='بازگشت به صفحه قبل ⬅️':
            
        buttons=[
        [KeyboardButton("تجهیزات پزشکی  🩺"),KeyboardButton("سنسور ها و قطعات")],
        [KeyboardButton('بازگشت به صفحه قبل  ⬅️')]
        ]
    
        reply_markup=ReplyKeyboardMarkup(buttons,resize_keyboard=True) 
        await update.message.reply_text('  لطفا یکی از گزینه‌ها را انتخاب کنید :',reply_markup=reply_markup)


    elif text =='بازگشت به صفحه قبل  ⬅️':
        await start(update,context)

    elif text == "برو به صفحه قبل⬅️":

        keyboard = [
            [KeyboardButton("مشتق‌گیری 📈"), KeyboardButton("انتگرال‌گیری ∫")],
            [KeyboardButton("مشتقات جزئی ∂"), KeyboardButton("انتگرال چندگانه ∬")],

            [KeyboardButton('بازگشت به صفحه قبل  ⬅️')]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text('لطفاً یک گزینه را انتخاب کنید:', reply_markup=reply_markup)

    elif text =='تعداد کاربران فعال':

        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        await update.message.reply_text(f'تعداد کاربران ربات تا به این لحظه : {count} نفر')
        conn.close()

    elif text=="ارسال پست به تمام کاربران":
        user_id =update.message.from_user.id
        if str(user_id) not in ADMIN_CHAT_ID:
            # print(user_id,ADMIN)
            await update.message.reply_text('شما مجوز ارسال پست را ندارید.')
            return

        await update.message.reply_text('لطفا عکس و کپشن را ارسال کنید.')

        # تغییر وضعیت به دریافت عکس و کپشن
        context.user_data['waiting_for_photo'] = True

    
    elif text == "سوالات متداول":
        await update.message.reply_text(text=question_page1,parse_mode=ParseMode.MARKDOWN,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('➡️ برو به صفحه بعد ',callback_data='next_question')]]))



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
        for ids in ADMIN_CHAT_ID:
            await context.bot.send_message(chat_id=ids, text=admin_message)

        # ارسال پیام تایید به کاربر
        await update.message.reply_text('ممنون از پیشنهادتون! ما اون رو بررسی خواهیم کرد.')

        # غیرفعال کردن حالت انتظار
        context.user_data['awaiting_request'] = False

        




async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("handle photo")
    if 'waiting_for_photo' in context.user_data and context.user_data['waiting_for_photo']:
        if update.message.photo:
            photo = update.message.photo[-1].file_id
            caption = update.message.caption if update.message.caption else ''

            # اتصال به دیتابیس و خواندن chat_idها
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            cursor.execute("SELECT chat_id FROM users")
            user_ids = [row[0] for row in cursor.fetchall()]
            conn.close()
            print("database is close")

            # ذخیره‌ی اطلاعات برای ارسال به کاربران
            context.user_data['photo_id'] = photo
            context.user_data['caption'] = caption
            context.user_data['waiting_for_photo'] = False

            await update.message.reply_text('عکس با کپشن دریافت شد. در حال ارسال به تمام کاربران...')
            print('post recived')
            # ارسال عکس به تمام کاربران
            for user_id in user_ids:
                try:
                    await context.bot.send_photo(chat_id=user_id, photo=photo, caption=caption)
                except Exception as e:
                    logger.error(f"Error sending photo to user {user_id}: {e}")

            await update.message.reply_text('پست به تمام کاربران ارسال شد.')
        else:
            await update.message.reply_text('لطفا یک عکس ارسال کنید.')





class_callback_map = callback_map()
callback_map_diagnostic = class_callback_map.callback_map_diagnostic()
callback_map_therapeutic = class_callback_map.callback_map_therapeutic()
callback_map_monitoring = class_callback_map.callback_map_monitoring()
callback_map_general = class_callback_map.callback_map_general_equipment()
callback_map_specialized = class_callback_map.callback_map_specialized_equipment()
callback_map_rehabilitation = class_callback_map.callback_map_rehabilitation_and_support()
callback_map_homecare = class_callback_map.callback_map_home_care_equipment()


combined_callback_map = {}
combined_callback_map.update(callback_map_diagnostic)
combined_callback_map.update(callback_map_therapeutic)
combined_callback_map.update(callback_map_monitoring)
combined_callback_map.update(callback_map_general)
combined_callback_map.update(callback_map_specialized)
combined_callback_map.update(callback_map_rehabilitation)
combined_callback_map.update(callback_map_homecare)


keyboards_manager = KeyboardsManager()

# دسته‌بندی‌های اصلی
main_keyboard = keyboards_manager.get_keyboard_main_categories()

# دسته‌بندی‌های مختلف
categories = {
    'diagnostic': [
        'diagnostic', 'imaging_devices', 'laboratory_devices',
        'cardiac_devices', 'neurological_devices',
        'pulmonary_devices', 'gastrointestinal_devices',
        'ent_diagnostic_devices', 'ophthalmic_diagnostic'
    ],
    'therapeutic': [
        'therapeutic', 'surgical_equipment', 'orthopedic_therapeutic', 'cardiovascular_therapeutic',
        'respiratory_equipment', 'other_therapeutic_equipment'
    ],
    'monitoring': [
        'monitoring','cardiac_monitors',
        'fetal_maternal_monitors', 'fetal_monitors',
        'blood_glucose_monitors'
    ],
    'general_medical': [
        'general_medical', 'hospital_equipment','emergency_equipment'
    ],
    'rehabilitation_and_support': [
        'rehabilitation_and_support', 'rehabilitation', 'patient_support'
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
    'ophthalmic_diagnostic': keyboard_ophthalmic_diagnostic,

    'surgical_equipment': keyboard_surgical_equipment,
    'orthopedic_therapeutic': keyboard_orthopedic_therapeutic,
    'cardiovascular_therapeutic': keyboard_cardiovascular_therapeutic,
    'respiratory_equipment': keyboard_respiratory_equipment,
    'other_therapeutic_equipment': keyboard_other_therapeutic_equipment,


    'cardiac_monitors': keyboard_cardiac_monitors,
    'fetal_maternal_monitors': keyboard_fetal_maternal_monitors,
    'fetal_monitors': keyboard_fetal_monitors,
    'blood_glucose_monitors': keyboard_blood_glucose_monitors,
    
    'hospital_equipment': keyboard_hospital_equipment,
    'emergency_equipment': keyboard_emergency_equipment,

    'rehabilitation': keyboard_rehabilitation,
    'patient_support': keyboard_patient_support,

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
    line = None 
    if data in combined_callback_map:
      
    #   print("-----     combined     -----")
      await combined_callback_map[data](data,update, context)

    elif data in keyboard_map:
        # print(f"----     keyboard_map     ----")
        reply_markup = InlineKeyboardMarkup(keyboard_map[data])
        await query.edit_message_reply_markup(reply_markup=reply_markup)



    elif ':' in data:

        parts = data.split(':')
        device = parts[0]
        action = parts[1]


        if len(parts) > 2:
            line = parts[2]
 
        keyboard_define =([
            [InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types:{line}')],
            [InlineKeyboardButton('ساختار و اجزاء دستگاه', callback_data=f'{device}:structure:{line}')],
            [InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation:{line}'),
             InlineKeyboardButton(' تکنولوژی‌های مشابه', callback_data=f'{device}:related_technologies:{line}')],
            [InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages:{line}'), 
             InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety:{line}')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data=line)],
        ])
        reply_markup_deine =InlineKeyboardMarkup(keyboard_define)

        keyboard_menu =([
            [InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types:{line}'), 
             InlineKeyboardButton('معرفی دستگاه', callback_data=f'{device}:definition:{line}')],
            [InlineKeyboardButton('ساختار و اجزاء دستگاه', callback_data=f'{device}:structure:{line}')],
            [InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation:{line}'),
             InlineKeyboardButton(' تکنولوژی‌های مشابه', callback_data=f'{device}:related_technologies:{line}')],
            [InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages:{line}'), 
             InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety:{line}')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data=line)],
        ])
        reply_markup_menu =InlineKeyboardMarkup(keyboard_menu)


        print(f" ----    {action}  --  : --  {device}  --  :   {line}   ----")

        


        if action == 'definition':
            cursor.execute(f"SELECT definition FROM information WHERE name = '{device}'")
            device_info = cursor.fetchone()[0]

            cursor.execute(f"SELECT photo FROM information WHERE name = '{device}'")
            device_photo = cursor.fetchone()[0]
            
            await query.delete_message()
            await context.bot.send_photo(chat_id=chat_id,caption=device_info,photo=device_photo,parse_mode=ParseMode.MARKDOWN,reply_markup=reply_markup_deine)
        else:
            print('----------')

        
        if action == 'types':
            cursor.execute(f"SELECT types FROM information WHERE name = '{device}'")
            device_info = cursor.fetchone()[0]
            try:
                await query.edit_message_text(text = device_info,parse_mode=ParseMode.MARKDOWN,reply_markup=reply_markup_menu)
            except:    
                await query.delete_message()
                await context.bot.send_message(chat_id=chat_id,text = device_info,parse_mode=ParseMode.MARKDOWN,reply_markup=reply_markup_menu)

        elif action == 'structure':
            cursor.execute(f"SELECT structure FROM information WHERE name = '{device}'")
            device_info = cursor.fetchone()[0]
            try:
                await query.edit_message_text(text = device_info,parse_mode=ParseMode.MARKDOWN,reply_markup=reply_markup_menu)
            except:    
                await query.delete_message()
                await context.bot.send_message(chat_id=chat_id,text = device_info,parse_mode=ParseMode.MARKDOWN,reply_markup=reply_markup_menu)

        elif action == 'operation':
            cursor.execute(f"SELECT operation FROM information WHERE name = '{device}'")
            device_info = cursor.fetchone()[0]
            try:
                await query.edit_message_text(text = device_info,parse_mode=ParseMode.MARKDOWN,reply_markup=reply_markup_menu)
            except:    
                await query.delete_message()
                await context.bot.send_message(chat_id=chat_id,text = device_info,parse_mode=ParseMode.MARKDOWN,reply_markup=reply_markup_menu)

        elif action == 'advantages_disadvantages':
            cursor.execute(f"SELECT advantages_disadvantages FROM information WHERE name = '{device}'")
            device_info = cursor.fetchone()[0]
            try:
                await query.edit_message_text(text = device_info,parse_mode=ParseMode.MARKDOWN,reply_markup=reply_markup_menu)
            except:    
                await query.delete_message()
                await context.bot.send_message(chat_id=chat_id,text = device_info,parse_mode=ParseMode.MARKDOWN,reply_markup=reply_markup_menu)

        elif action == 'safety':
            cursor.execute(f"SELECT safety FROM information WHERE name = '{device}'")
            device_info = cursor.fetchone()[0]
            try:
                await query.edit_message_text(text = device_info,parse_mode=ParseMode.MARKDOWN,reply_markup=reply_markup_menu)
            except:    
                await query.delete_message()
                await context.bot.send_message(chat_id=chat_id,text = device_info,parse_mode=ParseMode.MARKDOWN,reply_markup=reply_markup_menu)

        elif action == 'related_technologies':
            cursor.execute(f"SELECT related_technologies FROM information WHERE name = '{device}'")
            device_info = cursor.fetchone()[0]
            try:
                await query.edit_message_text(text = device_info,parse_mode=ParseMode.MARKDOWN,reply_markup=reply_markup_menu)
            except:    
                await query.delete_message()
                await context.bot.send_message(chat_id=chat_id,text = device_info,parse_mode=ParseMode.MARKDOWN,reply_markup=reply_markup_menu)

        cursor.close()

        
 
    elif data == 'back_to_main':
        reply_markup = InlineKeyboardMarkup(main_keyboard)
        await query.edit_message_reply_markup(reply_markup=reply_markup)
    
    elif data == 'check_membership':
        await check_membership(update,context)

    elif data == 'next_question':
        await query.edit_message_text(text=question_page2,parse_mode=ParseMode.MARKDOWN,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⬅️ برو به صفحه قبل ',callback_data='previous_question')]]))

    
    elif data == 'previous_question':
        await query.edit_message_text(text=question_page1,parse_mode=ParseMode.MARKDOWN,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⬅️ برو به صفحه بعد ',callback_data='next_question')]]))

    
    else:
        await query.answer("مثل اینکه این بخش اماده نشده هنوز  ")










def main():
    app = Application.builder().token(token).build()

    start_handler = CommandHandler("start",start)
    Buttun_handler =MessageHandler(filters.TEXT & ~filters.COMMAND ,Button_click)

    app.add_handler(start_handler)
    app.add_handler(Buttun_handler)
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.PHOTO,handle_photo))

    app.run_polling()

if __name__=="__main__":
    main()
