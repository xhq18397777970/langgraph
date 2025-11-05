# Director多Agent系统 Gradio界面

这是一个基于LangGraph构建的多Agent智能助手系统，通过Gradio提供友好的Web界面。

## 功能特性

- 🗺️ **旅游规划**：智能推荐旅游路线和景点
- 😄 **笑话生成**：创作有趣的笑话内容
- 📝 **对联创作**：生成精彩的对联作品
- 💬 **通用问答**：处理其他类型的咨询问题

## 系统架构

- **Supervisor Node**: 负责问题分类和任务调度
- **Travel Node**: 专门处理旅游相关问题
- **Joke Node**: 专门生成笑话内容
- **Couplet Node**: 专门创作对联
- **Other Node**: 处理其他类型问题

## 安装和运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 环境配置

确保设置以下环境变量：

```bash
export DEEPSEEK_API_KEY="your_deepseek_api_key"
export DEEPSEEK_BASE_URL="https://api.deepseek.com"
export DEEPSEEK_MODEL="deepseek-chat"
```

或者在项目根目录创建 `.env` 文件：

```
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

### 3. 启动应用

```bash
cd src/MultiAgent
python gradio_app.py
```

应用将在 `http://localhost:7860` 启动。

## 使用示例

### 旅游规划
- "推荐一个三天的北京旅游路线"
- "我想去云南旅游，有什么好的建议吗？"

### 笑话生成
- "讲一个程序员的笑话"
- "来个冷笑话"

### 对联创作
- "帮我对个对联，上联是：春风得意马蹄疾"
- "创作一个关于新年的对联"

### 其他问题
- "今天天气怎么样？"
- "你能做什么？"

## 技术栈

- **LangGraph**: 多Agent工作流编排框架
- **LangChain**: 大语言模型集成工具
- **DeepSeek**: 底层语言模型
- **Gradio**: Web界面框架
- **Python**: 主要编程语言

## 文件结构

```
src/MultiAgent/
├── Director.py          # 多Agent系统核心逻辑
├── DirectorServer.py    # 服务器测试脚本
├── gradio_app.py        # Gradio Web界面
├── requirements.txt     # 项目依赖
└── README.md           # 使用说明
```

## 注意事项

1. 确保网络连接正常，能够访问DeepSeek API
2. API密钥需要有足够的调用额度
3. 首次运行可能需要下载相关依赖包
4. 如遇到问题，请检查环境变量配置和网络连接

## 故障排除

### 常见问题

1. **API密钥错误**
   - 检查 `DEEPSEEK_API_KEY` 环境变量是否正确设置
   - 确认API密钥有效且有足够额度

2. **模块导入错误**
   - 确认已安装所有依赖：`pip install -r requirements.txt`
   - 检查Python路径配置

3. **网络连接问题**
   - 确认能够访问 `https://api.deepseek.com`
   - 检查防火墙和代理设置

4. **Gradio界面无法访问**
   - 检查端口7860是否被占用
   - 尝试更改端口号或重启应用