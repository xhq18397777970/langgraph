import hashlib
import time
import requests
from datetime import datetime
import json

# 配置参数
CONFIG = {
    'appCode': 'JC_PIDLB',
    'token': '9b78f9ab773774f5b2c4b627ff007152',
    'api_url': 'http://api-np.jd.local/'
}

def get_np_auth_headers(app_code, token):
    """生成NP接口鉴权header"""
    now = datetime.now()
    time_str = now.strftime("%H%m%Y%m%d")
    timestamp = str(int(time.time()))
    
    sign_str = f"#{token}NP{time_str}"
    sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    
    return {
        "appCode": app_code,
        "sign": sign,
        "time": timestamp,
        "Content-Type": "application/json"
    }
