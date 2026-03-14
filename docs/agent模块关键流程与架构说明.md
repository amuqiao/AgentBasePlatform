# agent 模块关键流程与架构说明

## 1. 文档目标

本文面向 `examples/agent` 目录，系统讲清楚：

- AgentScope 中常见 agent 的能力边界与适用场景
- 每类 agent 的关键流程与核心概念
- 从工程视角理解每类 agent 的架构分层

并且为每个 agent 提供两张 Mermaid 图：

- 一张**架构图**（组件关系）
- 一张**流程图**（端到端执行路径）

---

## 2. 范围与分类

本文覆盖以下 8 类 agent：

1. `react_agent`
2. `meta_planner_agent`
3. `deep_research_agent`
4. `browser_agent`
5. `voice_agent`
6. `realtime_voice_agent`
7. `a2a_agent`
8. `a2ui_agent`

---

## 3. 通用概念（先看这一节）

### 3.1 ReAct 基本循环

大多数 agent 都遵循 ReAct 的闭环：

1. **Reasoning**：模型决定下一步
2. **Acting**：调用工具或外部能力
3. **Observation**：读取工具结果并写入记忆
4. **Convergence**：满足完成条件后结束

### 3.2 Toolkit 与 Tool

- `Toolkit` 是工具注册和执行中枢
- 工具来源可以是本地函数、MCP 客户端、Skill 包装函数
- 工具返回结构化 `ToolResponse`，可支持流式输出

### 3.3 Session 与 Memory

- `InMemoryMemory`：会话内短期记忆
- `JSONSession`：会话持久化，支持中断恢复
- 多代理场景中通常通过 session id 关联上下文

### 3.4 MCP（Model Context Protocol）

- 将浏览器、搜索、地图、GitHub 等外部能力标准化为“可调用工具”
- 常见接入方式：
  - `StdIOStatefulClient`
  - `HttpStatelessClient`

---

## 4. Agent 总览架构

```mermaid
flowchart LR
    classDef agentStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef modelStyle fill:#ffd700,stroke:#333,stroke-width:2px
    classDef toolStyle fill:#9f9,stroke:#333,stroke-width:2px
    classDef sessionStyle fill:#9ff,stroke:#333,stroke-width:2px
    classDef ioStyle fill:#f99,stroke:#333,stroke-width:2px
    classDef extStyle fill:#e8f4f8,stroke:#4299e1,stroke-width:1.5px
    classDef boxStyle fill:#f5f5f5,stroke:#666,stroke-width:1px

    subgraph InputLayer["输入与接入层"]
        U[User or Client]:::ioStyle
        API[CLI WebSocket A2A]:::ioStyle
    end
    class InputLayer boxStyle

    subgraph AgentLayer["Agent 执行层"]
        A1[ReAct Family]:::agentStyle
        A2[RealtimeAgent]:::agentStyle
        A3[A2AAgent]:::agentStyle
    end
    class AgentLayer boxStyle

    subgraph CoreLayer["核心能力层"]
        M[Chat or Realtime Model]:::modelStyle
        T[Toolkit and Tools]:::toolStyle
        S[Memory Session]:::sessionStyle
    end
    class CoreLayer boxStyle

    subgraph ExternalLayer["外部能力层"]
        X1[MCP Servers]:::extStyle
        X2[Browser Search GitHub Map]:::extStyle
        X3[A2A or A2UI Clients]:::extStyle
    end
    class ExternalLayer boxStyle

    U --> API --> A1
    API --> A2
    API --> A3
    A1 --> M
    A1 --> T
    A1 --> S
    A2 --> M
    A2 --> T
    A3 --> S
    T --> X1 --> X2
    A3 --> X3
```

---

## 5. `react_agent`

### 5.1 关键概念

- 典型单体 ReAct Agent，强调“推理 + 工具调用”
- 默认注册 `execute_shell_command`、`execute_python_code`、`view_text_file`
- 适合作为最小可运行智能体基座

### 5.2 架构图

