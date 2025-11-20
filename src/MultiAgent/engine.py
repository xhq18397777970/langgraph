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
        
        您是一个工作流监督者，管理着由三个专业智能体组成的团队：域名信息查询专家、日志检索专家。您的职责是根据任务的当前状态和需求，选择最合适的下一个智能体来协调工作流程。请为每个决策提供清晰、简洁的理由，以确保决策过程的透明度。

        **团队成员**：
        2. **域名信息查询专家**：专门负责域名元数据信息收集（域名状态、管理者）、事实查找以及收集解决用户请求所需的相关数据。
        3. **日志检索专家**：专注于历史日志数据的检索（指定时间段的事实数据，为解决问题提供有力的数据支撑）。

        **您的职责**：
        1. 分析每个用户请求和智能体响应的完整性、准确性和相关性。
        2. 在每个决策点将任务路由至最合适的智能体。
        3. 通过智能体分配来保持工作流的顺畅推进。
        4. 持续该过程，直到用户的请求得到完全且令人满意的解决。

        您的目标是创建一个高效的工作流，充分利用每个智能体的优势，同时尽量减少不必要的步骤，最终为用户请求提供完整且准确的解决方案。 
                 
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
    **IMPORTANT**: You must respond with a valid JSON object that follows the specified schema.
    Your task is to ensure reasonable quality. 
    Specifically, you must:
    - Review the user's question (the first message in the workflow).
    - Review the answer (the last message in the workflow).
    - If the answer addresses the core intent of the question, even if not perfectly, signal to end the workflow with 'FINISH'.
    - Only route back to the supervisor if the answer is completely off-topic, harmful, or fundamentally misunderstands the question.
    
    - Accept answers that are "good enough" rather than perfect
    - Prioritize workflow completion over perfect responses
    - Give benefit of doubt to borderline answers
    
    Routing Guidelines:
    1. 'supervisor' Agent: ONLY for responses that are completely incorrect or off-topic.
    2. Respond with 'FINISH' in all other cases to end the workflow.
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
     