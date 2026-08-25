# Postmortem — DR Drill Lab 23

Theo đúng template §4 "Sau Failover: Blameless Postmortem". Blameless: câu hỏi là
"hệ thống/process nào cho phép chuyện này", không phải "ai làm sai".

## 1. Timeline (mọi dòng phải có evidence path:line)

| ISO time            | Sự kiện                                              | Evidence                             |
| ------------------- | ------------------------------------------------------ | ------------------------------------ |
| 2026-08-25T13:29:37 | outage bắt đầu                                      | `chaos/chaos-events.jsonl:3`       |
| 2026-08-25T13:29:37 | user đầu tiên bị ảnh hưởng (+0.1s)              | `reports/drill-2-withdr.jsonl:81`  |
| 2026-08-25T13:29:56 | health check alert (+19.6s)                            | `reports/health-events.jsonl:2`    |
| 2026-08-25T13:30:25 | operator confirm cutover                               | `reports/runbook-run.jsonl:2`      |
| 2026-08-25T13:30:34 | resolved, request đầu tiên OK từ region B (+57.2s) | `reports/drill-2-withdr.jsonl:109` |

## 2. RTO/RPO đo được vs mục tiêu — gap ở bước nào?

- RTO mục tiêu: 300s · đo được: `57.2s` · gap: `242.8s`
- RPO mục tiêu: 300s · đo được: `20.0s` (`10` doc bị mất) · gap: `280.0s`
- **Bước tốn nhiều giây nhất:** operator response và timeout sau alert, khoảng 29.0s trong khoảng từ alert đến runbook; GPU warm-up là bước tự động lớn nhất với 6.12s (`reports/failover-events.jsonl:4`).

## 3. Root cause (5 whys)

Không phải "vì tôi chạy chaos script". Câu hỏi: *nếu đây là outage thật, bước nào

1. Vì edge tiếp tục route vào Region A cho đến khi DNS cutover hoàn tất.
2. Vì health checker cần ba failure liên tiếp với interval 5s để chống flapping.
3. Vì sau alert vẫn có độ trễ operator trước khi bắt đầu runbook.
4. Vì quy trình chưa có auto-page/ack deadline cho alert đã xác nhận.
5. Vì ownership và SLO cho bước từ alert đến xác nhận chưa được định nghĩa trong vận hành.

Root cause hệ thống: cơ chế DR đã có health threshold và automation, nhưng quy trình
thông báo/acknowledgement chưa tự động hóa; replication cũng cho phép mất 20.0s dữ liệu.

## 4. Action items (có owner + deadline)

| # | Action                                                                                           | Owner               | Deadline   | Giảm RTO/RPO bao nhiêu giây                   |
| - | ------------------------------------------------------------------------------------------------ | ------------------- | ---------- | ------------------------------------------------ |
| 1 | Thêm paging và escalation nếu chưa xác nhận trong 60s; theo dõi alert-to-runbook          | SRE on-call         | 2026-09-01 | giảm phần operator response, mục tiêu 20-30s |
| 2 | Giảm replication interval từ 30s sau khi đo chi phí lưu trữ; cảnh báo khi RPO vượt 10s | Data platform owner | 2026-09-08 | giảm tối đa khoảng 20s RPO                   |

## 5. Ba câu hỏi bắt buộc trả lời

1. `interval × threshold` là `5 × 3 = 15.0s`; chiếm khoảng `26.2%` của RTO `57.2s`.
2. Nếu hạ interval xuống 1s, detection floor lý thuyết giảm `12.0s`, nhưng tăng request/alert noise và nguy cơ flapping; threshold hoặc circuit breaker vẫn phải giữ.
3. Nếu outage kéo dài 6 giờ và region chính mất dữ liệu vĩnh viễn, `docs_lost` là số document đã được ghi ở primary nhưng không có trong snapshot restore. Trong drill này là `10`, tức khách hàng có thể mất 10 document mới nhất; không phải số giờ outage.
   bạn có nghĩa gì với khách hàng?
