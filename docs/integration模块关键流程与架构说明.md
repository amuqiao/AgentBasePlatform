# `examples/integration` 模块关键流程与架构说明

本文档用于快速理解 `examples/integration` 的能力定位、核心概念、关键流程与整体架构关系，并提供 Mermaid 图辅助说明。

---

## 1. 模块总览

`examples/integration` 主要展示如何将 AgentScope 与外部生态能力做端到端集成，当前包含两个方向：

- **深度研究模型集成**：`qwen_deep_research_model`
  - 展示基于 `qwen-deep-research` 的两阶段研究流程（澄清 -> 深度研究）。
- **云 API MCP 集成**：`alibabacloud_api_mcp`
  - 展示通过 OAuth 登录，将阿里云 OpenAPI 以 MCP 工具方式接入智能体。

典型入口文件：

- `examples/integration/qwen_deep_research_model/main.py`
- `examples/integration/qwen_deep_research_model/qwen_deep_research_agent.py`
- `examples/integration/alibabacloud_api_mcp/main.py`
- `examples/integration/alibabacloud_api_mcp/oauth_handler.py`

---

## 2. 核心概念

- **Integration（集成层）**：将“外部模型能力”与“外部工具能力”接入 AgentScope 的适配层，不改变 Agent 的主编排思想。
- **两阶段研究交互**（Qwen Deep Research）：
  - 第一阶段：模型根据初始问题产出澄清问题（Clarification）。
  - 第二阶段：用户补充后，模型执行检索、分析与答案汇总（Deep Research）。
- **流式阶段信号**：通过 `phase/status/extra` 识别模型所处阶段（如 `WebResearch`、`answer`、`KeepAlive`），并在终态汇总参考链接。
- **MCP（Model Context Protocol）工具接入**：通过 `HttpStatelessClient` 将远端 MCP Server 暴露的能力注册为工具给 `ReActAgent` 调用。
- **OAuth 授权闭环**：本地启动回调服务，浏览器授权后拿到 `code`，由 MCP OAuth Provider 完成 token 流转。

---

## 3. 整体架构图（Integration 分层）

```mermaid
flowchart LR
    %% 样式定义（参考项目 Mermaid 风格）
    classDef producerStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef topicStyle fill:#ffd700,stroke:#333,stroke-width:3px
    classDef partitionStyle1 fill:#9ff,stroke:#333,stroke-width:2px
    classDef partitionStyle2 fill:#9f9,stroke:#333,stroke-width:2px
    classDef consumerGroup1Style fill:#ff9,stroke:#333,stroke-width:2px
    classDef consumerGroup2Style fill:#f99,stroke:#333,stroke-width:2px
    classDef subgraphStyle fill:#f5f5f5,stroke:#666,stroke-width:1px,rounded:10px
    classDef kafkaClusterStyle fill:#e8f4f8,stroke:#4299e1,stroke-width:1.5px,rounded:10px
    classDef ruleNoteStyle fill:#fff8e6,stroke:#ffb74d,stroke-width:1px,rounded:8px

    subgraph interactionLayer["交互层"]
        U[用户]:::producerStyle
        CLI[命令行交互<br/>UserAgent]:::consumerGroup1Style
        Browser[浏览器授权页<br/>OAuth]:::consumerGroup2Style
    end
    class interactionLayer subgraphStyle

    subgraph integrationCore["Integration 编排核心层"]
        AG[AgentScope Agent<br/>ReActAgent / 自定义 Agent]:::topicStyle
        MEM[InMemoryMemory]:::partitionStyle1
        FORMAT[DashScopeChatFormatter]:::partitionStyle2
    end
    class integrationCore kafkaClusterStyle

    subgraph externalCapability["外部能力层"]
        QWEN[Qwen Deep Research API<br/>stream phases]:::consumerGroup1Style
        MCP[MCP Server<br/>Alibaba Cloud OpenAPI]:::consumerGroup2Style
        OAUTH[OAuthClientProvider<br/>TokenStorage]:::partitionStyle2
    end
    class externalCapability subgraphStyle

    U -->|输入研究问题/云操作意图| AG
    CLI -->|消息轮询| AG
    AG -->|上下文读写| MEM
    AG -->|消息格式化| FORMAT
    AG -->|研究请求| QWEN
    AG -->|工具调用| MCP
    MCP -->|鉴权委托| OAUTH
    OAUTH -->|打开授权页| Browser
    Browser -->|回调 code/state| OAUTH
    OAUTH -->|token 注入会话| MCP
    QWEN -->|阶段化流式结果| AG
    MCP -->|工具执行结果| AG

    linkStyle 0,1,2,3 stroke:#666,stroke-width:1.5px,arrowheadStyle:filled
    linkStyle 4,5,6,7 stroke:#333,stroke-width:2px,arrowheadStyle:filled
    linkStyle 8,9,10,11 stroke:#4299e1,stroke-width:1.5px,arrowheadStyle:filled

    Note[Integration 关键点：<br/>1. Agent 仍是统一编排入口<br/>2. 外部模型与外部工具均通过适配层接入<br/>3. 鉴权、流式状态、工具结果都回收为统一消息语义]:::ruleNoteStyle
    Note -.-> integrationCore
```

---

## 4. 关键流程一：Qwen Deep Research 双阶段流程

该流程由 `QwenDeepResearchAgent.reply()` 驱动，基于“用户消息数量”在澄清和深度研究之间切换。

