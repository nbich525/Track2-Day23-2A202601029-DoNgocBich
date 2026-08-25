# Postmortem ? DR Drill Lab 23

Theo ??ng template ?4 "Sau Failover: Blameless Postmortem". Blameless: c?u h?i l?
"h? th?ng/process n?o cho ph?p chuy?n n?y", kh?ng ph?i "ai l?m sai".

## 1. Timeline (m?i d?ng ph?i c? evidence path:line)

| ISO time | S? ki?n | Evidence |
|---|---|---|
| 2026-08-25T13:29:37 | outage b?t ??u | `chaos/chaos-events.jsonl:3` |
| 2026-08-25T13:29:37 | user ??u ti?n b? ?nh h??ng (+0.1s) | `reports/drill-2-withdr.jsonl:81` |
| 2026-08-25T13:29:56 | health check alert (+19.6s) | `reports/health-events.jsonl:2` |
| 2026-08-25T13:30:25 | operator confirm cutover | `reports/runbook-run.jsonl:2` |
| 2026-08-25T13:30:32 | resolved, request ??u ti?n OK t? region B (+57.2s) | `reports/drill-2-withdr.jsonl:109` |

## 2. RTO/RPO ?o ???c vs m?c ti?u ? gap ? b??c n?o?

- RTO m?c ti?u: 300s ? ?o ???c: `57.2s` ? gap: `242.8s`
- RPO m?c ti?u: 300s ? ?o ???c: `20.0s` (`10` doc b? m?t) ? gap: `280.0s`
- **B??c t?n nhi?u gi?y nh?t:** operator response v? timeout sau alert, kho?ng 29.0s trong kho?ng t? alert ??n runbook; GPU warm-up l? b??c t? ??ng l?n nh?t v?i 6.12s (`reports/failover-events.jsonl:4`).

## 3. Root cause (5 whys)

Kh?ng ph?i "v? t?i ch?y chaos script". C?u h?i: *n?u ??y l? outage th?t, b??c n?o
1. V? edge ti?p t?c route v?o Region A cho ??n khi DNS cutover ho?n t?t.
2. V? health checker c?n ba failure li?n ti?p v?i interval 5s ?? ch?ng flapping.
3. V? sau alert v?n c? ?? tr? operator tr??c khi b?t ??u runbook.
4. V? quy tr?nh ch?a c? auto-page/ack deadline cho alert ?? x?c nh?n.
5. V? ownership v? SLO cho b??c t? alert ??n x?c nh?n ch?a ???c ??nh ngh?a trong v?n h?nh.

Root cause h? th?ng: c? ch? DR ?? c? health threshold v? automation, nh?ng quy tr?nh
th?ng b?o/acknowledgement ch?a t? ??ng h?a; replication c?ng cho ph?p m?t 20.0s d? li?u.

## 4. Action items (c? owner + deadline)

| # | Action | Owner | Deadline | Gi?m RTO/RPO bao nhi?u gi?y |
|---|---|---|---|---|
| 1 | Th?m paging v? escalation n?u ch?a x?c nh?n trong 60s; theo d?i alert-to-runbook | SRE on-call | 2026-09-01 | gi?m ph?n operator response, m?c ti?u 20-30s |
| 2 | Gi?m replication interval t? 30s sau khi ?o chi ph? l?u tr?; c?nh b?o khi RPO v??t 10s | Data platform owner | 2026-09-08 | gi?m t?i ?a kho?ng 20s RPO |

## 5. Ba c?u h?i b?t bu?c tr? l?i

1. `interval ? threshold` l? `5 ? 3 = 15.0s`; chi?m kho?ng `26.2%` c?a RTO `57.2s`.
2. N?u h? interval xu?ng 1s, detection floor l? thuy?t gi?m `12.0s`, nh?ng t?ng request/alert noise v? nguy c? flapping; threshold ho?c circuit breaker v?n ph?i gi?.
3. N?u outage k?o d?i 6 gi? v? region ch?nh m?t d? li?u v?nh vi?n, `docs_lost` l? s? document ?? ???c ghi ? primary nh?ng kh?ng c? trong snapshot restore. Trong drill n?y l? `10`, t?c kh?ch h?ng c? th? m?t 10 document m?i nh?t; kh?ng ph?i s? gi? outage.
   b?n c? ngh?a g? v?i kh?ch h?ng?
