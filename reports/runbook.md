# Runbook 1 trang — Region chính down

Runbook phải chạy được lúc 3h sáng bởi người KHÔNG viết nó. Mỗi bước: lệnh copy-paste
được + cách biết bước đó xong.

| # | Bước                       | Lệnh                                                                                                       | Biết là xong khi                                                                                       | Ai làm            |
| - | ---------------------------- | ----------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ------------------ |
| 1 | Xác nhận outage            | `./.venv/Scripts/python.exe chaos/kill_region.py status`                                                  | `a.alive=false` hoặc health alert `UNHEALTHY`; kiểm tra 3 lần                                     | on-call            |
| 2 | Mở incident + bấm giờ RTO | `./.venv/Scripts/python.exe dr/runbook.py --primary a --target b --backend fs`                            | `reports/runbook-run.jsonl` có bước `thong_bao_incident`                                          | incident commander |
| 3 | Restore state ở region phụ | `./.venv/Scripts/python.exe state/snapshot.py get --region b --backend fs`                                | `state/region-b/vectors.sqlite`, weights và manifest tồn tại                                        | data platform      |
| 4 | Scale pool warm→full        | Không chạy lệnh riêng; bước này do lệnh ở bước 2 thực hiện                     | `reports/failover-events.jsonl` có `4_wait_ready` với `ready:true`                               | serving owner      |
| 5 | DNS/LB cutover               | `curl --max-time 5 http://localhost:8080/edge/state`                                                      | JSON có`active_region=b`; chỉ chấp nhận sau bước 4                                               | edge owner         |
| 6 | Verify golden signals        | `curl --max-time 5 http://localhost:8080/v1/infer` (10 lần)                                              | runbook ghi`requests:10`, `errors:0`, p95 `32.5ms`                                                 | on-call            |
| 7 | Đo RTO + postmortem         | `./.venv/Scripts/python.exe tools/measure_rto.py --loadgen reports/drill-2-withdr.jsonl --target-rto 300` | `valid:true`, `warnings:[]`, `rto_verdict:PASS`; lưu output vào `reports/measure-drill-2.json` | incident commander |

**Rollback (failover ngược):** chỉ trả traffic về A khi A có `/readyz` 200 liên tục
ít nhất 3 lần trong 15 giây, state/vector và model version đã đối chiếu, và B vẫn
đang healthy. Incident commander phê duyệt, edge owner thực hiện; không tự động
rollback nếu chưa có circuit breaker để tránh flap hai region.
