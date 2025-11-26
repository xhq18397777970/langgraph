from typing import Annotated, Sequence, List, Literal 
from pydantic import BaseModel, Field 
from langchain_core.messages import HumanMessage

from langgraph.types import Command 
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import create_react_agent 
from IPython.display import Image, display 
from dotenv import load_dotenv


import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.model_config import get_deepseek_model
#配置加载
load_dotenv()
llm = get_deepseek_model()

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

class Supervisor(BaseModel):
    next: Literal["domain_expert", "deeplog_expert"] = Field(
        description="决定在工作流序列中接下来激活哪位专家： "
                    "'当用户需要查询域名信息查询、域名状态检查时选择'domain_expert',"
                    "当用户需要查询某时间段内监控日志(如:域名在指定时段QPS、出入口带宽,状态码分布)需要额外的事实、数据收集时选择'deeplog_expert',"
    )
    reason: str = Field(
        description="路由决策的详细理由，解释选择特定专家的背后逻辑，以及这一选择如何推动任务向完成迈进。"
    )

def supervisor_node(state: MessagesState) -> Command[Literal["domain_expert", "deeplog_expert"]]:

    system_prompt = ('''
        **IMPORTANT**: You must respond with a valid JSON object that follows the specified schema.

        你是一个工作流监督者，管理两个专业智能体：域名信息查询专家（domain_expert）和日志检索专家（deeplog_expert）。
        你的决策目标是**完成用户的所有子任务并及时交付**，而不是在节点间无限往返。

        **工作步骤**：
        1) 重新阅读用户的原始请求，列出需要完成的所有子任务（域名信息、日志区间等）。
        2) 结合对话历史，标记哪些子任务已经有来自对应专家的结果，哪些仍然缺失。
        3) 仅对“未完成的子任务”选择下一位专家；不要重复派发同一专家超过 2 次，若最近两轮没有新增信息，则直接转交 validator 结束或总结。
        4) 所有子任务都已覆盖时，不再循环分派，改由 validator 做最终判定。

        **可选节点**：
        - domain_expert：负责域名状态/管理者等域名信息查询。
        - deeplog_expert：负责特定时间段的日志/指标数据查询。

        **输出要求**：
        - 始终返回结构化 JSON：{"next": "domain_expert" | "deeplog_expert", "reason": "为何选择该节点/或直接结束路由"}
        - 理由需包含“剩余未完成的子任务列表”或“已完成，无需继续分派”，避免空泛表述。
        - 如果无法从历史中提取有效信息，请谨慎选择最可能补全缺口的节点，而不是在两个节点之间来回切换。
    ''')
    
    messages = [
        {"role": "system", "content": system_prompt},  
    ] + state["messages"] 

    response = llm.with_structured_output(Supervisor).invoke(messages)

    goto = response.next
    reason = response.reason

    print(f"--- 工作流转移: Supervisor → {goto.upper()} ---")
    
    return Command(
        update={
            "messages": [
                HumanMessage(content=reason, name="supervisor")
            ]
        },
        goto=goto,  
    )
    
def domain_node(state: MessagesState) -> Command[Literal["validator"]]:

    """
        domain agent node that gathers information about Metadata related to domain.
        Takes the current task state, performs relevant domain,
        and returns findings for validation.
    """
    
    client = MultiServerMCPClient(
            {
                "domain-info-service": {
                    "url": "http://127.0.0.1:10025/sse",
                    "transport": "sse",
                }
            }
        )
    print("🔍 [DEBUG] 获取 MCP 工具...")
    async_tools = asyncio.run(client.get_tools())
    sync_tools = convert_async_tools_to_sync(async_tools)
    
    
    domain_agent = create_react_agent(
        llm,  
        tools=sync_tools,  
        state_modifier= "您是一名域名信息查询专家研究方面具备深厚专业能力。您的主要职责包括："
                        "1. 根据用户提供域名信息，查询背景识别关键信息需求"
                        "2. 调用所拥有的工具，从可靠来源收集相关、准确且最新的信息"
                        "3. 以结构化、易于理解的形式整理研究发现"
                        "4. 专注于信息收集工作——不进行分析或实施建议"
                        "CRITICAL: To select and use a tool, your entire response must be a single valid JSON object. Do not include any text before or after the JSON."
    )

    result = domain_agent.invoke(state)

    print(f"--- 工作流转移: Researcher → Validator ---")

    return Command(
        update={
            "messages": [ 
                HumanMessage(
                    content=result["messages"][-1].content,  
                    name="domain_expert"  
                )
            ]
        },
        goto="validator", 
    )
    
    