```mermaid
flowchart TD
    classDef producerStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef topicStyle fill:#ffd700,stroke:#333,stroke-width:3px
    classDef partitionStyle1 fill:#9ff,stroke:#333,stroke-width:2px
    classDef partitionStyle2 fill:#9f9,stroke:#333,stroke-width:2px
    classDef consumerGroup1Style fill:#ff9,stroke:#333,stroke-width:2px
    classDef consumerGroup2Style fill:#f99,stroke:#333,stroke-width:2px
    classDef ruleNoteStyle fill:#fff8e6,stroke:#ffb74d,stroke-width:1px,rounded:8px

    A[接收用户问题]:::producerStyle --> B[写入 InMemoryMemory]:::topicStyle
    B --> C{用户消息数 == 1 ?}:::partitionStyle1
    C -->|是| D[Clarification 阶段<br/>生成追问]:::consumerGroup1Style
    C -->|否| E[Deep Research 阶段<br/>执行深度研究]:::consumerGroup2Style

    D --> F[调用 dashscope.AioGeneration.call<br/>stream=true]:::partitionStyle2
    E --> F

    F --> G{流式 phase/status 解析}:::partitionStyle1
    G -->|WebResearch| H[抽取 researchGoal 与网站候选]:::consumerGroup1Style
    G -->|answer finished| I[拼接 References 并收敛答案]:::consumerGroup2Style
    G -->|KeepAlive| J[等待下一阶段]:::partitionStyle2

    H --> I
    J --> I
    I --> K[构造 assistant Msg metadata<br/>phase/requires_user_response]:::topicStyle
    K --> L[写回 memory 并返回给用户]:::producerStyle

    Note[流程要点：<br/>1. 单轮首问先澄清，降低研究偏航风险<br/>2. 流式阶段信息可观测，便于调试与监控<br/>3. answer 终态统一附上 References，提升可追溯性]:::ruleNoteStyle
    Note -.-> G
```

---

## 5. 关键流程二：OAuth + MCP 工具调用流程

该流程由 `alibabacloud_api_mcp/main.py` 与 `oauth_handler.py` 协同完成。

```mermaid
flowchart TD
    classDef producerStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef topicStyle fill:#ffd700,stroke:#333,stroke-width:3px
    classDef partitionStyle1 fill:#9ff,stroke:#333,stroke-width:2px
    classDef partitionStyle2 fill:#9f9,stroke:#333,stroke-width:2px
    classDef consumerGroup1Style fill:#ff9,stroke:#333,stroke-width:2px
    classDef consumerGroup2Style fill:#f99,stroke:#333,stroke-width:2px
    classDef ruleNoteStyle fill:#fff8e6,stroke:#ffb74d,stroke-width:1px,rounded:8px

    A[启动 main.py]:::producerStyle --> B[构造 OAuthClientProvider<br/>绑定 redirect/callback handler]:::topicStyle
    B --> C[创建 HttpStatelessClient<br/>transport=streamable_http]:::partitionStyle2
    C --> D[toolkit.register_mcp_client]:::partitionStyle1
    D --> E[ReActAgent 启动会话循环]:::topicStyle

    E --> F[用户提出云资源操作请求]:::consumerGroup1Style
    F --> G[Agent 决策调用 MCP 工具]:::partitionStyle1
    G --> H{是否已有有效 token?}:::partitionStyle1

    H -->|否| I[handle_redirect 打开浏览器授权页]:::consumerGroup2Style
    I --> J[本地 CallbackServer:3000 接收 code/state]:::consumerGroup1Style
    J --> K[handle_callback 返回授权码]:::partitionStyle2
    K --> L[OAuth Provider 换取并存储 token]:::topicStyle
    H -->|是| M[直接携带 token 调用 MCP]:::consumerGroup2Style
    L --> M

    M --> N[远端 OpenAPI 执行并返回结果]:::consumerGroup1Style
    N --> O[Agent 生成自然语言响应]:::producerStyle

    Note[流程要点：<br/>1. OAuth 只解决鉴权，工具编排仍由 ReActAgent 决策<br/>2. 回调服务本地监听，适合 Demo 与开发调试<br/>3. MCP 层把云 API 统一为可调用工具，降低接入复杂度]:::ruleNoteStyle
    Note -.-> H
```

---

## 6. 子模块与关键流程映射

| 子模块 | 关键概念 | 核心流程关键词 | 典型入口 |
|---|---|---|---|
| `qwen_deep_research_model` | 双阶段研究代理 | 首问澄清 -> 用户补充 -> 深度研究 -> 参考文献汇总 | `main.py` / `qwen_deep_research_agent.py` |
| `alibabacloud_api_mcp` | OAuth + MCP 工具链 | 浏览器授权 -> 回调收码 -> token 注入 -> 工具调用 | `main.py` / `oauth_handler.py` |

---

## 7. 推荐阅读与实践顺序

1. 先读 `qwen_deep_research_model/main.py`，理解两阶段交互入口。
2. 再读 `qwen_deep_research_agent.py`，重点关注 `reply()` 与 `_process_responses()`。
3. 然后读 `alibabacloud_api_mcp/main.py`，理解 OAuth Provider 与 MCP Client 装配关系。
4. 最后读 `oauth_handler.py`，理解本地回调服务与授权码回收逻辑。

如果要快速验证：

- 研究链路：设置 `DASHSCOPE_API_KEY` 后运行 `qwen_deep_research_model/main.py`。
- MCP 链路：将 `server_url` 替换为你自己的 MCP 地址后运行 `alibabacloud_api_mcp/main.py`。
