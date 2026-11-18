# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không đạt | loại |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | H-008 | FAIL | PASS | Người đúng | Reply thiếu hành động rõ ràng |
| 2 | H-017 | FAIL | PASS | Người đúng | Số tiền reply không khớp ledger |
| 3 | H-029 | FAIL | PASS | Người đúng | Không có bước xử lý cụ thể |
| 4 | H-042 | PASS | FAIL | Người đúng | Judge chặt hơn human |
| 5 | HL-015 | FAIL | PASS | Người đúng | Helpful miss số tiền sai |
| 6 | HL-016 | FAIL | PASS | Người đúng | Xin lỗi nhưng không giải quyết yêu cầu |
| 7 | HL-020 | FAIL | PASS | Người đúng | Số tiền reply sai |
| 8 | HL-028 | FAIL | PASS | Người đúng | Thiếu giải pháp cụ thể |

## Kết luận
- `tone_ok` đạt đủ κ, precision và recall nên có thể dùng calibration.
- `helpful` bị loại: κ=0.375, recall=0.300 dù precision=1.000. Ma trận: TP=9, FP=0, FN=21, TN=70.
- Rủi ro còn lại: judge replay công khai chưa là held-out người dùng thật.
