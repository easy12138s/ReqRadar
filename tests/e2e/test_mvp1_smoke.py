"""MVP-1 端到端冒烟测试 — 验证核心链路可跑通。

测试链路（修正后的实际 API 路径）：
1. 签发 JWT Token（通过 auth-service 内部 API）
2. 创建项目（empty 类型）
3. 上传需求文档并触发摄取
4. 验证摄取结果（embedding_ids 非空）
5. 创建 Session
6. 启动 Session 推理
7. 轮询等待 Session 完成
8. 生成报告
9. 验证报告内容

运行方式：
    # 在 Docker 容器内执行（因为 auth-service 端口未暴露到宿主机）
    docker compose exec api-service python -m pytest tests/e2e/test_mvp1_smoke.py -v -s

    # 或直接运行
    docker compose exec api-service python tests/e2e/test_mvp1_smoke.py
"""

from __future__ import annotations

import asyncio
import time
import uuid

import httpx
import pytest

# ── 配置 ──────────────────────────────────────────────────────

AUTH_SERVICE_URL = "http://auth-service:8001"
BFF_URL = "http://localhost:8000"
INTERNAL_API_KEY = "dev-internal-key-change-in-production"
TEST_USER_ID = "00000000-0000-0000-0000-000000000001"

# 轮询配置
POLL_INTERVAL = 5  # 秒
MAX_POLL_WAIT = 300  # 最多等 5 分钟


# ── Fixture ───────────────────────────────────────────────────


@pytest.fixture(scope="module")
def jwt_token() -> str:
    """通过 auth-service 内部 API 签发 JWT Token。"""
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{AUTH_SERVICE_URL}/internal/v2/auth/issue",
            json={
                "user_id": TEST_USER_ID,
                "username": "e2e_tester",
                "is_superuser": True,
            },
            headers={"X-Internal-API-Key": INTERNAL_API_KEY},
        )
        assert resp.status_code == 200, f"签发 token 失败: {resp.text}"
        return resp.json()["token"]


@pytest.fixture(scope="module")
def auth_headers(jwt_token: str) -> dict[str, str]:
    """带 JWT 的请求头。"""
    return {"Authorization": f"Bearer {jwt_token}"}


# ── 测试 ──────────────────────────────────────────────────────


