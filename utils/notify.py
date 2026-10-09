from utils.whatsapp import whatsapp_gonder
def hatirlat_wp(nums, mesaj):
    try: return whatsapp_gonder(nums, mesaj)
    except Exception as e: return {'gonderilen':0,'fail':nums,'hata':str(e)}
