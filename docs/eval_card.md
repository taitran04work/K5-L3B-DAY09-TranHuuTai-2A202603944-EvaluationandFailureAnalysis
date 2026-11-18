# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:** baseline `E-swarm-20261118-d5a7`; eval set SHA `d5a75e33b47c`
- **Phiên bản:** eval set v1 · metric_spec 1.0 · grader lab9 hiện tại · seeds 11/22/33/44/55
- **Eval set:** v1, 14 item × 5 seed, nguồn lab8_public; nhãn: labels_v1.json
- **Metric & ngưỡng:** xem `config/metric_spec.yaml`
- **Kết quả baseline vs PR:** baseline pass_rate 0.9857; fixed 1.0000; seeded_regression 0.7143; CI seeded Δ=-0.271 [-0.500,-0.057]
- **Judge:** tone_ok κ=0.757, P=0.857, R=0.800; helpful bị loại: κ=0.375, P=1.000, R=0.300
- **Trace case:** link `docs/trace_case.md`, bước sai đầu tiên, regression test
- **Gate owner:** ai xử lý khi gate exit 1
- **Phạm vi pilot:** …
- **Giới hạn / bằng chứng còn thiếu:** MockLLM, 14 item × 5 seed, judge replay; không đo trên người dùng thật
- **Khi nào tăng eval-set version:** khi thêm trace failure, thay slice, thay adversarial pack hoặc bổ sung failure mode mới