```mermaid
flowchart LR
    classDef agentStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef modelStyle fill:#ffd700,stroke:#333,stroke-width:2px
    classDef memoryStyle fill:#9ff,stroke:#333,stroke-width:2px
    classDef toolStyle fill:#9f9,stroke:#333,stroke-width:2px
    classDef ioStyle fill:#f99,stroke:#333,stroke-width:2px
    classDef boxStyle fill:#f5f5f5,stroke:#666,stroke-width:1px

    subgraph Input["交互层"]
        U[UserAgent]:::ioStyle
    end
    class Input boxStyle

    subgraph Core["核心层"]
        R[ReActAgent Friday]:::agentStyle
        M[DashScopeChatModel]:::modelStyle
        MEM[InMemoryMemory]:::memoryStyle
        TK[Toolkit]:::toolStyle
    end
    class Core boxStyle

    subgraph ToolLayer["工具层"]
        T1[execute shell command]:::toolStyle
        T2[execute python code]:::toolStyle
        T3[view text file]:::toolStyle
    end
    class ToolLayer boxStyle

    U --> R
    R --> M
    R --> MEM
    R --> TK
    TK --> T1
    TK --> T2
    TK --> T3
```

### 5.3 流程图

```mermaid
flowchart TD
    classDef startStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef processStyle fill:#9ff,stroke:#333,stroke-width:2px
    classDef decisionStyle fill:#ffd700,stroke:#333,stroke-width:2px
    classDef endStyle fill:#f99,stroke:#333,stroke-width:2px

    A[用户输入]:::startStyle
    B[ReAct 推理]:::processStyle
    C{是否需要工具}:::decisionStyle
    D[调用 Toolkit 工具]:::processStyle
    E[观察工具结果并写入记忆]:::processStyle
    F[输出回答]:::endStyle

    A --> B --> C
    C -- 是 --> D --> E --> B
    C -- 否 --> F
```

---

## 6. `meta_planner_agent`

### 6.1 关键概念

- 主 Agent 负责规划，不直接做重执行
- 通过 `create_worker` 动态创建 Worker 子 Agent
- 使用 `PlanNotebook` 管理任务分解与推进
- 子 Agent 的流式输出回传到 Planner，形成统一交互窗口

### 6.2 架构图

```mermaid
flowchart LR
    classDef plannerStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef modelStyle fill:#ffd700,stroke:#333,stroke-width:2px
    classDef sessionStyle fill:#9ff,stroke:#333,stroke-width:2px
    classDef workerStyle fill:#9f9,stroke:#333,stroke-width:2px
    classDef mcpStyle fill:#ff9,stroke:#333,stroke-width:2px
    classDef ioStyle fill:#f99,stroke:#333,stroke-width:2px
    classDef boxStyle fill:#f5f5f5,stroke:#666,stroke-width:1px

    subgraph PlannerLayer["规划层"]
        U[UserAgent]:::ioStyle
        P[Planner Friday]:::plannerStyle
        PN[PlanNotebook]:::sessionStyle
        CT[create worker tool]:::workerStyle
    end
    class PlannerLayer boxStyle

    subgraph WorkerLayer["执行层"]
        W[Worker ReActAgent]:::workerStyle
        TK[Worker Toolkit]:::workerStyle
    end
    class WorkerLayer boxStyle

    subgraph ToolLayer["工具与MCP层"]
        B[Playwright MCP]:::mcpStyle
        G[GitHub MCP]:::mcpStyle
        A[AMap MCP]:::mcpStyle
        F[file read write tools]:::mcpStyle
    end
    class ToolLayer boxStyle

    U --> P
    P --> PN
    P --> CT --> W
    W --> TK
    TK --> B
    TK --> G
    TK --> A
    TK --> F
    W --> P
```

### 6.3 流程图

```mermaid
flowchart TD
    classDef startStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef processStyle fill:#9ff,stroke:#333,stroke-width:2px
    classDef decisionStyle fill:#ffd700,stroke:#333,stroke-width:2px
    classDef toolStyle fill:#9f9,stroke:#333,stroke-width:2px
    classDef endStyle fill:#f99,stroke:#333,stroke-width:2px

    A[接收复杂任务]:::startStyle
    B[Planner 生成计划]:::processStyle
    C{是否存在未完成子任务}:::decisionStyle
    D[调用 create worker]:::toolStyle
    E[Worker 执行并流式回传]:::processStyle
    F[Planner 更新计划状态]:::processStyle
    G[输出最终结果]:::endStyle

    A --> B --> C
    C -- 是 --> D --> E --> F --> C
    C -- 否 --> G
```

