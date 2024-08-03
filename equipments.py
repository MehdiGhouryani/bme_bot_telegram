from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

# لیست دستگاه‌های تشخیصی
Diagnostic_devices = {
    'imaging_devices': ['xray', 'ct_scan', 'mri', 'ultrasound', 'mammography', 'fluoroscopy', 'pet_scan', 'blood_analyzers'],
    'laboratory_devices': ['blood_analyzers', 'electrophoresis_equipment', 'spectrophotometers'],
    'cardiac_devices': ['ecg', 'echocardiography'],
    'neurological_devices': ['eeg', 'emg'],
    'pulmonary_devices': ['spirometer', 'polysomnography', 'pulse_oximetry'],
    'gastrointestinal_devices': ['endoscopy'],
    'ent_diagnostic_devices': ['otoscope', 'audiogram', 'laryngoscope'],
    'ophthalmic_diagnostic_devices': ['ophthalmoscope', 'tonometer', 'slit_lamp']
}

# لیست دستگاه‌های درمانی
therapeutic_devices = {
    'surgical_equipment': ['surgical_instruments', 'electrocautery', 'surgical_laser', 'infusion_pumps', 'blood_pumps', 'robotic_surgical_systems'],
    'orthopedic_equipment': ['prosthetics_orthotics', 'physical_therapy_equipment', 'electrotherapy_devices'],
    'cardiovascular_equipment': ['pacemakers', 'defibrillators'],
    'respiratory_equipment': ['ventilators', 'nebulizers'],
    'other_therapeutic_equipment': ['therapeutic_laser_machines', 'dialysis_machines']
}

# لیست دستگاه‌های مانیتورینگ
monitoring_devices = {
    'cardiac_monitors': ['ecg_monitors', 'automatic_blood_pressure_monitors', 'manual_blood_pressure_monitors'],
    'fetal_maternal_monitors':['maternal_monitors'],
    'fetal_monitors': ['neonatal_monitors', 'fetal_heart_rate_monitors'],
    'blood_glucose_monitors': ['portable_blood_glucose_meters', 'continuous_blood_glucose_monitors']
}

# تابع تولید کلیدها
def generate_keys(device_list,category):
    keys = []
    for device in device_list:
        keys.extend([
            [InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types'), InlineKeyboardButton('معرفی دستگاه', callback_data=f'{device}:definition')],
            [InlineKeyboardButton('ساختار و اجزاء دستگاه', callback_data=f'{device}:structure')],
            [InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation')],
            [InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'), InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')],
            [InlineKeyboardButton(' تکنولوژی‌های مرتبط و مشابه', callback_data=f'{device}:related_technologies')],
            [InlineKeyboardButton('بازگشت به صفحه قبل  ⬅️', callback_data=category)]
        ])
    return keys

# کلاس تشخیصی
class Diagnostic:
    def init(self):
        pass

    async def handle_equipment(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE, category):
        device_list = Diagnostic_devices.get(category)
        if not device_list:
            return
        
        keys = generate_keys(device_list,category)
        index = device_list.index(data)
        reply_markup = InlineKeyboardMarkup(keys[index*5:(index+1)*5])
        await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)

    async def imaging_devices(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_equipment(data, update, context, 'imaging_devices')

    async def laboratory_devices(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_equipment(data, update, context, 'laboratory_devices')

    async def cardiac_devices(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_equipment(data, update, context, 'cardiac_devices')

    async def neurological_devices(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_equipment(data, update, context, 'neurological_devices')

    async def pulmonary_devices(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_equipment(data, update, context, 'pulmonary_devices')


    async def gastrointestinal_devices(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_equipment(data, update, context, 'gastrointestinal_devices')

    async def ent_diagnostic_devices(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_equipment(data, update, context, 'ent_diagnostic_devices')

    async def ophthalmic_diagnostic_devices(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_equipment(data, update, context, 'ophthalmic_diagnostic_devices')



# کلاس درمانی
class Therapeutic:
    def init(self):
        pass

    async def handle_equipment(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE, category):
        device_list = therapeutic_devices.get(category)
        if not device_list:
            return
        
        keys = generate_keys(device_list,category)
        index = device_list.index(data)
        reply_markup = InlineKeyboardMarkup(keys[index*5:(index+1)*5])
        await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)

    async def surgical_equipment(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_equipment(data, update, context, 'surgical_equipment')

    async def orthopedic_equipment(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_equipment(data, update, context, 'orthopedic_equipment')

    async def cardiovascular_equipment(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_equipment(data, update, context, 'cardiovascular_equipment')

    async def respiratory_equipment(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_equipment(data, update, context, 'respiratory_equipment')

    async def other_therapeutic_equipment(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_equipment(data, update, context, 'other_therapeutic_equipment')






# کلاس مانیتورینگ
class Monitoring:
    def init(self):
        pass

    async def handle_equipment(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE, category):
        device_list = monitoring_devices.get(category)
        if not device_list:
            return
        
        keys = generate_keys(device_list,category)
        index = device_list.index(data)
        reply_markup = InlineKeyboardMarkup(keys[index*5:(index+1)*5])
        await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)

    async def cardiac_monitors(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_equipment(data, update, context, 'cardiac_monitors')

    async def fetal_maternal_monitors(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_equipment(data, update, context, 'fetal_maternal_monitors')


    async def fetal_monitors(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_equipment(data, update, context, 'fetal_monitors')

    async def blood_glucose_monitors(self, data, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_equipment(data, update, context, 'blood_glucose_monitors')
