
from typing import Annotated, Sequence, List, Literal ,TypedDict
from pydantic import BaseModel, Field 
from langchain_core.messages import HumanMessage,AIMessage,ToolMessage,SystemMessage
from langchain_core.tools import tool
from langgraph.types import Command 
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import create_react_agent 
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
import os
from langchain_openai import ChatOpenAI
import json
import asyncio
from langchain_core.tools import StructuredTool

def create_sync_tool_wrapper(async_tool):
    """创建同步工具包装器，将异步 MCP 工具转换为同步工具"""
    
    def sync_func(**kwargs):
        """同步包装函数，使用 asyncio.run 调用异步工具"""
        try:
            # 调用异步工具的 coroutine 函数
            result = asyncio.run(async_tool.coroutine(**kwargs))
            return result
        except Exception as e:
            print(f"🔍 [DEBUG] 同步包装器执行异常: {e}")
            raise e
    
    # 创建新的同步 StructuredTool
    sync_tool = StructuredTool.from_function(
        func=sync_func,
        name=async_tool.name,
        description=async_tool.description,
        args_schema=async_tool.args_schema,
        return_direct=getattr(async_tool, 'return_direct', False)
    )
    
    print(f"🔍 [DEBUG] 创建同步工具包装器: {async_tool.name}")
    return sync_tool

def convert_async_tools_to_sync(async_tools):
    """将异步工具列表转换为同步工具列表"""
    sync_tools = []
    for tool in async_tools:
        if hasattr(tool, 'coroutine') and tool.coroutine is not None:
            # 这是一个异步工具，需要包装
            sync_tool = create_sync_tool_wrapper(tool)
            sync_tools.append(sync_tool)
            print(f"🔍 [DEBUG] 转换异步工具: {tool.name} -> 同步工具")
        else:
            # 这已经是同步工具，直接使用
            sync_tools.append(tool)
            print(f"🔍 [DEBUG] 保持同步工具: {tool.name}")
    
    return sync_tools
#配置加载
def get_deepseek_model(temperature=0.3):
    """
    配置并返回 DeepSeek 模型实例
    
    Returns:
        ChatOpenAI: 配置好的 DeepSeek 模型实例
    """
    model = ChatOpenAI(
        model="deepseek-chat",
        api_key="sk-7ce2292c26e546f78aaff58c4bf55fac",
        base_url="https://api.deepseek.com",
        temperature=temperature,
        # model_kwargs={"response_format": None} 
    )
    return model




class OverallState(TypedDict):
    messages: Annotated[list, "LangGraph standard messages"]
    
    deeplog_node_tool_results: str  #存储工具调用原始结果
    deeplog_analysis_result: str  # 用于存储模型的最终分析结果



