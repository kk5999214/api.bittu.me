import httpx
import asyncio

async def check_player_ban(uid: str) -> dict:
    cookies = {
        '_ga': 'GA1.1.2123120599.1674510784',
        '_fbp': 'fb.1.1674510785537.363500115',
        '_ga_7JZFJ14B0B': 'GS1.1.1674510784.1.1.1674510789.0.0.0',
        'source': 'mb',
        'region': 'MA',
        'language': 'ar',
        '_ga_TVZ1LG7BEB': 'GS1.1.1674930050.3.1.1674930171.0.0.0',
        'datadome': '6h5F5cx_GpbuNtAkftMpDjsbLcL3op_5W5Z-npxeT_qcEe_7pvil2EuJ6l~JlYDxEALeyvKTz3~LyC1opQgdP~7~UDJ0jYcP5p20IQlT3aBEIKDYLH~cqdfXnnR6FAL0',
        'session_key': 'efwfzwesi9ui8drux4pmqix4cosane0y',
    }

    shop_headers = {
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
        'Origin': 'https://shop2game.com',
        'Referer': 'https://shop2game.com/app/100067/idlogin',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 11; Redmi Note 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36',
        'accept': 'application/json',
        'content-type': 'application/json',
        'sec-ch-ua': '"Chromium";v="107", "Not=A?Brand";v="24"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'x-datadome-clientid': '6h5F5cx_GpbuNtAkftMpDjsbLcL3op_5W5Z-npxeT_qcEe_7pvil2EuJ6l~JlYDxEALeyvKTz3~LyC1opQgdP~7~UDJ0jYcP5p20IQlT3aBEIKDYLH~cqdfXnnR6FAL0',
    }

    json_data = {
        'app_id': 100067,
        'login_id': uid,
        'app_server_id': 0,
    }

    ban_headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'authority': 'ff.garena.com',
        'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
        'referer': 'https://ff.garena.com/en/support/',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'x-requested-with': 'B6FksShzIgjfrYImLpTsadjS86sddhFH',
    }

    async with httpx.AsyncClient(verify=False) as client:
        try:
            # Firing both web requests simultaneously for ultimate speed ⚡
            shop_req = client.post('https://shop2game.com/api/auth/player_id_login', cookies=cookies, headers=shop_headers, json=json_data, timeout=15.0)
            ban_req = client.get(f'https://ff.garena.com/api/antihack/check_banned?lang=en&uid={uid}', headers=ban_headers, timeout=15.0)

            shop_res, ban_res = await asyncio.gather(shop_req, ban_req, return_exceptions=True)
            
            # 1. Validate Shop2Game response
            if isinstance(shop_res, Exception) or shop_res.status_code != 200 or not shop_res.json().get('nickname'):
                raise ValueError("UID NOT FOUND or Shop2Game Request Blocked")
            
            player_data = shop_res.json()
            nickname = player_data.get('nickname', 'N/A')
            region = player_data.get('region', 'N/A')

            # 2. Validate Anti-Hack response
            ban_message = "Failed to retrieve ban status"
            period_str = None
            
            if not isinstance(ban_res, Exception) and ban_res.status_code == 200:
                ban_data = ban_res.json()
                if ban_data.get("status") == "success" and "data" in ban_data:
                    is_banned = ban_data["data"].get("is_banned", 0)
                    period = ban_data["data"].get("period", 0)
                    
                    if is_banned:
                        ban_message = f"Banned {period} months" if period > 0 else "Banned indefinitely"
                        period_str = f"{period} months" if period > 0 else None
                    else:
                        ban_message = "Not banned"
                        
            return {
                "nickname": nickname,
                "region": region,
                "ban_status": ban_message,
                "ban_period": period_str
            }
            
        except Exception as e:
            raise ValueError(str(e))
