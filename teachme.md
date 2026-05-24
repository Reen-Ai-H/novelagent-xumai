# NovelAgent 使用与调试手册

这份手册用来帮助你从终端启动项目，并理解前端填写的数据如何进入 FastAPI 后端，后端如何调用云端 LLM，以及 LLM 的返回结果如何被处理并展示到页面。

## 1. 项目是什么

NovelAgent 是一个基于 FastAPI、LangGraph、LangChain 和云端大模型的网文共创工作台。

它不是只生成一段文本，而是把小说创作拆成多个可控阶段：

```text
前端填写创作信息
-> FastAPI 接收请求
-> LangGraph 推进工作流
-> Planner 生成剧情节点
-> 人工确认剧情节点
-> Writer 生成正文
-> Reviewer 审查正文
-> 人工接受或要求修订
-> Librarian 抽取稳定设定
-> 写入本地作品和长期记忆
```

项目入口文件是：

```text
C:\Users\asus\Desktop\learning\novelagent\main.py
```

前端页面在：

```text
C:\Users\asus\Desktop\learning\novelagent\frontend
```

后端 API 路由主要在：

```text
C:\Users\asus\Desktop\learning\novelagent\app\routes.py
C:\Users\asus\Desktop\learning\novelagent\app\novel_routes.py
```

LLM 调用代码主要在：

```text
C:\Users\asus\Desktop\learning\novelagent\app\chain.py
C:\Users\asus\Desktop\learning\novelagent\app\agents\planner_chain.py
C:\Users\asus\Desktop\learning\novelagent\app\agents\writer_chain.py
C:\Users\asus\Desktop\learning\novelagent\app\agents\reviewer_chain.py
C:\Users\asus\Desktop\learning\novelagent\app\agents\librarian_chain.py
```

## 2. 进入 conda 环境

当前机器上可用的 conda 环境包括：

```text
base
ai_project
label
pytorch
```

这个项目应该使用：

```text
ai_project
```

因为这个环境已经安装了 FastAPI、Uvicorn、LangChain、LangGraph 等项目依赖。

### 2.1 推荐方式：使用普通 cmd 或 Anaconda Prompt

打开普通 cmd，进入项目目录后，按 Cursor 那种方式执行：

```bat
C:/Users/asus/anaconda3/Scripts/activate
conda activate ai_project
cd C:\Users\asus\Desktop\learning\novelagent
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

也可以写成一行一行的完整 Windows 路径版本：

```bat
call C:\Users\asus\anaconda3\Scripts\activate.bat ai_project
cd /d C:\Users\asus\Desktop\learning\novelagent
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 2.2 如果使用普通 PowerShell

当前这台机器上，下面这种 PowerShell hook 写法会报错，不推荐使用：

```powershell
& "$env:USERPROFILE\anaconda3\shell\condabin\conda-hook.ps1"
conda activate ai_project
```

更稳的方式是在 PowerShell 里启动一个 cmd 会话来运行 conda：

```powershell
cmd /k "C:/Users/asus/anaconda3/Scripts/activate && conda activate ai_project && cd /d C:\Users\asus\Desktop\learning\novelagent"
```

进入后再运行：

```bat
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 2.3 如果使用 Codex 里的 PowerShell 7 终端

Codex 终端当前是 PowerShell 7，不是 cmd。

因此这些 cmd 命令不能直接用：

```bat
call C:\Users\asus\anaconda3\Scripts\activate.bat ai_project
cd /d C:\Users\asus\Desktop\learning\novelagent
```

在 PowerShell 里：

```text
call 不是 PowerShell 命令
cd /d 是 cmd 写法，PowerShell 不认识 /d
C:/Users/asus/anaconda3/Scripts/activate 是 cmd 激活方式，不能可靠修改当前 PowerShell 会话
```

最稳的方式是不激活 conda，直接调用目标环境里的 Python：

```powershell
Set-Location C:\Users\asus\Desktop\learning\novelagent
& "C:\Users\asus\anaconda3\envs\ai_project\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

也可以先检查当前用的是哪个 Python：

```powershell
& "C:\Users\asus\anaconda3\envs\ai_project\python.exe" -c "import sys; print(sys.executable)"
```

应该输出：

```text
C:\Users\asus\anaconda3\envs\ai_project\python.exe
```

如果输出的是下面这个，就说明没有进到 conda 环境：

```text
C:\Users\asus\AppData\Local\Programs\Python\Python310\python.exe
```

## 3. 启动 FastAPI 服务

进入项目目录并激活环境后，运行：

```powershell
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

参数含义：

```text
main:app      表示从 main.py 里找到 app 这个 FastAPI 实例
--reload      代码修改后自动重启服务
--host        绑定本机地址
--port 8000   使用 8000 端口
```

启动成功后访问：

```text
http://127.0.0.1:8000
```

API 文档访问：

```text
http://127.0.0.1:8000/docs
```

如果 8000 端口被占用，可以换一个端口：

```powershell
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

