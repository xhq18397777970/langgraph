
from typing import Annotated, Sequence, List, Literal 
from pydantic import BaseModel, Field 
from langchain_core.messages import HumanMessage,AIMessage
from langchain_core.tools import tool
from langgraph.types import Command 
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import create_react_agent 
from dotenv import load_dotenv

import os
from langchain_openai import ChatOpenAI
import json

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

load_dotenv()


def supervisor_node(state: MessagesState) -> Command[Literal["domain", "deeplog"]]:
    
    llm = get_deepseek_model(temperature=0.4)
    # supervisor_system_prompt = '''
    #     **最终输出格式要求**:
    #     你的**唯一**输出必须是一个有效的JSON对象。不要在JSON对象前后添加任何解释性文字、代码块标记（如```json）或任何其他内容。
        
    #     **输出格式示例**:
    #     {
    #         "next": "domain"  或 "deeplog",
    #         "reason": "详细的决策理由，解释为什么选择该专家"
    #     }
    #     【重要】"next"字段的值必须是以下三者之一，绝对不能是其他任何值：domain、deeplog
        
    #     **示例 1**:
    #     用户输入: "帮我看看facebook.com的所有人信息。"
    #     期望输出: {"next": "domain", "reason": "用户明确要求查询域名信息，需要激活domain。"}
    #     **示例 2**:
    #     用户输入: "昨天下午2点到4点的CPU负载日志给我看一下。"
    #     期望输出: {"next": "deeplog", "reason": "用户需要查询特定时间段内的历史指标数据，这是deeplog的工作。"}
        
    #     **违反格式的后果**:
    #     如果你的输出不是纯JSON对象，系统将无法解析并导致任务失败。请确保你的输出可以直接被Python的json.loads()函数解析。
        
        
	#     你是一个工作流主管，管理着一个由2个专业代理组成的团队：domain、deeplog
    #     你的角色是通过根据任务的当前状态和需求选择最合适的下一个node。
 
    #     **团队成员**:
    #     1. domain_expert：专门从事域名信息的查询，比如域名的注册状态、管理者
    #     2. deeplog_expert：专门负责检索域名指定时间段日志信息（QPS）。
 
    #     **你的职责**:
    #     1. 分析用户请求，判断需要哪个专家来处理。
    #     2. 将任务路由到最合适的node。

    # '''
    supervisor_system_prompt = '''
        你是一个工作流调度器，负责将用户任务分配给合适的专家节点。

        输出格式: JSON
        {
            "next": "domain" 或 "deeplog",
            "reason": "一句简洁的决策依据"
        }
        
        **各节点职责**:
        - `domain`: 处理域名元数据(注册状态、管理者)相关的查询请求。
        - `deeplog`: 处理指定时间段的历史指标数据查询请求。
        
        **路由规则**:
        1.  检查对话历史，找出尚未完成的用户子任务。
        2.  根据子任务类型，从上述节点中选择一个进行调度。
            -   如果存在域名查询子任务，则选择 `domain`。
            -   如果域名任务已完成，但存在指标数据查询子任务，则选择 `deeplog`。
        3.  如果所有任务均已完成，则你的逻辑应该由 `validator` 来处理，你只需在收到新请求时进行路由。
        
        **理由示例**:
        -   `{"next": "domain", "reason": "当前已完成xx子任务,待完成xx任务"}`
        '''
    messages = [
        {"role": "system", "content": supervisor_system_prompt}, 
        ] + state["messages"] 

    response = llm.invoke(messages)

    # 从响应中提取内容
    try:
        # 模型可能会在JSON前后加上```json ```标记，我们尝试清理它
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        
        # 解析JSON
        response_dict = json.loads(content)
        # print(response_dict)
        
        # 确保字段存在
        goto = response_dict.get("next")
        reason = response_dict.get("reason", "未提供理由")
        
        print(f"supervisor 结果为  [{goto}]")
        print(f"supervisor 理由为  [{reason}]")
        
        if goto not in ["domain", "deeplog"]:
            raise ValueError(f"无效的路由决策: {goto}")
 
        print(f"--- 工作流转移: Supervisor → {goto.upper()} ---")
        
        return Command(
            update={
                "messages": [
                    AIMessage(content=reason, name="supervisor")
                ]
            },
            goto=goto,  
        )
    except (json.JSONDecodeError, AttributeError, ValueError) as e:
        # 如果解析失败，打印错误信息并抛出异常
        print("--- 模型输出解析失败 ---")
        print(f"模型原始回复: {response.content}")
        print(f"错误信息: {e}")
        raise ValueError("模型未能返回有效的JSON格式决策。") from e


# validator_system_prompt = '''
#         你是一个工作流验证器，负责判断用户的任务是否已经完全、准确地完成。
        
#         **你的唯一职责**：
#         审查所有的对话历史（messages），并做出最终决策：是继续工作，还是结束流程。
        
