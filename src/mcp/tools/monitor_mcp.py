
from fastmcp import FastMCP
import hashlib
import requests
import time
import json
from langchain_core.tools import tool
from typing import List, Dict
import logging
# 创建MCP服务器实例
mcp = FastMCP("Monitor Service", port=10027)

#鉴权
def npa_summary_data(postdata, apiurl,method="POST"):
    user = "xiehanqi.jackson"
    ctime = str(int(time.time()))
    new_key = f"{user}|{ctime}"
    # 修正这里：使用 hashlib.md5() 来计算哈希值
    api_header_val = f"{hashlib.md5(new_key.encode()).hexdigest()}|{ctime}"
    url = f'http://npa-test.jd.com{apiurl}'
    user_agent = 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'
    headers = {'auth-api': api_header_val, 'auth-user': user, 'Content-Type': "application/json", 'User-Agent': user_agent}
    try:
        if method=="POST":
            response = requests.post(url, json=postdata, headers=headers)
        if method=="GET":
            response = requests.get(url, params=postdata, headers=headers)
        response.raise_for_status()
        # logging.info(f"code:{response.status_code}, response:{response.text}")
        return response.json()
    except requests.RequestException as e:
        # logging.error(f"API request error: {e}")
        return {}


@mcp.tool
def npa_analysis_prometheus_core(
    groupname: str, 
    begin_time: str, 
    end_time: str
) -> dict:
    """
            工具功能：查询指定时间段内集群的CPU指标，所需三个必填参数
                
                参数说明：
                - groupname: 集群名称（必填）。（例如lf-lan-ha1）
                - begin_time: 开始时间（必填），格式为 "YYYY-MM-DD HH:MM:SS"。(如2025-10-04 14:00:00)
                - end_time: 结束时间（必填），格式为 "YYYY-MM-DD HH:MM:SS"。(如2025-10-04 14:10:10)
                
                时间格式处理：
                - 用户可能以 "2025-12-04 14:00:00到2025-12-04 14:10:10" 格式提供时间。
                - 必须将其拆分为两个参数：
                  * begin_time: "2025-12-04 14:00:00"
                  * end_time: "2025-12-04 14:10:10"
    
    """
    postdata = {"groupname":groupname,"begin_time":begin_time,"end_time":end_time}
    apiurl= "/prod-api/api/v2/analysis/prometheus/core?format=json"
    result = npa_summary_data(postdata,apiurl)
    cpu_result = {
        "code":result['code'],
        "data":result['data'][0]
    #     # "unit_char":result['data'][0]["unit"],
    #     # "unit":"使用率"
    }
    return cpu_result



if __name__ == "__main__":
    print("🚀 启动域名查询 MCP 服务...")
    print("📡 传输方式: SSE")
    print(f"🔗 服务端口: 10027")
    
    # 使用SSE传输方式启动服务器
    mcp.run(transport="sse")