然后访问：

```text
http://127.0.0.1:8001
```

## 4. main.py 做了什么

`main.py` 是服务入口，只负责装配：

```python
app = FastAPI(...)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.include_router(chat_router)
app.include_router(novel_router)
```

它做了三件事：

1. 创建 FastAPI 应用。
2. 挂载前端静态文件。
3. 注册普通聊天接口和小说工作流接口。

首页 `/` 会返回：

```text
frontend/index.html
```

所以你打开 `http://127.0.0.1:8000` 时，看到的是前端页面，但这个页面是由 FastAPI 服务出来的。

## 5. 前端数据如何发给后端

前端统一使用 `frontend/app.js` 里的 `requestJson()` 发请求：

```javascript
async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail || `请求失败：${response.status}`;
    throw new Error(Array.isArray(detail) ? JSON.stringify(detail, null, 2) : detail);
  }
  return data;
}
```

这段代码的意思是：

```text
前端把表单数据整理成 JSON
-> fetch 请求后端 API
-> 后端返回 JSON
-> 前端解析 JSON
-> 如果成功就渲染页面
-> 如果失败就显示错误提示
```

## 6. 如何观察前端发了什么数据

最推荐用浏览器开发者工具。

操作步骤：

1. 打开 `http://127.0.0.1:8000`
2. 按 `F12`
3. 进入 `Network`
4. 选择 `Fetch/XHR`
5. 在页面上填写内容并点击按钮
6. 找到对应请求，例如 `/novel/chapters/plan`
7. 查看 `Payload`，这是前端发给后端的数据
8. 查看 `Response`，这是后端返回给前端的数据

例如点击 Planner 生成时，前端会发送类似数据：

```json
{
  "session_id": null,
  "project_id": "default",
  "project_title": "月光禁区",
  "global_worldview": "玄幻都市，灵气复苏刚刚开始...",
  "chapter_number": 1,
  "previous_summary": "故事开篇前...",
  "user_instruction": "本章要突出神秘感...",
  "characters": []
}
```

请求地址是：

```text
POST /novel/chapters/plan
```

后端对应代码在：

```text
app\novel_routes.py
```

## 7. 主要 API 流程

### 7.1 生成剧情节点

前端调用：

```text
POST /novel/chapters/plan
```

后端函数：

```python
plan_chapter(...)
```

作用：

```text
收集世界观、章节号、前文摘要、人物卡和用户要求
-> 调用 Planner
-> 返回剧情节点 plot_beats
-> 工作流暂停，等待人工确认
```

### 7.2 人工确认剧情节点并生成正文

前端调用：

```text
POST /novel/chapters/{session_id}/approve
```

后端函数：

```python
approve_plot_beats(...)
```

作用：

```text
提交人工确认后的剧情节点
-> 调用 Writer
-> 生成章节正文 draft
-> 返回给前端展示
```

### 7.3 审查正文

前端调用：

```text
POST /novel/chapters/{session_id}/review
```

后端函数：

```python
review_chapter_draft(...)
```

作用：

```text
把 Writer 生成的正文交给 Reviewer
-> 检查人物 OOC、逻辑漏洞、设定冲突、伏笔断裂
-> 返回审查意见和评分
```

### 7.4 修订正文

前端调用：

```text
POST /novel/chapters/{session_id}/revise
```

后端函数：

```python
revise_chapter_draft(...)
```

作用：

```text
把用户意见和 Reviewer 意见交给 Writer
-> Writer 重新生成修订稿
-> 再交给 Reviewer 审查
```

### 7.5 接受章节并写入长期记忆

前端调用：

```text
POST /novel/chapters/{session_id}/accept
```

后端函数：

```python
accept_chapter(...)
```

作用：

```text
用户确认接受本章
-> Librarian 从正文中抽取稳定设定
-> 写入作品数据
-> 写入长期记忆
-> 章节状态变为 completed
```

## 8. 后端如何调用云端 LLM

项目使用 `langchain_openai.ChatOpenAI` 调用云端模型。

配置读取位置：

```text
core\config.py
```

`.env` 示例：

```env
OPENAI_API_KEY="sk-your-api-key"
OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_MODEL="qwen3.6-plus"
LLM_TEMPERATURE="0.7"
```

`OPENAI_API_KEY` 是模型服务密钥。

`OPENAI_BASE_URL` 是模型服务地址。

`LLM_MODEL` 是实际调用的模型名称。

普通聊天链路在：

```text
app\chain.py
```

核心代码：

```python
llm = ChatOpenAI(
    model=settings.llm_model,
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url,
    temperature=settings.llm_temperature,
    streaming=True,
)
```

小说多智能体链路也使用同样的配置，只是每个 Agent 有不同的 Prompt 和输出结构。

