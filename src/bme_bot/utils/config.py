# src/bme_bot/config.py
#
# منبع واحد تنظیمات ربات.

import os
from dotenv import load_dotenv

load_dotenv()

# --- متغیرهای ربات ---
CHANNEL_USERNAME = "@studentsbme"
GROUP_CHAT_ID = '@chat_studentsbme'

# لیست شناسه‌ی چت ادمین‌ها؛ در .env به‌صورت رشته‌ی جدا‌شده با کاما نگه داشته
# می‌شود، مثلاً: ADMIN_CHAT_ID=1717599240,686724429
ADMIN_CHAT_ID = [
    admin_id.strip()
    for admin_id in os.getenv('ADMIN_CHAT_ID', '').split(',')
    if admin_id.strip()
]

# مقصد هشدارهای خودکار سطح ERROR (utils/telegram_error_handler.py) — «ادمین
# اصلی» عمداً تک‌نفره است، نه broadcast به همه‌ی ADMIN_CHAT_ID (که مخصوص
# هشدارهای دستی/فیچرهاست). پیش‌فرض: اولین آیدی از ADMIN_CHAT_ID، مگر این‌که
# MAIN_ADMIN_CHAT_ID جدا در .env ست شده باشد.
MAIN_ADMIN_CHAT_ID = os.getenv('MAIN_ADMIN_CHAT_ID') or (ADMIN_CHAT_ID[0] if ADMIN_CHAT_ID else None)

# --- کلیدهای API و توکن ---
TELEGRAM_BOT_TOKEN = os.getenv('Token')
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# کلیدهای لایه‌های دوم/سوم زنجیره‌ی fallback هوش مصنوعی. هر دو اختیاری‌اند —
# اگر خالی باشند، همان لایه به‌سادگی رد می‌شود (ai_service.py این را در
# AI_FALLBACK_MODELS مدیریت می‌کند).
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# نام مدل اصلی و زنجیره‌ی fallback (به سبک LiteLLM: "provider/model"). عمداً
# اینجا و نه هاردکد در ai_service.py، چون کاتالوگ مدل‌های رایگان ارائه‌دهندگان
# ثالث به‌کرات تغییر/منسوخ می‌شود — پیش‌فرض‌ها قابل بازنویسی با متغیر محیطی‌اند،
# بدون نیاز به لمس کد. مدل دوم Groq فعلی (`qwen/qwen3.6-27b`) هنوز در فهرست
# «Production Models» رسمی Groq نیست (Preview است) ولی deprecation هم ندارد؛
# همین مدل هم‌زمان مدل vision-capable سرویس OCR است (services/ocr_service.py).
# قبل از استقرار جدید، وضعیت فعلی مدل‌ها را با console.groq.com/docs/models
# چک کن.
#
# ۲۰۲۶-۰۸-۳۰: gemini-2.5-flash از کار افتاد — لاگ production واقعی نشون داد
# هر تک درخواست AI (بدون استثنا) روی این مدل با ۴۰۴
# "This model models/gemini-2.5-flash is no longer available to new users"
# fail می‌شد و همیشه به لایه‌ی دوم (Groq) سقوط می‌کرد؛ یعنی لایه‌ی اول
# (رایگان، قرار بود اول امتحان بشه) عملاً کلاً حذف شده بود و کل ترافیک AI
# داشت بی‌دلیل بودجه‌ی روزانه‌ی مشترک Groq رو می‌خورد. متن همون پیام خطا
# صراحتاً gemini-3.6-flash رو پیشنهاد داده؛ همون رو گذاشتیم. اگه دوباره این
# اتفاق افتاد، اول لاگ رو برای پیام دقیق دیپریکیشن چک کن (گوگل مدل‌های
# gemini-2.5-flash رو مرتب عوض می‌کنه)، بعد این مقدار رو عوض کن.
AI_PRIMARY_MODEL = os.getenv("AI_PRIMARY_MODEL", "gemini/gemini-3.6-flash")
AI_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv(
        "AI_FALLBACK_MODELS",
        "groq/openai/gpt-oss-120b,groq/qwen/qwen3.6-27b,"
        "openrouter/meta-llama/llama-3.3-70b-instruct:free",
    ).split(",")
    if model.strip()
]

