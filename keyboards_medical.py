# keyboards.py
from telegram import InlineKeyboardButton

class KeyboardsManager:
    def init(self):
        pass
    
    def get_keyboard_main_categories(self):
        return [
            [InlineKeyboardButton('تجهیزات تشخیصی', callback_data='diagnostic_equipment')],
            [InlineKeyboardButton('تجهیزات درمانی', callback_data='therapeutic_equipment')],
            [InlineKeyboardButton('تجهیزات مانیتورینگ', callback_data='monitoring_equipment')],
            [InlineKeyboardButton('تجهیزات پزشکی عمومی', callback_data='general_medical_equipment')],
            [InlineKeyboardButton('تجهیزات پشتیبانی و توانبخشی', callback_data='support_rehabilitation_equipment')],
            [InlineKeyboardButton('تجهیزات تخصصی', callback_data='specialized_equipment')],
            [InlineKeyboardButton('تجهیزات مراقبت در منزل', callback_data='home_care_equipment')],
        ]
    



   #دستگاه های تشخصیصی


    def get_keyboard_diagnostic(self):
        return [
            [InlineKeyboardButton('تصویربرداری پزشکی', callback_data='imaging_devices')],
            [InlineKeyboardButton('تجهیزات آزمایشگاهی', callback_data='laboratory_devices')],
            [InlineKeyboardButton('تجهیزات تشخیصی قلبی', callback_data='cardiac_devices')],
            [InlineKeyboardButton('تجهیزات تشخیصی نورولوژیکی', callback_data='neurological_devices')],
            [InlineKeyboardButton('تجهیزات تشخیصی ریوی', callback_data='pulmonary_devices')],
            [InlineKeyboardButton('تجهیزات تشخیصی گوارشی', callback_data='gastrointestinal_devices')],
            [InlineKeyboardButton('تجهیزات تشخیصی گوش، حلق و بینی', callback_data='ent_diagnostic_devices')],
            [InlineKeyboardButton('تجهیزات تشخیصی چشم‌پزشکی', callback_data='ophthalmic_diagnostic')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='back_to_main')],
        ]

    def get_keyboard_imaging_devices(self):
        return [
            [InlineKeyboardButton('Xray', callback_data='xray')],
            [InlineKeyboardButton(' CT SCAN', callback_data='ct_scan')],
            [InlineKeyboardButton(' (MRI) تصویربرداری مغناطیسی', callback_data='mri')],
            [InlineKeyboardButton('سونوگرافی', callback_data='ultrasound')],
            [InlineKeyboardButton('ماموگرافی', callback_data='mammography')],
            [InlineKeyboardButton('فلوروسکوپی', callback_data='fluoroscopy')],
            [InlineKeyboardButton('پت اسکن', callback_data='pet_scan')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='diagnostic_equipment')],
        ]

    def get_keyboard_laboratory_devices(self):
        return [
            [InlineKeyboardButton('آنالایزرهای خون', callback_data='blood_analyzers')],
            [InlineKeyboardButton('اسپکتروفتومترها', callback_data='spectrophotometers')],
            [InlineKeyboardButton('دستگاه‌های الکتروفورز', callback_data='electrophoresis')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='diagnostic_equipment')],
        ]

    def get_keyboard_cardiac_devices(self):
        return [
            [InlineKeyboardButton(' (ECG) الکتروکاردیوگراف', callback_data='ecg')],
            [InlineKeyboardButton('اکوکاردیوگرافی', callback_data='echocardiography')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='diagnostic_equipment')],
        ]

    def get_keyboard_neurological_devices(self):
        return [
            [InlineKeyboardButton('(EEG) الکتروانسفالوگراف', callback_data='eeg')],
            [InlineKeyboardButton('(EMG) الکترومیوگراف', callback_data='emg')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='diagnostic_equipment')],
        ]

    def get_keyboard_pulmonary_devices(self):
        return [
            [InlineKeyboardButton('اسپیرومتر', callback_data='spirometer')],
            [InlineKeyboardButton('پلی‌سومنوگرافی', callback_data='polysomnography')],
            [InlineKeyboardButton('پالس اکسیمتری', callback_data='pulse_oximetry')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='diagnostic_equipment')],
        ]

    def get_keyboard_gastrointestinal_devices(self):
        return [
            [InlineKeyboardButton('اندوسکوپی', callback_data='endoscopy')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='diagnostic_equipment')],
        ]

    def get_keyboard_ent_diagnostic_devices(self):
        return [
            [InlineKeyboardButton('اتوسکوپ', callback_data='otoscope')],
            [InlineKeyboardButton('دستگاه شنوایی سنجی', callback_data='audiogram')],
            [InlineKeyboardButton('لارنگوسکوپ', callback_data='laryngoscope')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='diagnostic_equipment')],
        ]

    def get_keyboard_ophthalmic_diagnostic(self):
        return [
            [InlineKeyboardButton('افتالموسکوپ', callback_data='ophthalmoscope')],
            [InlineKeyboardButton('تونومتر', callback_data='tonometer')],
            [InlineKeyboardButton('اسلیت لامپ', callback_data='slit_lamp')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='diagnostic_equipment')],
        ]














