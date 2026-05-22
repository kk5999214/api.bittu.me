import binascii
import time
import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToDict

from app.settings import settings
from proto import uid_generator_pb2
from proto import data_pb2

TOKEN_CACHE = {}
JWT_API_BASE = "https://api.bittu.me"

def encrypt_aes(hex_data: str, key: str, iv: str) -> str:
    key_bytes = key.encode()[:16]
    iv_bytes = iv.encode()[:16]
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
    padded_data = pad(bytes.fromhex(hex_data), AES.block_size)
    encrypted_data = cipher.encrypt(padded_data)
    return binascii.hexlify(encrypted_data).decode()

def get_client_url(region: str) -> str:
    reg = region.upper()
    if reg == "IND":
        return "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
    elif reg in ["ME", "TH"]:
        return "https://clientbp.common.ggbluefox.com/GetPlayerPersonalShow"
    elif reg == "GHOST":
        return "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"
    else:
        return "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow"

def reformat_entries(entries_list):
    for entry in entries_list:
        if "modeId" in entry:
            entry["Id"] = entry.pop("modeId")
        if "points" in entry:
            entry["code"] = entry.pop("points")
        if "unlockStatus" in entry:
            entry["unlockStatus"] = entry.pop("unlockStatus")
    return entries_list

async def get_valid_jwt(region: str) -> str:
    now = time.time()
    
    if region in TOKEN_CACHE and TOKEN_CACHE[region]["expires"] > now:
        return TOKEN_CACHE[region]["token"]
        
    async with httpx.AsyncClient(verify=False) as client:
        url = f"{JWT_API_BASE}/token?region={region}"
        r = await client.get(url, timeout=20.0)
        
        if r.status_code != 200:
            raise ValueError(f"HTTP Token Call Failed: {r.text}")
            
        data = r.json()
        token = data.get("token") or data.get("Token")
        
        if not token or token == "0":
            raise ValueError(f"JWT API Returned Invalid Token: {data}")
            
        TOKEN_CACHE[region] = {"token": token, "expires": now + 7200}
        return token

async def extract_player_info(uid: str, region: str, jwt_token: str) -> dict:
    message = uid_generator_pb2.uid_generator()
    message.saturn_ = int(uid)
    message.garena = 1
    protobuf_data = message.SerializeToString()
    hex_data = binascii.hexlify(protobuf_data).decode()
    
    encrypted_hex = encrypt_aes(hex_data, settings.INFO_KEY, settings.INFO_IV)
    
    endpoint = get_client_url(region)
    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 15; I2404 Build/AP3A.240905.015.A2_V000L1)',
        'Connection': 'Keep-Alive',
        'Expect': '100-continue',
        'Authorization': f'Bearer {jwt_token}',
        'X-Unity-Version': '2018.4.11f1',
        'X-GA': 'v1 1',
        'ReleaseVersion': 'OB53',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept-Encoding': 'gzip'
    }
    
    async with httpx.AsyncClient(verify=False) as client:
        api_res = await client.post(endpoint, headers=headers, content=bytes.fromhex(encrypted_hex), timeout=15.0)
        api_res.raise_for_status()
        res_hex = api_res.content.hex()

    if not res_hex:
        raise ValueError("Garena Returned An Empty Response")

    acc_info = data_pb2.AccountPersonalShowInfo()
    acc_info.ParseFromString(bytes.fromhex(res_hex))
    result = MessageToDict(acc_info)
    
    if "basicInfo" in result and "csRankEntries" in result["basicInfo"]:
        result["basicInfo"]["playerFEItems"] = reformat_entries(result["basicInfo"].pop("csRankEntries"))
        
    if "captainBasicInfo" in result and "csRankEntries" in result["captainBasicInfo"]:
        result["captainBasicInfo"]["captainFEItems"] = reformat_entries(result["captainBasicInfo"].pop("csRankEntries"))
        
    if "profileInfo" in result and "equippedSkills" in result["profileInfo"]:
        result["profileInfo"]["playerOutfits"] = result["profileInfo"].pop("equippedSkills")
        
    return result
