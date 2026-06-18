from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

def get_gps(image_path):
    try:
        img = Image.open(image_path)
        exif = img.getexif()
        if not exif: return None

        gps_raw = exif.get_ifd(34853) 
        if not gps_raw: return None

        gps_data = {GPSTAGS.get(k, k): v for k, v in gps_raw.items()}

        def to_deg(val):
            return float(val[0]) + (float(val[1])/60.0) + (float(val[2])/3600.0)

        lat = to_deg(gps_data['GPSLatitude'])
        if gps_data['GPSLatitudeRef'] == 'S': lat = -lat
        lon = to_deg(gps_data['GPSLongitude'])
        if gps_data['GPSLongitudeRef'] == 'W': lon = -lon

        return lat, lon

    except Exception as e:
        return None