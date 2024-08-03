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
            [InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation'),InlineKeyboardButton(' تکنولوژی‌های مشابه', callback_data=f'{device}:related_technologies')],
            [InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'), InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')],
            [InlineKeyboardButton('بازگشت به صفحه قبل ⬅️', callback_data=category)],
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

























diagnostic_class = Diagnostic()
therapeutic_class = Therapeutic()
monitoring_class = Monitoring()

class callback_map:
    def __init__(self):
        pass

    def callback_map_diagnostic(self):
        
        # DIAGNOSTIC

        callback_map = {}

        imaging_devices_keys = [
        'xray','ct_scan','mri','ultrasound','mammography','fluoroscopy',
        'pet_scan'
        ]


        laboratory_keys =['blood_analyzers','electrophoresis_equipment','spectrophotometers']

        cardiac_keys = [ 'ecg','echocardiography']

        neurological_keys = ['eeg','emg']

        pulmonary_keys = ['spirometer','polysomnography','pulse_oximetry']

        gastrointestinal_keys = ['endoscopy']

        ent_diagnostic_keys = ['otoscope','audiogram','laryngoscope']

        ophthalmic_diagnostic = ['ophthalmoscope','tonometer','slit_lamp']


        for keys in imaging_devices_keys:
            callback_map[keys] = diagnostic_class.imaging_devices

        for keys in laboratory_keys:
            callback_map[keys] = diagnostic_class.laboratory_devices

        for keys in cardiac_keys:
            callback_map[keys] = diagnostic_class.cardiac_devices

        for keys in neurological_keys:
            callback_map[keys] =diagnostic_class.neurological_devices 

        for keys in pulmonary_keys:
            callback_map[keys] =diagnostic_class.pulmonary_devices

        for keys in gastrointestinal_keys:
            callback_map[keys] = diagnostic_class.gastrointestinal_devices

        for keys in ent_diagnostic_keys:
            callback_map[keys] = diagnostic_class.ent_diagnostic_devices
    
        for keys in ophthalmic_diagnostic:
            callback_map[keys] = diagnostic_class.ophthalmic_diagnostic_devices

        return callback_map





    def callback_map_therapeutic(self):
        

        callback_map ={}


        surgical_devices =['surgical_instruments','electrocautery','surgical_laser','infusion_pumps','blood_pumps','robotic_surgical_systems']
        orthopedic_devices =['prosthetics_orthotics','physical_therapy_equipment','electrotherapy_devices']
        cardiovascular_devices =['pacemakers','defibrillators']
        respiratory_devices =['ventilators','nebulizers']
        other_therapeutic_devices =['therapeutic_laser_machines','dialysis_machines']


        for keys in surgical_devices:
            callback_map[keys] =therapeutic_class.surgical_equipment

        for keys in orthopedic_devices:
            callback_map[keys] =therapeutic_class.orthopedic_equipment

        for keys in cardiovascular_devices:
            callback_map[keys] =therapeutic_class.cardiovascular_equipment

        for keys in respiratory_devices:
            callback_map[keys] =therapeutic_class.respiratory_equipment

        for keys in other_therapeutic_devices:
            callback_map[keys] =therapeutic_class.other_therapeutic_equipment


        return callback_map



    def callback_map_monitoring(self):

        callback_map ={}    
        cardiac_monitors_device = ['ecg_monitors','automatic_blood_pressure_monitors','manual_blood_pressure_monitors']
        fetal_maternal_monitors=['maternal_monitors']
        fetal_monitors_device = ['neonatal_monitors','fetal_heart_rate_monitors']
        blood_glucose_monitors_device =['portable_blood_glucose_meters','continuous_blood_glucose_monitors']    


        for keys in cardiac_monitors_device:
            callback_map[keys] = monitoring_class.cardiac_monitors

        for keys in fetal_maternal_monitors:
             callback_map[keys] =monitoring_class.fetal_maternal_monitors
        for keys in fetal_monitors_device:
            callback_map[keys] =monitoring_class.fetal_monitors
            
        for keys in blood_glucose_monitors_device:
            callback_map[keys] = monitoring_class.blood_glucose_monitors


        
        return callback_map