#دستگاه های درمانی 


    def get_keyboard_therapeutic(self):
        return [
            [InlineKeyboardButton('تجهیزات جراحی', callback_data='surgical_equipment')],
            [InlineKeyboardButton('تجهیزات ارتوپدی', callback_data='orthopedic_therapeutic')],
            [InlineKeyboardButton('تجهیزات قلبی و عروقی', callback_data='cardiovascular_therapeutic')],
            [InlineKeyboardButton('تجهیزات تنفسی', callback_data='respiratory_equipment')],
            [InlineKeyboardButton('تجهیزات دیگر درمانی', callback_data='other_therapeutic_equipment')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='back_to_main')],
        ]

    def get_keyboard_surgical_equipment(self):
        return [
            [InlineKeyboardButton('ابزارهای جراحی', callback_data='surgical_instruments')],
            [InlineKeyboardButton('الکتروکوتر', callback_data='electrocautery')],
            [InlineKeyboardButton('لیزر جراحی', callback_data='surgical_laser')],
            [InlineKeyboardButton('پمپ‌های تزریق', callback_data='infusion_pumps')],
            [InlineKeyboardButton('پمپ‌های خون', callback_data='blood_pumps')],
            [InlineKeyboardButton('دستگاه‌های جراحی روباتیک', callback_data='robo_surgical')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='therapeutic_equipment')],
        ]

    def get_keyboard_orthopedic_therapeutic(self):
        return [
            [InlineKeyboardButton('پروتزها و ارتزها', callback_data='prosthes')],
            [InlineKeyboardButton('دستگاه‌های فیزیوتراپی', callback_data='physical_therapy')],
            [InlineKeyboardButton('دستگاه‌های الکتروتراپی', callback_data='electrotherapy')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='therapeutic_equipment')],
        ]

    def get_keyboard_cardiovascular_therapeutic(self):
        return [
            [InlineKeyboardButton('(PCR) پی سی آر ', callback_data='PCR')],
            [InlineKeyboardButton(' دفیبریلاتور', callback_data='defibr')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='therapeutic_equipment')],
        ]

    def get_keyboard_respiratory_equipment(self):
        return [
            [InlineKeyboardButton('ونتیلاتورها', callback_data='ventilators')],
            [InlineKeyboardButton('نبولایزرها', callback_data='nebulizers')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='therapeutic_equipment')],
        ]

    def get_keyboard_other_therapeutic_equipment(self):
        return [
            [InlineKeyboardButton('دستگاه‌های دیالیز', callback_data='dialysis')],
            [InlineKeyboardButton('دستگاه‌های لیزر درمانی', callback_data='therapy_laser')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='therapeutic_equipment')],
        ]













