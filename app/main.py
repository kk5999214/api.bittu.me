import json
import os
import random
from fastapi import FastAPI, Query, Body, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from app.jwt_core import create_jwt
from app.info_core import extract_player_info, get_valid_jwt

app = FastAPI(title="BITTU__DEV Master API", version="6.0")

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

@app.get("/")
async def root():
    return JSONResponse(content={
        "Status": "Master API Live Vercel Decoupled Edition 💀",
        "Loaded_Regions": list(accounts_db.keys()),
        "Endpoints": [
            "/api/info?uid=PLAYER_UID&region=IND",
            "/api/token?uid=xxx&password=yyy&region=IND",
            "/api/token?region=IND",
            "/api/token?access_token=xxx&open_id=yyy"
        ]
    })

@app.get("/api/token")
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
            response_data = {"Developer": "BITTU__DEV", "Status": "Bypass Mode Active"}
            response_data.update(result)
            return response_data
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    elif uid and password:
        target_region = (region or "IND").upper()
        try:
            result = await create_jwt(uid, password, target_region)
            response_data = {"Developer": "BITTU__DEV", "Uid": uid, "Password": password}
            response_data.update(result)
            return response_data
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    elif region:
        target_region = region.upper()
        
        if target_region not in accounts_db or not accounts_db[target_region]:
            raise HTTPException(status_code=404, detail=f"No Accounts Available For Region {target_region}")
            
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
                    "Developer": "BITTU__DEV",
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
                
        raise HTTPException(status_code=500, detail=f"Extraction Failed After {max_retries} Attempts Last Error {last_error}")

    else:
        raise HTTPException(status_code=400, detail="Strictly Require Uid And Password OR Region OR Access Token And Open Id Parameters To Proceed")

@app.post("/api/token")
async def post_token(payload: TokenRequest = Body(...)):
    return await get_token(
        region=payload.region, 
        uid=payload.uid, 
        password=payload.password,
        access_token=payload.access_token,
        open_id=payload.open_id
    )

@app.get("/api/info")
async def get_player_info(uid: str = Query(...), region: str = Query("IND")):
    target_region = region.upper()

    if not uid.isdigit():
        raise HTTPException(status_code=400, detail="Invalid Uid Format Must Be Numeric")

    try:
        jwt_token = await get_valid_jwt(target_region)
        result = await extract_player_info(uid, target_region, jwt_token)

        return JSONResponse(content={
            "Developer": "@BITTU__DEV",
            "Status": "Success",
            "Data": result
        })

    except Exception as e:
        err_str = str(e).lower()
        if "401" in err_str or "unauthorized" in err_str:
             from app.info_core import TOKEN_CACHE
             TOKEN_CACHE.pop(target_region, None)
             raise HTTPException(status_code=401, detail="Token Expired Or Rejected Cache Cleared Try Again")
        raise HTTPException(status_code=500, detail=f"Extraction Failed {str(e)}")
