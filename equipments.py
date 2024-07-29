from telegram import InlineKeyboardButton , InlineKeyboardMarkup ,Update 
from telegram.ext import ContextTypes





  

imaging_devices= [
    'xray','ct_scan','mri','ultrasound','mammography','fluoroscopy',
    'pet_scan','blood_analyzers'
    ]


laboratory_devices = ['blood_analyzers','electrophoresis_equipment','spectrophotometers']

cardiac_devices = [ 'ecg','echocardiography']
neurological_devices = ['eeg','emg']
pulmonary_devices = ['spirometer','polysomnography','pulse_oximetry']
gastrointestinal_devices = ['endoscopy']
ent_diagnostic_devices = ['otoscope','audiogram','laryngoscope']
ophthalmic_diagnostic_devices = ['ophthalmoscope','tonometer','slit_lamp']





class diagnostic :

    def init(self):
        pass


    async def medical_imaging(self,data,update : Update , context:ContextTypes.DEFAULT_TYPE):
       
       
        imaging_keys = []
        for device in imaging_devices:
            imaging_keys.append([
                InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types'),
                InlineKeyboardButton('تعریف دستگاه', callback_data=f'{device}:definition')
            ])
            imaging_keys.append([
                InlineKeyboardButton('ساختار و اجزا', callback_data=f'{device}:structure'),
                InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation')
            ])
            imaging_keys.append([
                InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'),
                InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')
            ])
            imaging_keys.append([InlineKeyboardButton('تکنولوژی‌های مرتبط', callback_data=f'{device}:related_technologies')])
            imaging_keys.append([InlineKeyboardButton('بازگشت به منوی قبل', callback_data='medical_imaging')])
        
        
        if data == 'xray':
            reply_markup = InlineKeyboardMarkup(imaging_keys[0:5])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)

        elif data == 'ct_scan':
               
            reply_markup = InlineKeyboardMarkup(imaging_keys[5:10])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


        elif data == 'mri':
               
            reply_markup = InlineKeyboardMarkup(imaging_keys[10:15])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


        elif data == 'ultrasound':
               
            reply_markup = InlineKeyboardMarkup(imaging_keys[15:20])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


        elif data == 'mammography':
               
            reply_markup = InlineKeyboardMarkup(imaging_keys[20:25])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


        elif data == 'fluoroscopy':
               
            reply_markup = InlineKeyboardMarkup(imaging_keys[25:30])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


        elif data == 'pet_scan':
               
            reply_markup = InlineKeyboardMarkup(imaging_keys[30:35])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)





    async def laboratory_equipment(self,data,update : Update , context:ContextTypes.DEFAULT_TYPE):
        labratory_keys = []
        for device in imaging_devices:
                 labratory_keys.append([
                    InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types'),
                    InlineKeyboardButton('تعریف دستگاه', callback_data=f'{device}:definition')
                ])
                 labratory_keys.append([
                     InlineKeyboardButton('ساختار و اجزا', callback_data=f'{device}:structure'),
                     InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation')
                 ])
                 labratory_keys.append([
                     InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'),
                     InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')
                 ])
                 labratory_keys.append([InlineKeyboardButton('تکنولوژی‌های مرتبط', callback_data=f'{device}:related_technologies')])
                 labratory_keys.append([InlineKeyboardButton('بازگشت به منوی قبل', callback_data='laboratory_equipment')])


        if data == 'blood_analyzers':
           reply_markup = InlineKeyboardMarkup(labratory_keys[0:5])
           await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


        elif data == 'electrophoresis_equipment':
               
            reply_markup = InlineKeyboardMarkup(labratory_keys[5:10])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)

    

        elif data == 'spectrophotometers':
               
            reply_markup = InlineKeyboardMarkup(labratory_keys[10:15])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)



    

    async def cardiac_diagnostic_equipment(self,data,update : Update , context:ContextTypes.DEFAULT_TYPE):
            cardiac_keys =[]
            for device in cardiac_devices:
                    cardiac_keys.append([
                        InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types'),
                        InlineKeyboardButton('تعریف دستگاه', callback_data=f'{device}:definition'),
                    ])
                    cardiac_keys.append([
                        InlineKeyboardButton('ساختار و اجزا', callback_data=f'{device}:structure'),
                        InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation')
                    ])
                    cardiac_keys.append([
                        InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'),
                        InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')
                    ])
                    cardiac_keys.append([InlineKeyboardButton('تکنولوژی‌های مرتبط', callback_data=f'{device}:related_technologies')])
                    cardiac_keys.append([InlineKeyboardButton('بازگشت به منوی قبل', callback_data='cardiac_diagnostic_equipment')])


            if data == 'ecg':

                reply_markup = InlineKeyboardMarkup(cardiac_keys[0:5])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


            elif data == 'echocardiography':

                reply_markup = InlineKeyboardMarkup(cardiac_keys[5:10])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)



            

    async def neurological_diagnostic_equipment(self,data,update : Update , context:ContextTypes.DEFAULT_TYPE):
            neurological_keys =[]
            for device in neurological_devices:
                    neurological_keys.append([
                        InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types'),
                        InlineKeyboardButton('تعریف دستگاه', callback_data=f'{device}:definition'),
                    ])
                    neurological_keys.append([
                        InlineKeyboardButton('ساختار و اجزا', callback_data=f'{device}:structure'),
                        InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation')
                    ])
                    neurological_keys.append([
                        InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'),
                        InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')
                    ])
                    neurological_keys.append([InlineKeyboardButton('تکنولوژی‌های مرتبط', callback_data=f'{device}:related_technologies')])
                    neurological_keys.append([InlineKeyboardButton('بازگشت به منوی قبل', callback_data='neurological_diagnostic_equipment')])


            if data == 'ecg':

                reply_markup = InlineKeyboardMarkup(neurological_keys[0:5])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


            elif data == 'emg':

                reply_markup = InlineKeyboardMarkup(neurological_keys[5:10])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)





    async def pulmonary_diagnostic_equipment(self,data,update : Update , context:ContextTypes.DEFAULT_TYPE):
            pulmonary_keys =[]
            for device in pulmonary_devices:
                    pulmonary_keys.append([
                        InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types'),
                        InlineKeyboardButton('تعریف دستگاه', callback_data=f'{device}:definition'),
                    ])
                    pulmonary_keys.append([
                        InlineKeyboardButton('ساختار و اجزا', callback_data=f'{device}:structure'),
                        InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation')
                    ])
                    pulmonary_keys.append([
                        InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'),
                        InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')
                    ])
                    pulmonary_keys.append([InlineKeyboardButton('تکنولوژی‌های مرتبط', callback_data=f'{device}:related_technologies')])
                    pulmonary_keys.append([InlineKeyboardButton('بازگشت به منوی قبل', callback_data='pulmonary_diagnostic_equipment')])


            if data == 'spirometer':

                reply_markup = InlineKeyboardMarkup(pulmonary_keys[0:5])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


            elif data == 'polysomnography':

                reply_markup = InlineKeyboardMarkup(pulmonary_keys[5:10])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


            elif data == 'pulse_oximetry':

                reply_markup = InlineKeyboardMarkup(pulmonary_keys[10:15])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)




    async def gastrointestinal_diagnostic_equipment(self,data,update : Update , context:ContextTypes.DEFAULT_TYPE):
            gastrointestinal_keys =[]
            for device in gastrointestinal_devices:
                    gastrointestinal_keys.append([
                        InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types'),
                        InlineKeyboardButton('تعریف دستگاه', callback_data=f'{device}:definition'),
                    ])
                    gastrointestinal_keys.append([
                        InlineKeyboardButton('ساختار و اجزا', callback_data=f'{device}:structure'),
                        InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation')
                    ])
                    gastrointestinal_keys.append([
                        InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'),
                        InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')
                    ])
                    gastrointestinal_keys.append([InlineKeyboardButton('تکنولوژی‌های مرتبط', callback_data=f'{device}:related_technologies')])
                    gastrointestinal_keys.append([InlineKeyboardButton('بازگشت به منوی قبل', callback_data='gastrointestinal_diagnostic_equipment')])

         
            if data == 'endoscopy':

                reply_markup = InlineKeyboardMarkup(gastrointestinal_keys[0:5])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)





    async def ent_diagnostic_equipment(self,data,update : Update , context:ContextTypes.DEFAULT_TYPE):
            ent_keys =[]
            for device in ent_diagnostic_devices:
                    ent_keys.append([
                        InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types'),
                        InlineKeyboardButton('تعریف دستگاه', callback_data=f'{device}:definition'),
                    ])
                    ent_keys.append([
                        InlineKeyboardButton('ساختار و اجزا', callback_data=f'{device}:structure'),
                        InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation')
                    ])
                    ent_keys.append([
                        InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'),
                        InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')
                    ])
                    ent_keys.append([InlineKeyboardButton('تکنولوژی‌های مرتبط', callback_data=f'{device}:related_technologies')])
                    ent_keys.append([InlineKeyboardButton('بازگشت به منوی قبل', callback_data='ent_diagnostic_equipment')])

            if data == 'otoscope':

                reply_markup = InlineKeyboardMarkup(ent_keys[0:5])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


            elif data == 'audiogram':

                reply_markup = InlineKeyboardMarkup(ent_keys[5:10])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


            elif data == 'laryngoscope':

                reply_markup = InlineKeyboardMarkup(ent_keys[10:15])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)





    async def ophthalmic_diagnostic_equipment(self,data,update : Update , context:ContextTypes.DEFAULT_TYPE):
            ophthalmic_keys =[]
            for device in ophthalmic_diagnostic_devices:
                    ophthalmic_keys.append([
                        InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types'),
                        InlineKeyboardButton('تعریف دستگاه', callback_data=f'{device}:definition'),
                    ])
                    ophthalmic_keys.append([
                        InlineKeyboardButton('ساختار و اجزا', callback_data=f'{device}:structure'),
                        InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation')
                    ])
                    ophthalmic_keys.append([
                        InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'),
                        InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')
                    ])
                    ophthalmic_keys.append([InlineKeyboardButton('تکنولوژی‌های مرتبط', callback_data=f'{device}:related_technologies')])
                    ophthalmic_keys.append([InlineKeyboardButton('بازگشت به منوی قبل', callback_data='ophthalmic_diagnostic_equipment')])


            if data == 'ophthalmoscope':

                reply_markup = InlineKeyboardMarkup(ophthalmic_keys[0:5])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


            elif data == 'tonometer':

                reply_markup = InlineKeyboardMarkup(ophthalmic_keys[5:10])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


            elif data == 'slit_lamp':

                reply_markup = InlineKeyboardMarkup(ophthalmic_keys[10:15])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)












