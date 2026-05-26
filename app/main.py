import json
import os
import random
import asyncio
from fastapi import FastAPI, Query, Body, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel
from typing import Optional

from app.jwt_core import create_jwt
from app.info_core import extract_player_info, extract_clan_info, get_valid_jwt
from app.stats_core import extract_all_stats
from app.ban_core import check_player_ban

app = FastAPI(title="BITTU__DEV Master API", version="10.0", docs_url=None, redoc_url=None)

ACCOUNTS_FILE = "GuestAccounts.json"

def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r") as f:
            return json.load(f)
    return {}

accounts_db = load_accounts()

class TokenRequest(BaseModel):
    uid: Optional[str] = None
    password: Optional[str] = None
    region: Optional[str] = None
    access_token: Optional[str] = None
    open_id: Optional[str] = None

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return JSONResponse(
            status_code=404,
            content={"Developer": "BITTU_DEV", "Error": "404 Not Found", "Message": "Endpoint mismatch or route does not exist."}
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"Developer": "BITTU_DEV", "Error": f"{exc.status_code} Error", "Message": exc.detail}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"Developer": "BITTU_DEV", "Error": "400 Bad Request", "Message": "Parameter mismatch or invalid format."}
    )

@app.get("/")
async def root():
    return JSONResponse(content={
        "Developer": "BITTU_DEV",
        "Status": "API Online"
    })

@app.get("/token")
async def get_token(
    region: Optional[str] = Query(None),
    uid: Optional[str] = Query(None), 
    password: Optional[str] = Query(None),
    access_token: Optional[str] = Query(None),
    open_id: Optional[str] = Query(None)
):
    if access_token and open_id:
        target_region = (region or "IND").upper()
        try:
            result = await create_jwt(uid="Bypass", password="None", region=target_region, bypass_token=access_token, bypass_id=open_id)
            response_data = {"Developer": "BITTU_DEV", "Status": "Bypass Mode Active"}
            response_data.update(result)
            return response_data
        except Exception as e:
            return JSONResponse(status_code=500, content={"Developer": "BITTU_DEV", "Error": "500 Internal Error", "Message": str(e)})

    elif uid and password:
        target_region = (region or "IND").upper()
        try:
            result = await create_jwt(uid, password, target_region)
            response_data = {"Developer": "BITTU_DEV", "Uid": uid, "Password": password}
            response_data.update(result)
            return response_data
        except Exception as e:
            return JSONResponse(status_code=500, content={"Developer": "BITTU_DEV", "Error": "500 Internal Error", "Message": str(e)})

    elif region:
        target_region = region.upper()
        if target_region not in accounts_db or not accounts_db[target_region]:
            return JSONResponse(status_code=404, content={"Developer": "BITTU_DEV", "Error": "404 Not Found", "Message": f"No Accounts Available For Region {target_region}"})
            
        account_pool = accounts_db[target_region]
        max_retries = 2
        last_error = "Unknown Error"
        
        for attempt in range(max_retries):
            active_account = random.choice(account_pool)
            active_uid = active_account.get("uid")
            active_pwd = active_account.get("password")
            
            if not active_uid or not active_pwd:
                continue 
                
            try:
                result = await create_jwt(active_uid, active_pwd, target_region)
                response_data = {
                    "Developer": "BITTU_DEV",
                    "Status": "Active",
                    "Region": target_region,
                    "Attempt": attempt + 1,
                    "Uid": active_uid,
                    "Password": active_pwd
                }
                response_data.update(result)
                return response_data
            except Exception as e:
                last_error = str(e)
                
        return JSONResponse(status_code=500, content={"Developer": "BITTU_DEV", "Error": "500 Internal Error", "Message": f"Extraction Failed After {max_retries} Attempts. Last Error: {last_error}"})

    else:
        return JSONResponse(status_code=400, content={"Developer": "BITTU_DEV", "Error": "400 Bad Request", "Message": "Strictly Require Uid & Password OR Region OR Access Token & Open Id."})

@app.post("/token")
async def post_token(payload: TokenRequest = Body(...)):
    return await get_token(
        region=payload.region, 
        uid=payload.uid, 
        password=payload.password,
        access_token=payload.access_token,
        open_id=payload.open_id
    )

@app.get("/info")
async def get_player_info(uid: str = Query(...), region: Optional[str] = Query(None)):
    if not uid.isdigit():
        return JSONResponse(status_code=400, content={"Developer": "BITTU_DEV", "Error": "400 Bad Request", "Message": "Invalid UID Format. Must Be Numeric."})

    target_region = region.upper() if region else None

    if not target_region:
        try:
            ban_data = await check_player_ban(uid)
            target_region = ban_data.get("region", "").upper()
            
            if not target_region or target_region == "N/A":
                return JSONResponse(status_code=404, content={"Developer": "BITTU_DEV", "Error": "404 Not Found", "Message": "Could not auto-detect region. Please provide the ?region= parameter manually."})
        except Exception as e:
            return JSONResponse(status_code=500, content={"Developer": "BITTU_DEV", "Error": "500 Internal Error", "Message": f"Region auto-detect failed: {str(e)}"})

    try:
        jwt_token = await get_valid_jwt(target_region)
        result = await extract_player_info(uid, target_region, jwt_token)

        return JSONResponse(content={
            "Developer": "BITTU_DEV",
            "Status": "Success",
            "Region": target_region,
            "Data": result
        })

    except Exception as e:
        err_str = str(e).lower()
        if "401" in err_str or "unauthorized" in err_str:
             from app.info_core import redis
             if redis:
                 await redis.delete(f"jwt_cache_{target_region}")
             return JSONResponse(status_code=401, content={"Developer": "BITTU_DEV", "Error": "401 Unauthorized", "Message": "Token Expired Or Rejected. Cache Cleared. Try Again."})
        
        return JSONResponse(status_code=500, content={"Developer": "BITTU_DEV", "Error": "500 Internal Error", "Message": f"Extraction Failed: {str(e)}"})


