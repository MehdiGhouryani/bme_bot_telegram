# BME Bot — دستیار تلگرامی دانشجویان مهندسی پزشکی

بات آموزشی برای دانشجویان BME: دانشنامه‌ی تجهیزات پزشکی (+ بخش تعمیرات و
نگهداری)، سنسورها/قطعات، پرسش‌های رایج، پرسش‌وپاسخ با AI، و چند ابزار
کمکی (OCR، تبدیل ویس به متن، کوییزساز، ویس-به-جزوه). پنل ادمین کامل
(broadcast، جستجوی کاربر، آمار سلامت، محدودیت‌های قابل‌تنظیم).

## راه‌اندازی

```bash
pip install -r requirements.txt
apt install ffmpeg          # برای دو تایر fallback تبدیل ویس به متن
cp .env.example .env        # و مقداردهی
# users.db و medical_device.db باید در ریشه‌ی پروژه باشند
PYTHONPATH=src python -m bme_bot.app
```

## ساختار و قراردادهای مهم

- **دو دیتابیس کاملاً جدا، عمداً:** `users.db` (کاربر/مصرف/ادمین، از طریق
  `db/app_connection.py`) و `medical_device.db` (دانشنامه‌ی تجهیزات + جدول‌های
  `device_maintenance_*`، از طریق `db/equipment_connection.py`). هیچ‌وقت قاطی
  نشوند.
- **ترتیب ثبت handler در `app.py` حیاتی است:** همه‌ی `ConversationHandler`ها
  (admin ×۳، equipment_admin_edit، maintenance_admin_edit) باید *قبل* از
  `CallbackQueryHandler(callback_handler)` عمومی ثبت بشن — وگرنه دیسپچر عمومی
  زودتر و نادرست callback رو می‌قاپه و ConversationHandler هیچ‌وقت اجرا
  نمی‌شه. `tests/test_handler_registration.py` این ترتیب رو با یک
  `Application` واقعی (نه mock) تضمین می‌کنه؛ هر ConversationHandler جدید باید
  همون‌جا هم اضافه بشه.
- **namespace جدای callback_data برای هر ConversationHandler**
  (`admin_edit_field:`, `maint_admin_*:`, ...) — چون تشخیص کلیک روی
  دستگاه/اکشن با split محدود انجام می‌شه، یک prefix متفاوت لازمه تا با فرمت
  عمومی `device:action:line` قاطی نشه.
- **هر فیچر AI-محور: فایل/جدول مستقل خودش** (handler + `db/*_usage_repository.py`
  + `data/*_prompt.json` مستقل، نه مشترک) مگر ورودی/خروجیش عملاً همون فیچر
  باشه (مثل کوییز-از-فایل که `quiz_usage` رو با کوییز-از-متن مشترک گذاشت).
- **`services/ai_service.ask()` نقطه‌ی ورود مشترک همه‌ی فیچرهای AI** (ai_assistant،
  quiz، jozve). زنجیره: Gemini (`gemini/gemini-2.5-flash`) → Groq
  (`openai/gpt-oss-120b` → `qwen/qwen3.6-27b`) → OpenRouter. **سقف توکن روزانه‌ی
  Groq (۲۰۰,۰۰۰ توکن/روز) بین همه‌ی این فیچرها مشترکه** — محدودیت‌های سخت‌گیرانه‌ی
  jozve (۱/روز) و سقف ۴۰۹۶ کاراکتری کوییز-از-فایل هردو برای همین طراحی شدن.
- **محدودیت مصرف:** `db/feature_limits_repository.py` + `db/usage_limit_helper.py`
  (منطق SQL مشترک، allow-list صریح روی نام جدول چون پارامتر جای‌گذاری‌شده
  برای نام جدول وجود نداره). سقف/کول‌داون هر فیچر از پنل ادمین («🎚
  محدودیت‌ها») قابل‌تغییره، seed اولیه در `app_connection.py`. **ادمین در سطح
  handler معاف می‌شه**، نه در repository (اصلاً `check_*_limit` صدا زده
  نمی‌شه).
- **گزارش خطا دو لایه‌ست:** `utils/error_reporting.py`
  (`report_error`/`report_service_issue`، throttle ۱۰دقیقه‌ای، برای
  شکست‌های شناخته‌شده‌ی هر فیچر) + `utils/telegram_error_handler.py` (شبکه‌ی
  ایمنی سطح root logger، هر `logger.error` ناگرفته خودکار به
  `MAIN_ADMIN_CHAT_ID` می‌ره). لاگ فایل: truncate در ۱۰MB (نه rotate).
