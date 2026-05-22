import asyncio
import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from google.protobuf.json_format import ParseDict, MessageToDict

from app.settings import settings
from proto import PlayerStats_pb2
from proto import PlayerCSStats_pb2

def get_stats_base_url(region: str) -> str:
    reg = region.upper()
    if reg == "IND":
        return "https://client.ind.freefiremobile.com"
    elif reg in ["ME", "TH"]:
        return "https://clientbp.common.ggbluefox.com"
    elif reg == "GHOST":
        return "https://clientbp.ggblueshark.com"
    else:
        return "https://clientbp.ggpolarbear.com"

def encode_protobuf(data_dict, proto_obj):
    ParseDict(data_dict, proto_obj, ignore_unknown_fields=True)
    raw_bytes = proto_obj.SerializeToString()
    key_bytes = settings.INFO_KEY.encode()[:16]
    iv_bytes = settings.INFO_IV.encode()[:16]
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
    return cipher.encrypt(pad(raw_bytes, AES.block_size))

async def fetch_stat_safe(client, token, base_url, uid, mode, mtype):
    uid = int(uid)
    mode = mode.lower()
    mtype = mtype.upper()
    
    if mode == "br":
        type_mapping = {"CAREER": 0, "NORMAL": 1, "RANKED": 2}
        url = f"{base_url}/GetPlayerStats"
        proto_module = PlayerStats_pb2
        payload_data = {"accountid": uid, "matchmode": type_mapping.get(mtype, 0)}
    else:
        type_mapping = {"CAREER": 0, "NORMAL": 1, "RANKED": 6}
        url = f"{base_url}/GetPlayerTCStats"
        proto_module = PlayerCSStats_pb2
        payload_data = {"accountid": uid, "gamemode": 15, "matchmode": type_mapping.get(mtype, 0)}
    
    request_proto = proto_module.request()
    encrypted_payload = encode_protobuf(payload_data, request_proto)
    
    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 15; I2404 Build/AP3A.240905.015.A2_V000L1)',
        'Connection': 'Keep-Alive',
        'Accept-Encoding': 'gzip',
        'Expect': '100-continue',
        'Authorization': f'Bearer {token}',
        'X-Unity-Version': '2018.4.11f1',
        'X-GA': 'v1 1',
        'ReleaseVersion': 'OB53',
        'Content-Type': 'application/octet-stream'
    }
    
    try:
        response = await client.post(url, content=encrypted_payload, headers=headers, timeout=10.0)
        response.raise_for_status()
        response_obj = proto_module.response()
        response_obj.ParseFromString(response.content)
        return MessageToDict(response_obj, preserving_proto_field_name=True)
    except Exception:
        return {}

def clean_stat_data(raw_data):
    if isinstance(raw_data, dict):
        cleaned = {}
        for k, v in raw_data.items():
            lower_k = str(k).lower()
            if lower_k in ['accountid', 'matchmode', 'gamemode', 'gametype', 'account_id']:
                continue
            new_key = "".join([" " + c if c.isupper() else c for c in str(k)]).title().strip()
            cleaned[new_key] = clean_stat_data(v)
        return cleaned
    elif isinstance(raw_data, list):
        return [clean_stat_data(i) for i in raw_data]
    else:
        if isinstance(raw_data, float):
            return round(raw_data, 4)
        return raw_data

def recursive_sort(obj):
    if isinstance(obj, dict):
        return {k: recursive_sort(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, list):
        return [recursive_sort(item) for item in obj]
    return obj

async def extract_all_stats(uid: str, region: str, jwt_token: str, req_mode: str = None, req_type: str = None):
    base_url = get_stats_base_url(region)
    
    all_stats_tasks = [
        ("BR Career", "br", "CAREER"),
        ("BR Ranked", "br", "RANKED"),
        ("BR Casual", "br", "NORMAL"),
        ("CS Career", "cs", "CAREER"),
        ("CS Ranked", "cs", "RANKED"),
        ("CS Casual", "cs", "NORMAL"),
    ]

    stats_to_run = {}
    for key, task_mode, task_type in all_stats_tasks:
        if req_mode and task_mode != req_mode.lower(): continue
        if req_type and task_type != req_type.upper(): continue
        stats_to_run[key] = (task_mode, task_type)

    async with httpx.AsyncClient(verify=False) as client:
        tasks = [
            fetch_stat_safe(client, jwt_token, base_url, uid, m, t)
            for key, (m, t) in stats_to_run.items()
        ]
        results_list = await asyncio.gather(*tasks)

    stats_output = {}
    for (key, _), result_data in zip(stats_to_run.items(), results_list):
        if result_data:
            cleaned = clean_stat_data(result_data)
            if cleaned:
                stats_output[key] = cleaned

    return recursive_sort(stats_output)
