"""
Agent Engine 验证脚本 —— 验证 ChatAgent 与 ReActAgent 的真实 LLM 对话能力。

测试流程：
  1. 登录获取 Token（复用已有用户或注册新用户）
  2. 创建 ChatAgent → 非流式对话 → 流式对话（SSE）
  3. 创建 ReActAgent（带工具） → 非流式对话 → 流式对话（SSE）
  4. 多轮对话历史验证
  5. 验证 llm_config 自动填充（省略 model_name）

前置条件：
  - 服务已启动：uvicorn src.main:app
  - .env 中已配置 DASHSCOPE_API_KEY

Usage:
    python -m scripts.validate_agent_engine
    python -m scripts.validate_agent_engine --base-url http://localhost:8000
"""

import asyncio
import argparse
import json
import time

DEFAULT_BASE_URL = "http://localhost:8000"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="验证 Agent Engine 智能体引擎层")
    parser.add_argument(
        "--base-url", default=DEFAULT_BASE_URL,
        help=f"API base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument("--email", default="engine_test@example.com")
    parser.add_argument("--password", default="test123456")
    parser.add_argument("--display-name", default="引擎测试用户")
    parser.add_argument("--tenant-name", default="引擎测试团队")
    return parser.parse_args()


async def ensure_login(client, args) -> str:
    """注册（如未注册）并登录，返回 access_token。"""
    await client.post("/api/v1/auth/register", json={
        "email": args.email,
        "password": args.password,
        "display_name": args.display_name,
        "tenant_name": args.tenant_name,
    })

    r = await client.post("/api/v1/auth/login", json={
        "email": args.email,
        "password": args.password,
    })
    assert r.status_code == 200 and r.json()["code"] == 0, f"登录失败: {r.text}"
    return r.json()["data"]["access_token"]


async def create_agent_and_conversation(client, headers, agent_payload) -> tuple[str, str, dict]:
    """创建智能体 + 发布 + 创建会话，返回 (agent_id, conv_id, agent_data)。"""
    r = await client.post("/api/v1/agents", headers=headers, json=agent_payload)
    assert r.status_code == 200 and r.json()["code"] == 0, f"创建智能体失败: {r.text}"
    agent_data = r.json()["data"]
    agent_id = agent_data["id"]

    r = await client.post(
        f"/api/v1/agents/{agent_id}/publish", headers=headers,
        json={"publish_note": "engine test"},
    )
    assert r.status_code == 200, f"发布失败: {r.text}"

    r = await client.post(
        "/api/v1/conversations", headers=headers,
        json={"agent_id": agent_id, "title": f"测试-{agent_payload['name']}"},
    )
    assert r.status_code == 200 and r.json()["code"] == 0, f"创建会话失败: {r.text}"
    conv_id = r.json()["data"]["id"]

    return agent_id, conv_id, agent_data


async def test_send_message(client, headers, conv_id, content) -> str:
    """非流式发送消息并返回回复内容。"""
    r = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        headers=headers,
        json={"content": content},
        timeout=120,
    )
    assert r.status_code == 200 and r.json()["code"] == 0, f"发送消息失败: {r.text}"
    return r.json()["data"]["content"]


async def test_send_message_stream(client, headers, conv_id, content) -> tuple[str, int]:
    """流式发送消息（SSE），拼接并返回完整回复。"""
    full_text = ""
    chunk_count = 0

    async with client.stream(
        "POST",
        f"/api/v1/conversations/{conv_id}/messages/stream",
        headers=headers,
        json={"content": content},
        timeout=120,
    ) as response:
        assert response.status_code == 200, f"SSE 请求失败: {response.status_code}"
        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            data = json.loads(payload)
            chunk = data.get("content", "")
            full_text += chunk
            chunk_count += 1

    return full_text, chunk_count


