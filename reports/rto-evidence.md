# RTO/RPO Evidence ? Lab 23

Quy t?c duy nh?t: m?i con s? ? ??y ph?i tr? ???c v? **m?t d?ng log th?t**
(`???ng/d?n.jsonl:s?_d?ng`). `pytest tests/test_rto_evidence.py` s? m? t?ng file ra ki?m tra.
Con s? kh?ng c? evidence = tr??t, b?t k? c?c ph?n kh?c.

## 1. Drill 1 ? kh?ng c? DR (baseline)

| Ch? s? | Gi? tr? | C?ch ?o | Evidence |
|---|---|---|---|
| t_outage | `2026-08-25T13:25:12` | chaos kill | `chaos/chaos-events.jsonl:1` |
| Request fail ??u ti?n | `+0.1s` | d?ng `ok:false` ??u ti?n sau t_outage | `reports/drill-1-nodr.jsonl:48` |
| Request th?nh c?ng sau ?? | kh?ng c? | kh?ng c? d?ng `ok:true` n?o sau t_outage | `reports/measure-drill-1.json` |
| RTO | `NO_RECOVERY` | `tools/measure_rto.py` | `reports/measure-drill-1.json` |

## 2. Drill 2 ? c? DR

| M?c | +gi?y t? t_outage | C?ch ?o | Evidence |
|---|---|---|---|
| t_outage (m?c 0) | 0 | `action:kill` | `chaos/chaos-events.jsonl:3` |
| User th?y l?i ??u ti?n | 0.1s | d?ng `ok:false` ??u | `reports/drill-2-withdr.jsonl:81` |
| Health check ph?t hi?n | 19.6s | `to:UNHEALTHY, region:a` | `reports/health-events.jsonl:2` |
| Snapshot restore xong | 48.7s | `step:2_restore_snapshot` | `reports/failover-events.jsonl:2` |
| Region ph? ready | 54.9s | `step:4_wait_ready` | `reports/failover-events.jsonl:4` |
| DNS cutover | 54.9s | `step:5_dns_cutover` | `reports/failover-events.jsonl:5` |
| **RTO ?o ???c** | **57.2s** | d?ng `ok:true` ??u sau l?i | `reports/drill-2-withdr.jsonl:109` |

| Ch? s? | ?o ???c | M?c ti?u (slide ?1) | Verdict |
|---|---|---|---|
| RTO ? Inference API | `57.2s` | 300s (5 ph?t) | PASS |
| RPO ? Vector DB | `20.0s` / `10` doc | 300s (5 ph?t) | PASS |

## 3. RTO c?a t?i g?m nh?ng g? (b?t bu?c ? ??y l? ph?n ch?m ?i?m hi?u b?i)

| Th?nh ph?n | Gi?y | N? ??n t? ??u | Gi?m ???c b?ng c?ch n?o |
|---|---|---|---|
| Health-check detect floor + operator response | 48.6s | `interval_s ? threshold = 15.0s`, alert ? `reports/health-events.jsonl:2`, runbook b?t ??u ? `reports/runbook-run.jsonl:1` | gi?m interval, alert routing v? thao t?c x?c nh?n |
| Snapshot restore | 0.0s | `reports/failover-events.jsonl:2` ? `reports/failover-events.jsonl:3` | snapshot g?n nh?t, restore song song |
| GPU pool warm-up | 6.1s | `waited_s: 6.12` ? `reports/failover-events.jsonl:4` | pool warm s?n ho?c gi? capacity d? ph?ng |
| DNS/LB TTL cache | 2.5s | request OK `reports/drill-2-withdr.jsonl:109` ? cutover `reports/failover-events.jsonl:5` | gi?m TTL/cache propagation |

C?c th?nh ph?n l?m tr?n: `48.6 + 0.0 + 6.1 + 2.5 = 57.2s`. Kho?n 48.6s bao g?m
detect floor 15.0s, th?i gian probe/timeout th?c t? v? 29.0s operator response;
kh?ng coi th?i ?i?m operator ch?y runbook l? th?i ?i?m outage.