#         **判断标准（按优先级排序）**：
#         1.  **核心需求满足度**：
#             *   用户的原始问题是否得到了直接、明确的回答？
#             *   如果是查询类请求，返回的数据是否全面、准确？
#             *   如果是创作类请求，生成的内容是否符合用户的所有要求？
        
#         2.  **执行正确性**：
#             *   业务节点是否调用了正确的工具？
#             *   工具调用的结果是否有效、无错误？
#             *   是否存在明显的逻辑矛盾或事实错误？
        
#         3.  **任务完整性**：
#             *   对于多步骤任务，所有步骤是否都已执行完毕？
#             *   是否有任何遗漏的环节？
        
#         **决策流程**：
#         1.  首先，仔细审查用户最初的请求。
#         2.  然后，依次分析之后每个节点的输出，评估其对满足用户需求的贡献。
#         3.  最后，根据上述判断标准进行综合评估。
        
#         **输出格式**：
#         你必须严格按照以下JSON格式返回你的决策，不要有任何额外文字。
#         {
#             "next": "__end__" 或 "supervisor",
#             "reason": "详细说明你的判断依据，引用对话历史中的具体内容来支持你的结论。"
#         }
#         【重要】"next"字段的值必须是以下两者之一，绝对不能是其他任何值：__end__、supervisor
        
#         **决策指引**：
#         - 如果任务已完美完成，或无法进一步推进，则返回 "__end__"。
#         - 如果任务未完成、结果有误、或需要修正/补充，则返回 "supervisor"，让主管重新调度。
# '''

validator_system_prompt = '''
        你是一个工作流程验证器，你的唯一职责是判断用户的原始任务是否已经完全完成。
        
        **判断规则**：
        1.  仔细识别用户最初的、完整的请求。
        2.  检查对话历史，确认所有请求的子任务是否都已由相关专家执行并返回了结果。
        3.  如果所有子任务都有明确的执行记录和结果输出，则任务完成。
        4.  如果仍有任何子任务未被处理或处理失败，则任务未完成。
        
        **输出要求**：
        你必须严格按照以下JSON格式返回你的决策，**不得包含任何额外的解释、叙述或对话历史复述**。
        
        {
            "next": "__end__" 或 "supervisor",
            "reason": "用一句话说明任务完成或未完成的核心事实。"
        }
        
        完成"next"值为"__end__"，未完成为 "supervisor"。
        
        【重要】
        - "next" 字段只能是 "__end__" 或 "supervisor"。
        - "reason" 字段必须是简洁、客观的结论性陈述，例如：
            - (完成) "域名查询和日志查询两项任务均已完成。"
            - (未完成) "域名查询已完成，但日志查询任务尚未执行。"
            - (未完成) "两项任务均未执行。"
        
        **决策指引**：
        - 任务完成 -> 返回 "__end__"
        - 任务未完成 -> 返回 "supervisor"
'''

def validator_node(state: MessagesState) -> Command[Literal["supervisor", "__end__"]]:

    llm = get_deepseek_model(temperature=0.4)
    
    #validator获取所有message对话历史
    messages = [
        {"role": "system", "content": validator_system_prompt}
    ] + state["messages"]

    response = llm.invoke(messages)
    
    # 从响应中提取内容
    try:
        # 模型可能会在JSON前后加上```json ```标记，我们尝试清理它
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        
        # 解析JSON
        response_dict = json.loads(content)
        # print(response)
        
        # 确保字段存在
        goto = response_dict.get("next")
        print(f"validator 结果为  [ {goto}]")
        reason = response_dict.get("reason", "未提供理由")
        print(f"validator 理由为  [ {reason}]")
        
        if goto not in ["__end__", "supervisor"]:
            raise ValueError(f"无效的路由决策: {goto}")
        if goto =="__end__":
            print(" --- Transitioning to END ---")
        else:
            print(f"--- 工作流转移: validator → supervisor ---")
        
        return Command(
            update={
                "messages": [
                    AIMessage(content=reason, name="validator")
                ]
            },
            goto=goto,  
        )
    except (json.JSONDecodeError, AttributeError, ValueError) as e:
        # 如果解析失败，打印错误信息并抛出异常
        print("--- validator解析失败 ---")
        print(f"模型原始回复: {response.content}")
        print(f"错误信息: {e}")
        raise ValueError("validator未能返回有效的JSON格式决策。") from e
    
@tool
def domain_user_info(domain):

    """
    查询指定域名的管理人信息。
    输入：域名
    输出：域名的管理者
    Args:
        domain (str): 需要查询的完整域名。请提供一个不含协议（如http://）和路径（如/path）的纯净域名，例如 'google.com' 或 'github.com'。
    """
    print("[domain_info]工具被调用")
    return f"域名 {domain} 的管理者为：谢晗琦"

