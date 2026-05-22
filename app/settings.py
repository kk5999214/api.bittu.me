
import base64
from pydantic import BaseModel

class Settings(BaseModel):
    MAIN_KEY_B64: str = "WWcmdGMlREV1aDYlWmNeOA=="
    MAIN_IV_B64: str = "Nm95WkRyMjJFM3ljaGpNJQ=="
    RELEASE_VERSION: str = "OB53"

    USER_AGENT: str = "GarenaMSDK/4.0.19P10(I2404 ;Android 15;en;US;)" 
    
    OAUTH_URL: str = "https://ffmconnect.live.gop.garenanow.com/api/v2/oauth/guest/token:grant"
    
    CLIENT_SECRET_PAYLOAD: str = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3&client_id=100067"
    X_UNITY_VERSION: str = "2018.4.11f1"
    TIMEOUT: float = 15.0

    REGION_MAP: dict = {
        "IND": "https://loginbp.ggpolarbear.com",
        "BD":  "https://loginbp.ggpolarbear.com",
        "PK":  "https://loginbp.ggpolarbear.com",
        "BR":  "https://loginbp.ggpolarbear.com",
        "NA":  "https://loginbp.ggpolarbear.com",
        "VN":  "https://loginbp.ggpolarbear.com",
        "SG":  "https://loginbp.ggpolarbear.com",
        "ID":  "https://loginbp.ggpolarbear.com",
        "CIS": "https://loginbp.ggpolarbear.com",
        "TW":  "https://loginbp.ggpolarbear.com",      
        "SAC": "https://loginbp.ggpolarbear.com",      
        "ME":  "https://loginbp.common.ggbluefox.com", 
        "TH":  "https://loginbp.common.ggbluefox.com", 
        "GHOST": "https://loginbp.ggblueshark.com"
    }

    INFO_KEY: str = "Yg&tc%DEuh6%Zc^8"
    INFO_IV: str = "6oyZDr22E3ychjM%"

    @property
    def MAIN_KEY(self) -> bytes:
        return base64.b64decode(self.MAIN_KEY_B64)

    @property
    def MAIN_IV(self) -> bytes:
        return base64.b64decode(self.MAIN_IV_B64)

settings = Settings()
