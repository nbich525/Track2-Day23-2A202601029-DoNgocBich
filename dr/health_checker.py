"""BƯỚC 3a — SINH VIÊN VIẾT. Health checker cho 2 region.

Yêu cầu (đọc §4 "Kiến Trúc Health-Check-Based Failover" + §2 "DNS Failover"):
  1. Poll /readyz của CẢ HAI region mỗi `interval` giây (mặc định 5s).
     Dùng /readyz, KHÔNG dùng /healthz. /healthz chỉ nói "process còn sống" —
     region có process sống nhưng vector DB rỗng thì vẫn không serve được.
  2. Chỉ đổi trạng thái sau `threshold` lần fail LIÊN TIẾP (mặc định 3).
     Một lần fail không phải outage. Đây là chống flapping (§4 Anti-Patterns).
  3. Ghi 1 dòng JSONL MỖI LẦN ĐỔI TRẠNG THÁI (không ghi mỗi lần poll — log sẽ ngập).
     Dòng bắt buộc có: ts, region, to (HEALTHY|UNHEALTHY), reason,
     interval_s, threshold. Thiếu interval_s/threshold thì tools/measure_rto.py
     không tính được detect floor -> mất điểm.

Chạy:  python dr/health_checker.py --interval 5 --threshold 3 --duration 300 \
              --out reports/health-events.jsonl

CÂU HỎI PHẢI TRẢ LỜI TRƯỚC KHI VIẾT (ghi câu trả lời vào reports/postmortem.md):
  interval=5s, threshold=3 -> sớm nhất bạn có thể phát hiện outage là bao nhiêu giây?
  Con số đó nằm TRONG RTO của bạn. Muốn RTO 5 phút thì được phép chọn interval bao nhiêu?
"""
import argparse
import json
import pathlib
import time

import httpx

URL = {"a": "http://127.0.0.1:8001", "b": "http://127.0.0.1:8002"}


def probe(region: str, timeout: float) -> tuple[bool, str]:
    """TODO: trả về (ready, reason). Timeout PHẢI có — netblock làm request treo mãi."""
    try:
        response = httpx.get(f"{URL[region]}/readyz", timeout=timeout)
        body = response.json()
        if response.status_code == 200 and body.get("ready", True):
            return True, "ready"
        reasons = body.get("reasons") or [f"status={response.status_code}"]
        return False, ";".join(str(reason) for reason in reasons)
    except Exception as exc:
        return False, type(exc).__name__


def run(interval: float, timeout: float, threshold: int, duration: float, out: pathlib.Path):
    """TODO: vòng lặp poll + phát hiện transition + ghi JSONL."""
    if interval <= 0 or timeout <= 0 or threshold < 1 or duration < 0:
        raise ValueError("interval, timeout, threshold phai duong va duration khong am")
    out.parent.mkdir(parents=True, exist_ok=True)
    states = {region: "HEALTHY" for region in URL}
    consecutive_fails = {region: 0 for region in URL}
    end = time.monotonic() + duration

    with out.open("a", encoding="utf-8") as stream:
        while time.monotonic() < end:
            for region in URL:
                ready, reason = probe(region, timeout)
                if ready:
                    consecutive_fails[region] = 0
                    if states[region] == "UNHEALTHY":
                        states[region] = "HEALTHY"
                        record = {
                            "event": "state_change", "ts": time.time(),
                            "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
                            "region": region, "to": "HEALTHY", "reason": reason,
                            "consecutive_fails": 0, "interval_s": interval,
                            "threshold": threshold,
                        }
                        stream.write(json.dumps(record) + "\n")
                        stream.flush()
                else:
                    consecutive_fails[region] += 1
                    if (states[region] == "HEALTHY" and
                            consecutive_fails[region] >= threshold):
                        states[region] = "UNHEALTHY"
                        record = {
                            "event": "state_change", "ts": time.time(),
                            "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
                            "region": region, "to": "UNHEALTHY", "reason": reason,
                            "consecutive_fails": consecutive_fails[region],
                            "interval_s": interval, "threshold": threshold,
                        }
                        stream.write(json.dumps(record) + "\n")
                        stream.flush()
            time.sleep(min(interval, max(0.0, end - time.monotonic())))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--interval", type=float, default=5.0)
    p.add_argument("--timeout", type=float, default=2.0)
    p.add_argument("--threshold", type=int, default=3)
    p.add_argument("--duration", type=float, default=300)
    p.add_argument("--out", default="reports/health-events.jsonl")
    a = p.parse_args()
    run(a.interval, a.timeout, a.threshold, a.duration, pathlib.Path(a.out))
