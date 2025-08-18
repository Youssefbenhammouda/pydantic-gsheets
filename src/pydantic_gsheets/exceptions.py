class RequiredValueError(ValueError):
    pass

class noWriteSupport(ValueError):
    def __init__(self):
        message = f"Only links to Google Drive files can be written as chips."
        super().__init__(message)