async def main():
    args = parse_args()

    try:
        import httpx
    except ModuleNotFoundError:
        print("✗ 缺少依赖: httpx\n  pip install httpx")
        return

    async with httpx.AsyncClient(base_url=args.base_url, timeout=30) as client:
        print("=" * 65)
        print("  AgentBasePlatform — Agent Engine 验证")
        print("=" * 65)

        # ---- 0. 健康检查 + 登录 ----
        print("\n[0] 前置准备...")
        r = await client.get("/health")
        assert r.status_code == 200, f"服务未启动: {r.text}"
        print("  ✓ 服务健康")

        token = await ensure_login(client, args)
        headers = {"Authorization": f"Bearer {token}"}
        print(f"  ✓ 登录成功: {token[:20]}...")

        passed = 0
        failed = 0

        # ================================================================
        # TEST 1: ChatAgent 非流式（显式指定 model_name）
        # ================================================================
        print("\n" + "-" * 65)
        print("[1/6] ChatAgent — 非流式对话（显式 model_name）")
        print("-" * 65)
        try:
            agent_id, conv_id, agent_data = await create_agent_and_conversation(
                client, headers,
                {
                    "name": "Chat测试助手",
                    "agent_type": "chat",
                    "system_prompt": "你是一个简洁的AI助手，回答限制在50字以内。",
                    "llm_config": {"model_name": "qwen-max", "max_tokens": 256},
                },
            )
            cfg = agent_data.get("llm_config", {})
            assert cfg.get("model_name") == "qwen-max", f"llm_config 异常: {cfg}"
            print(f"  → Agent: {agent_id[:8]}... | model: {cfg['model_name']}")

            t0 = time.time()
            reply = await test_send_message(client, headers, conv_id, "你好，请用一句话介绍自己")
            elapsed = time.time() - t0

            assert reply and len(reply) > 0, "回复为空"
            assert "[Mock]" not in reply and "[MVP" not in reply, f"仍为 Mock 回复: {reply[:100]}"
            print(f"  ✓ 收到回复 ({elapsed:.1f}s):")
            print(f"    「{reply[:200]}」")
            passed += 1
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            failed += 1

        # ================================================================
        # TEST 2: ChatAgent 流式 (SSE)
        # ================================================================
        print("\n" + "-" * 65)
        print("[2/6] ChatAgent — 流式对话 (SSE)")
        print("-" * 65)
        try:
            agent_id, conv_id, _ = await create_agent_and_conversation(
                client, headers,
                {
                    "name": "Chat流式测试",
                    "agent_type": "chat",
                    "system_prompt": "你是一个友好的AI助手，回答限制在100字以内。",
                    "llm_config": {"model_name": "qwen-max", "max_tokens": 512},
                },
            )
            print(f"  → Agent: {agent_id[:8]}... | Conv: {conv_id[:8]}...")

            t0 = time.time()
            full_text, chunk_count = await test_send_message_stream(
                client, headers, conv_id, "请简单解释什么是大语言模型"
            )
            elapsed = time.time() - t0

            assert full_text and len(full_text) > 0, "流式回复为空"
            assert chunk_count > 1, f"流式 chunk 数 = {chunk_count}，未真正流式输出"
            assert "[Mock]" not in full_text, "仍为 Mock 回复"
            print(f"  ✓ 流式完成 ({elapsed:.1f}s, {chunk_count} chunks):")
            print(f"    「{full_text[:200]}」")
            passed += 1
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            failed += 1

        # ================================================================
        # TEST 3: ChatAgent 多轮对话
        # ================================================================
        print("\n" + "-" * 65)
        print("[3/6] ChatAgent — 多轮对话（历史上下文）")
        print("-" * 65)
        try:
            agent_id, conv_id, _ = await create_agent_and_conversation(
                client, headers,
                {
                    "name": "多轮对话测试",
                    "agent_type": "chat",
                    "system_prompt": "你是一个记忆力很好的助手，请记住用户告诉你的信息。回答限制在50字以内。",
                    "llm_config": {"model_name": "qwen-max", "max_tokens": 256},
                },
            )

            reply1 = await test_send_message(client, headers, conv_id, "我叫张三，请记住我的名字")
            print(f"  → 第1轮: 「{reply1[:100]}」")

            reply2 = await test_send_message(client, headers, conv_id, "我叫什么名字？")
            print(f"  → 第2轮: 「{reply2[:100]}」")

            assert "张三" in reply2, f"模型未利用历史上下文，回复中未包含'张三': {reply2[:200]}"

            r = await client.get(
                f"/api/v1/conversations/{conv_id}/messages", headers=headers
            )
            msg_count = r.json()["data"]["total"]
            assert msg_count == 4, f"期望 4 条消息(2轮×2)，实际 {msg_count}"
            print(f"  ✓ 多轮对话验证通过 (历史消息数: {msg_count})")
            passed += 1
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            failed += 1

        # ================================================================
        # TEST 4: ChatAgent 不传 model_name — 验证自动填充
        # ================================================================
        print("\n" + "-" * 65)
        print("[4/6] ChatAgent — 省略 model_name（验证 .env 自动填充）")
        print("-" * 65)
        try:
            agent_id, conv_id, agent_data = await create_agent_and_conversation(
                client, headers,
                {
                    "name": "自动配置测试",
                    "agent_type": "chat",
                    "system_prompt": "你是一个简洁的助手，回答限制在30字以内。",
                },
            )
            cfg = agent_data.get("llm_config", {})
            model_name = cfg.get("model_name", "")
            assert model_name, f"自动填充失败: {cfg}"
            assert model_name != "mock", f"model_name 不应为 mock: {cfg}"
            print(f"  ✓ 自动填充 model_name={model_name}")

            t0 = time.time()
            reply = await test_send_message(client, headers, conv_id, "你好")
            elapsed = time.time() - t0

            assert reply and "[Mock]" not in reply, f"回复异常: {reply[:100]}"
            print(f"  ✓ 调用成功 ({elapsed:.1f}s): 「{reply[:150]}」")
            passed += 1
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            failed += 1

        # ================================================================
        # TEST 5: ReActAgent 非流式
        # ================================================================
        print("\n" + "-" * 65)
        print("[5/6] ReActAgent — 非流式对话（带工具）")
        print("-" * 65)
        try:
            agent_id, conv_id, agent_data = await create_agent_and_conversation(
                client, headers,
                {
                    "name": "ReAct测试助手",
                    "agent_type": "react",
                    "system_prompt": "你是一个有帮助的AI助手。回答限制在100字以内。",
                    "llm_config": {"model_name": "qwen-max", "max_tokens": 1024},
                    "tool_config": {"builtin_tools": ["view_text_file"]},
                },
            )
            cfg = agent_data.get("llm_config", {})
            print(f"  → Agent: {agent_id[:8]}... (type=react, model={cfg.get('model_name')})")

            t0 = time.time()
            reply = await test_send_message(
                client, headers, conv_id,
                "你好，请简单介绍一下你能做什么",
            )
            elapsed = time.time() - t0

            assert reply and len(reply) > 0, "回复为空"
            assert "[Mock]" not in reply, "仍为 Mock 回复"
            print(f"  ✓ 收到回复 ({elapsed:.1f}s):")
            print(f"    「{reply[:300]}」")
            passed += 1
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            failed += 1

        # ================================================================
        # TEST 6: ReActAgent 流式 (SSE)
        # ================================================================
        print("\n" + "-" * 65)
        print("[6/6] ReActAgent — 流式对话 (SSE)")
        print("-" * 65)
        try:
            agent_id, conv_id, _ = await create_agent_and_conversation(
                client, headers,
                {
                    "name": "ReAct流式测试",
                    "agent_type": "react",
                    "system_prompt": "你是一个有帮助的AI助手。回答限制在100字以内。",
                    "llm_config": {"model_name": "qwen-max", "max_tokens": 1024},
                    "tool_config": {"builtin_tools": ["view_text_file"]},
                },
            )
            print(f"  → Agent: {agent_id[:8]}... (type=react, streaming)")

            t0 = time.time()
            full_text, chunk_count = await test_send_message_stream(
                client, headers, conv_id,
                "请用一句话总结什么是人工智能",
            )
            elapsed = time.time() - t0

            assert full_text and len(full_text) > 0, "流式回复为空"
            assert "[Mock]" not in full_text, "仍为 Mock 回复"
            print(f"  ✓ 流式完成 ({elapsed:.1f}s, {chunk_count} chunks):")
            print(f"    「{full_text[:300]}」")
            passed += 1
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            failed += 1

        # ---- 汇总 ----
        print("\n" + "=" * 65)
        total = passed + failed
        if failed == 0:
            print(f"✅ 全部通过! ({passed}/{total})")
        else:
            print(f"⚠️  通过 {passed}/{total}，失败 {failed}")

        labels = [
            "ChatAgent  非流式（显式 model_name）",
            "ChatAgent  流式 SSE",
            "ChatAgent  多轮对话（上下文）",
            "ChatAgent  自动填充 model_name",
            "ReActAgent 非流式（带工具）",
            "ReActAgent 流式 SSE",
        ]
        for i, label in enumerate(labels):
            status = "✓" if i < passed else "✗"
            print(f"  {status} [{i+1}] {label}")
        print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
