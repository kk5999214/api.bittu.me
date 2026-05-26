import binascii
import time
import json
import random
import os
import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToDict
from upstash_redis.asyncio import Redis

from app.settings import settings
from proto import uid_generator_pb2
from proto import data_pb2
from proto import ClanInfo_pb2
from app.jwt_core import create_jwt

# Initialize Serverless Redis connection automatically using Vercel Env Vars
try:
    redis = Redis.from_env()
except Exception as e:
    redis = None
    print(f"Redis Initialization Warning: {e}")

JWT_API_BASE = "https://api.bittu.me"
ACCOUNTS_FILE = "GuestAccounts.json"

def load_accounts_for_region(region: str):
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r") as f:
            db = json.load(f)
            return db.get(region, [])
    return []

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
    region = region.upper()
    redis_key = f"jwt_cache_{region}"
    
    # 1. Ask Serverless Redis for a globally cached token
    if redis:
        cached_token = await redis.get(redis_key)
        if cached_token:
            return cached_token
            
    # 2. If Cache Miss (or Redis fails), execute internal extraction logic
    account_pool = load_accounts_for_region(region)
    if not account_pool:
        raise ValueError(f"No accounts available in pool for region {region}")
        
    for _ in range(2):
        active_account = random.choice(account_pool)
        if not active_account.get("uid") or not active_account.get("password"):
            continue
            
        try:
            # Generate JWT natively without network self-calling
            result = await create_jwt(active_account["uid"], active_account["password"], region)
            token = result.get("token")
            
            if token and token != "0":
                # 3. Save to Redis globally with a 2-Hour TTL (7200 seconds)
                if redis:
                    await redis.set(redis_key, token, ex=7200)
                return token
        except Exception:
            continue
            
    raise ValueError(f"Extraction Pipeline Exhausted: Failed to internally generate JWT for {region}.")

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

async def extract_clan_info(clan_id: str, region: str, jwt_token: str) -> dict:
    message = ClanInfo_pb2.ClanInfoRequest()
    message.clan_id = int(clan_id)
    protobuf_data = message.SerializeToString()
    hex_data = binascii.hexlify(protobuf_data).decode()
    
    encrypted_hex = encrypt_aes(hex_data, settings.INFO_KEY, settings.INFO_IV)
    
    base_url = get_client_url(region).replace("/GetPlayerPersonalShow", "")
    endpoint = f"{base_url}/GetClanInfoByClanID"
    
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
        raise ValueError("Garena Returned An Empty Clan Response")

    clan_res = ClanInfo_pb2.ClanInfoResponse()
    clan_res.ParseFromString(bytes.fromhex(res_hex))
    result = MessageToDict(clan_res, preserving_proto_field_name=True)
    
    if "clan_tags" in result:
        try: result["clan_tags"] = json.loads(result["clan_tags"])
        except json.JSONDecodeError: pass
        
    if "officers" in result:
        try: result["officers"] = json.loads(result["officers"])
        except json.JSONDecodeError: pass

    keys_to_remove = [key for key in result.keys() if key.startswith("field_") or key.startswith("timestamp_")]
    for key in keys_to_remove:
        result.pop(key, None)

    return result
