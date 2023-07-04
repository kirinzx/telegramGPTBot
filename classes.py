class User:
    def __init__(self,phoneNumber,app_id,app_hash):
        self.phoneNumber = phoneNumber
        self.app_id = app_id
        self.app_hash = app_hash
        self.isParsing = False

class Channel:
    def __init__(self,channel_id):
        self.channel_id = channel_id
        self.isParsing = False