@app.get("/stats")
async def get_player_stats(uid: str = Query(...), region: Optional[str] = Query(None), mode: Optional[str] = Query(None), type: Optional[str] = Query(None)):
    if not uid.isdigit():
        return JSONResponse(status_code=400, content={"Developer": "BITTU_DEV", "Error": "400 Bad Request", "Message": "Invalid UID Format. Must Be Numeric."})

    target_region = region.upper() if region else None

    if not target_region:
        try:
            ban_data = await check_player_ban(uid)
            target_region = ban_data.get("region", "").upper()
            
            if not target_region or target_region == "N/A":
                return JSONResponse(status_code=404, content={"Developer": "BITTU_DEV", "Error": "404 Not Found", "Message": "Could not auto-detect region. Please provide the ?region= parameter manually."})
        except Exception as e:
            return JSONResponse(status_code=500, content={"Developer": "BITTU_DEV", "Error": "500 Internal Error", "Message": f"Region auto-detect failed: {str(e)}"})

    req_mode = None
    if mode:
        m = mode.strip().lower()
        if m in ['br', 'battle royale']: req_mode = 'br'
        elif m in ['cs', 'clash squad']: req_mode = 'cs'
        else: req_mode = m

    req_type = None
    if type:
        t = type.strip().lower()
        if t in ['casual', 'normal']: req_type = 'NORMAL'
        elif t in ['ranked', 'rank']: req_type = 'RANKED'
        elif t in ['career', 'lifetime']: req_type = 'CAREER'
        else: req_type = t.upper()

    try:
        jwt_token = await get_valid_jwt(target_region)
        
        profile_task = extract_player_info(uid, target_region, jwt_token)
        stats_task = extract_all_stats(uid, target_region, jwt_token, req_mode, req_type)
        
        profile_raw, stats_output = await asyncio.gather(profile_task, stats_task)

        basic_info = profile_raw.get("basicInfo", {})
        profile_result = {
            "nickname": basic_info.get("nickname", "Unknown"),
            "uid": str(uid),
            "likes": basic_info.get("liked", 0),
            "exp": basic_info.get("exp", 0),
            "level": basic_info.get("level", 0)
        }

        return JSONResponse(content={
            "Developer": "BITTU_DEV",
            "Status": "Success",
            "Region": target_region,
            "filters_applied": {
                "mode": req_mode.upper() if req_mode else "ALL MODES",
                "type": req_type if req_type else "ALL TYPES"
            },
            "profile": profile_result,
            "stats": stats_output
        })

    except Exception as e:
        err_str = str(e).lower()
        if "401" in err_str or "unauthorized" in err_str:
             from app.info_core import redis
             if redis:
                 await redis.delete(f"jwt_cache_{target_region}")
             return JSONResponse(status_code=401, content={"Developer": "BITTU_DEV", "Error": "401 Unauthorized", "Message": "Token Expired Or Rejected. Cache Cleared. Try Again."})
             
        return JSONResponse(status_code=500, content={"Developer": "BITTU_DEV", "Error": "500 Internal Error", "Message": f"Extraction Failed: {str(e)}"})

@app.get("/bancheck")
async def get_ban_status(uid: str = Query(...)):
    if not uid.isdigit():
        return JSONResponse(status_code=400, content={"Developer": "BITTU_DEV", "Error": "400 Bad Request", "Message": "Invalid UID Format. Must Be Numeric."})
        
    try:
        result = await check_player_ban(uid)
        
        return JSONResponse(content={
            "Developer": "BITTU_DEV",
            "Status": "Success",
            "Data": result
        })
    except Exception as e:
        return JSONResponse(status_code=404, content={"Developer": "BITTU_DEV", "Error": "404 Not Found", "Message": str(e)})

@app.get("/clan")
async def get_clan_data(id: str = Query(...), region: str = Query("IND")):
    target_region = region.upper()
    if not id.isdigit():
        return JSONResponse(status_code=400, content={"Developer": "BITTU_DEV", "Error": "400 Bad Request", "Message": "Invalid Clan ID Format. Must Be Numeric."})
        
    try:
        jwt_token = await get_valid_jwt(target_region)
        result = await extract_clan_info(id, target_region, jwt_token)

        return JSONResponse(content={
            "Developer": "BITTU_DEV",
            "Status": "Success",
            "Data": result
        })
    except Exception as e:
        err_str = str(e).lower()
        if "401" in err_str or "unauthorized" in err_str:
             from app.info_core import redis
             if redis:
                 await redis.delete(f"jwt_cache_{target_region}")
             return JSONResponse(status_code=401, content={"Developer": "BITTU_DEV", "Error": "401 Unauthorized", "Message": "Token Expired Or Rejected. Cache Cleared. Try Again."})
             
        return JSONResponse(status_code=500, content={"Developer": "BITTU_DEV", "Error": "500 Internal Error", "Message": f"Extraction Failed: {str(e)}"})
