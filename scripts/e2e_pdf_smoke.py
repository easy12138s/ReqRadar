"""MVP-1 E2E smoke test with real PDF — run inside api-service container."""
from __future__ import annotations

import time
import uuid

import httpx

AUTH_URL = "http://auth-service:8001"
BFF_URL = "http://localhost:8000"
INTERNAL_KEY = "dev-internal-key-change-in-production"


def main() -> None:
    # 1. 签发 token
    r = httpx.post(
        f"{AUTH_URL}/internal/v2/auth/issue",
        json={"user_id": "00000000-0000-0000-0000-000000000001", "username": "e2e_tester", "is_superuser": True},
        headers={"X-Internal-API-Key": INTERNAL_KEY},
        timeout=30,
    )
    assert r.status_code == 200, f"Token failed: {r.text}"
    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    print("[1/9] Token OK")

    # 2. 创建项目
    r = httpx.post(
        f"{BFF_URL}/api/v2/projects",
        json={"name": f"PDF-E2E-{uuid.uuid4().hex[:8]}", "description": "MVP-1 PDF test", "source_type": "empty"},
        headers=h,
        timeout=30,
    )
    assert r.status_code == 201, f"Create project failed: {r.text}"
    pid = r.json()["id"]
    print(f"[2/9] Project OK id={pid}")

    # 3. 上传真实 PDF 文档
    with open("/tmp/test_req.pdf", "rb") as f:
        pdf_bytes = f.read()
    print(f"  PDF size: {len(pdf_bytes)} bytes")

    r = httpx.post(
        f"{BFF_URL}/api/v2/projects/{pid}/ingest",
        files={"file": ("cool_agent_requirements.pdf", pdf_bytes, "application/pdf")},
        data={"project_id": pid},
        headers=h,
        timeout=300,
    )
    assert r.status_code == 200, f"Ingest failed: {r.text}"
    ingest = r.json()
    eids = ingest.get("embedding_ids", [])
    items_count = ingest.get("items_count", 0)
    print(f"[3/9] Ingest OK items={items_count} embeddings={len(eids)}")

    # 4. 验证向量化
    assert len(eids) > 0, f"Embedding empty: {ingest}"
    print("[4/9] Embedding OK")

    # 5. 创建 Session
    r = httpx.post(
        f"{BFF_URL}/api/v2/sessions",
        json={"project_id": pid},
        headers=h,
        timeout=30,
    )
    assert r.status_code == 201, f"Session create failed: {r.text}"
    sid = r.json()["session_id"]
    print(f"[5/9] Session OK id={sid}")

    # 6. 启动推理
    r = httpx.post(
        f"{BFF_URL}/api/v2/sessions/{sid}/start",
        json={},
        headers=h,
        timeout=30,
    )
    assert r.status_code == 200, f"Start failed: {r.text}"
    print("[6/9] Running")

    # 7. 轮询
    t0 = time.time()
    status = "RUNNING"
    while time.time() - t0 < 600:
        r = httpx.get(f"{BFF_URL}/api/v2/sessions/{sid}", headers=h, timeout=30)
        status = r.json()["status"]
        if status in ("COMPLETED", "FAILED", "ABORTED", "CANCELLED"):
            break
        time.sleep(5)
    elapsed = time.time() - t0
    assert status == "COMPLETED", f"Session ended with {status}"
    print(f"[7/9] Completed in {elapsed:.0f}s")

    # 8. 生成报告
    r = httpx.post(
        f"{BFF_URL}/api/v2/reports/generate",
        json={"session_id": sid},
        headers=h,
        timeout=30,
    )
    assert r.status_code == 202, f"Report gen failed: {r.text}"
    tid = r.json()["task_id"]
    print(f"[8/9] Report generating task={tid}")

    t1 = time.time()
    rs = "pending"
    while time.time() - t1 < 60:
        r = httpx.get(f"{BFF_URL}/api/v2/reports/{tid}/status", headers=h, timeout=30)
        rs = r.json()["status"]
        if rs in ("completed", "failed"):
            break
        time.sleep(2)
    assert rs == "completed", f"Report failed: {rs}"
    sz = r.json().get("size_bytes", 0)
    print(f"[9/9] Report OK size={sz}")

    print(f"\nALL 9 STEPS PASSED WITH REAL PDF! project={pid} session={sid} report_size={sz}")


if __name__ == "__main__":
    main()