---

## 7. `deep_research_agent`

### 7.1 关键概念

- 面向复杂研究任务，强调多轮搜索、提取、总结与报告生成
- 通过 Tavily MCP 做搜索与抽取
- 内置“子任务递进 + 失败反思 + 中间报告沉淀”机制
- 最终可产出结构化报告和落盘文件

### 7.2 架构图

```mermaid
flowchart LR
    classDef agentStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef modelStyle fill:#ffd700,stroke:#333,stroke-width:2px
    classDef memoryStyle fill:#9ff,stroke:#333,stroke-width:2px
    classDef toolStyle fill:#9f9,stroke:#333,stroke-width:2px
    classDef mcpStyle fill:#ff9,stroke:#333,stroke-width:2px
    classDef ioStyle fill:#f99,stroke:#333,stroke-width:2px
    classDef boxStyle fill:#f5f5f5,stroke:#666,stroke-width:1px

    subgraph AgentLayer["研究代理层"]
        U[User Query]:::ioStyle
        D[DeepResearchAgent]:::agentStyle
        ST[Subtask Stack]:::memoryStyle
        IM[Intermediate Memory]:::memoryStyle
    end
    class AgentLayer boxStyle

    subgraph CoreLayer["核心能力层"]
        M[DashScopeChatModel]:::modelStyle
        TK[Toolkit]:::toolStyle
        FS[local report files]:::toolStyle
    end
    class CoreLayer boxStyle

    subgraph SearchLayer["搜索能力层"]
        TV[Tavily MCP]:::mcpStyle
        S[tavily search]:::mcpStyle
        E[tavily extract]:::mcpStyle
    end
    class SearchLayer boxStyle

    U --> D
    D --> ST
    D --> IM
    D --> M
    D --> TK
    TK --> TV --> S
    TK --> TV --> E
    D --> FS
```

### 7.3 流程图

```mermaid
flowchart TD
    classDef startStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef processStyle fill:#9ff,stroke:#333,stroke-width:2px
    classDef decisionStyle fill:#ffd700,stroke:#333,stroke-width:2px
    classDef toolStyle fill:#9f9,stroke:#333,stroke-width:2px
    classDef endStyle fill:#f99,stroke:#333,stroke-width:2px

    A[输入研究问题]:::startStyle
    B[分解子任务并识别知识缺口]:::processStyle
    C[生成当前工作计划]:::processStyle
    D[调用 search or extract 工具]:::toolStyle
    E[整理中间结果并必要时写报告草稿]:::processStyle
    F{信息是否充分}:::decisionStyle
    G[扩展查询或下钻子任务]:::processStyle
    H[生成最终综合报告]:::endStyle

    A --> B --> C --> D --> E --> F
    F -- 否 --> G --> C
    F -- 是 --> H
```

---

## 8. `browser_agent`

### 8.1 关键概念

- 基于 ReAct 的网页自动化智能体
- 先任务拆解，再执行子任务
- 对 `browser_snapshot` 支持分块观察推理
- 通过 `browser_subtask_manager` 控制子任务推进与修订
- 通过 `browser_generate_final_response` 收敛结构化输出

### 8.2 架构图

```mermaid
flowchart LR
    classDef agentStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef modelStyle fill:#ffd700,stroke:#333,stroke-width:2px
    classDef memoryStyle fill:#9ff,stroke:#333,stroke-width:2px
    classDef toolStyle fill:#9f9,stroke:#333,stroke-width:2px
    classDef mcpStyle fill:#ff9,stroke:#333,stroke-width:2px
    classDef ioStyle fill:#f99,stroke:#333,stroke-width:2px
    classDef extStyle fill:#e8f4f8,stroke:#4299e1,stroke-width:1.5px
    classDef boxStyle fill:#f5f5f5,stroke:#666,stroke-width:1px

    subgraph InputLayer["输入层"]
        U[UserAgent]:::ioStyle
    end
    class InputLayer boxStyle

    subgraph AgentLayer["BrowserAgent 层"]
        B[BrowserAgent]:::agentStyle
        SB[browser subtask manager]:::toolStyle
        FR[browser generate final response]:::toolStyle
    end
    class AgentLayer boxStyle

    subgraph CoreLayer["核心层"]
        M[DashScopeChatModel]:::modelStyle
        MEM[InMemoryMemory]:::memoryStyle
        TK[Toolkit]:::toolStyle
    end
    class CoreLayer boxStyle

    subgraph ExternalLayer["外部能力层"]
        PW[Playwright MCP tools]:::mcpStyle
        SK1[file download]:::extStyle
        SK2[form filling]:::extStyle
        SK3[image understanding]:::extStyle
        SK4[video understanding]:::extStyle
    end
    class ExternalLayer boxStyle

    U --> B
    B --> M
    B --> MEM
    B --> TK
    B --> SB
    B --> FR
    TK --> PW
    B --> SK1
    B --> SK2
    B --> SK3
    B --> SK4
```

