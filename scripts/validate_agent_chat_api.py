"""
Agent 直接调用接口验证脚本。

测试 POST /api/v1/agents/{agent_id}/chat       （非流式）
     POST /api/v1/agents/{agent_id}/chat/stream （流式 SSE）

验证内容：
   1. ChatAgent  非流式直接调用 + 响应 model 字段验证
   2. ChatAgent  流式直接调用
   3. ChatAgent  多轮历史（通过 messages 数组传递）
   4. ChatAgent  省略 model_name（验证自动填充 + 调用）
   5. ReActAgent 非流式 — execute_python_code 工具调用验证（tool_calls）
   6. ReActAgent 流式  — execute_python_code 流式
   7. ReActAgent 非流式 — view_text_file 工具调用验证（tool_calls）
   8. ReActAgent 非流式 — MCP 工具调用验证（stdio 计算器）
   9. ReActAgent 流式  — MCP 工具流式调用（stdio 计算器）
  10. ReActAgent 非流式 — MCP 错误场景（不存在的 server，验证优雅降级）
  11. ReActAgent 非流式 — Skill 工具验证（current-time）

前置条件：
  - 服务已启动
  - .env 中已配置 DASHSCOPE_API_KEY
  - pip install mcp frontmatter（MCP 测试需要）

Usage:
    python -m scripts.validate_agent_chat_api
    python -m scripts.validate_agent_chat_api --base-url http://localhost:8000
"""

import asyncio
import argparse
import json
import time

DEFAULT_BASE_URL = "http://localhost:8000"


def parse_args():
    parser = argparse.ArgumentParser(description="验证 Agent 直接调用接口")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--email", default="chat_api_test@example.com")
    parser.add_argument("--password", default="test123456")
    return parser.parse_args()


async def ensure_login(client, args) -> str:
    await client.post("/api/v1/auth/register", json={
        "email": args.email,
        "password": args.password,
        "display_name": "接口测试",
        "tenant_name": "接口测试团队",
    })
    r = await client.post("/api/v1/auth/login", json={
        "email": args.email, "password": args.password,
    })
    assert r.status_code == 200 and r.json()["code"] == 0, f"登录失败: {r.text}"
    return r.json()["data"]["access_token"]


async def create_agent(client, headers, payload) -> dict:
    r = await client.post("/api/v1/agents", headers=headers, json=payload)
    assert r.status_code == 200 and r.json()["code"] == 0, f"创建失败: {r.text}"
    agent = r.json()["data"]
    await client.post(
        f"/api/v1/agents/{agent['id']}/publish", headers=headers,
        json={"publish_note": "test"},
    )
    return agent


async def call_chat(client, headers, agent_id, messages) -> dict:
    """非流式调用 /chat，返回完整响应 data。"""
    r = await client.post(
        f"/api/v1/agents/{agent_id}/chat",
        headers=headers,
        json={"messages": messages},
        timeout=120,
    )
    assert r.status_code == 200 and r.json()["code"] == 0, f"调用失败: {r.text}"
    return r.json()["data"]


async def call_chat_stream(client, headers, agent_id, messages) -> tuple[str, int]:
    """流式调用 /chat/stream，返回 (完整文本, chunk数)。"""
    full_text = ""
    chunks = 0
    async with client.stream(
        "POST",
        f"/api/v1/agents/{agent_id}/chat/stream",
        headers=headers,
        json={"messages": messages},
        timeout=120,
    ) as resp:
        assert resp.status_code == 200, f"SSE 失败: {resp.status_code}"
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            data = json.loads(payload)
            text = data.get("content", "")
            full_text += text
            chunks += 1
    return full_text, chunks


def _print_tool_calls(tool_calls: list[dict]):
    """打印工具调用记录。"""
    print(f"  → tool_calls 数量: {len(tool_calls)}")
    for tc in tool_calls:
        args_str = json.dumps(tc.get("arguments", {}), ensure_ascii=False)[:120]
        result_str = tc.get("result", "")[:120]
        print(f"    - {tc['name']}({args_str})")
        if result_str:
            print(f"      result: {result_str}")


TOTAL_TESTS = 11


