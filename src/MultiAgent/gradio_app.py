import gradio as gr
import random
from Director import graph
from langchain_core.messages import HumanMessage
import os
import sys
from datetime import datetime, timedelta

# 添加路径以导入模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def chat_with_director(message, history):
    """
    与Director多Agent系统交互的函数
    
    Args:
        message: 用户输入的消息
        history: 对话历史
    
    Returns:
        回复消息和更新后的历史记录
    """
    try:
        # 生成随机线程ID
        config = {
            "configurable": {
                "thread_id": random.randint(1, 10000)
            }
        }
        
        # 构建输入数据
        input_data = {
            "messages": [HumanMessage(content=message)]
        }
        
        # 调用多Agent系统
        result = graph.invoke(
            input_data,
            config=config,
            stream_mode="values"
        )
        
        # 提取最终回复
        if result and "messages" in result and result["messages"]:
            response = result["messages"][-1].content
        else:
            response = "抱歉，系统暂时无法处理您的请求。"
            
        return response
        
    except Exception as e:
        error_msg = f"系统出错：{str(e)}"
        print(f"Error: {error_msg}")
        return error_msg

def create_gradio_interface():
    """创建Gradio界面"""
    
    # 创建聊天界面
    with gr.Blocks(
        title="Director多Agent助手",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container {
            max-width: 800px !important;
            margin: auto !important;
        }
        .chat-message {
            padding: 10px;
            margin: 5px 0;
            border-radius: 10px;
        }
        .time-selector-card {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 15px;
            margin: 10px 0;
            background: #f8f9fa;
        }
        .time-button {
            margin: 2px;
        }
        """
    ) as demo:
        
        gr.Markdown(
            """
            # 🤖 Multi-Agent运维线上客服
            """
        )
                # 聊天界面
        chatbot = gr.Chatbot(
            label="对话记录",
            height=400,
            show_label=True,
            container=True,
            bubble_full_width=False
        )
        
        # 输入框
        msg = gr.Textbox(
            label="请输入您的问题",
            placeholder="例如：帮我查询域名信息、查询CK平台日志数据",
            lines=2,
            max_lines=5
        )
        
        # 按钮组
        with gr.Row():
            submit_btn = gr.Button("发送", variant="primary", scale=2)
            clear_btn = gr.Button("清空对话", variant="secondary", scale=1)
            
            
        # 时间选择卡片
        with gr.Accordion("🕒 快速时间选择", open=False):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("**相对时间**")
                    
                    with gr.Row():
                        last_5min = gr.Button("最近5分钟", size="sm",min_width=60, elem_classes="time-button")
                        last_15min = gr.Button("最近15分钟", size="sm",min_width=60, elem_classes="time-button")
                        last_30min = gr.Button("最近30分钟", size="sm", min_width=60,elem_classes="time-button")
                    
                    with gr.Row():
                        last_1hour = gr.Button("最近1小时", size="sm",min_width=60, elem_classes="time-button")
                        last_3hours = gr.Button("最近3小时", size="sm",min_width=60, elem_classes="time-button")
                        last_6hours = gr.Button("最近6小时", size="sm",min_width=60, elem_classes="time-button")
                    
                    with gr.Row():
                        last_12hours = gr.Button("最近12小时", size="sm", min_width=60,elem_classes="time-button")
                        last_24hours = gr.Button("最近24小时", size="sm",min_width=60, elem_classes="time-button")
                        last_7days = gr.Button("最近7天", size="sm",min_width=60, elem_classes="time-button")
                
                with gr.Column(scale=1):
                    gr.Markdown("**今日时间**")
                    
                    with gr.Row():
                        today_morning = gr.Button("今天上午 (08:00-12:00)", size="sm", elem_classes="time-button")
                        today_afternoon = gr.Button("今天下午 (12:00-18:00)", size="sm", elem_classes="time-button")
                    
                    with gr.Row():
                        today_evening = gr.Button("今天晚上 (18:00-22:00)", size="sm", elem_classes="time-button")
                        today_night = gr.Button("今天夜间 (22:00-02:00)", size="sm", elem_classes="time-button")
                    
                    with gr.Row():
                        today_all = gr.Button("今天全天", size="sm", elem_classes="time-button")
                        today_working = gr.Button("工作时间 (09:00-18:00)", size="sm", elem_classes="time-button")
                

        
        # 示例问题
        gr.Examples(
            examples=[
                "查询jd.com域名注册状态、详细信息",
                "查询域名QPS，带宽","查询LB服务器QPS","状态码404占比","404访问最多地址",
                "后端实例访问统计"
            ],
            inputs=msg,
            label="示例问题"
        )
        
        # 系统信息
        with gr.Accordion("系统信息", open=False):
            gr.Markdown(
                """
                ### 🔧 系统架构
                - **Supervisor Node**: 负责问题分类和任务调度
                - **Travel Node**: 专门处理旅游相关问题
                - **Joke Node**: 专门生成笑话内容
                - **Couplet Node**: 专门创作对联
                - **Other Node**: 处理其他类型问题
                
                ### 🚀 技术栈
                - **LangGraph**: 多Agent工作流编排
                - **LangChain**: 大语言模型集成
                - **DeepSeek**: 底层语言模型
                - **Gradio**: Web界面框架
                """
            )
        
        def respond(message, chat_history):
            """处理用户输入并更新对话历史"""
            if not message.strip():
                return "", chat_history
            
            # 获取系统回复
            bot_message = chat_with_director(message, chat_history)
            
            # 更新对话历史
            chat_history.append((message, bot_message))
            
            return "", chat_history
        
        def clear_chat():
            """清空对话历史"""
            return None, []
        
        # 时间选择功能函数
        def get_current_time():
            """获取当前时间"""
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        def calculate_time_range(minutes_ago):
            """计算相对时间范围"""
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=minutes_ago)
            return start_time.strftime("%Y-%m-%d %H:%M:%S"), end_time.strftime("%Y-%m-%d %H:%M:%S")
        
        def get_today_time_range(start_hour, end_hour):
            """获取今天指定时间段"""
            today = datetime.now().date()
            start_time = datetime(today.year, today.month, today.day, start_hour, 0, 0)
            end_time = datetime(today.year, today.month, today.day, end_hour, 0, 0)
            
            # 如果结束时间小于开始时间，说明跨天了
            if end_hour < start_hour:
                end_time += timedelta(days=1)
                
            return start_time.strftime("%Y-%m-%d %H:%M:%S"), end_time.strftime("%Y-%m-%d %H:%M:%S")
        
        def format_time_message(start_time, end_time, description=None):
            """格式化时间选择消息"""
            if description:
                return f"时间段：{description} ({start_time} 到 {end_time})"
            else:
                return f"时间段：{start_time} 到 {end_time}"
        
        def append_time_to_input(current_input, start_time, end_time, description=None):
            """将时间信息添加到输入框"""
            time_message = format_time_message(start_time, end_time, description)
            
            if current_input:
                # 如果已有内容，换行添加时间信息
                return f"{current_input}\n{time_message}"
            else:
                return time_message
        
        # 相对时间按钮点击事件
        def on_relative_time_click(btn_label, minutes):
            start, end = calculate_time_range(minutes)
            return append_time_to_input("", start, end, btn_label)
        
        # 今日时间按钮点击事件
        def on_today_time_click(btn_label, start_hour, end_hour):
            start, end = get_today_time_range(start_hour, end_hour)
            return append_time_to_input("", start, end, btn_label)
        
        # 绑定时间选择事件
        # 相对时间
        last_5min.click(
            fn=lambda: on_relative_time_click("最近5分钟", 5),
            outputs=msg
        )
        
        last_15min.click(
            fn=lambda: on_relative_time_click("最近15分钟", 15),
            outputs=msg
        )
        
        last_30min.click(
            fn=lambda: on_relative_time_click("最近30分钟", 30),
            outputs=msg
        )
        
        last_1hour.click(
            fn=lambda: on_relative_time_click("最近1小时", 60),
            outputs=msg
        )
        
        last_3hours.click(
            fn=lambda: on_relative_time_click("最近3小时", 180),
            outputs=msg
        )
        
        last_6hours.click(
            fn=lambda: on_relative_time_click("最近6小时", 360),
            outputs=msg
        )
        
        last_12hours.click(
            fn=lambda: on_relative_time_click("最近12小时", 720),
            outputs=msg
        )
        
        last_24hours.click(
            fn=lambda: on_relative_time_click("最近24小时", 1440),
            outputs=msg
        )
        
        last_7days.click(
            fn=lambda: on_relative_time_click("最近7天", 10080),
            outputs=msg
        )
        
        # 今日时间
        today_morning.click(
            fn=lambda: on_today_time_click("今天上午", 8, 12),
            outputs=msg
        )
        
        today_afternoon.click(
            fn=lambda: on_today_time_click("今天下午", 12, 18),
            outputs=msg
        )
        
        today_evening.click(
            fn=lambda: on_today_time_click("今天晚上", 18, 22),
            outputs=msg
        )
        
        today_night.click(
            fn=lambda: on_today_time_click("今天夜间", 22, 2),
            outputs=msg
        )
        
        today_all.click(
            fn=lambda: on_today_time_click("今天全天", 0, 23),
            outputs=msg
        )
        
        today_working.click(
            fn=lambda: on_today_time_click("工作时间", 9, 18),
            outputs=msg
        )
        
        # 绑定聊天事件
        submit_btn.click(
            respond,
            inputs=[msg, chatbot],
            outputs=[msg, chatbot]
        )
        
        msg.submit(
            respond,
            inputs=[msg, chatbot],
            outputs=[msg, chatbot]
        )
        
        clear_btn.click(
            clear_chat,
            outputs=[chatbot, msg]
        )
    
    return demo

if __name__ == "__main__":
    # 检查环境变量
    required_env_vars = ["DEEPSEEK_API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"⚠️  警告：缺少环境变量: {', '.join(missing_vars)}")
        print("请确保已设置相关环境变量，否则系统可能无法正常工作。")
    
    # 创建并启动界面
    demo = create_gradio_interface()
    
    print("🚀 启动Gradio界面...")
    print("📝 支持的功能：域名检查、CK平台日志分析、监控数据查询、其他问题")
    print("🕒 新增功能：快速时间选择器")
    print("🌐 访问地址：http://localhost:7860")
    
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
        quiet=False
    )