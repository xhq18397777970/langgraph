
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
    获取指定集群在指定时间段的CPU指标数据
    
    Args:
    - groupname: 集群名称（示例："lf-lan-ha1"）
    - 起止时间(例如从2023年1月1日0点0分0秒到2023年1月2日10点10分10秒("begin_time": "2023-01-01 00:00:00", "end_time": "2023-01-02 10:00:00")
    
    Returns:
        dict:查询结果
    
    example:
        查集群lf-lan-ha1在2025-12-03 09:43:14到2025-12-03 10:13:14的CPU指标数据
        请求参数：
            groupname="lf-lan-ha1",
            begin_time="2025-12-03 09:43:14",
            end_time="2025-12-03 10:13:14"
    """
    postdata = {"groupname":groupname,"begin_time":begin_time,"end_time":end_time}
    apiurl= "/prod-api/api/v2/analysis/prometheus/core?format=json"
    result = npa_summary_data(postdata,apiurl)
    cpu_result = {
        "code":result['code'],
        "data":result['data'][0]
        # "unit_char":result['data'][0]["unit"],
        # "unit":"使用率"
    }
    return cpu_result



if __name__ == "__main__":
    print("🚀 启动域名查询 MCP 服务...")
    print("📡 传输方式: SSE")
    print(f"🔗 服务端口: 10027")
    
    # 使用SSE传输方式启动服务器
    mcp.run(transport="sse")