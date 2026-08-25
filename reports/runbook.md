# Runbook 1 trang ? Region ch?nh down

Runbook ph?i ch?y ???c l?c 3h s?ng b?i ng??i KH?NG vi?t n?. M?i b??c: l?nh copy-paste
???c + c?ch bi?t b??c ?? xong.

| # | B??c | L?nh | Bi?t l? xong khi | Ai l?m |
|---|---|---|---|---|
| 1 | X?c nh?n outage | `./.venv/Scripts/python.exe chaos/kill_region.py status` | `a.alive=false` ho?c health alert `UNHEALTHY`; ki?m tra 3 l?n | on-call |
| 2 | M? incident + b?m gi? RTO | `./.venv/Scripts/python.exe dr/runbook.py --primary a --target b --backend fs` | `reports/runbook-run.jsonl` c? b??c `thong_bao_incident` | incident commander |
| 3 | Restore state ? region ph? | `./.venv/Scripts/python.exe state/snapshot.py get --region b --backend fs` | `state/region-b/vectors.sqlite`, weights v? manifest t?n t?i | data platform |
| 4 | Scale pool warm?full | `./.venv/Scripts/python.exe dr/runbook.py --primary a --target b --backend fs --auto` | `reports/failover-events.jsonl` c? `4_wait_ready` v?i `ready:true` | serving owner |
| 5 | DNS/LB cutover | `curl --max-time 5 http://localhost:8080/edge/state` | JSON c? `active_region=b`; ch? ch?p nh?n sau b??c 4 | edge owner |
| 6 | Verify golden signals | `curl --max-time 5 http://localhost:8080/v1/infer` (10 l?n) | runbook ghi `requests:10`, `errors:0`, p95 `32.5ms` | on-call |
| 7 | ?o RTO + postmortem | `./.venv/Scripts/python.exe tools/measure_rto.py --loadgen reports/drill-2-withdr.jsonl --target-rto 300` | `valid:true`, `warnings:[]`, `rto_verdict:PASS`; l?u output v?o `reports/measure-drill-2.json` | incident commander |

**Rollback (failover ng??c):** ch? tr? traffic v? A khi A c? `/readyz` 200 li?n t?c
?t nh?t 3 l?n trong 15 gi?y, state/vector v? model version ?? ??i chi?u, v? B v?n
?ang healthy. Incident commander ph? duy?t, edge owner th?c hi?n; kh?ng t? ??ng
rollback n?u ch?a c? circuit breaker ?? tr?nh flap hai region.