surgical_devices =['surgical_instruments','electrocautery','surgical_laser','infusion_pumps','blood_pumps','robotic_surgical_systems']

orthopedic_devices =['prosthetics_orthotics','physical_therapy_equipment','electrotherapy_devices']

cardiovascular_devices =['pacemakers','defibrillators']

respiratory_devices =['ventilators','nebulizers']

other_therapeutic_devices =['therapeutic_laser_machines','dialysis_machines']

class therapeutic :

    def init(self):
        pass

    
    async def surgical_equipment(self,data,update : Update , context:ContextTypes.DEFAULT_TYPE):
       
       
        surgical_keys = []
        for device in surgical_devices:
            surgical_keys.append([
                InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types'),
                InlineKeyboardButton('تعریف دستگاه', callback_data=f'{device}:definition'),
            ])
            surgical_keys.append([
                InlineKeyboardButton('ساختار و اجزا', callback_data=f'{device}:structure'),
                InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation')
            ])
            surgical_keys.append([
                InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'),
                InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')
            ])
            surgical_keys.append([InlineKeyboardButton('تکنولوژی‌های مرتبط', callback_data=f'{device}:related_technologies')])
            surgical_keys.append([InlineKeyboardButton('بازگشت به منوی قبل', callback_data='surgical_equipment')])
        
        
        if data == 'surgical_instruments':
            reply_markup = InlineKeyboardMarkup(surgical_keys[0:5])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)

        elif data == 'electrocautery':
               
            reply_markup = InlineKeyboardMarkup(surgical_keys[5:10])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


        elif data == 'surgical_laser':
               
            reply_markup = InlineKeyboardMarkup(surgical_keys[10:15])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


        elif data == 'infusion_pumps':
               
            reply_markup = InlineKeyboardMarkup(surgical_keys[15:20])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


        elif data == 'blood_pumps':
               
            reply_markup = InlineKeyboardMarkup(surgical_keys[20:25])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


        elif data == 'robotic_surgical_systems':
               
            reply_markup = InlineKeyboardMarkup(surgical_keys[25:30])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)




    async def orthopedic_equipment(self,data,update : Update , context:ContextTypes.DEFAULT_TYPE):
        orthopedic_keys = []
        for device in orthopedic_devices:
                orthopedic_keys.append([
                    InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types'),
                    InlineKeyboardButton('تعریف دستگاه', callback_data=f'{device}:definition'),
                ])
                orthopedic_keys.append([
                    InlineKeyboardButton('ساختار و اجزا', callback_data=f'{device}:structure'),
                    InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation')
                ])
                orthopedic_keys.append([
                    InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'),
                    InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')
                ])
                orthopedic_keys.append([InlineKeyboardButton('تکنولوژی‌های مرتبط', callback_data=f'{device}:related_technologies')])
                orthopedic_keys.append([InlineKeyboardButton('بازگشت به منوی قبل', callback_data='orthopedic_equipment')])


        if data == 'prosthetics_orthotics':
           reply_markup = InlineKeyboardMarkup(orthopedic_keys[0:5])
           await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


        elif data == 'physical_therapy_equipment':
               
            reply_markup = InlineKeyboardMarkup(orthopedic_keys[5:10])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)

    

        elif data == 'electrotherapy_devices':
               
            reply_markup = InlineKeyboardMarkup(orthopedic_keys[10:15])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


    

    async def cardiovascular_equipment(self,data,update : Update , context:ContextTypes.DEFAULT_TYPE):
            cardiovascular_keys =[]
            for device in cardiovascular_devices:
                    cardiovascular_keys.append([
                        InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types'),
                        InlineKeyboardButton('تعریف دستگاه', callback_data=f'{device}:definition'),
                    ])
                    cardiovascular_keys.append([
                        InlineKeyboardButton('ساختار و اجزا', callback_data=f'{device}:structure'),
                        InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation')
                    ])
                    cardiovascular_keys.append([
                        InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'),
                        InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')
                    ])
                    cardiovascular_keys.append([InlineKeyboardButton('تکنولوژی‌های مرتبط', callback_data=f'{device}:related_technologies')])
                    cardiovascular_keys.append([InlineKeyboardButton('بازگشت به منوی قبل', callback_data='cardiovascular_equipment')])


            if data == 'pacemakers':

                reply_markup = InlineKeyboardMarkup(cardiovascular_keys[0:5])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


            elif data == 'defibrillators':

                reply_markup = InlineKeyboardMarkup(cardiovascular_keys[5:10])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)



        
    async def respiratory_equipment(self,data,update : Update , context:ContextTypes.DEFAULT_TYPE):
            respiratory_keys =[]
            for device in respiratory_devices:
                    respiratory_keys.append([
                        InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types'),
                        InlineKeyboardButton('تعریف دستگاه', callback_data=f'{device}:definition'),
                    ])
                    respiratory_keys.append([
                        InlineKeyboardButton('ساختار و اجزا', callback_data=f'{device}:structure'),
                        InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation')
                    ])
                    respiratory_keys.append([
                        InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'),
                        InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')
                    ])
                    respiratory_keys.append([InlineKeyboardButton('تکنولوژی‌های مرتبط', callback_data=f'{device}:related_technologies')])
                    respiratory_keys.append([InlineKeyboardButton('بازگشت به منوی قبل', callback_data='respiratory_equipment')])


            if data == 'ventilators':

                reply_markup = InlineKeyboardMarkup(respiratory_keys[0:5])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


            elif data == 'nebulizers':

                reply_markup = InlineKeyboardMarkup(respiratory_keys[5:10])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)




    async def other_therapeutic_equipment(self,data,update : Update , context:ContextTypes.DEFAULT_TYPE):
            other_therapeutic_keys =[]
            for device in other_therapeutic_devices:
                    other_therapeutic_keys.append([
                        InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types'),
                        InlineKeyboardButton('تعریف دستگاه', callback_data=f'{device}:definition'),
                    ])
                    other_therapeutic_keys.append([
                        InlineKeyboardButton('ساختار و اجزا', callback_data=f'{device}:structure'),
                        InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation')
                    ])
                    other_therapeutic_keys.append([
                        InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'),
                        InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')
                    ])
                    other_therapeutic_keys.append([InlineKeyboardButton('تکنولوژی‌های مرتبط', callback_data=f'{device}:related_technologies')])
                    other_therapeutic_keys.append([InlineKeyboardButton('بازگشت به منوی قبل', callback_data='other_therapeutic_equipment')])


            if data == 'dialysis_machines':

                reply_markup = InlineKeyboardMarkup(other_therapeutic_keys[0:5])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


            elif data == 'therapeutic_laser_machines':

                reply_markup = InlineKeyboardMarkup(other_therapeutic_keys[5:10])
                await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)







