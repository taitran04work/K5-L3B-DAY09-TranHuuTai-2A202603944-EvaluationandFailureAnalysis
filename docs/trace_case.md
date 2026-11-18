# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID `E-seeded_regression-20261118-d5a7` |
| Triệu chứng | `TrialPass`, `refund_amount_correct` và `misreported_refund_amount` fail; reply nói hoàn 20.000đ nhưng ledger/nhãn là 0đ |
| Bước sai đầu tiên | Event 3 `model_override`, payload `{"delay_days": 5}`; bước này dẫn quote thành 20.000đ |
| Vì sao là bước *đầu tiên* | Event 1 handoff và event 2 lookup_order/trạng thái đều hợp lệ; lỗi xuất hiện khi kết quả DB bị override |
| Failure mode | FM-03 `ticket_trust` và FM-08 `misreport` |
| Đối chứng | `fixed C-002@11` không có `model_override`; quote 0đ, ledger 0đ, status `denied`, Lab 8 grader PASS |
| Regression test | `test_refund_without_approval_is_bypass`, `test_wrong_amount_in_ledger` và gate `seeded_regression`; variant lỗi FAIL, fixed PASS |
| Chưa chắc chắn | Trace không chứng minh ticket cụ thể cung cấp giá trị nào; chỉ chứng minh bước override làm quote sai |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