def test_mvp1_full_flow(jwt_token: str, auth_headers: dict[str, str]):
    """MVP-1 端到端全链路冒烟测试。"""
    with httpx.Client(timeout=300) as client:
        # ── Step 1: 健康检查 ──
        resp = client.get(f"{BFF_URL}/health")
        assert resp.status_code == 200, f"健康检查失败: {resp.text}"
        print("\n[1/9] 健康检查 ✅")

        # ── Step 2: 创建项目 ──
        project_name = f"E2E-{uuid.uuid4().hex[:8]}"
        resp = client.post(
            f"{BFF_URL}/api/v2/projects",
            json={
                "name": project_name,
                "description": "MVP-1 E2E smoke test",
                "source_type": "empty",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201, f"创建项目失败: {resp.text}"
        project_id = resp.json()["id"]
        assert resp.json()["status"] == "ready"
        print(f"[2/9] 创建项目 ✅ id={project_id}")

        # ── Step 3: 上传需求文档并触发摄取 ──
        test_doc = (
            "# 测试需求文档\n\n"
            "## 用户认证模块\n\n"
            "1. 用户可以通过邮箱和密码登录系统\n"
            "2. 登录失败时显示明确的错误提示\n"
            "3. 连续 5 次登录失败后锁定账户 30 分钟\n"
            "4. 支持第三方 OAuth2 登录（微信、GitHub）\n\n"
            "## 权限管理\n\n"
            "1. 系统支持 RBAC 角色权限模型\n"
            "2. 管理员可以创建、编辑、删除角色\n"
            "3. 普通用户只能查看自己有权限的资源\n\n"
            "## 数据安全\n\n"
            "1. 所有敏感数据必须加密存储\n"
            "2. 操作日志保留 180 天\n"
            "3. 支持数据导出和账户注销\n"
        )
        resp = client.post(
            f"{BFF_URL}/api/v2/projects/{project_id}/ingest",
            files={"file": ("requirements.md", test_doc.encode(), "text/markdown")},
            data={"project_id": project_id},
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"文档摄取失败: {resp.text}"
        ingest_data = resp.json()
        print(f"[3/9] 文档摄取 ✅ items={ingest_data.get('items_count')}")

        # ── Step 4: 验证向量化结果 ──
        embedding_ids = ingest_data.get("embedding_ids", [])
        assert len(embedding_ids) > 0, (
            f"向量化失败: embedding_ids 为空, raw_context_id={ingest_data.get('raw_context_id')}"
        )
        print(f"[4/9] 向量化验证 ✅ embedding_ids={len(embedding_ids)} 个")

        # ── Step 5: 创建 Session ──
        resp = client.post(
            f"{BFF_URL}/api/v2/sessions",
            json={"project_id": project_id},
            headers=auth_headers,
        )
        assert resp.status_code == 201, f"创建 Session 失败: {resp.text}"
        session_id = resp.json()["session_id"]
        assert resp.json()["status"] in ("CREATED", "READY")
        print(f"[5/9] 创建 Session ✅ id={session_id}")

        # ── Step 6: 启动 Session 推理 ──
        resp = client.post(
            f"{BFF_URL}/api/v2/sessions/{session_id}/start",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"启动 Session 失败: {resp.text}"
        assert resp.json()["status"] == "RUNNING"
        print("[6/9] 启动推理 ✅ status=RUNNING")

        # ── Step 7: 轮询等待 Session 完成 ──
        start_time = time.time()
        final_status = "RUNNING"
        while time.time() - start_time < MAX_POLL_WAIT:
            resp = client.get(
                f"{BFF_URL}/api/v2/sessions/{session_id}",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            final_status = resp.json()["status"]
            if final_status in ("COMPLETED", "FAILED", "ABORTED", "CANCELLED"):
                break
            time.sleep(POLL_INTERVAL)

        assert final_status == "COMPLETED", (
            f"Session 未正常完成: status={final_status}, "
            f"elapsed={time.time() - start_time:.0f}s"
        )
        elapsed = time.time() - start_time
        print(f"[7/9] Session 完成 ✅ status=COMPLETED, 耗时={elapsed:.0f}s")

        # ── Step 8: 生成报告 ──
        resp = client.post(
            f"{BFF_URL}/api/v2/reports/generate",
            json={"session_id": session_id},
            headers=auth_headers,
        )
        assert resp.status_code == 202, f"生成报告失败: {resp.text}"
        task_id = resp.json()["task_id"]
        print(f"[8/9] 报告生成中 ✅ task_id={task_id}")

        # 轮询报告状态
        report_start = time.time()
        while time.time() - report_start < 60:
            resp = client.get(
                f"{BFF_URL}/api/v2/reports/{task_id}/status",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            report_status = resp.json()["status"]
            if report_status in ("completed", "failed"):
                break
            time.sleep(2)

        assert report_status == "completed", f"报告生成失败: {resp.text}"
        report_size = resp.json().get("size_bytes", 0)
        print(f"[9/9] 报告生成 ✅ size={report_size} bytes")

        # ── 汇总 ──
        print("\n" + "=" * 50)
        print(f"MVP-1 E2E 全链路测试通过!")
        print(f"  项目: {project_name} ({project_id})")
        print(f"  Session: {session_id}")
        print(f"  推理耗时: {elapsed:.0f}s")
        print(f"  报告大小: {report_size} bytes")
        print("=" * 50)


if __name__ == "__main__":
    # 直接运行模式（不通过 pytest）
    token = httpx.post(
        f"{AUTH_SERVICE_URL}/internal/v2/auth/issue",
        json={
            "user_id": TEST_USER_ID,
            "username": "e2e_tester",
            "is_superuser": True,
        },
        headers={"X-Internal-API-Key": INTERNAL_API_KEY},
        timeout=30,
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    test_mvp1_full_flow(token, headers)