#دستگاه های نظارتی

    def get_keyboard_monitoring(self):
        return [
            [InlineKeyboardButton('مانیتورهای علائم حیاتی', callback_data='cardiac_monitors')],
            [InlineKeyboardButton('مانیتورهای جنینی و مادر', callback_data='fetal_maternal_monitors')],
            [InlineKeyboardButton('مانیتورهای گلوکز خون', callback_data='blood_glucose_monitors')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='back_to_main')],
        ]


    def get_keyboard_cardiac_monitors(self):
        return [
            [InlineKeyboardButton('مانیتورهای الکتروکاردیوگرافی', callback_data='ecg_monitors')],
            [InlineKeyboardButton('دستگاه‌های اندازه‌گیری فشار خون اتوماتیک', callback_data='automatic_pressure')],
            [InlineKeyboardButton('دستگاه‌های اندازه‌گیری فشار خون دستی', callback_data='manual_pressure')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='monitoring_equipment')],
        ]


    def get_keyboard_fetal_maternal_monitors(self):
        return [
            [InlineKeyboardButton('مانیتورهای جنینی', callback_data='fetal_monitors')],
            [InlineKeyboardButton('مانیتورهای مادر', callback_data='maternal')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='monitoring_equipment')],
        ]

    def get_keyboard_fetal_monitors(self):
        return [
            [InlineKeyboardButton('مانیتورهای نیوناتال', callback_data='neonatal_monitors')],
            [InlineKeyboardButton('مانیتورهای قلبی جنین', callback_data='fetal_heart_rate')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='monitoring_equipment')],
        ]

    def get_keyboard_blood_glucose_monitors(self):
        return [
            [InlineKeyboardButton('دستگاه‌های اندازه‌گیری گلوکز خون قابل حمل', callback_data='portable_glucose')],
            [InlineKeyboardButton('دستگاه‌های اندازه‌گیری گلوکز خون مداوم', callback_data='contine_glucose')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='monitoring_equipment')],
        ]
    













#تجهیزات عمومی 

    def get_keyboard_general_medical(self):
        return [
            [InlineKeyboardButton('تجهیزات بیمارستانی', callback_data='hospital_equipment')],
            [InlineKeyboardButton('تجهیزات اورژانسی', callback_data='emergency_equipment')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='back_to_main')],
        ]

    def get_keyboard_hospital_equipment(self):
        return [
            [InlineKeyboardButton('تخت‌های بیمارستانی', callback_data='hospital_beds')],
            [InlineKeyboardButton('استریلیزاتورها', callback_data='sterilizers')],
            [InlineKeyboardButton('ترالی‌ها', callback_data='medical_trolleys')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='general_medical_equipment')],
        ]


    def get_keyboard_emergency_equipment(self):
        return [
            [InlineKeyboardButton('دستگاه های تنفس مصنوعی', callback_data='resuscitation')],
            [InlineKeyboardButton('آمبوبگ ها', callback_data='ambu_bags')],
            [InlineKeyboardButton('دستگاه های CPR', callback_data='cpr')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='general_medical_equipment')],
        ]

    











# تجهیزات توانبخشی

    def get_keyboard_rehabilitation_and_support(self):
        return [
            [InlineKeyboardButton('تجهیزات توانبخشی', callback_data='rehabilitation')],
            [InlineKeyboardButton('تجهیزات پشتیبانی بیمار', callback_data='patient_support')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='back_to_main')],
        ]

    def get_keyboard_rehabilitation(self):
        return [
            [InlineKeyboardButton('تنس (TENS Units)', callback_data='tens_units')],
            [InlineKeyboardButton('دستگاه‌های الکتروتراپی عضلانی (EMS Units)', callback_data='ems_units')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='support_rehabilitation_equipment')],
        ]

    def get_keyboard_patient_support(self):
        return [
            [InlineKeyboardButton('تشک‌های فشارمتغیر', callback_data='pressure_relief')],
            [InlineKeyboardButton('دستگاه‌های بالابر بیمار', callback_data='patient_lifts')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='support_rehabilitation_equipment')],
        ]

   

   









