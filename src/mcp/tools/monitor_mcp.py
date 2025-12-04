
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
        工具功能:查询指定时间段内集群的CPU指标数据
        请从用户的提问中抽取关键的参数（集群名称、开始时间、结束时间）
        
        Args:
            groupname: 集群名称(如：ga-lan-jdns1、lf-lan-jdns、ozhl-lan-jdns，通常为用2个-连接的字符串)
            begin_time: 开始时间(格式： "YYYY-MM-DD HH:MM:SS"，例如 "2025-10-04 14:00:00")
            end_time: 结束时间 （格式： "YYYY-MM-DD HH:MM:SS"，例如 "2025-10-04 14:30:00"）
        
        案例:
        (1)查集群login-test-001在2023-08-01 00:00:00到2023-08-01 00:10:00的CPU指标数据
        参数为：
            "groupname":"login-test-001", 
            "begin_time":"2023-08-01 00:00:00",
            "end_time":"2023-08-01 00:10:00"
        (2)查集群ga-ha-1在2025年10月1日 12:50:00到2025年10月1日 13:20:00的CPU指标数据
        参数为：
            "groupname":"ga-ha-1", 
            "begin_time":"2025-10-01 12:50:00",
            "end_time":"2025-10-01 13:20:00"
        (2)查一下sq-lan-jdns1在2025年12月4日 13:00:00到13:20:00的CPU指标数据
        参数为：
            "groupname":"ga-ha-1", 
            "begin_time":"2025-12-04 13:00:00",
            "end_time":"2025-12-04 13:20:00"

    """
    postdata = {
            "groupname":groupname, 
            "begin_time":begin_time,
            "end_time":end_time
        }
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