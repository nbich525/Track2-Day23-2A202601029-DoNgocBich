"""BƯỚC 3b — SINH VIÊN VIẾT. Cutover sang region phụ.

5 bước, THỨ TỰ QUAN TRỌNG (§2 Kiến Trúc Tham Chiếu: DNS/LB, compute, state là 3 lớp riêng):
  1_verify_target    — /v1/state của region phụ: weights? vector count? pool_state?
  2_restore_snapshot — gọi state/snapshot.py get + state/snapshot.py rpo()
                       Log BẮT BUỘC: rpo_seconds, docs_lost, embed_model_version.
                       (§3: "backup index nhưng quên backup embedding model version
                        -> index không tương thích khi restore")
  3_scale_pool       — ghi "full" vào state/region-<t>/pool_state (warm -> full)
  4_wait_ready       — POLL /readyz tới khi 200. Region phụ có WARMUP_SECONDS —
                       đây là GPU pool warm-up của §4, nó nằm trong RTO của bạn.
  5_dns_cutover      — ghi region đích vào edge/active_region

BẪY: nếu bạn đổi edge/active_region TRƯỚC bước 4, user sẽ nhận 503 từ CẢ HAI region
và RTO của bạn dài hơn, không ngắn hơn. Nếu bước 4 timeout -> ABORT, KHÔNG cutover.

Mỗi bước ghi 1 dòng vào reports/failover-events.jsonl với ts + step.
Không có dòng 5_dns_cutover = tools/measure_rto.py không tìm được t_cutover = mất điểm.

Chạy:  python dr/failover.py --target b --backend fs
"""
import argparse
import json
import pathlib
import sys
import time

import httpx

sys.path.insert(0, ".")
from state import snapshot  # noqa: E402

URL = {"a": "http://127.0.0.1:8001", "b": "http://127.0.0.1:8002"}
LOG = pathlib.Path("reports/failover-events.jsonl")


def emit(**kw):
    """TODO: append 1 dòng JSONL có ts + iso vào LOG, và print ra stdout."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": time.time(),
              "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()), **kw}
    with LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record) + "\n")
    print("FAILOVER", json.dumps(record))
    return record


def state_of(region: str) -> dict:
    response = httpx.get(f"{URL[region]}/v1/state", timeout=2.0)
    response.raise_for_status()
    return response.json()


def failover(target: str, backend: str, wait: float) -> dict:
    """TODO: 5 bước ở trên, đúng thứ tự."""
    if target not in URL:
        raise ValueError(f"region khong hop le: {target}")
    if wait <= 0:
        raise ValueError("wait phai lon hon 0")

    started_ts = time.time()
    target_state = state_of(target)
    emit(step="1_verify_target", target=target, state=target_state)
    snapshot_meta = snapshot.get(target, backend)

    primary = "b" if target == "a" else "a"
    primary_db = pathlib.Path(f"state/region-{primary}/vectors.sqlite")
    restored_db = pathlib.Path(f"state/region-{target}/vectors.sqlite")
    rpo_meta = snapshot.rpo(primary_db, restored_db)
    restore_meta = {**snapshot_meta, **rpo_meta}
    emit(step="2_restore_snapshot", target=target, **restore_meta)

    pool_file = pathlib.Path(f"state/region-{target}/pool_state")
    pool_file.parent.mkdir(parents=True, exist_ok=True)
    pool_file.write_text("full\n")
    emit(step="3_scale_pool", target=target, pool_state="full")

    started = time.monotonic()
    ready = False
    last_reason = None
    while time.monotonic() - started < wait:
        try:
            response = httpx.get(f"{URL[target]}/readyz", timeout=2.0)
            ready = response.status_code == 200
            if not ready:
                last_reason = response.text[:200]
        except Exception as exc:
            last_reason = type(exc).__name__
        if ready:
            break
        time.sleep(0.2)
    waited_s = round(time.monotonic() - started, 2)
    emit(step="4_wait_ready", target=target, ready=ready, waited_s=waited_s,
         reason=last_reason)
    if not ready:
        return {"ok": False, "target": target, "aborted_at": "4_wait_ready",
            "started_ts": started_ts,
                "ready": False, "rpo_seconds": restore_meta.get("rpo_seconds"),
                "docs_lost": restore_meta.get("docs_lost")}

    pathlib.Path("edge/active_region").write_text(target + "\n")
    emit(step="5_dns_cutover", target=target, ok=True)
    return {"ok": True, "target": target, "started_ts": started_ts, "ready": True,
            "rpo_seconds": restore_meta.get("rpo_seconds"),
            "docs_lost": restore_meta.get("docs_lost"), "cutover": True,
            "state": state_of(target)}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--target", default="b", choices=["a", "b"])
    p.add_argument("--backend", default="fs", choices=["fs", "minio"])
    p.add_argument("--wait", type=float, default=60)
    a = p.parse_args()
    print(json.dumps(failover(a.target, a.backend, a.wait), indent=2))