def deeplog_node(state: MessagesState) -> Command[Literal["validator"]]:

    client = MultiServerMCPClient(
            {
                "deeplog-ck-server": {
                    "url": "http://127.0.0.1:10026/sse",
                    "transport": "sse",
                }
            }
        )
    print("🔍 [DEBUG] 获取 MCP 工具...")
    async_tools = asyncio.run(client.get_tools())
    sync_tools = convert_async_tools_to_sync(async_tools)
    
    # 创建具备数学计算与数据分析能力的 ReAct 智能体
    deeplog_agent = create_react_agent(
        llm,
        tools=sync_tools,
        state_modifier=(
            "你是一名日志检索专家。专注于指定时间段的日志查询任务（包括查询域名的QPS历史数据、出入口带宽，域名后端实例的请求数）",
            "CRITICAL: To select and use a tool, your entire response must be a single valid JSON object. Do not include any text before or after the JSON."
        )
    )

    # 调用智能体处理当前状态并获取结果
    result = deeplog_agent.invoke(state)

    # 打印工作流切换日志，方便追踪节点流转
    print(f"--- 工作流转到: deeplog → Validator ---")

    # 将智能体最新回复封装为 HumanMessage，并指定下一步跳转到 validator 节点
    return Command(
        update={
            "messages": [
                HumanMessage(content=result["messages"][-1].content, name="deeplog_expert")
            ]
        },
        goto="validator",
    )


# System prompt providing clear instructions to the validator agent
system_prompt = '''
    **IMPORTANT**: Return a strict JSON object following the schema, with no extra text.**

    你是工作流的最终验证器，必须确认“用户原始请求的每个子任务”都被明确完成后才允许结束。

    核查流程：
    1. 重读用户的原始请求，列出需要完成的子任务（域名信息、日志区间等）。
    2. 检查对话历史中各专家（domain_expert、deeplog_expert）的输出，逐项匹配这些子任务是否都有对应结果。
    3. 若有任何子任务缺失、回答含糊或工具未成功执行，必须返回 supervisor 继续分派；不要放宽要求。
    4. 仅当所有子任务都有清晰结果时，才返回 FINISH 结束流程。
    5. 如果已经两次回到 validator 仍未补全缺口，可直接根据当前信息作出完成/未完成的最终判定，避免无限循环。

    输出格式：
    {"next": "FINISH" | "supervisor", "reason": "简洁说明已覆盖/缺失的子任务"}
    - 理由需要点名哪些子任务已完成、哪些缺失，禁止泛泛而谈。
    - 只能使用上述两个取值，否则视为错误。
'''

class Validator(BaseModel):
    next: Literal["supervisor", "FINISH"] = Field(
        description="Specifies the next worker in the pipeline: 'supervisor' to continue or 'FINISH' to terminate."
    )
    reason: str = Field(
        description="The reason for the decision."
    )

def validator_node(state: MessagesState) -> Command[Literal["supervisor", "__end__"]]:

    user_question = state["messages"][0].content
    agent_answer = state["messages"][-1].content

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_question},
        {"role": "assistant", "content": agent_answer},
    ]

    response = llm.with_structured_output(Validator).invoke(messages)

    goto = response.next
    reason = response.reason

    if goto == "FINISH" or goto == END:
        goto = END  
        print(" --- Transitioning to END ---")  
    else:
        print(f"--- Workflow Transition: Validator → Supervisor ---")
 

    return Command(
        update={
            "messages": [
                HumanMessage(content=reason, name="validator")
            ]
        },
        goto=goto, 
    )
    

graph = StateGraph(MessagesState)

graph.add_node("supervisor", supervisor_node) 
graph.add_node("deeplog_expert", deeplog_node)  
graph.add_node("domain_expert", domain_node) 
# graph.add_node("coder", code_node) 
graph.add_node("validator", validator_node)  

graph.add_edge(START, "supervisor")  
app = graph.compile()
 
import pprint

inputs = {
    "messages": [
        ("user", "帮我查询api.m.jd.com域名的状态是否被注册，并且查询2025年11月20日14:00:00到14:01:00时间段，该域名下状态码的分布情况，按照10秒时间间隔"),
    ]
}

for event in app.stream(inputs):
    for key, value in event.items():
        if value is None:
            continue
        last_message = value.get("messages", [])[-1] if "messages" in value else None
        if last_message:
            pprint.pprint(f"Output from node '{key}':")
            pprint.pprint(last_message, indent=2, width=80, depth=None)
            print()
     