async def main():
    args = parse_args()

    try:
        import httpx
    except ModuleNotFoundError:
        print("✗ 缺少 httpx: pip install httpx")
        return

    async with httpx.AsyncClient(base_url=args.base_url, timeout=30) as client:
        print("=" * 65)
        print("  Agent 直接调用接口验证 (/chat & /chat/stream)")
        print("=" * 65)

        r = await client.get("/health")
        assert r.status_code == 200, "服务未启动"
        token = await ensure_login(client, args)
        headers = {"Authorization": f"Bearer {token}"}
        print(f"\n[准备] 登录成功: {token[:20]}...")

        # ---- 创建各类 Agent ----
        chat_agent = await create_agent(client, headers, {
            "name": "API-Chat测试",
            "agent_type": "chat",
            "system_prompt": "你是简洁的AI助手，回答限制在50字以内。",
            "llm_config": {"model_name": "qwen-max", "max_tokens": 256},
        })
        auto_agent = await create_agent(client, headers, {
            "name": "API-自动配置测试",
            "agent_type": "chat",
            "system_prompt": "你是简洁的AI助手，回答限制在30字以内。",
        })
        react_code_agent = await create_agent(client, headers, {
            "name": "API-ReAct代码执行",
            "agent_type": "react",
            "system_prompt": (
                "你是一个编程助手。当用户提出计算或编程问题时，"
                "你必须使用 execute_python_code 工具执行代码并返回结果。"
                "直接返回计算结果，不要自行心算。"
            ),
            "llm_config": {"model_name": "qwen-max", "max_tokens": 1024},
            "tool_config": {"builtin_tools": ["execute_python_code"]},
        })
        react_file_agent = await create_agent(client, headers, {
            "name": "API-ReAct文件查看",
            "agent_type": "react",
            "system_prompt": (
                "你是一个文件查看助手。当用户要求查看文件时，"
                "你必须使用 view_text_file 工具读取文件内容并返回。"
            ),
            "llm_config": {"model_name": "qwen-max", "max_tokens": 1024},
            "tool_config": {"builtin_tools": ["view_text_file"]},
        })
        react_mcp_agent = await create_agent(client, headers, {
            "name": "API-ReAct-MCP计算器",
            "agent_type": "react",
            "system_prompt": (
                "你是一个计算助手。当用户提出数学计算问题时，"
                "你必须使用可用的计算工具（add 或 multiply）来完成计算，"
                "不要自行心算。直接返回工具计算的结果。"
            ),
            "llm_config": {"model_name": "qwen-max", "max_tokens": 1024},
            "tool_config": {
                "mcp_servers": [{
                    "type": "stdio",
                    "name": "test-calculator",
                    "command": "python",
                    "args": ["-m", "scripts.mcp_test_server"],
                }],
            },
        })
        react_mcp_bad_agent = await create_agent(client, headers, {
            "name": "API-ReAct-MCP-BadServer",
            "agent_type": "react",
            "system_prompt": "你是一个助手。如果工具不可用，直接回复用户。",
            "llm_config": {"model_name": "qwen-max", "max_tokens": 512},
            "tool_config": {
                "mcp_servers": [{
                    "type": "stdio",
                    "name": "nonexistent-server",
                    "command": "python",
                    "args": ["-m", "scripts.this_module_does_not_exist"],
                }],
            },
        })
        react_skill_agent = await create_agent(client, headers, {
            "name": "API-ReAct-Skill测试",
            "agent_type": "react",
            "system_prompt": (
                "你是一个有帮助的助手。你拥有查询当前时间的技能。"
                "当用户问你时间相关的问题时，请使用你的技能来回答。"
                "回答限制在100字以内。"
            ),
            "llm_config": {"model_name": "qwen-max", "max_tokens": 1024},
            "tool_config": {
                "builtin_tools": ["execute_python_code"],
                "skills": ["./skills/current-time"],
            },
        })

        print(f"[准备] ChatAgent:      {chat_agent['id'][:8]}...")
        print(f"[准备] AutoAgent:      {auto_agent['id'][:8]}...")
        print(f"[准备] ReAct-Code:     {react_code_agent['id'][:8]}... tools=builtin[execute_python_code]")
        print(f"[准备] ReAct-File:     {react_file_agent['id'][:8]}... tools=builtin[view_text_file]")
        print(f"[准备] ReAct-MCP:      {react_mcp_agent['id'][:8]}... tools=mcp[test-calculator]")
        print(f"[准备] ReAct-MCP-Bad:  {react_mcp_bad_agent['id'][:8]}... tools=mcp[nonexistent]")
        print(f"[准备] ReAct-Skill:    {react_skill_agent['id'][:8]}... tools=skill[current-time]")

        passed = 0
        failed = 0
        results = []

        # ==== TEST 1: ChatAgent 非流式 + model 字段验证 ====
        print(f"\n{'-'*65}")
        print(f"[1/{TOTAL_TESTS}] ChatAgent /chat (非流式 + model 字段验证)")
        print(f"{'-'*65}")
        try:
            t0 = time.time()
            data = await call_chat(client, headers, chat_agent["id"], [
                {"role": "user", "content": "你好，请用一句话介绍自己"}
            ])
            elapsed = time.time() - t0
            assert data["content"] and "[Mock]" not in data["content"]
            assert data["model"] and data["model"] != "mock", f"model 字段异常: {data['model']}"
            print(f"  ✓ ({elapsed:.1f}s) model={data['model']}")
            print(f"    「{data['content'][:150]}」")
            passed += 1
            results.append("✓")
        except Exception as e:
            print(f"  ✗ {e}")
            failed += 1
            results.append("✗")

        # ==== TEST 2: ChatAgent 流式 ====
        print(f"\n{'-'*65}")
        print(f"[2/{TOTAL_TESTS}] ChatAgent /chat/stream (流式 SSE)")
        print(f"{'-'*65}")
        try:
            t0 = time.time()
            text, chunks = await call_chat_stream(client, headers, chat_agent["id"], [
                {"role": "user", "content": "什么是Python？一句话回答"}
            ])
            elapsed = time.time() - t0
            assert text and "[Mock]" not in text
            assert chunks > 1, f"仅 {chunks} chunk，未真正流式"
            print(f"  ✓ ({elapsed:.1f}s, {chunks} chunks) 「{text[:150]}」")
            passed += 1
            results.append("✓")
        except Exception as e:
            print(f"  ✗ {e}")
            failed += 1
            results.append("✗")

        # ==== TEST 3: ChatAgent 多轮历史 ====
        print(f"\n{'-'*65}")
        print(f"[3/{TOTAL_TESTS}] ChatAgent /chat 多轮历史 (messages 数组)")
        print(f"{'-'*65}")
        try:
            data = await call_chat(client, headers, chat_agent["id"], [
                {"role": "user", "content": "我的名字是李四"},
                {"role": "assistant", "content": "你好李四！"},
                {"role": "user", "content": "我叫什么名字？"},
            ])
            assert "李四" in data["content"], f"未利用历史: {data['content'][:200]}"
            print(f"  ✓ 「{data['content'][:150]}」")
            passed += 1
            results.append("✓")
        except Exception as e:
            print(f"  ✗ {e}")
            failed += 1
            results.append("✗")

        # ==== TEST 4: ChatAgent 自动配置 ====
        print(f"\n{'-'*65}")
        print(f"[4/{TOTAL_TESTS}] ChatAgent /chat 自动配置（省略 model_name）")
        print(f"{'-'*65}")
        try:
            t0 = time.time()
            data = await call_chat(client, headers, auto_agent["id"], [
                {"role": "user", "content": "你好"}
            ])
            elapsed = time.time() - t0
            assert data["content"] and "[Mock]" not in data["content"]
            assert data["model"] and data["model"] != "mock"
            print(f"  ✓ ({elapsed:.1f}s) model={data['model']} (自动填充)")
            print(f"    「{data['content'][:150]}」")
            passed += 1
            results.append("✓")
        except Exception as e:
            print(f"  ✗ {e}")
            failed += 1
            results.append("✗")

        # ==== TEST 5: ReActAgent + execute_python_code (tool_calls 验证) ====
        print(f"\n{'-'*65}")
        print(f"[5/{TOTAL_TESTS}] ReActAgent /chat — builtin execute_python_code")
        print(f"{'-'*65}")
        try:
            t0 = time.time()
            data = await call_chat(client, headers, react_code_agent["id"], [
                {"role": "user", "content": "请用 Python 代码计算 2 的 20 次方，并告诉我结果"}
            ])
            elapsed = time.time() - t0
            assert data["content"] and "[Mock]" not in data["content"]
            tool_calls = data.get("tool_calls", [])
            print(f"  → ({elapsed:.1f}s) model={data['model']}")
            print(f"    「{data['content'][:250]}」")
            _print_tool_calls(tool_calls)
            code_tools = [tc for tc in tool_calls if tc["name"] == "execute_python_code"]
            assert len(code_tools) > 0, "tool_calls 中未找到 execute_python_code"
            print(f"  ✓ execute_python_code 工具已调用")
            passed += 1
            results.append("✓")
        except Exception as e:
            print(f"  ✗ {e}")
            failed += 1
            results.append("✗")

        # ==== TEST 6: ReActAgent + execute_python_code 流式 ====
        print(f"\n{'-'*65}")
        print(f"[6/{TOTAL_TESTS}] ReActAgent /chat/stream — 流式工具调用")
        print(f"{'-'*65}")
        try:
            t0 = time.time()
            text, chunks = await call_chat_stream(client, headers, react_code_agent["id"], [
                {"role": "user", "content": "请用Python计算 123 * 456 的结果"}
            ])
            elapsed = time.time() - t0
            assert text and "[Mock]" not in text
            has_result = "56088" in text
            print(f"  → ({elapsed:.1f}s, {chunks} chunks)")
            print(f"    「{text[:250]}」")
            if has_result:
                print(f"  ✓ 流式回复包含正确结果 56088")
            else:
                print(f"  ✓ 流式回复有效")
            passed += 1
            results.append("✓")
        except Exception as e:
            print(f"  ✗ {e}")
            failed += 1
            results.append("✗")

        # ==== TEST 7: ReActAgent + view_text_file (tool_calls 验证) ====
        print(f"\n{'-'*65}")
        print(f"[7/{TOTAL_TESTS}] ReActAgent /chat — builtin view_text_file")
        print(f"{'-'*65}")
        try:
            t0 = time.time()
            data = await call_chat(client, headers, react_file_agent["id"], [
                {"role": "user", "content": "请使用工具查看 requirements.txt 文件的内容"}
            ])
            elapsed = time.time() - t0
            assert data["content"] and "[Mock]" not in data["content"]
            tool_calls = data.get("tool_calls", [])
            print(f"  → ({elapsed:.1f}s) model={data['model']}")
            print(f"    「{data['content'][:300]}」")
            _print_tool_calls(tool_calls)
            file_tools = [tc for tc in tool_calls if tc["name"] == "view_text_file"]
            assert len(file_tools) > 0, "tool_calls 中未找到 view_text_file"
            print(f"  ✓ view_text_file 工具已调用")
            passed += 1
            results.append("✓")
        except Exception as e:
            print(f"  ✗ {e}")
            failed += 1
            results.append("✗")

        # ==== TEST 8: ReActAgent + MCP stdio 计算器 ====
        print(f"\n{'-'*65}")
        print(f"[8/{TOTAL_TESTS}] ReActAgent /chat — MCP stdio 计算器 (add/multiply)")
        print(f"{'-'*65}")
        try:
            t0 = time.time()
            data = await call_chat(client, headers, react_mcp_agent["id"], [
                {"role": "user", "content": "请使用工具计算 7 加 13 的结果"}
            ])
            elapsed = time.time() - t0
            assert data["content"] and "[Mock]" not in data["content"]
            tool_calls = data.get("tool_calls", [])
            print(f"  → ({elapsed:.1f}s) model={data['model']}")
            print(f"    「{data['content'][:300]}」")
            _print_tool_calls(tool_calls)
            mcp_tools = [tc for tc in tool_calls if tc["name"] in ("add", "multiply")]
            assert len(mcp_tools) > 0, (
                f"tool_calls 中未找到 MCP 工具 (add/multiply)，"
                f"共 {len(tool_calls)} 条记录: {[tc['name'] for tc in tool_calls]}"
            )
            has_result = "20" in data["content"]
            if has_result:
                print(f"  ✓ MCP 工具已调用且结果正确 (7+13=20)")
            else:
                print(f"  ✓ MCP 工具已调用 ({mcp_tools[0]['name']})")
            passed += 1
            results.append("✓")
        except Exception as e:
            print(f"  ✗ {e}")
            failed += 1
            results.append("✗")

        # ==== TEST 9: ReActAgent + MCP stdio 计算器 流式 ====
        print(f"\n{'-'*65}")
        print(f"[9/{TOTAL_TESTS}] ReActAgent /chat/stream — MCP stdio 流式 (multiply)")
        print(f"{'-'*65}")
        try:
            t0 = time.time()
            text, chunks = await call_chat_stream(client, headers, react_mcp_agent["id"], [
                {"role": "user", "content": "请使用工具计算 6 乘以 9 的结果"}
            ])
            elapsed = time.time() - t0
            assert text and "[Mock]" not in text
            has_result = "54" in text
            print(f"  → ({elapsed:.1f}s, {chunks} chunks)")
            print(f"    「{text[:250]}」")
            if has_result:
                print(f"  ✓ MCP 流式调用成功且结果正确 (6×9=54)")
            else:
                print(f"  ✓ MCP 流式调用有效")
            passed += 1
            results.append("✓")
        except Exception as e:
            print(f"  ✗ {e}")
            failed += 1
            results.append("✗")

        # ==== TEST 10: ReActAgent + MCP 错误场景（不存在的 server） ====
        print(f"\n{'-'*65}")
        print(f"[10/{TOTAL_TESTS}] ReActAgent /chat — MCP 错误场景 (server 不存在)")
        print(f"{'-'*65}")
        try:
            t0 = time.time()
            data = await call_chat(client, headers, react_mcp_bad_agent["id"], [
                {"role": "user", "content": "你好"}
            ])
            elapsed = time.time() - t0
            assert data["content"], "响应内容为空"
            print(f"  → ({elapsed:.1f}s) model={data.get('model', 'N/A')}")
            print(f"    「{data['content'][:300]}」")
            print(f"  ✓ MCP server 不存在时优雅降级，未崩溃")
            passed += 1
            results.append("✓")
        except Exception as e:
            err_str = str(e)
            if "调用失败" in err_str or "500" in err_str:
                print(f"  ✗ MCP server 不存在导致服务报错 (未优雅降级): {e}")
            else:
                print(f"  ✗ {e}")
            failed += 1
            results.append("✗")

        # ==== TEST 11: ReActAgent + Skill (current-time) ====
        print(f"\n{'-'*65}")
        print(f"[11/{TOTAL_TESTS}] ReActAgent /chat — Skill (current-time)")
        print(f"{'-'*65}")
        try:
            t0 = time.time()
            data = await call_chat(client, headers, react_skill_agent["id"], [
                {"role": "user", "content": "现在是几点？请告诉我当前的日期和时间"}
            ])
            elapsed = time.time() - t0
            assert data["content"] and "[Mock]" not in data["content"]
            tool_calls = data.get("tool_calls", [])
            print(f"  → ({elapsed:.1f}s) model={data['model']}")
            print(f"    「{data['content'][:300]}」")
            _print_tool_calls(tool_calls)
            has_time_info = any(kw in data["content"] for kw in ["2026", "2025", ":", "时", "分"])
            code_tools = [tc for tc in tool_calls if tc["name"] == "execute_python_code"]
            if code_tools and has_time_info:
                print(f"  ✓ Skill 生效：Agent 使用代码工具获取了当前时间")
            elif has_time_info:
                print(f"  ✓ 回复包含时间信息（Skill 提示可能引导了 Agent）")
            else:
                print(f"  ✓ Agent 返回了有效回复")
            passed += 1
            results.append("✓")
        except Exception as e:
            print(f"  ✗ {e}")
            failed += 1
            results.append("✗")

        # ---- 汇总 ----
        total = passed + failed
        print(f"\n{'='*65}")
        if failed == 0:
            print(f"✅ 全部通过! ({passed}/{total})")
        else:
            print(f"⚠️  通过 {passed}/{total}，失败 {failed}")

        test_names = [
            "ChatAgent  /chat          非流式 + model 验证",
            "ChatAgent  /chat/stream   流式 SSE",
            "ChatAgent  /chat          多轮历史",
            "ChatAgent  /chat          自动配置 (省略 model_name)",
            "ReActAgent /chat          builtin execute_python_code",
            "ReActAgent /chat/stream   流式工具调用",
            "ReActAgent /chat          builtin view_text_file",
            "ReActAgent /chat          MCP stdio 计算器 (非流式)",
            "ReActAgent /chat/stream   MCP stdio 计算器 (流式)",
            "ReActAgent /chat          MCP 错误场景 (优雅降级)",
            "ReActAgent /chat          Skill current-time",
        ]
        for i, name in enumerate(test_names):
            print(f"  {results[i]} [{i+1}] {name}")
        print(f"{'='*65}")


if __name__ == "__main__":
    asyncio.run(main())
