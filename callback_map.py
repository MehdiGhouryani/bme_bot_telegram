
from equipments import *


diagnostic_class = diagnostic()
therapeutic_class = therapeutic()
monitoring_class = monitoring()
class callback_map:
    def __init__(self):
        pass

    def callback_map_diagnostic(self):
        
        # DIAGNOSTIC

        callback_map = {}

        medical_imaging_keys = [
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


        for keys in medical_imaging_keys:
            callback_map[keys] = diagnostic_class.medical_imaging

        for keys in laboratory_keys:
            callback_map[keys] = diagnostic_class.laboratory_equipment

        for keys in cardiac_keys:
            callback_map[keys] = diagnostic_class.cardiac_diagnostic_equipment

        for keys in neurological_keys:
            callback_map[keys] =diagnostic_class.neurological_diagnostic_equipment 

        for keys in pulmonary_keys:
            callback_map[keys] =diagnostic_class.pulmonary_diagnostic_equipment

        for keys in gastrointestinal_keys:
            callback_map[keys] = diagnostic_class.gastrointestinal_diagnostic_equipment

        for keys in ent_diagnostic_keys:
            callback_map[keys] = diagnostic_class.ent_diagnostic_equipment
    
        for keys in ophthalmic_diagnostic:
            callback_map[keys] = diagnostic_class.ophthalmic_diagnostic_equipment

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
        pulse_oximeters_device = ['fingertip_pulse_oximeters','hospital_pulse_oximeters']
        fetal_monitors_device = ['neonatal_monitors','fetal_heart_rate_monitors']
        blood_glucose_monitors_device =['portable_blood_glucose_meters','continuous_blood_glucose_monitors']    


        for keys in cardiac_monitors_device:
            callback_map[keys] = monitoring_class.cardiac_monitors

        for keys in pulse_oximeters_device:
            callback_map[keys] =monitoring_class.pulse_oximeters

        for keys in fetal_monitors_device:
            callback_map[keys] =monitoring_class.fetal_monitors
            
        for keys in blood_glucose_monitors_device:
            callback_map[keys] = monitoring_class.blood_glucose_monitors


        
        return callback_map









