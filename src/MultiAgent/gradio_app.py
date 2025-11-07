import gradio as gr
import random
from Director import graph
from langchain_core.messages import HumanMessage
import os
import sys
from datetime import datetime, timedelta
import json

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
        theme=gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="cyan",
            neutral_hue="slate"
        ),
        css="""
        /* 全局容器样式 */
        .gradio-container {
            max-width: 1400px !important;
            margin: auto !important;
            font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        
        /* 主标题样式 */
        .main-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-align: center;
            font-size: 2.5rem !important;
            font-weight: 700 !important;
            margin-bottom: 2rem !important;
            text-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        /* 聊天界面样式 */
        .chatbot {
            border: 2px solid #e2e8f0 !important;
            border-radius: 16px !important;
            box-shadow: 0 10px 25px rgba(0,0,0,0.1) !important;
            background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%) !important;
        }
        
        /* 输入框样式 */
        .input-textbox {
            border: 2px solid #e2e8f0 !important;
            border-radius: 12px !important;
            transition: all 0.3s ease !important;
            font-size: 16px !important;
            padding: 12px !important;
        }
        
        .input-textbox:focus {
            border-color: #667eea !important;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
            transform: translateY(-1px) !important;
        }
        
        /* 按钮样式 */
        .primary-button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            border: none !important;
            border-radius: 10px !important;
            color: white !important;
            font-weight: 600 !important;
            transition: all 0.3s ease !important;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3) !important;
        }
        
        .primary-button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4) !important;
        }
        
        .secondary-button {
            background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%) !important;
            border: 2px solid #cbd5e1 !important;
            border-radius: 10px !important;
            color: #475569 !important;
            font-weight: 600 !important;
            transition: all 0.3s ease !important;
        }
        
        .secondary-button:hover {
            background: linear-gradient(135deg, #e2e8f0 0%, #cbd5e1 100%) !important;
            transform: translateY(-1px) !important;
        }
        
        /* 时间选择按钮样式 */
        .time-button {
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%) !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 8px !important;
            color: #475569 !important;
            font-size: 13px !important;
            font-weight: 500 !important;
            padding: 8px 12px !important;
            margin: 3px !important;
            transition: all 0.2s ease !important;
            min-width: 80px !important;
        }
        
        .time-button:hover {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3) !important;
        }
        
        /* 手风琴样式 */
        .accordion {
            border: 1px solid #e2e8f0 !important;
            border-radius: 12px !important;
            margin: 16px 0 !important;
            overflow: hidden !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important;
        }
        
        .accordion-header {
            background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%) !important;
            padding: 16px !important;
            font-weight: 600 !important;
            color: #334155 !important;
        }
        
        /* 示例问题样式 */
        .examples {
            background: linear-gradient(135deg, #fef7ff 0%, #f3e8ff 100%) !important;
            border: 2px solid #e9d5ff !important;
            border-radius: 12px !important;
            padding: 20px !important;
            margin: 16px 0 !important;
        }
        
        .example-item {
            background: white !important;
            border: 1px solid #d8b4fe !important;
            border-radius: 8px !important;
            padding: 12px !important;
            margin: 8px 0 !important;
            transition: all 0.2s ease !important;
            cursor: pointer !important;
        }
        
        .example-item:hover {
            background: #f3e8ff !important;
            transform: translateX(4px) !important;
            box-shadow: 0 4px 12px rgba(139, 92, 246, 0.15) !important;
        }
        
        /* 系统信息样式 */
        .system-info {
            background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%) !important;
            border: 2px solid #bae6fd !important;
            border-radius: 12px !important;
            padding: 20px !important;
        }
        
        .system-info h3 {
            color: #0369a1 !important;
            font-weight: 700 !important;
            margin-bottom: 12px !important;
        }
        
        .system-info ul {
            color: #0c4a6e !important;
        }
        
        /* 时间选择区域样式 */
        .time-selector-section {
            background: linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%) !important;
            border: 2px solid #bbf7d0 !important;
            border-radius: 12px !important;
            padding: 20px !important;
            margin: 16px 0 !important;
        }
        
        .time-category-title {
            color: #166534 !important;
            font-weight: 700 !important;
            font-size: 16px !important;
            margin-bottom: 12px !important;
            text-align: center !important;
        }
        
        /* 响应式设计 */
        @media (max-width: 768px) {
            .gradio-container {
                max-width: 100% !important;
                padding: 10px !important;
            }
            
            .main-header {
                font-size: 2rem !important;
            }
            
            .time-button {
                min-width: 70px !important;
                font-size: 12px !important;
                padding: 6px 8px !important;
            }
        }
        
        /* 动画效果 */
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .fade-in-up {
            animation: fadeInUp 0.6s ease-out;
        }
        
        /* 加载动画 */
        .loading-dots {
            display: inline-block;
        }
        
        .loading-dots:after {
            content: '...';
            animation: dots 2s infinite;
        }
        
        @keyframes dots {
            0%, 20% { content: '.'; }
            40% { content: '..'; }
            60%, 100% { content: '...'; }
        }
        """
    ) as demo:
        
        gr.Markdown(
            """
            <div class="main-header fade-in-up">
                🤖 Multi-Agent 运维线上客服
            </div>
            <div style="text-align: center; margin-bottom: 2rem; color: #64748b; font-size: 1.1rem;">
                🚀 智能化运维助手 | 🔍 Deeplog-ck日志查询 | 🛠️ 跨平台数据收集整合分析
            </div>
            """,
            elem_classes="main-header-container"
        )
        
        # 聊天界面
        chatbot = gr.Chatbot(
            label="💬 对话记录",
            height=550,
            show_label=True,
            container=True,
            bubble_full_width=False,
            elem_classes="chatbot fade-in-up",
            avatar_images=("🧑‍💻", "🤖")
        )
        
        # 输入框
        msg = gr.Textbox(
            label="💭 请输入您的问题",
            placeholder="💡 例如：帮我查询域名信息、查询CK平台日志数据、监控服务器状态...",
            lines=2,
            max_lines=5,
            elem_classes="input-textbox fade-in-up"
        )
        
        # 按钮组
        with gr.Row(elem_classes="fade-in-up"):
            submit_btn = gr.Button(
                "🚀 发送",
                variant="primary",
                scale=2,
                elem_classes="primary-button"
            )
            clear_btn = gr.Button(
                "🗑️ 清空对话",
                variant="secondary",
                scale=1,
                elem_classes="secondary-button"
            )
            
            
        # 时间选择卡片
        with gr.Accordion("🕒 快速时间选择", open=False, elem_classes="accordion time-selector-section fade-in-up"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown(
                        "<div class='time-category-title'>⏰ 相对时间</div>",
                        elem_classes="time-category-header"
                    )
                    
                    with gr.Row():
                        last_5min = gr.Button("⚡ 最近5分钟", size="sm", elem_classes="time-button")
                        last_15min = gr.Button("🔥 最近15分钟", size="sm", elem_classes="time-button")
                        last_30min = gr.Button("⭐ 最近30分钟", size="sm", elem_classes="time-button")
                    
                    with gr.Row():
                        last_1hour = gr.Button("🚀 最近1小时", size="sm", elem_classes="time-button")
                        last_3hours = gr.Button("💫 最近3小时", size="sm", elem_classes="time-button")
                        last_6hours = gr.Button("🌟 最近6小时", size="sm", elem_classes="time-button")
                    
                    with gr.Row():
                        last_12hours = gr.Button("🌙 最近12小时", size="sm", elem_classes="time-button")
                        last_24hours = gr.Button("📅 最近24小时", size="sm", elem_classes="time-button")
                        last_7days = gr.Button("📆 最近7天", size="sm", elem_classes="time-button")
                
                with gr.Column(scale=1):
                    gr.Markdown(
                        "<div class='time-category-title'>📍 今日时间</div>",
                        elem_classes="time-category-header"
                    )
                    
                    with gr.Row():
                        today_morning = gr.Button("🌅 今天上午 (08:00-12:00)", size="sm", elem_classes="time-button")
                        today_afternoon = gr.Button("☀️ 今天下午 (12:00-18:00)", size="sm", elem_classes="time-button")
                    
                    with gr.Row():
                        today_evening = gr.Button("🌆 今天晚上 (18:00-22:00)", size="sm", elem_classes="time-button")
                        today_night = gr.Button("🌃 今天夜间 (22:00-02:00)", size="sm", elem_classes="time-button")
                    
                    with gr.Row():
                        today_all = gr.Button("🔄 今天全天", size="sm", elem_classes="time-button")
                        today_working = gr.Button("💼 工作时间 (09:00-18:00)", size="sm", elem_classes="time-button")
                

        
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
                return f"时间段：{description} ({start_time} 到 {end_time})\n"
            else:
                return f"时间段：{start_time} 到 {end_time}\n"
        
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
            fn=lambda: on_relative_time_click("5分钟", 5),
            outputs=msg
        )
        
        last_15min.click(
            fn=lambda: on_relative_time_click("15分钟", 15),
            outputs=msg
        )
        
        last_30min.click(
            fn=lambda: on_relative_time_click("30分钟", 30),
            outputs=msg
        )
        
        last_1hour.click(
            fn=lambda: on_relative_time_click("1小时", 60),
            outputs=msg
        )
        
        last_3hours.click(
            fn=lambda: on_relative_time_click("3小时", 180),
            outputs=msg
        )
        
        last_6hours.click(
            fn=lambda: on_relative_time_click("6小时", 360),
            outputs=msg
        )
        
        last_12hours.click(
            fn=lambda: on_relative_time_click("12小时", 720),
            outputs=msg
        )
        
        last_24hours.click(
            fn=lambda: on_relative_time_click("24小时", 1440),
            outputs=msg
        )
        
        last_7days.click(
            fn=lambda: on_relative_time_click("7天", 10080),
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