### 8.3 流程图

```mermaid
flowchart TD
    classDef startStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef processStyle fill:#9ff,stroke:#333,stroke-width:2px
    classDef decisionStyle fill:#ffd700,stroke:#333,stroke-width:2px
    classDef toolStyle fill:#9f9,stroke:#333,stroke-width:2px
    classDef endStyle fill:#f99,stroke:#333,stroke-width:2px

    A[用户任务输入]:::startStyle
    B[初始化并导航 start url]:::processStyle
    C[任务拆解与反思修订]:::processStyle
    D[进入 ReAct 循环]:::processStyle
    E{是否 snapshot 观察}:::decisionStyle
    F[分块观察推理]:::processStyle
    G[执行浏览器或技能工具]:::toolStyle
    H[子任务推进管理]:::processStyle
    I{是否可生成最终结构化结果}:::decisionStyle
    J[输出结构化结果并结束]:::endStyle

    A --> B --> C --> D --> E
    E -- 是 --> F --> G --> H --> I
    E -- 否 --> G --> H --> I
    I -- 否 --> D
    I -- 是 --> J
```

---

## 9. `voice_agent`

### 9.1 关键概念

- 本质是启用音频输出能力的 ReActAgent
- 模型 `generate_kwargs` 指定 `modalities: [text, audio]`
- 适合“文本输入 + 语音回复”的对话场景
- 开启音频输出时，工具调用能力可能受模型限制

### 9.2 架构图

```mermaid
flowchart LR
    classDef agentStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef modelStyle fill:#ffd700,stroke:#333,stroke-width:2px
    classDef memoryStyle fill:#9ff,stroke:#333,stroke-width:2px
    classDef ioStyle fill:#f99,stroke:#333,stroke-width:2px
    classDef extStyle fill:#e8f4f8,stroke:#4299e1,stroke-width:1.5px
    classDef boxStyle fill:#f5f5f5,stroke:#666,stroke-width:1px

    subgraph InputLayer["交互层"]
        U[UserAgent Bob]:::ioStyle
    end
    class InputLayer boxStyle

    subgraph AgentLayer["语音 Agent 层"]
        V[ReActAgent Friday]:::agentStyle
        MEM[InMemoryMemory]:::memoryStyle
    end
    class AgentLayer boxStyle

    subgraph ModelLayer["模型层"]
        M[OpenAIChatModel qwen3 omni flash]:::modelStyle
        A[Audio output wav voice Cherry]:::extStyle
    end
    class ModelLayer boxStyle

    U --> V
    V --> MEM
    V --> M --> A
```

### 9.3 流程图

```mermaid
flowchart TD
    classDef startStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef processStyle fill:#9ff,stroke:#333,stroke-width:2px
    classDef decisionStyle fill:#ffd700,stroke:#333,stroke-width:2px
    classDef endStyle fill:#f99,stroke:#333,stroke-width:2px

    A[用户输入文本]:::startStyle
    B[写入对话记忆]:::processStyle
    C[模型生成文本与音频]:::processStyle
    D{用户是否退出}:::decisionStyle
    E[播放语音并展示文本]:::endStyle

    A --> B --> C --> E --> D
    D -- 否 --> A
```

---

## 10. `realtime_voice_agent`

### 10.1 关键概念

- 基于 `RealtimeAgent` 的双向流式语音会话
- FastAPI + WebSocket 负责前后端实时事件转发
- 支持 DashScope/Gemini/OpenAI 实时模型切换
- 对 Gemini/OpenAI 可额外挂载工具