# --- استریم پیش‌نمایش /ask با sendRichMessageDraft (Bot API 10.1+، فقط چت خصوصی) ---
# قابلیت کاملاً افزوده با auto-fallback خودکار روی هر خطای واقعی API (رجوع
# به utils/draft_stream.py) — نیازی به دخالت دستی برای اون حالت نیست. این
# فلگ فقط برای یه حالت متفاوت است که auto-fallback نمی‌تونه تشخیصش بده: یه
# گزارش واقعی (نه رسمی از تلگرام، ولی از تجربه‌ی واقعی پیاده‌سازی مشابه در
# پروژه‌ای دیگر) که پیام‌های استریم‌شده در چت خصوصی روی تلگرام iOS به‌شکل
# «Pinned Message» نمایش داده می‌شن — یه quirk سمت کلاینت که درخواست API
# خودش با موفقیت برمی‌گرده، پس هیچ exception ای نیست که به‌طور خودکار
# گرفته بشه. امکان تست مستقیم این پروژه با یه بات/چت واقعی تلگرام نبود؛
# (این گزارش اصلش برای نسخه‌ی قدیمی‌تر/plain-text این قابلیت بود — برای
# نسخه‌ی rich-markdown فعلی جداگانه تأیید یا رد نشده، پس همون احتیاط قبلی
# رو نگه داشتیم.)
# اگه بعد از استقرار این رفتار رو دیدید، فقط این خط رو False کنید یا
# AI_STREAMING_ENABLED=false را در محیط ست کنید — بدون نیاز به تغییر کد.
AI_STREAMING_ENABLED = os.getenv("AI_STREAMING_ENABLED", "true").strip().lower() not in ("false", "0", "no")

# --- زنجیره‌ی OCR چندلایه ---
# کلیدهای Google Cloud Vision و Azure AI Vision اختیاری‌اند — هرکدام خالی
# باشد، آن لایه رد می‌شود. ترتیب پیش‌فرض: این دو لایه‌ی اول (بهترین دقت
# مستند برای فارسی چاپی)، بعد Groq، بعد Gemini، به‌عنوان لایه‌های پشتیبان.
#
# Google Cloud Vision: از یک API key ساده (نه service account) پشتیبانی می‌کند
# — docs.cloud.google.com/vision/product-search/docs/auth. همان الگوی ساده‌ی
# GEMINI_API_KEY، بدون فایل JSON جداگانه.
GOOGLE_VISION_API_KEY = os.getenv("GOOGLE_VISION_API_KEY")

# Azure AI Vision: نیاز به کلید + آدرس endpoint اختصاصی همان منبع Azure دارد
# (چیزی شبیه https://<resource-name>.cognitiveservices.azure.com).
AZURE_VISION_KEY = os.getenv("AZURE_VISION_KEY")
AZURE_VISION_ENDPOINT = os.getenv("AZURE_VISION_ENDPOINT")

# ترتیب لایه‌های زنجیره‌ی OCR. نام‌ها باید دقیقاً یکی از کلیدهای شناخته‌شده‌ی
# ocr_service._PROVIDER_FUNCS باشند (google, azure, groq_vision, gemini). قابل
# بازنویسی/تغییر ترتیب از .env بدون لمس کد.
#
# لایه‌ی gemini جدیدترین عضو این زنجیره است — بدون نیاز به کلید/ثبت‌نام جدید
# (همون GEMINI_API_KEY بالا رو استفاده می‌کنه، بی‌هزینه‌ی اضافه). عمداً آخر
# صف پیش‌فرض قرار گرفته (فقط اگه بقیه شکست بخورن/پیکربندی نشده باشن اجرا
# می‌شه)، چون برخلاف Google Vision/Azure (سرویس‌های اختصاصی OCR با سابقه‌ی
# مستند)، دقتش برای فارسی هنوز با داده‌ی واقعی این پروژه تست نشده. برای
# ارزیابی مستقیم کیفیتش (نه صرفاً به‌عنوان fallback آخر)، موقتاً
# OCR_PROVIDER_ORDER=gemini رو تنها مقدار این متغیر در .env بذارید — با
# عکس‌های واقعی فارسی امتحان کنید، بعد بر اساس نتیجه تصمیم بگیرید جایگاه
# دائمی‌ش کجا باشه (یا همین‌جا، آخر صف، بمونه).
OCR_PROVIDER_ORDER = [
    p.strip()
    for p in os.getenv("OCR_PROVIDER_ORDER", "google,azure,groq_vision,gemini").split(",")
    if p.strip()
]