@tool
def domain_register_info(domain):
    """
    查询指定域名的注册状态，只有"未注册","已注册"两种结果
    输入：域名
    输出：域名的注册状态
    Args:
        domain (str): 需要查询的完整域名。请提供一个不含协议（如http://）和路径（如/path）的纯净域名，例如 'google.com' 或 'github.com'。
    """
    print("[domain_info]工具被调用")
    return f"域名 {domain} 的注册状态为：已注册"

@tool
def history_info(time):

    """
    根据指定的时间范围，检索域名的QPS数据
    输入：时间段
    输出：域名指定时间段，QPS
    Args:
        time (str):如"2023-10-1-00:00:00至2023-10-1-00:05:00"
    """
    print("[history_info]工具被调用")
    return f"在该时间段：{time}，QPS平均值是：1.2"


def domain_node(state: MessagesState) -> Command[Literal["validator"]]:
    
    llm = get_deepseek_model(0.1)
    domain_system_prompt="""
        你是域名查询工具的执行器。
        你的任务是：从用户输入中提取域名，调用工具，然后只输出工具的返回结果。
        你必须忽略用户输入中所有与域名无关的内容。        
        
        你的回答必须严格按照格式：
        {
            "状态":"执行成功"
            "任务":"",
            "调用工具":"",
            "返回结果":"",
            ""
        }
    """

    state_with_prompt = state.copy()
    state_with_prompt["messages"] = [
        AIMessage(content=domain_system_prompt, name="system")
    ] + state["messages"]
    
    domain_agent = create_react_agent(
        llm,  
        tools=[domain_user_info,domain_register_info],
        # state_modifier=(domain_system_prompt)
    )
    # result = domain_agent.invoke(state)
    result = domain_agent.invoke(state_with_prompt)
    final_node_output = result["messages"][-1].content
    print(f"--- Domain Node 输出结果 ---\n{final_node_output}")
    print(f"--- 工作流转移: domain → Validator ---")

    return Command(
        update={
            "messages": [ 
                AIMessage(
                    content=result["messages"][-1].content,  
                    name="domain_expert"  
                )
            ]
        },
        goto="validator", 
    )
    
def deeplog_node(state: MessagesState) -> Command[Literal["validator"]]:
    
    llm = get_deepseek_model(0.1)
    deeplog_system_prompt="""
        你是一个日志查询工具的执行代理。你的唯一职责是调用已有工具并直接、完整地返回其结果。
        
        你的回答必须严格按照格式：
        {
            "任务":"",
            "调用工具":"",
            "返回结果":""
        }
        
        你是日志查询工具的执行器。
        你的任务是：从用户输入中提取时间范围，调用工具，然后只输出工具的返回结果。
        你必须忽略用户输入中所有与时间范围无关的内容。
 
    """
    state_with_prompt = state.copy()
    state_with_prompt["messages"] = [
        AIMessage(content=deeplog_system_prompt, name="system")
    ] + state["messages"]
    

    deeplog_agent = create_react_agent(
        llm,  
        tools=[history_info],
        # state_modifier=(deeplog_system_prompt)
    )
    
    result = deeplog_agent.invoke(state_with_prompt)
    final_node_output = result["messages"][-1].content
    print(f"--- Deeplog Node 输出结果 ---\n{final_node_output}")
    print(f"--- 工作流转移: deeplog → Validator ---")

    return Command(
        update={
            "messages": [ 
                AIMessage(
                    content=result["messages"][-1].content,  
                    name="deeplog_expert"  
                )
            ]
        },
        goto="validator", 
    )

graph = StateGraph(MessagesState)

graph.add_node("supervisor", supervisor_node) 
graph.add_node("deeplog", deeplog_node)  
graph.add_node("domain", domain_node) 
# graph.add_node("coder", code_node) 
graph.add_node("validator", validator_node)  

graph.add_edge(START, "supervisor")  
app = graph.compile()

 
if __name__ == "__main__":
    print("--- Agent任务执行 ---")
    
    # 1. 定义要注入到图中的初始状态（测试用例）
    initial_state = {
        "messages": [
            HumanMessage(content="帮我查询域名api.m.jd.com域名的注册信息，并且帮我查询其在2023年11月20日11:00:00到11:05:00时间段的QPS")
        ]
    }
    
    try:
        # 2. 使用 app.invoke() 将状态注入并运行整个图
        # 这会启动从 START 开始的完整工作流程
        final_state = app.invoke(initial_state)
 
        # 3. (可选) 打印最终的完整对话历史，以验证结果
        print("\n" + "=" * 20 + " 最终结果 " + "=" * 20)
        for i, message in enumerate(final_state["messages"]):
            print(f"--- 消息 {i} ---")
            print(f"[类型]: {type(message).__name__}")
            if message.name:
                print(f"[当前执行]: {message.name}")
            print(f"[内容]: {message.content}\n")
 
    except Exception as e:
        print(f"执行出错: {e}")