### 10.2 架构图

```mermaid
flowchart LR
    classDef ioStyle fill:#f99,stroke:#333,stroke-width:2px
    classDef agentStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef modelStyle fill:#ffd700,stroke:#333,stroke-width:2px
    classDef toolStyle fill:#9f9,stroke:#333,stroke-width:2px
    classDef queueStyle fill:#9ff,stroke:#333,stroke-width:2px
    classDef boxStyle fill:#f5f5f5,stroke:#666,stroke-width:1px

    subgraph Frontend["前端层"]
        UI[chatbot html]:::ioStyle
        WS[WebSocket client events]:::ioStyle
    end
    class Frontend boxStyle

    subgraph Server["服务层"]
        API[FastAPI endpoint]:::ioStyle
        Q[frontend queue]:::queueStyle
        A[RealtimeAgent]:::agentStyle
    end
    class Server boxStyle

    subgraph Runtime["运行能力层"]
        M[Realtime model provider]:::modelStyle
        T[optional toolkit]:::toolStyle
    end
    class Runtime boxStyle

    UI --> WS --> API
    API --> A
    A --> M
    A --> T
    A --> Q --> API --> UI
```

### 10.3 流程图

```mermaid
flowchart TD
    classDef startStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef processStyle fill:#9ff,stroke:#333,stroke-width:2px
    classDef decisionStyle fill:#ffd700,stroke:#333,stroke-width:2px
    classDef endStyle fill:#f99,stroke:#333,stroke-width:2px

    A[前端建立 WebSocket]:::startStyle
    B[发送 session create 事件]:::processStyle
    C[服务端创建 RealtimeAgent]:::processStyle
    D[agent start 并绑定前端队列]:::processStyle
    E[接收语音文本视频事件]:::processStyle
    F[Realtime 模型实时推理]:::processStyle
    G[流式事件回推前端]:::processStyle
    H{是否 session end}:::decisionStyle
    I[agent stop 并断开]:::endStyle

    A --> B --> C --> D --> E --> F --> G --> H
    H -- 否 --> E
    H -- 是 --> I
```

---

## 11. `a2a_agent`

### 11.1 关键概念

- `A2AAgent` 是 A2A 协议客户端，连接外部 A2A Server
- Server 端可承载普通 ReActAgent 并通过 A2A 协议返回消息
- 适合跨 Agent 系统的标准化互联
- 当前能力限制：偏 chatbot 场景，不支持实时中断与 agentic structured output

### 11.2 架构图

```mermaid
flowchart LR
    classDef ioStyle fill:#f99,stroke:#333,stroke-width:2px
    classDef agentStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef modelStyle fill:#ffd700,stroke:#333,stroke-width:2px
    classDef toolStyle fill:#9f9,stroke:#333,stroke-width:2px
    classDef sessionStyle fill:#9ff,stroke:#333,stroke-width:2px
    classDef boxStyle fill:#f5f5f5,stroke:#666,stroke-width:1px

    subgraph ClientSide["A2A 客户端侧"]
        U[UserAgent]:::ioStyle
        C[A2AAgent client]:::agentStyle
    end
    class ClientSide boxStyle

    subgraph Protocol["协议层"]
        P[A2A protocol message stream]:::ioStyle
    end
    class Protocol boxStyle

    subgraph ServerSide["A2A 服务端侧"]
        S[A2AStarletteApplication]:::ioStyle
        R[ReActAgent Friday]:::agentStyle
        M[DashScopeChatModel]:::modelStyle
        T[Toolkit functions]:::toolStyle
        J[JSONSession]:::sessionStyle
    end
    class ServerSide boxStyle

    U --> C --> P --> S --> R
    R --> M
    R --> T
    R --> J
    R --> S --> P --> C --> U
```

### 11.3 流程图

