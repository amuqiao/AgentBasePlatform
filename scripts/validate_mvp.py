"""
MVP Validation Script.

Tests the core flow:
  1. Register a user
  2. Login
  3. Create an agent (with explicit model config)
  4. Create an agent (without model config — auto-fill from .env)
  5. Publish the agent
  6. List agents and verify llm_config
  7. Create a conversation
  8. Send a message and get a response
  9. Get conversation history

Usage:
    python -m scripts.validate_mvp
    python -m scripts.validate_mvp --base-url http://localhost:8000
    python3 -m scripts.validate_mvp --base-url http://0.0.0.0:8000
"""

import asyncio
import argparse

DEFAULT_BASE_URL = "http://localhost:8000"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate MVP core flow.")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument("--email", default="test@example.com", help="Test user email")
    parser.add_argument("--password", default="test123456", help="Test user password")
    parser.add_argument("--display-name", default="测试用户", help="Test display name")
    parser.add_argument("--tenant-name", default="测试团队", help="Test tenant name")
    return parser.parse_args()


async def main():
    args = parse_args()
    try:
        import httpx
    except ModuleNotFoundError:
        print("✗ 缺少依赖: httpx")
        print("  请先安装依赖后重试: pip install -r requirements.txt")
        return

    async with httpx.AsyncClient(base_url=args.base_url, timeout=60) as client:
        print("=" * 60)
        print("AgentBasePlatform MVP 验证")
        print("=" * 60)

        # 1. Health check
        print("\n[1/9] 健康检查...")
        r = await client.get("/health")
        assert r.status_code == 200, f"Health check failed: {r.text}"
        print(f"  ✓ 服务运行正常: {r.json()}")

        # 2. Readiness check
        print("\n[2/9] 就绪检查...")
        r = await client.get("/ready")
        print(f"  → 就绪状态: {r.json()}")

        # 3. Register
        print("\n[3/9] 用户注册...")
        r = await client.post(
            "/api/v1/auth/register",
            json={
                "email": args.email,
                "password": args.password,
                "display_name": args.display_name,
                "tenant_name": args.tenant_name,
            },
        )
        register_json = r.json()
        if r.status_code == 200 and register_json["code"] == 0:
            print(f"  ✓ 注册成功: {r.json()['data']['email']}")
        elif register_json.get("code") == 40900:
            print("  → 用户已存在, 跳过注册")
        else:
            print(f"  ✗ 注册失败: {register_json}")
            return

        # 4. Login
        print("\n[4/9] 用户登录...")
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": args.email, "password": args.password},
        )
        assert r.status_code == 200 and r.json()["code"] == 0, f"Login failed: {r.text}"
        token = r.json()["data"]["access_token"]
        print(f"  ✓ 登录成功, Token: {token[:20]}...")

        headers = {"Authorization": f"Bearer {token}"}

        # 5. Get current user
        print("\n[5/9] 获取当前用户信息...")
        r = await client.get("/api/v1/auth/me", headers=headers)
        assert r.status_code == 200, f"Get me failed: {r.text}"
        user_info = r.json()["data"]
        print(f"  ✓ 用户: {user_info['display_name']} ({user_info['email']})")

        # 6. Create agent (explicit model config)
        print("\n[6/9] 创建智能体（显式指定模型配置）...")
        r = await client.post(
            "/api/v1/agents",
            headers=headers,
            json={
                "name": "MVP测试助手",
                "description": "用于MVP验证的测试智能体",
                "agent_type": "chat",
                "system_prompt": "你是一个友好的AI助手，擅长回答各种问题。请用简洁清晰的方式回复用户。",
                "llm_config": {"model_name": "qwen-max", "temperature": 0.7, "max_tokens": 256},
            },
        )
        assert r.status_code == 200 and r.json()["code"] == 0, f"Create agent failed: {r.text}"
        agent_data = r.json()["data"]
        agent_id = agent_data["id"]
        print(f"  ✓ 智能体创建成功: {agent_id}")

        llm_cfg = agent_data.get("llm_config", {})
        assert llm_cfg.get("model_name") == "qwen-max", f"llm_config 异常: {llm_cfg}"
        print(f"  ✓ llm_config 正确: model_name={llm_cfg['model_name']}")

        # 6b. Create agent (auto-fill from .env)
        print("\n     创建智能体（不传 model_name，验证自动填充）...")
        r = await client.post(
            "/api/v1/agents",
            headers=headers,
            json={
                "name": "自动配置测试",
                "description": "不传 model_name，应自动从 .env 填充",
                "agent_type": "chat",
                "system_prompt": "你是一个简洁的助手。",
            },
        )
        assert r.status_code == 200 and r.json()["code"] == 0, f"Create agent failed: {r.text}"
        auto_cfg = r.json()["data"].get("llm_config", {})
        assert auto_cfg.get("model_name"), f"自动填充失败，llm_config 无 model_name: {auto_cfg}"
        print(f"  ✓ 自动填充成功: model_name={auto_cfg['model_name']}")

        # 6c. Publish agent
        print("\n     发布智能体...")
        r = await client.post(
            f"/api/v1/agents/{agent_id}/publish",
            headers=headers,
            json={"publish_note": "MVP v1.0 初始版本"},
        )
        assert r.status_code == 200 and r.json()["code"] == 0, f"Publish failed: {r.text}"
        print(f"  ✓ 已发布版本: v{r.json()['data']['version_number']}")

        # 7. List agents and verify llm_config
        print("\n[7/9] 列表接口验证（llm_config 真实性）...")
        r = await client.get(
            "/api/v1/agents", headers=headers, params={"page": 1, "page_size": 20},
        )
        assert r.status_code == 200 and r.json()["code"] == 0, f"List agents failed: {r.text}"
        items = r.json()["data"]["items"]
        print(f"  → 共 {r.json()['data']['total']} 个智能体")

        all_valid = True
        for item in items:
            model_name = item.get("llm_config", {}).get("model_name", "")
            has_junk = "additionalProp" in str(item.get("llm_config", {}))
            if not model_name or model_name == "mock" or has_junk:
                print(f"  ✗ [{item['name']}] llm_config 异常: {item['llm_config']}")
                all_valid = False
            else:
                print(f"  ✓ [{item['name']}] model={model_name}")
        assert all_valid, "存在模型配置异常的智能体"

        # 8. Create conversation & send message
        print("\n[8/9] 创建对话会话...")
        r = await client.post(
            "/api/v1/conversations",
            headers=headers,
            json={"agent_id": agent_id, "title": "MVP验证对话"},
        )
        assert r.status_code == 200 and r.json()["code"] == 0, f"Create conv failed: {r.text}"
        conv_id = r.json()["data"]["id"]
        print(f"  ✓ 会话创建成功: {conv_id}")

        # 9. Send message
        print("\n[9/9] 发送消息并获取回复...")
        r = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": "你好！请介绍一下你自己。"},
            timeout=120,
        )
        assert r.status_code == 200 and r.json()["code"] == 0, f"Send msg failed: {r.text}"
        reply = r.json()["data"]
        assert "[Mock]" not in reply["content"], f"仍为 Mock 回复: {reply['content'][:100]}"
        print(f"  ✓ 收到回复 (role={reply['role']}):")
        print(f"    {reply['content'][:200]}")

        # Get message history
        print("\n  查询对话历史...")
        r = await client.get(
            f"/api/v1/conversations/{conv_id}/messages",
            headers=headers,
        )
        assert r.status_code == 200, f"Get messages failed: {r.text}"
        msgs = r.json()["data"]["items"]
        print(f"  ✓ 历史消息数: {len(msgs)}")
        for m in msgs:
            print(f"    [{m['role']}] {m['content'][:80]}...")

        print("\n" + "=" * 60)
        print("✅ MVP 核心链路验证通过!")
        print("  - 用户注册/登录 ✓")
        print("  - 智能体 CRUD + 版本发布 ✓")
        print("  - llm_config 自动填充 + 列表返回真实配置 ✓")
        print("  - 会话创建/消息收发/历史查询 ✓")
        print("  - 真实 LLM 模型调用（非 Mock）✓")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