cardiac_monitors_device = ['ecg_monitors','automatic_blood_pressure_monitors','manual_blood_pressure_monitors']
pulse_oximeters_device = ['fingertip_pulse_oximeters','hospital_pulse_oximeters']
fetal_monitors_device = ['neonatal_monitors','fetal_heart_rate_monitors']
blood_glucose_monitors_device =['portable_blood_glucose_meters','continuous_blood_glucose_monitors']    


class monitoring:
     
    def init(self):
        pass
    
    async def cardiac_monitors(self,data,update : Update , context:ContextTypes.DEFAULT_TYPE):
       
       
        cardiac_monitors_keys = []
        for device in cardiac_monitors_device:
            cardiac_monitors_keys.append([
                InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types'),
                InlineKeyboardButton('تعریف دستگاه', callback_data=f'{device}:definition'),
            ])
            cardiac_monitors_keys.append([
                InlineKeyboardButton('ساختار و اجزا', callback_data=f'{device}:structure'),
                InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation')
            ])
            cardiac_monitors_keys.append([
                InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'),
                InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')
            ])
            cardiac_monitors_keys.append([InlineKeyboardButton('تکنولوژی‌های مرتبط', callback_data=f'{device}:related_technologies')])
            cardiac_monitors_keys.append([InlineKeyboardButton('بازگشت به منوی قبل', callback_data='cardiac_monitors')])
        
        
        if data == 'ecg_monitors':
            reply_markup = InlineKeyboardMarkup(cardiac_monitors_keys[0:5])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)

        elif data == 'automatic_blood_pressure_monitors':
               
            reply_markup = InlineKeyboardMarkup(cardiac_monitors_keys[5:10])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


        elif data == 'manual_blood_pressure_monitors':
               
            reply_markup = InlineKeyboardMarkup(cardiac_monitors_keys[10:15])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)




    async def pulse_oximeters(self,data,update : Update , context:ContextTypes.DEFAULT_TYPE):
        pulse_oximeters_keys = []
        for device in pulse_oximeters_device:
                pulse_oximeters_keys.append([
                    InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types'),
                    InlineKeyboardButton('تعریف دستگاه', callback_data=f'{device}:definition'),
                ])
                pulse_oximeters_keys.append([
                    InlineKeyboardButton('ساختار و اجزا', callback_data=f'{device}:structure'),
                    InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation')
                ])
                pulse_oximeters_keys.append([
                    InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'),
                    InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')
                ])
                pulse_oximeters_keys.append([InlineKeyboardButton('تکنولوژی‌های مرتبط', callback_data=f'{device}:related_technologies')])
                pulse_oximeters_keys.append([InlineKeyboardButton('بازگشت به منوی قبل', callback_data='pulse_oximeters')])


        if data == 'fingertip_pulse_oximeters':
           reply_markup = InlineKeyboardMarkup(pulse_oximeters_keys[0:5])
           await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


        elif data == 'hospital_pulse_oximeters':
               
            reply_markup = InlineKeyboardMarkup(pulse_oximeters_keys[5:10])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)

    


    async def fetal_monitors(self,data,update : Update , context:ContextTypes.DEFAULT_TYPE):
        fetal_monitors_keys = []
        for device in fetal_monitors_device:
                fetal_monitors_keys.append([
                    InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types'),
                    InlineKeyboardButton('تعریف دستگاه', callback_data=f'{device}:definition'),
                ])
                fetal_monitors_keys.append([
                    InlineKeyboardButton('ساختار و اجزا', callback_data=f'{device}:structure'),
                    InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation')
                ])
                fetal_monitors_keys.append([
                    InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'),
                    InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')
                ])
                fetal_monitors_keys.append([InlineKeyboardButton('تکنولوژی‌های مرتبط', callback_data=f'{device}:related_technologies')])
                fetal_monitors_keys.append([InlineKeyboardButton('بازگشت به منوی قبل', callback_data='fetal_monitors')])


        if data == 'neonatal_monitors':
           reply_markup = InlineKeyboardMarkup(fetal_monitors_keys[0:5])
           await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


        elif data == 'fetal_heart_rate_monitors':
               
            reply_markup = InlineKeyboardMarkup(fetal_monitors_keys[5:10])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)

    


    async def blood_glucose_monitors(self,data,update : Update , context:ContextTypes.DEFAULT_TYPE):
        blood_glucose_monitors_keys = []
        for device in blood_glucose_monitors_device:
                blood_glucose_monitors_keys.append([
                    InlineKeyboardButton('انواع دستگاه', callback_data=f'{device}:types'),
                    InlineKeyboardButton('تعریف دستگاه', callback_data=f'{device}:definition'),
                ])
                blood_glucose_monitors_keys.append([
                    InlineKeyboardButton('ساختار و اجزا', callback_data=f'{device}:structure'),
                    InlineKeyboardButton('نحوه عملکرد', callback_data=f'{device}:operation')
                ])
                blood_glucose_monitors_keys.append([
                    InlineKeyboardButton('مزایا و معایب', callback_data=f'{device}:advantages_disadvantages'),
                    InlineKeyboardButton('نکات ایمنی', callback_data=f'{device}:safety')
                ])
                blood_glucose_monitors_keys.append([InlineKeyboardButton('تکنولوژی‌های مرتبط', callback_data=f'{device}:related_technologies')])
                blood_glucose_monitors_keys.append([InlineKeyboardButton('بازگشت به منوی قبل', callback_data='blood_glucose_monitors')])


        if data == 'portable_blood_glucose_meters':
           reply_markup = InlineKeyboardMarkup(blood_glucose_monitors_keys[0:5])
           await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


        elif data == 'continuous_blood_glucose_monitors':
               
            reply_markup = InlineKeyboardMarkup(blood_glucose_monitors_keys[5:10])
            await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)

    