```mermaid
flowchart TD
    classDef startStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef processStyle fill:#9ff,stroke:#333,stroke-width:2px
    classDef decisionStyle fill:#ffd700,stroke:#333,stroke-width:2px
    classDef endStyle fill:#f99,stroke:#333,stroke-width:2px

    A[用户向 A2AAgent 发消息]:::startStyle
    B[客户端封装 A2A 请求]:::processStyle
    C[服务端解析并恢复会话]:::processStyle
    D[ReActAgent 执行并流式产出]:::processStyle
    E[格式化为 A2A 状态事件]:::processStyle
    F{任务是否完成}:::decisionStyle
    G[发送 completed 事件]:::endStyle

    A --> B --> C --> D --> E --> F
    F -- 否 --> D
    F -- 是 --> G
```

---

## 12. `a2ui_agent`

### 12.1 关键概念

- 在 A2A 通道上输出 A2UI 协议 UI 消息
- Agent 不仅回答文本，还生成可渲染的交互式 UI JSON
- 通过 Skill 逐步暴露 schema 与模板，提升 UI 生成稳定性
- 服务端会对 UI 事件做前后处理，形成“交互闭环”

### 12.2 架构图

```mermaid
flowchart LR
    classDef ioStyle fill:#f99,stroke:#333,stroke-width:2px
    classDef agentStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef modelStyle fill:#ffd700,stroke:#333,stroke-width:2px
    classDef toolStyle fill:#9f9,stroke:#333,stroke-width:2px
    classDef sessionStyle fill:#9ff,stroke:#333,stroke-width:2px
    classDef extStyle fill:#e8f4f8,stroke:#4299e1,stroke-width:1.5px
    classDef boxStyle fill:#f5f5f5,stroke:#666,stroke-width:1px

    subgraph ClientLayer["客户端层"]
        C1[A2UI client renderer]:::ioStyle
        C2[UI interactions]:::ioStyle
    end
    class ClientLayer boxStyle

    subgraph ServerLayer["A2UI 服务层"]
        A2A[A2AStarletteApplication]:::ioStyle
        H[SimpleStreamHandler]:::ioStyle
        AG[ReActAgent Friday]:::agentStyle
        S[JSONSession]:::sessionStyle
    end
    class ServerLayer boxStyle

    subgraph CapabilityLayer["能力层"]
        M[DashScopeChatModel]:::modelStyle
        TK[Toolkit]:::toolStyle
        SK[A2UI response generator skill]:::extStyle
        PP[pre post UI event process]:::extStyle
    end
    class CapabilityLayer boxStyle

    C1 --> C2 --> A2A --> H --> AG
    H --> PP
    AG --> M
    AG --> TK --> SK
    AG --> S
    H --> A2A --> C1
```

### 12.3 流程图

```mermaid
flowchart TD
    classDef startStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef processStyle fill:#9ff,stroke:#333,stroke-width:2px
    classDef decisionStyle fill:#ffd700,stroke:#333,stroke-width:2px
    classDef endStyle fill:#f99,stroke:#333,stroke-width:2px

    A[客户端发送用户输入或 UI 事件]:::startStyle
    B[服务端预处理 UI 事件]:::processStyle
    C[恢复 session 并执行 ReActAgent]:::processStyle
    D[调用 A2UI skill 生成 UI JSON]:::processStyle
    E[后处理消息为可渲染 UI 响应]:::processStyle
    F{是否需要继续用户交互}:::decisionStyle
    G[返回 input required 与 UI 消息]:::endStyle

    A --> B --> C --> D --> E --> F
    F -- 是 --> G
    F -- 否 --> G
```

---

## 13. 选型建议（工程实践）

- `react_agent`：通用问答 + 轻工具任务，最小起步
- `meta_planner_agent`：复杂任务拆解与多 worker 协作
- `deep_research_agent`：研究型任务、报告型产出
- `browser_agent`：网页操作、数据提取、表单自动化
- `voice_agent`：低复杂度语音交互
- `realtime_voice_agent`：低延迟双向语音会话
- `a2a_agent`：跨系统 agent 互联
- `a2ui_agent`：需要“Agent 直接驱动 UI”的交互场景

---

## 14. Mermaid 绘图约束（按当前仓库风格）

- 使用稳定属性：`fill`、`stroke`、`stroke-width`
- 避免在节点内放复杂 JSON、未转义括号与过长文本
- 优先 `flowchart LR` 或 `flowchart TD`
- 边标签保持短语化，详细语义放正文
- 若渲染失败，先缩减到骨架再逐步恢复样式

