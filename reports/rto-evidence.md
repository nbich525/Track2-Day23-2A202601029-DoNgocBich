# RTO/RPO Evidence — Lab 23

Quy tắc duy nhất: mỗi con số ở đây phải trỏ được về **một dòng log thật**
(`đường/dẫn.jsonl:số_dòng`). `pytest tests/test_rto_evidence.py` sẽ mở từng file ra kiểm tra.
Con số không có evidence = trượt, bất kể các phần khác.

## 1. Drill 1 — không có DR (baseline)

| Chỉ số | Giá trị | Cách đo | Evidence |
|---|---|---|---|
| t_outage | `2026-08-25T13:25:12` | chaos kill | `chaos/chaos-events.jsonl:1` |
| Request fail đầu tiên | `+0.1s` | dòng `ok:false` đầu tiên sau t_outage | `reports/drill-1-nodr.jsonl:48` |
| Request thành công sau đó | không có | không có dòng `ok:true` nào sau t_outage | `reports/measure-drill-1.json` |
| RTO | `NO_RECOVERY` | `tools/measure_rto.py` | `reports/measure-drill-1.json` |

## 2. Drill 2 — có DR

| Mốc | +giây từ t_outage | Cách đo | Evidence |
|---|---|---|---|
| t_outage (mốc 0) | 0 | `action:kill` | `chaos/chaos-events.jsonl:3` |
| User thấy lỗi đầu tiên | 0.1s | dòng `ok:false` đầu | `reports/drill-2-withdr.jsonl:81` |
| Health check phát hiện | 19.6s | `to:UNHEALTHY, region:a` | `reports/health-events.jsonl:2` |
| Snapshot restore xong | 48.7s | `step:2_restore_snapshot` | `reports/failover-events.jsonl:2` |
| Region phụ ready | 54.7s | `step:4_wait_ready` | `reports/failover-events.jsonl:4` |
| DNS cutover | 54.7s | `step:5_dns_cutover` | `reports/failover-events.jsonl:5` |
| **RTO đo được** | **57.2s** | dòng `ok:true` đầu sau lỗi | `reports/drill-2-withdr.jsonl:109` |

| Chỉ số | Đo được | Mục tiêu (slide §1) | Verdict |
|---|---|---|---|
| RTO — Inference API | `57.2s` | 300s (5 phút) | PASS |
| RPO — Vector DB | `20.0s` / `10` doc | 300s (5 phút) | PASS |

## 3. RTO của tôi gồm những gì (bắt buộc — đây là phần chấm điểm hiểu bài)

| Thành phần | Giây | Nó đến từ đâu | Giảm được bằng cách nào |
|---|---|---|---|
| Health-check detect floor + operator response | 48.6s | `interval_s × threshold = 15.0s`, alert ở `reports/health-events.jsonl:2`, runbook bắt đầu ở `reports/runbook-run.jsonl:1` | giảm interval, alert routing và thao tác xác nhận |
| Snapshot restore | 0.0s | `reports/failover-events.jsonl:2` → `reports/failover-events.jsonl:3` | snapshot gần nhất, restore song song |
| GPU pool warm-up | 6.1s | `waited_s: 6.12` ở `reports/failover-events.jsonl:4` | pool warm sẵn hoặc giữ capacity dự phòng |
| DNS/LB TTL cache | 2.5s | request OK `reports/drill-2-withdr.jsonl:109` − cutover `reports/failover-events.jsonl:5` | giảm TTL/cache propagation |

Các thành phần làm tròn: `48.6 + 0.0 + 6.1 + 2.5 = 57.2s`. Khoản 48.6s bao gồm
detect floor 15.0s, thời gian probe/timeout thực tế và 29.0s operator response;
không coi thời điểm operator chạy runbook là thời điểm outage.