## 9. LLM 消息如何发送和接收

以 Planner 为例：

```text
前端点击 Planner 生成
-> POST /novel/chapters/plan
-> FastAPI 接收 NovelPlanRequest
-> novel_workflow_service.plan_chapter(...)
-> LangGraph 执行 planner 节点
-> planner_chain.invoke(...)
-> ChatOpenAI 把 prompt 发给云端 LLM
-> 云端 LLM 返回 JSON
-> LangChain 解析成 PlannerOutput
-> FastAPI 返回 NovelPlanResponse
-> 前端 renderBeats(...) 展示剧情节点
```

Planner 的链路代码在：

```text
app\agents\planner_chain.py
```

关键代码：

```python
planner_chain = planner_prompt | planner_llm.with_structured_output(PlannerOutput)
```

这说明 Planner 不是随便返回一段文字，而是要求 LLM 返回符合 `PlannerOutput` 的结构化数据。

Writer、Reviewer、Librarian 也是类似：

```text
Writer     -> WriterOutput
Reviewer   -> ReviewerOutput
Librarian  -> LibrarianOutput
```

## 10. 普通 /chat 接口是什么

除了小说工作流，项目还有一个普通聊天接口：

```text
POST /chat
```

代码在：

```text
app\routes.py
```

核心逻辑：

```python
async for chunk in chat_chain.astream({"input": request.query}):
    yield chunk
```

这表示：

```text
前端或调用方发送 query
-> 后端把 query 放入 chat_chain
-> chat_chain 调用云端 LLM
-> LLM 一边生成，后端一边流式返回 chunk
```

这个接口使用的是 SSE 风格的流式响应：

```python
StreamingResponse(generate_stream(), media_type="text/event-stream")
```

## 11. 小说工作流和普通聊天的区别

普通 `/chat`：

```text
用户输入一句话
-> LLM 返回一段普通文本
```

小说 `/novel/...`：

```text
用户输入作品设定、章节要求、人物卡
-> Planner 返回剧情节点
-> 用户审核
-> Writer 返回正文
-> Reviewer 返回审查意见
-> 用户决定修订或接受
-> Librarian 抽取设定
-> 保存作品和长期记忆
```

所以 `/novel/...` 更像一个产品工作流，而不是普通聊天。

## 12. 数据保存在哪里

作品数据保存在：

```text
.novel_projects
```

长期记忆保存在：

```text
.novel_memory
```

重要规则：

```text
Planner 阶段不写长期记忆
Writer 草稿阶段不写长期记忆
Reviewer 审查阶段不写长期记忆
只有用户 accept_chapter 后，Librarian 抽取结果才写入长期记忆
```

这样可以避免未确认的草稿污染作品设定。

## 13. 常见问题

### 13.1 conda 提示找不到

如果 PowerShell 提示：

```text
conda: The term 'conda' is not recognized
```

先运行：

```powershell
& "$env:USERPROFILE\anaconda3\shell\condabin\conda-hook.ps1"
conda activate ai_project
```

### 13.2 依赖缺失

如果启动时报某个包不存在，先确认环境是否正确：

```powershell
conda activate ai_project
python -c "import fastapi, uvicorn, langchain_openai, langgraph; print('ok')"
```

如果不是 `ok`，安装依赖：

```powershell
pip install -r requirements.txt
```

### 13.3 LLM 调用失败

检查 `.env`：

```env
OPENAI_API_KEY="你的真实 key"
OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_MODEL="qwen3.6-plus"
LLM_TEMPERATURE="0.7"
```

然后重启服务。

### 13.4 页面打开了但按钮没反应

按 `F12` 打开浏览器开发者工具：

```text
Console 查看前端报错
Network 查看请求是否发出
Payload 查看请求内容
Response 查看后端返回
```

同时看启动 FastAPI 的终端，后端报错会打印在那里。

### 13.5 8000 端口被占用

换端口启动：

```powershell
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

## 14. 你调试时最该盯住的地方

前端发请求：

```text
frontend\app.js
```

后端接请求：

```text
app\novel_routes.py
```

工作流推进：

```text
app\core\novel_graph.py
```

LLM 调用：

```text
app\agents\planner_chain.py
app\agents\writer_chain.py
app\agents\reviewer_chain.py
app\agents\librarian_chain.py
```

配置读取：

```text
core\config.py
```

本地数据：

```text
.novel_projects
.novel_memory
```

## 15. 一句话记住整个链路

```text
浏览器表单
-> frontend/app.js 的 fetch
-> FastAPI 路由
-> NovelWorkflowService
-> LangGraph 节点
-> LangChain Prompt + ChatOpenAI
-> 云端 LLM
-> 结构化输出
-> FastAPI JSON 响应
-> 前端更新页面
-> 用户确认后保存到本地作品和长期记忆
```