- **ذخیره‌ی عکس/ویدیوی تلگرامی:** برای محتوای تکراری/متغیر (مثل آیتم‌های
  تعمیرات) `file_id` تلگرام ذخیره می‌شه، نه بایت خام — طبق API تلگرام
  فایل ارسال‌شده با `file_id` بدون محدودیت و بدون آپلود مجدد قابل ارسال
  دوباره‌ست. (ستون `photo` قدیمی جدول `information` بایت خام داره — میراث
  import اولیه‌ی ۷۲ دستگاه، الگوی جدید نیست.)
- **قابلیت‌های Bot API جدیدتر از نسخه‌ی pin‌شده‌ی PTB (`==21.4`):**
  `bot.do_api_request(endpoint, data)` — راه رسمی خودِ PTB برای متدهای
  HTTP جدیدتر از نسخه‌ی نصب‌شده — و `api_kwargs={...}` روی کلاس‌های
  موجود (`InlineKeyboardButton`/`MessageEntity`) برای فیلدهای جدیدتر روی
  متدهای قدیمی. چهار utility مستقل، هرکدوم مستندسازی کامل خودش رو داره:
  `utils/button_style.py` (رنگ دکمه، Bot API 9.4)، `utils/date_time_entity.py`
  (entity نوع date_time، فیلد wire واقعیش `unix_time`ه نه `date_time`، دقت
  UTF-16 حیاتیه)، `utils/rich_message.py` (`sendRichMessage`، Bot API
  10.1 — پیام جزوه‌ی jozve هم به‌شکل رِیچ داخل چت هم فایل .md می‌فرسته)،
  `utils/draft_stream.py` (`sendMessageDraft`، Bot API 9.5+ — پیش‌نمایش
  تدریجیِ پاسخ `/ask` قبل از پیام نهایی، فقط چت خصوصی). هر چهارتا کاملاً
  افزوده‌ن: روی هر خطا (حتی exception غیرمنتظره) بی‌سروصدا `False`
  برمی‌گردونن و فراخواننده به مسیر قدیمی برمی‌گرده — آپگرید کل PTB
  عمداً انجام نشد (ریسک رگرشن رو کل پروژه، نامتناسب با این بهبودهای UI).

## تست

```bash
export PYTHONPATH=src && pytest tests/ -q
pyflakes src/ tests/ && pip check
```

فعلاً: pyflakes/pip check تمیز. ۵ تست preexisting شکست می‌خورن (drift متن/رفتار
قدیمی تست، نه باگ واقعی) — قبل از هر تغییر جدید با اجرای مستقیم روی نسخه‌ی
پیشین تایید کن که این ۵ تا هنوز همونن، نه رگرسیون تازه. **نکته‌ی مهم:** چند
فایل تست preexisting (jozve/ocr/stt/quiz/ai_assistant_rate_limit/app_routing)
موقع اجرا مستقیم رو `users.db` واقعی می‌نویسن، نه یه دیتابیس موقت — بعد از هر
اجرای کامل سوییت، `users.db`/`medical_device.db` رو با نسخه‌ی pristine چک/ریست
کن قبل از تحویل.

## نکات باز

- دو ردیف تکراری تو جدول `information`: `audiogram` (بی‌خطر) و `surgical_laser`
  (نسخه‌ی فعلاً نمایش‌داده‌شده `definition` خالی داره؛ نسخه‌ی کامل زیر یه `id`
  دیگه‌ست) — تصمیم حذف کدوم با شماست.
- `utils/persian_text.looks_like_persian()` عمداً به `ocr_service` وصل نشده
  (فیلتر زبانی، عکس انگلیسی رو هم رد می‌کرد؛ مشکل واقعی هالوسینیشن مدل
  ربطی به زبان نداشت) — تابع/تست‌هاش دست‌نخورده مونده برای استفاده‌ی آینده.
- تایر STT رسمی Google Cloud هنوز با یه ویس واقعی تلگرام تست نشده.
- کوییز از فایل: فقط docx/txt (نه pdf، نه .doc قدیمی) — طبق تصمیم صریح.
- **پیش‌نمایش تدریجی `/ask` (`utils/draft_stream.py`, `sendMessageDraft`)
  با یه بات/چت واقعی تست نشده** — امکانش تو این محیط نبود. طبق مستندات
  رسمی از اول مارس ۲۰۲۶ برای همه‌ی بات‌ها فعاله، ولی یه گزارش (نه رسمی از
  تلگرام) هست که این پیش‌نمایش‌ها تو چت خصوصی روی تلگرام iOS به‌شکل
  «Pinned Message» نمایش داده می‌شن — اگه بعد از استقرار این رو دیدید،
  `AI_STREAMING_ENABLED=false` رو در محیط ست کنید (بدون نیاز به تغییر
  کد)؛ خطاهای واقعی API خودشون خودکار fallback می‌کنن، این فلگ فقط برای
  همین یه حالت خاصه که هیچ exception ای تولید نمی‌کنه.
