



# لیست کلیدواژه‌های مقالات مهندسی پزشکی
keywords_article = [

    "Biomaterials", "Biomedical Imaging", "Biomimetics", 
    "Tissue Engineering", "Medical Devices", "Neuroengineering", "Biosensors", 
    "Bioprinting", "Clinical Engineering", "Rehabilitation Engineering", 
    "Bioelectrics", "Biomechanics", "Nanomedicine", "Regenerative Medicine", 
    "Biomedical Signal Processing", "Medical Robotics", "Wearable Health Technology", 
    "Telemedicine", "Cardiovascular Engineering", "Orthopaedic Bioengineering", 
    "Prosthetics and Implants", "Artificial Organs", "Cancer Bioengineering", 
    "Biomedical Data Science", "Biophotonics", "Medical Imaging Informatics", 
    "Robotic Surgery", "Wearable Sensors", "Digital Health", "Biomedical Optics", 
    "Point-of-Care Diagnostics", "Cardiac Engineering", "Personalized Medicine", 
    "Gene Therapy"

]

TARGET = '@Articles_studentsBme'  # کانال آرشیو مقالات

# تابع ارسال مقاله به کاربران
async def send_article(context: CallbackContext):
    selected_keyword = random.choice(keywords_article)
    search_query = scholarly.search_pubs(selected_keyword)
    articles = [next(search_query) for _ in range(5)]
    random_article = random.choice(articles)



    abstract = random_article['bib'].get('abstract', 'No abstract available')

    result = f"📚 {random_article['bib']['title']}\n" \
             f"👨‍🔬 Author(s): {', '.join(random_article['bib']['author'])}\n" \
             f"📅 Year: {random_article['bib'].get('pub_year', 'Unknown')}\n" \
             f"🔗 [Link to Article]({random_article.get('pub_url', '#')})\n\n\n" \
             f"Abstract:\n{abstract}\n\n" \
                "--"

    try:
        # ارسال به کاربران
        subscribers = get_subscribers('article_subscribers')
        for user_id in subscribers:
            await context.bot.send_message(chat_id=user_id, text=result, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

        # ارسال به کانال آرشیو
        await context.bot.send_message(chat_id=TARGET, text=result, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    
    except Exception as e:
        print(f"ERROR : {e}")


    try:
        genai.configure(api_key=gen_token)

        model = genai.GenerativeModel("gemini-1.5-flash")
        content = f"""لطفا این مقاله رو به شکل خیلی خوب و با جزيیات بررسی کن و برداشت هات رو به شکل زبان عامیانه فارسی به‌طور کامل شرح بده بطور علمی و دقیق با فرمولها و دلایل حرفه‌ای و دقیقا توضیح بده این مقاله رو.

لینک مقاله و خلاصه‌ای ازش: {result}
دقت کن حدود 8 تا 12 خط باشه توضیحاتت
لطفا انتهای پست هم رفرنس بزار 
"""
        response = await model.generate_content(content)
        text_ai = response.replace("#", "")

        subscribers = get_subscribers('article_subscribers')
        for user_id in subscribers:
            await context.bot.send_message(chat_id=user_id, text=text_ai, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

        # ارسال به کانال آرشیو
        await context.bot.send_message(chat_id=TARGET, text=text_ai, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    



    except Exception as e:
        print(f"ERROR : {e}")




