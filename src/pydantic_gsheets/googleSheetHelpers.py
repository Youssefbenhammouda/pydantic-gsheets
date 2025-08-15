
from datetime import datetime, timedelta


def gsheets_serial_to_datetime(serial):
    # Google Sheets "zero" date is 1899-12-30
    epoch = datetime(1899, 12, 30)
    return epoch + timedelta(days=serial)