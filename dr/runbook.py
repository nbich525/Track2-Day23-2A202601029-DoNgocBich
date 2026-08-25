"""BƯỚC 3c — SINH VIÊN VIẾT. Tự động hoá runbook §4 "Runbook: Region Chính Down".

7 bước trên slide, mỗi bước 1 dòng log có ts. Log này CHÍNH LÀ timeline của postmortem.
  1 xac_nhan_outage          — probe cả 2 region, đừng tin 1 lần fail (dùng nhiều lần
                              hoặc gọi health_checker.probe nếu đã viết xong 3a)
  2 thong_bao_incident       — ts của dòng này là mốc "operator biết tin", LUÔN LUÔN
                              SAU t_outage trong chaos-events (không thể trùng — operator
                              không thể biết ngay giây outage xảy ra). Ghi cả 2 ts vào
                              log để postmortem tính được "độ trễ thông báo".
  3 scale_gpu_pool           — gọi HÀM `failover.failover(...)` MỘT LẦN DUY NHẤT. Hàm
                              đó tự làm đủ 5 bước con (verify/restore/scale/wait/cutover)
                              và tự ghi log riêng vào reports/failover-events.jsonl.
  4 verify_state_replica     — KHÔNG gọi lại failover — chỉ ĐỌC kết quả (vector count +
                              weights ở region phụ) từ dict mà bước 3 trả về, để log vào
                              runbook-run.jsonl cho postmortem đọc 1 chỗ duy nhất.
  5 dns_cutover              — cũng chỉ đọc lại: kết quả cutover có ok hay không.
  6 verify_golden_signals    — 10 request thật vào region phụ: p95 latency + error rate
  7 post_incident            — elapsed_s + lệnh đo RTO

BÁN TỰ ĐỘNG, KHÔNG FULL-AUTO (§4: "failover đầu tiên nên là bán tự động — alert +
1-click confirm — tránh flapping gây failover 2 chiều liên tục"). Mặc định phải hỏi
người vận hành confirm; --auto chỉ dùng trong CI/khi chấm điểm.

Chạy:  python dr/runbook.py --primary a --target b --backend fs
"""
import argparse
import json
import pathlib
import sys
import time

import httpx

sys.path.insert(0, ".")
from dr import failover as fo  # noqa: E402

LOG = pathlib.Path("reports/runbook-run.jsonl")
URL = {"a": "http://127.0.0.1:8001", "b": "http://127.0.0.1:8002"}


def step(n, name, **kw):
    """TODO: ghi 1 dòng {ts, iso, step, name, ...} vào LOG."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": time.time(),
              "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
              "step": n, "name": name, **kw}
    with LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record) + "\n")
    print("RUNBOOK", json.dumps(record))
    return record


def confirm(auto: bool, msg: str) -> bool:
    """TODO: auto=True -> True; ngược lại hỏi y/N. Đừng bỏ hàm này đi."""
    return auto or input(f"{msg} [y/N] ").strip().lower() == "y"


def run(primary: str, target: str, backend: str, auto: bool) -> dict:
    """TODO: 7 bước ở trên."""
    primary_ready, primary_reason = False, None
    target_ready, target_reason = False, None
    for region in (primary, target):
        try:
            response = httpx.get(f"{URL[region]}/readyz", timeout=2.0)
            ready = response.status_code == 200
            reason = response.text[:200]
        except Exception as exc:
            ready, reason = False, type(exc).__name__
        if region == primary:
            primary_ready, primary_reason = ready, reason
        else:
            target_ready, target_reason = ready, reason
    step(1, "xac_nhan_outage", primary=primary, target=target,
         primary_ready=primary_ready, primary_reason=primary_reason,
         target_ready=target_ready, target_reason=target_reason)
    if primary_ready:
        return {"ok": False, "aborted_at": "xac_nhan_outage",
                "reason": "primary van ready"}
    if not confirm(auto, f"Confirm failover {primary} -> {target}?"):
        step(2, "thong_bao_incident", confirmed=False)
        return {"ok": False, "aborted_at": "confirmation"}
    step(2, "thong_bao_incident", confirmed=True, primary=primary,
         target=target, operator_known_ts=time.time())

    result = fo.failover(target, backend, wait=60.0)
    step(3, "scale_gpu_pool", failover_ok=result.get("ok"),
         aborted_at=result.get("aborted_at"))
    state = result.get("state") or {}
    step(4, "verify_state_replica", count=state.get("count"),
         weights=state.get("weights"), rpo_seconds=result.get("rpo_seconds"),
         docs_lost=result.get("docs_lost"))
    step(5, "dns_cutover", ok=result.get("cutover", False), target=target)

    latencies, failures = [], 0
    for _ in range(10):
        started = time.monotonic()
        try:
            response = httpx.get(f"{URL[target]}/v1/infer", timeout=3.0)
            latencies.append((time.monotonic() - started) * 1000)
            failures += response.status_code != 200
        except Exception:
            failures += 1
    ordered = sorted(latencies)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))] if ordered else None
    step(6, "verify_golden_signals", requests=10, errors=failures,
         error_rate=failures / 10, p95_ms=round(p95, 1) if p95 is not None else None)
    elapsed = round(time.time() - result.get("started_ts", time.time()), 2)
    summary = step(7, "post_incident", elapsed_s=elapsed,
                   measure_command="python3 tools/measure_rto.py --loadgen reports/drill-2-withdr.jsonl --target-rto 300")
    return {"ok": result.get("ok", False), "failover": result,
            "golden_signals": {"p95_ms": p95, "errors": failures},
            "post_incident": summary}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--primary", default="a")
    p.add_argument("--target", default="b")
    p.add_argument("--backend", default="fs", choices=["fs", "minio"])
    p.add_argument("--auto", action="store_true")
    a = p.parse_args()
    print(json.dumps(run(a.primary, a.target, a.backend, a.auto), indent=2))