def deeplog_node(state: OverallState) ->Command:
    
    system_prompt = """
    你是一个时序数据分析专家，专门负责对历史日志的时序数据执行以下三件事：
        1. **徒增突降点警告**：分析时序数据中的异常波动，识别并报告以下情况：
        - 突然的峰值（徒增）、突然的谷值（突降）
        - 超出正常范围的数据点
        - 请提供异常点的时间戳、数值和异常程度

        2. **趋势分析**：对时序数据的整体趋势进行分析：
        - 判断是上升、下降还是平稳趋势
        - 分析趋势的强度和持续性
        - 识别趋势变化的拐点
        - 提供趋势变化的可能原因分析

        3. **走势预测**：基于历史数据预测未来走势：
        - 预测未来一段时间（如下1小时、3小时）的可能变化
        - 提供预测的置信区间
        - 指出需要关注的风险点
        - 给出基于预测的运维建议

        **输出要求**：
        - 使用结构化格式呈现分析结果
        - 对每种分析都提供清晰的结论和建议
        - 如果有异常，优先报告并给出处理建议
        - 预测时要说明假设条件和局限性

        请确保你的分析基于提供的时序数据，并给出专业的运维洞察。
    """
    
    llm = get_deepseek_model(0.5)
 
    print("🔍 [DEBUG] 创建 MCP 客户端...")
    client = MultiServerMCPClient(
        {
            "monitor-service": {
                "url": "http://127.0.0.1:10027/sse",
                "transport": "sse",
            }
        }
    )
    print("🔍 [DEBUG] 获取 MCP 工具...")
    async_tools = asyncio.run(client.get_tools())
    print("🔍 [DEBUG] 转换异步工具为同步工具...")
    sync_tools = convert_async_tools_to_sync(async_tools)
    
    messages_with_system = [SystemMessage(content=system_prompt)] + state["messages"]
    
    deeplog_agent = create_react_agent(
        llm,
        tools=sync_tools,
    )
 
    result = deeplog_agent.invoke({"messages": messages_with_system})

    print(f"🛠️ [DEEPLOG RAW] Agent 最终输出:\n{result['messages'][-1].content}\n" + "="*40)
 
 
    # 提取模型的最终回答
    final_analysis = None
    for message in reversed(result["messages"]):
        if isinstance(message, AIMessage) and not isinstance(message, ToolMessage):
            final_analysis = message.content
            break
    
    if final_analysis:
        print(f"📊 [DEEPLOG ANALYSIS] 模型分析结果:\n{final_analysis}\n" + "="*40)
    else:
        print("⚠️ [DEEPLOG ANALYSIS] 未找到模型的分析结果")
        final_analysis = "未生成分析结果"
        
    # --- 更健壮地提取原始工具结果 ---
    raw_tool_result = None
    # 从消息历史中倒序查找，确保找到的是最后一次工具调用的结果
    for message in reversed(result["messages"]):
        if isinstance(message, ToolMessage):
            raw_tool_result = message.content
            break  # 找到后立即退出循环
 
    if not raw_tool_result:
        raise ValueError("Agent 没有成功调用任何工具或未找到工具结果。")
    
    return Command(
            update={
                # 原始工具结果字符串存入一个独立的字段
                "deeplog_node_tool_results": raw_tool_result,
                # 模型的最终分析结果也存入state
                "deeplog_analysis_result": final_analysis
            },
            goto="__end__",
        )
    
    
    
graph = StateGraph(OverallState)
graph.add_node("deeplog", deeplog_node)  
graph.add_edge(START, "deeplog")  

app = graph.compile()

def draw_graph_image():
    try:
        # 使用 xray=True 显示更多细节
        image_data = app.get_graph(xray=True).draw_mermaid_png()
        
        # 保存到当前文件夹
        filename = "langgraph_workflow.png"
        with open(filename, "wb") as f:
            f.write(image_data)
        
        print(f"✅ LangGraph 流程图已保存到当前文件夹: {filename}")
        
    except Exception as e:
        print(f"⚠️ 无法生成流程图图片: {e}")
        
def parse_simple(returned_string):
    """
    简化的解析方法，假设格式固定为 ["{...}", null]
    """
    # 去除开头的 [" 和结尾的 ", null]
    if returned_string.startswith('["') and returned_string.endswith('", null]'):
        json_string = returned_string[2:-8]  # 去除 [" 和 ", null]
        # 处理转义字符
        json_string = json_string.replace('\\"', '"')
        return json.loads(json_string)
    return None


if __name__ == "__main__":
    print("--- Agent任务执行 ---")
    
    # 1. 定义要注入到图中的初始状态（测试用例）
    initial_state = {
        "messages": [
            HumanMessage(content="查询集群lf-lan-ha1在时间范围2025-12-04 14:00:00到2025-12-04 14:10:10的CPU指标数据")
        ]
    }
    
    try:
        final_state = app.invoke(initial_state)
        print("\n" + "="*20 + " 工作流执行完毕，开始分析结果 " + "="*20)
        
        cpu_data = parse_simple(final_state.get("deeplog_node_tool_results"))
        llm_analysis_result = final_state.get("deeplog_analysis_result")
        
        print(cpu_data)
        print(llm_analysis_result)
    
        # if analysis_result:
        #     print(f"\n{analysis_result}")
        # else:
        #     print("未生成分析结果")
        
    except Exception as e:
        print(f"执行出错: {e}")