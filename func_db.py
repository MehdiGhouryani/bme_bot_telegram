import sqlite3



conn=sqlite3.connect('medical_device.db')
cursor=conn.cursor()



class MRI:
    def __init__(self):
        self.data = cursor.execute('SELECT * FROM devices WHERE name="mri"').fetchone()
        
    def get_name(self):
        return self.data[0]

    def get_caption(self):
        return self.data[1]

    def get_txt(self):
        return self.data[2]

    def get_pic(self):
        return self.data[3]




class CTScan:
    def __init__(self):
        self.data = self._get_ct_scan_data()

    def _get_ct_scan_data(self):
        return cursor.execute('SELECT * FROM devices WHERE name="ct_scan"').fetchone()

    def get_name(self):
        return self.data[0]

    def get_caption(self):
        return self.data[1]

    def get_txt(self):
        return self.data[2]

    def get_pic(self):
        return self.data[3]
    


class Sonography:
    def __init__(self):
        self.data = self._get_sonography_data()

    def get_sonography_data(self):
        return cursor.execute('SELECT * FROM devices WHERE name="sonography"').fetchone()

    def get_name(self):
        return self.data[0]

    def get_caption(self):
        return self.data[1]

    def get_txt(self):
        return self.data[2]

    def get_pic(self):
        return self.data[3]
    


class XRay:
    def __init__(self):
        self.data = self._get_xray_data()

    def _get_xray_data(self):
        return cursor.execute('SELECT * FROM devices WHERE name="xray"').fetchone()

    def get_name(self):
        return self.data[0]

    def get_caption(self):
        return self.data[1]

    def get_txt(self):
        return self.data[2]

    def get_pic(self):
        return self.data[3]

    

class Monitoring:
    def __init__(self):
        self.data = self._get_monitoring_data()

    def _get_monitoring_data(self):
        return cursor.execute('SELECT * FROM devices WHERE name="monitoring"').fetchone()

    def get_name(self):
        return self.data[0]

    def get_caption(self):
        return self.data[1]

    def get_txt(self):
        return self.data[2]

    def get_pic(self):
        return self.data[3]

    
