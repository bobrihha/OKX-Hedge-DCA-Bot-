import hmac
import base64
import json
import time
from datetime import datetime, timezone

import requests

from .hedge_config import API_KEY, API_SECRET_KEY, API_PASSPHRASE, DRY_RUN_MODE

# OKX API URLs
BASE_URL = "https://www.okx.com"


def get_timestamp():
    """Get current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def sign_request(timestamp, method, request_path, body=''):
    """Sign the request using HMAC-SHA256."""
    if not isinstance(body, str):
        body = json.dumps(body)
    message = f"{timestamp}{method.upper()}{request_path}{body}"
    mac = hmac.new(bytes(API_SECRET_KEY, 'utf-8'), bytes(message, 'utf-8'), digestmod='sha256')
    return base64.b64encode(mac.digest()).decode('utf-8')


def make_request(method, request_path, body=None):
    """Make a generic request to the OKX API."""
    url = f"{BASE_URL}{request_path}"
    timestamp = get_timestamp()
    headers = {
        'Content-Type': 'application/json',
        'OK-ACCESS-KEY': API_KEY,
        'OK-ACCESS-SIGN': sign_request(timestamp, method, request_path, body or ''),
        'OK-ACCESS-TIMESTAMP': timestamp,
        'OK-ACCESS-PASSPHRASE': API_PASSPHRASE,
    }
    if DRY_RUN_MODE:
        headers['x-simulated-trading'] = '1'

    try:
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers)
        elif method.upper() == 'POST':
            response = requests.post(url, headers=headers, json=body)
        else:
            raise ValueError(f"Unsupported method: {method}")

        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        # Handle connection errors, timeouts, etc.
        print(f"API request error: {e}")
        return None

# --- Specific API Functions ---

def get_account_balance():
    """Get account balance."""
    return make_request('GET', '/api/v5/account/balance')

def set_leverage(instId, lever, mgnMode='cross'):
    """Set leverage for a specific instrument."""
    body = {
        "instId": instId,
        "lever": str(lever),
        "mgnMode": mgnMode
    }
    return make_request('POST', '/api/v5/account/set-leverage', body=body)

def place_order(instId, side, ordType, sz, px=None, posSide=None):
    """Place a new order."""
    body = {
        "instId": instId,
        "tdMode": "cross",
        "side": side,
        "ordType": ordType,
        "sz": str(sz),
    }
    if px:
        body['px'] = str(px)
    if posSide:
        body['posSide'] = posSide

    return make_request('POST', '/api/v5/trade/order', body=body)

def cancel_multiple_orders(instId, ord_ids):
    """Cancel multiple orders at once."""
    # OKX API expects a list of dicts with instId and ordId
    body = []
    for ord_id in ord_ids:
        body.append({"instId": instId, "ordId": ord_id})
    return make_request('POST', '/api/v5/trade/cancel-batch-orders', body=body)



def cancel_order(instId, ordId):
    """Cancel a specific order."""
    body = {
        "instId": instId,
        "ordId": ordId
    }
    return make_request('POST', '/api/v5/trade/cancel-order', body=body)

def get_instrument_details(instId, instType='SWAP'):
    """Get instrument details, like tick size and lot size."""
    path = f'/api/v5/public/instruments?instType={instType}&instId={instId}'
    return make_request('GET', path)

def get_ticker(instId):
    """Get the last traded price for an instrument."""
    path = f'/api/v5/market/ticker?instId={instId}'
    return make_request('GET', path)

def get_order_details(instId, ordId):
    """Get details of a specific order."""
    path = f'/api/v5/trade/order?instId={instId}&ordId={ordId}'
    return make_request('GET', path)