# تجهیزات تخصصی

    def get_keyboard_specialized_equipment(self):
        return [
            [InlineKeyboardButton('تجهیزات تخصصی قلب و عروق', callback_data='cardiovascular_equipment')],
            [InlineKeyboardButton(' تجهیزات تخصصی نورولوژی', callback_data='neurology_equipment')],
            [InlineKeyboardButton('تجهیزات تخصصی ارتوپدی', callback_data='orthopedic_equipment')],
            [InlineKeyboardButton('تجهیزات تخصصی زنان و زایمان', callback_data='obstetrics_and_gynecology_equipment')],
            [InlineKeyboardButton('تجهیزات تخصصی گوش و حلق و بینی', callback_data='ent_equipment')],
            [InlineKeyboardButton('تجهیزات تخصصی دندانپزشکی', callback_data='dental_equipment')],
            [InlineKeyboardButton('تجهیزات تخصصی پوست', callback_data='dermatology_equipment')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='back_to_main')],
        ]

        

    def get_keyboard_cardiovascular_equipment(self):
        return [
            [InlineKeyboardButton('کاتترهای قلبی', callback_data='catheters')],
            [InlineKeyboardButton('استنت‌ها', callback_data='stents')],
            [InlineKeyboardButton('دیفیبریلاتورهای کاشتنی', callback_data='implantable')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='specialized_equipment')],
        ]

    def get_keyboard_neurology_equipment(self):
        return [
            [InlineKeyboardButton('دستگاه‌های الکتروانسفالوگرافی', callback_data='eeg_machines')],
            [InlineKeyboardButton('دستگاه‌های تحریک مغناطیسی', callback_data='tms_machines')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='specialized_equipment')],
        ]

    def get_keyboard_orthopedic_equipment(self):
        return [
            [InlineKeyboardButton('دستگاه‌های فیکساتور خارجی', callback_data='external_fixators')],
            [InlineKeyboardButton('پروتزهای ارتوپدی', callback_data='prosthetics')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='specialized_equipment')],
        ]

    def get_keyboard_obstetrics_and_gynecology_equipment(self):
        return [
            [InlineKeyboardButton('دستگاه‌های سونوگرافی تخصصی زنان', callback_data='obgyn')],
            [InlineKeyboardButton('سیستم‌های پایش جنین', callback_data='fetals')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='specialized_equipment')],
        ]

    def get_keyboard_ent_equipment(self):
        return [
            [InlineKeyboardButton('آندوسکوپ‌های گوش', callback_data='ear_endoscopes')],
            [InlineKeyboardButton('دستگاه‌های آزمون شنوایی', callback_data='audiometry_equipment')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='specialized_equipment')],
        ]

    def get_keyboard_dental_equipment(self):
        return [
            [InlineKeyboardButton('یونیت‌های دندانپزشکی', callback_data='dental_units')],
            [InlineKeyboardButton('دستگاه‌های تصویر برداری پانورامیک', callback_data='panoramic')],
            [InlineKeyboardButton('لیزرهای دندانپزشکی', callback_data='dental_lasers')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='specialized_equipment')],
        ]

    def get_keyboard_dermatology_equipment(self):
        return [
            [InlineKeyboardButton('درماتوسکوپ‌ها', callback_data='dermatoscopes')],
            [InlineKeyboardButton('لیزرهای پوستی', callback_data='derma_laser')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='specialized_equipment')],
        ]













# تجهیزات مراقبت خانگی


    def get_keyboard_home_care_equipment(self):
        return [
            [InlineKeyboardButton('تجهیزات مراقبت روزانه', callback_data='daily_care_equipment')],
            [InlineKeyboardButton('تجهیزات تنفسی خانگی', callback_data='home_respiratory_equipment')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='back_to_main')],
        ]

    def get_keyboard_daily_care_equipment(self):
        return [
            [InlineKeyboardButton('دستگاه‌های اندازه‌گیری فشار خون خانگی', callback_data='home_blood')],
            [InlineKeyboardButton('دستگاه‌های اندازه‌گیری گلوکز خون خانگی', callback_data='home_glucose')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='home_care_equipment')],
        ]

    def get_keyboard_home_respiratory_equipment(self):
        return [
            [InlineKeyboardButton('اکسیژن‌سازها', callback_data='oxygen')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data='home_care_equipment')],
        ]
