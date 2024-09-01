from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from main import Diagnostic,Therapeutic,Monitoring,GeneralEquipment,SpecializedEquipment,RehabilitationAndSupport,HomeCareEquipment

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
    'orthopedic_equipment_therapeutic': ['prosthetics_orthotics', 'physical_therapy_equipment', 'electrotherapy_devices'],
    'cardiovascular_equipment_therapeutic': ['pacemakers', 'defibrillators'],
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


# لیست دستگاه‌های تجهیزات عمومی
general_equipment_devices = {
    'hospital_equipment': ['hospital_beds','sterilizers','medical_trolleys',],
    
    'emergency_equipment': ['resuscitation','ambu_bags', 'cpr','defibrillators']
}



# لیست دستگاه‌های تجهیزات تخصصی
specialized_equipment_devices = {
    'cardiovascular_equipment': ['cardiac_catheters','stents','pacemakers','implantable_defibrillators'],
    'neurology_equipment': ['eeg_machines','transcranial_magnetic_stimulation'],
    'orthopedic_equipment': ['external_fixators','orthopedic_prosthetics'],
    'obstetrics_gynecology_equipment': ['ob_gyn_ultrasound_machines','fetal_monitoring_systems'],
    'ent_equipment': ['ear_endoscopes','audiometry_equipment'],
    'dental_equipment': ['dental_units','panoramic_xray_machines','dental_lasers'],
    'dermatology_equipment': ['dermatoscopes','dermatological_lasers']
}


# لیست دستگاه‌های تجهیزات توانبخشی و پشتیبانی بیمار
rehabilitation_and_support_devices = {
    # 'rehabilitation_equipment': ['electric_wheelchairs','electrotherapy_devices'],
    'rehabilitation':['tens_units','ems_units'],
    'patient_support': ['pressure_relief_mattresses','patient_lifts']
}




# لیست دستگاه‌های تجهیزات مراقبت در منزل
home_care_equipment_devices = {
        'daily_care_equipment':['home_blood_pressure_monitors','home_blood_glucose_meters'],
        'home_respiratory_equipment':['oxygen_concentrators']

}











diagnostic_class = Diagnostic()
therapeutic_class = Therapeutic()
monitoring_class = Monitoring()
general_class = GeneralEquipment()
specialized_class =SpecializedEquipment()
rehabilitation_class =RehabilitationAndSupport()
homecare_class = HomeCareEquipment()


class callback_map:
    def __init__(self):
        pass

    def callback_map_diagnostic(self):
        
        # DIAGNOSTIC

        callback_map = {}


        for keys in Diagnostic_devices['imaging_devices']:
            callback_map[keys] = diagnostic_class.imaging_devices

        for keys in Diagnostic_devices['laboratory_devices']:
            callback_map[keys] = diagnostic_class.laboratory_devices

        for keys in Diagnostic_devices['cardiac_devices']:
            callback_map[keys] = diagnostic_class.cardiac_devices

        for keys in Diagnostic_devices['neurological_devices']:
            callback_map[keys] =diagnostic_class.neurological_devices 

        for keys in Diagnostic_devices['pulmonary_devices']:
            callback_map[keys] =diagnostic_class.pulmonary_devices

        for keys in Diagnostic_devices['gastrointestinal_devices']:
            callback_map[keys] = diagnostic_class.gastrointestinal_devices

        for keys in Diagnostic_devices['ent_diagnostic_devices']:
            callback_map[keys] = diagnostic_class.ent_diagnostic_devices
    
        for keys in Diagnostic_devices['ophthalmic_diagnostic_devices']:
            callback_map[keys] = diagnostic_class.ophthalmic_diagnostic_devices

        return callback_map





    def callback_map_therapeutic(self):
        

        callback_map ={}


        for keys in therapeutic_devices['surgical_equipment']:
            callback_map[keys] =therapeutic_class.surgical_equipment

        for keys in therapeutic_devices['orthopedic_equipment_therapeutic']:
            callback_map[keys] =therapeutic_class.orthopedic_equipment_therapeutic

        for keys in therapeutic_devices['cardiovascular_equipment_therapeutic']:
            callback_map[keys] =therapeutic_class.cardiovascular_equipment_therapeutic

        for keys in therapeutic_devices['respiratory_equipment']:
            callback_map[keys] =therapeutic_class.respiratory_equipment

        for keys in therapeutic_devices['other_therapeutic_equipment']:
            callback_map[keys] =therapeutic_class.other_therapeutic_equipment


        return callback_map



    def callback_map_monitoring(self):

        callback_map ={}    


        for keys in monitoring_devices['cardiac_monitors']:
            callback_map[keys] = monitoring_class.cardiac_monitors

        for keys in monitoring_devices['fetal_maternal_monitors']:
             callback_map[keys] =monitoring_class.fetal_maternal_monitors
        for keys in monitoring_devices['fetal_monitors']:
            callback_map[keys] =monitoring_class.fetal_monitors
            
        for keys in monitoring_devices['blood_glucose_monitors']:
            callback_map[keys] = monitoring_class.blood_glucose_monitors


        
        return callback_map





    def callback_map_general_equipment(self):
        callback_map = {}
    
        for device in general_equipment_devices['hospital_equipment']:
            callback_map[device] = general_class.hospital_equipment
    
        for device in general_equipment_devices['emergency_equipment']:
            callback_map[device] = general_class.emergency_equipment

        return callback_map
    




    def callback_map_specialized_equipment(self):
        callback_map = {}
    
        for device in specialized_equipment_devices['cardiovascular_equipment']:
            callback_map[device] = specialized_class.cardiovascular_equipment
    
        for device in specialized_equipment_devices['neurology_equipment']:
            callback_map[device] = specialized_class.neurology_equipment
    
        for device in specialized_equipment_devices['orthopedic_equipment']:
            callback_map[device] = specialized_class.orthopedic_equipment
    
        for device in specialized_equipment_devices['obstetrics_gynecology_equipment']:
            callback_map[device] = specialized_class.obstetrics_gynecology_equipment
    
        for device in specialized_equipment_devices['ent_equipment']:
            callback_map[device] = specialized_class.ent_equipment
    
        for device in specialized_equipment_devices['dental_equipment']:
            callback_map[device] = specialized_class.dental_equipment
    
        for device in specialized_equipment_devices['dermatology_equipment']:
            callback_map[device] = specialized_class.dermatology_equipment
    
        return callback_map
    
    
    def callback_map_rehabilitation_and_support(self):
        callback_map = {}
    
        # for device in rehabilitation_and_support_devices['rehabilitation_equipment']:
        #     callback_map[device] = rehabilitation_class.rehabilitation_equipment
    
        for device in rehabilitation_and_support_devices['rehabilitation']:
            callback_map[device] = rehabilitation_class.rehabilitation

        for device in rehabilitation_and_support_devices['patient_support']:
            callback_map[device] = rehabilitation_class.patient_support
    
        return callback_map
    

    def callback_map_home_care_equipment(self):
        callback_map = {}
    
        for device in home_care_equipment_devices['daily_care_equipment']:
            callback_map[device] = homecare_class.daily_care_equipment

        for device in home_care_equipment_devices['home_respiratory_equipment']:   
            callback_map[device] = homecare_class.home_respiratory_equipment
    
        return callback_map
    
    
    
    
    