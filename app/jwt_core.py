import json
from typing import Tuple, Dict, Any, Optional

import httpx
from Crypto.Cipher import AES
from google.protobuf import json_format, message

from app.settings import settings
from proto import freefire_pb2 

def pkcs7_pad(b: bytes, block_size: int = 16) -> bytes:
    pad_len = block_size - (len(b) % block_size)
    padding = bytes([pad_len for _ in range(pad_len)])
    return b + padding

def aes_cbc_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pkcs7_pad(plaintext, 16))

def json_to_proto(json_data: Dict[str, Any], proto_message: message.Message) -> bytes:
    json_format.ParseDict(json_data, proto_message)
    return proto_message.SerializeToString()

async def get_access_token(client: httpx.AsyncClient, uid: str, password: str) -> Tuple[str, str]:
    parts = settings.CLIENT_SECRET_PAYLOAD.split('&client_id=')
    client_secret = parts[0]
    client_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 100067

    payload = {
        "client_id": client_id, 
        "client_secret": client_secret,
        "client_type": 2,
        "password": password,
        "response_type": "token",
        "uid": int(uid) 
    }
    
    headers = {
        "User-Agent": settings.USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip"
    }
    
    r = await client.post(settings.OAUTH_URL, json=payload, headers=headers, timeout=settings.TIMEOUT)
    
    if r.status_code != 200:
        raise RuntimeError(f"ACCOUNT BANNED Or OAUTH API HTTP Error {r.status_code}")

    data = r.json().get("data", {})
    if 'error' in data:
        raise RuntimeError(f"ACCOUNT BANNED Or API Error {data.get('error_description', data['error'])}")

    return data.get("access_token", "0"), data.get("open_id", "0")

async def create_jwt(uid: str, password: str, region: str = "IND", bypass_token: Optional[str] = None, bypass_id: Optional[str] = None) -> Dict[str, Any]:
    async with httpx.AsyncClient(http2=False, verify=False) as client:
        
        if bypass_token and bypass_id:
            access_token = bypass_token
            open_id = bypass_id
        else:
            access_token, open_id = await get_access_token(client, uid, password)
            
        if access_token == "0":
            raise RuntimeError("ACCOUNT BANNED Failed To Obtain Access Token")

        login_req = {
            "open_id": open_id,
            "open_id_type": "4",
            "login_token": access_token,
            "orign_platform_type": "4",
        }

        req_msg = freefire_pb2.LoginReq()
        encoded = json_to_proto(login_req, req_msg)
        encrypted_payload = aes_cbc_encrypt(settings.MAIN_KEY, settings.MAIN_IV, encoded)

        major_login_ua = "Dalvik/2.1.0 (Linux; U; Android 15; I2404 Build/AP3A.240905.015.A2_V000L1)"
        
        headers = {
            "User-Agent": major_login_ua,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "Content-Type": "application/octet-stream",
            "Expect": "100-continue",
            "X-Unity-Version": settings.X_UNITY_VERSION,
            "X-GA": "v1 1",
            "ReleaseVersion": settings.RELEASE_VERSION,
        }

        login_base = settings.REGION_MAP.get(region.upper(), "https://loginbp.ggpolarbear.com")
        major_login_url = f"{login_base}/MajorLogin"

        r = await client.post(
            major_login_url,
            content=encrypted_payload,
            headers=headers,
            timeout=settings.TIMEOUT,
        )
        
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Garena Rejected Login HTTP {r.status_code}")

        res_msg = freefire_pb2.LoginRes()
        try:
            res_msg.ParseFromString(r.content)
        except Exception:
            raise RuntimeError(f"Failed To Decode Protobuf Garena Sent Invalid Data")

        token = res_msg.token if res_msg.token else "0"
        lock_region = res_msg.lock_region if res_msg.lock_region else ""
        server_url = res_msg.server_url if res_msg.server_url else ""

        if token == "0" or len(token) == 0:
            res_dict = json.loads(json_format.MessageToJson(res_msg))
            err_str = str(res_dict).lower()
            if "ban" in err_str or "reason" in err_str:
                raise RuntimeError("ACCOUNT BANNED Profile Restricted By Garena")
            raise RuntimeError(f"Failed To Obtain JWT")

        return {
            "token": token,
            "LockRegion": lock_region,
            "ServerUrl": server_url,
        }