# مدل vision-capable برای لایه‌ی OCR مبتنی بر LiteLLM (فعلاً فقط Groq). طبق
# مستندات رسمی Groq (console.groq.com/docs/vision)، qwen/qwen3.6-27b صریحاً
# برای «Optical Character Recognition (OCR)» تبلیغ شده — تنها مدل vision این
# فهرست که چنین ادعای رسمی‌ای دارد.
OCR_VISION_MODEL = os.getenv("OCR_VISION_MODEL", "groq/qwen/qwen3.6-27b")

# مدل vision-capable Gemini برای لایه‌ی OCR جدید. عمداً جدا نگه داشته شده
# (نه ارجاع مستقیم به AI_PRIMARY_MODEL) دقیقاً به همون دلیلی که
# OCR_VISION_MODEL از AI_FALLBACK_MODELS جداست: این دو مصرف کاملاً متفاوتی
# دارن (تشخیص متن از عکس در برابر پاسخ‌دهی متنی)، تغییر مدل اصلی AI نباید
# ناخواسته مدل OCR رو هم عوض کنه. پیش‌فرض قبلی gemini-2.5-flash بود که طبق
# لاگ production منسوخ شده (رجوع به کامنت AI_PRIMARY_MODEL بالا)؛ همون نسخه‌ی
# جدید (gemini-3.6-flash) اینجا هم گذاشته شده، چون هر دو دقیقاً همون خانواده‌ی
# مدلن که گوگل عوضش کرده.
OCR_GEMINI_MODEL = os.getenv("OCR_GEMINI_MODEL", "gemini/gemini-3.6-flash")


# --- زنجیره‌ی fallback چندلایه‌ی STT فارسی (تبدیل ویس به متن) ---
# ترتیب پیش‌فرض: ElevenLabs → Groq → Deepgram → AssemblyAI → Azure →
# Google Cloud → wit.ai → Google غیررسمی. همه‌ی کلیدها اختیاری‌اند —
# هرکدام خالی باشد، همان لایه به‌سادگی رد می‌شود.
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

# جدا از AZURE_VISION_KEY/ENDPOINT (که مال OCR است) — Azure AI Speech یک
# منبع مستقل در پورتال Azure است، کلید/region خودش را دارد.
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")

# جدا از GOOGLE_VISION_API_KEY (که مال OCR است) — Google Cloud Speech-to-Text
# یک API مستقل با فعال‌سازی/کلید جدا در همان Google Cloud Console است.
GOOGLE_STT_API_KEY = os.getenv("GOOGLE_STT_API_KEY")

WIT_AI_TOKEN = os.getenv("WIT_AI_TOKEN")

# ترتیب لایه‌های زنجیره‌ی STT. نام‌ها باید دقیقاً یکی از کلیدهای شناخته‌شده‌ی
# stt_service._PROVIDER_FUNCS باشند. قابل بازنویسی/تغییر ترتیب از .env
# بدون لمس کد (همان الگوی OCR_PROVIDER_ORDER).
STT_PROVIDER_ORDER = [
    p.strip()
    for p in os.getenv(
        "STT_PROVIDER_ORDER",
        "elevenlabs,groq,deepgram,assemblyai,azure,google,wit,google_unofficial",
    ).split(",")
    if p.strip()
]

# --- مسیرها ---
# ریشه‌ی پروژه: سه پوشه بالاتر از این فایل (src/bme_bot/config.py -> src/bme_bot -> src -> ریشه)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, 'data')

# پوشه‌ی لاگ (logging_setup.py). طبق همان الگوی DATA_DIR، مسیر اینجا متمرکز
# است تا هیچ فایل دیگری مجبور به ساخت دستی مسیر لاگ نباشد.
LOG_DIR = os.path.join(BASE_DIR, 'logs')

# قابل بازنویسی با متغیر محیطی برای استقرارهای غیرمعمول.
USERS_DB_PATH = os.getenv('USERS_DB_PATH', 'users.db')
EQUIPMENT_DB_PATH = os.getenv('EQUIPMENT_DB_PATH', 'medical_device.db')

# آرشیو خام سوال‌های تولیدشده‌ی کوییز (utils/quiz_archive.py) — یک فایل
# JSONL (نه دیتابیس، نه پوشه‌ی data/ که فقط محتوای مرجع فقط-خواندنیه) که
# فقط انباشته می‌شه؛ فعلاً هیچ فیچری از روش نمی‌خونه، فقط برای استفاده‌ی
# احتمالی آینده (مثلاً یه کوییز رندم از آرشیو) ذخیره می‌شه.
QUIZ_ARCHIVE_PATH = os.getenv('QUIZ_ARCHIVE_PATH', 'quiz_archive.jsonl')
