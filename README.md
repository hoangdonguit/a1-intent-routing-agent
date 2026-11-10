# A1 Intent Routing Agent

Sinh cấu hình định tuyến từ intent có kiểm chứng tự động.
English: Intent-Based Routing Configuration with Automated Verification.

NT539.R11 — AI ứng dụng trong mạng và truyền thông, Nhóm 12.
Hoàng Xuân Đồng (23520297), Nguyễn Trường Huy (23520639).

## Trạng thái hiện tại

Đã hoàn thành chặng 01–04: audit, khung Python, hợp đồng dữ liệu, CLI validation,
preflight, topology tam giác, ba ca dev/oracle và unit/contract tests offline. Chưa có agent, chưa chạy lab, chưa chọn
model và chưa có số liệu thực nghiệm. Đã kiểm tra và bàn giao session-01; dừng buổi sáng.

- Đọc `AGENTS.md`, `docs/source-review.md`, rồi `docs/session-01.md`.
- Chạy buổi sáng: mở Codex tại thư mục này, yêu cầu thực hiện `docs/session-01.md`.
- Các prompt thành phần nằm trong `docs/prompts/`.
- Tài liệu gốc và bản trích xuất cho Codex đọc nằm trong `references/`, chỉ giữ local.
- ZIP học tập 76 MiB không được chép toàn bộ vào bộ khởi tạo. Ba slide R11 liên quan
  được chép nguyên bản cùng bản text; có danh mục đầy đủ ZIP để tra cứu.

## Audit chặng 01 (2026-11-10)

Đã đối chiếu nguồn và kiểm tra máy; xem [yêu cầu](docs/requirements.md) và
[môi trường, blocker, lệnh tái kiểm](docs/environment.md). Docker truy cập được;
Containerlab/Ollama chưa có trong PATH. Kết quả audit gốc được giữ; chặng 02 bổ sung source/tests như mô tả dưới đây.

## Chạy lại kiểm tra offline

Dùng Python 3.12+, không cần cài package. Từ thư mục repo:

```sh
timeout 30s env PYTHONPATH=src python3 -m unittest discover -s tests -v
timeout 55s python3 scripts/preflight.py
timeout 10s env PYTHONPATH=src python3 -m a1_intent_routing check-inputs data/dev --oracle-dir data/oracles/dev
```

14 unit/contract tests đạt. `data/dev` có đúng ba ca static, OSPF, path+regression;
lệnh cuối exit 0. Kiểm thêm oracle riêng bằng `--oracle-dir data/oracles/dev`. Có thể truyền nhiều file
`*.input.json` hoặc thư mục; `--oracle-dir DIR` chỉ dùng cho evaluator. Thành công
là `input_valid`, không chứng minh FRR/intent/connectivity đúng.

Xem [hợp đồng và kiến trúc](docs/architecture.md),
[bàn giao hiện tại](docs/handoff-session-01.md). Preflight báo dependency thiếu
mà không coi đó là lỗi code; chưa triển khai ba verifier hoặc model payload.

## Phạm vi cuối kỳ

IPv4, static routing, OSPF, eBGP, prefix-list/route-map, đường đi và hồi quy.
Ba phương pháp: one-pass, agent phản hồi đạt/không đạt, agent lỗi có cấu trúc.
32 ca gồm 8 development + 24 evaluation; cân bằng bốn nhóm tác vụ.
Topology tam giác 3 router và đa đường 6 router chạy tuần tự.

Buổi sáng chỉ xây nền tảng cho phạm vi này. Không gọi validator dữ liệu là bộ
kiểm chứng FRR/Batfish/lab. README phải được cập nhật theo kết quả thực tế.

## Git

Theo dõi code, dữ liệu benchmark, oracle, cấu hình tham chiếu, tests, docs và
kết quả tổng hợp nhỏ. `references/`, model và log thô `runs/` được giữ local.
Không xóa log thất bại; bổ sung checksum/manifest và cách lưu trữ khi chạy thật.

## Chặng 03

Xem [dữ liệu dev](data/dev/README.md) và [reference configs](reference_configs/README.md).
Static/path+regression có base và solution thủ công, đều UNVERIFIED. OSPF
configs pending. Chưa sinh eval, gọi LLM hoặc kiểm chứng lab/routing thật.

## Kiểm tra cuối buổi — chặng 04

Tái kiểm lúc 13:11 (+07:00), 2026-11-10: 14 tests đạt, ba input/oracle hợp lệ,
preflight exit 0 (báo quan sát dependency, không có nghĩa lab sẵn sàng).
CLI dùng đường dẫn input; topology lấy từ từng input, không có option
`--topology`/`--cases` trong ví dụ prompt 04.

Docker client/server 29.1.3 truy cập được; RTX 2050 có 4096 MiB VRAM.
Containerlab, Ollama CLI và vtysh thiếu trong PATH; Ollama localhost:11434
không kết nối được. Batfish/FRR image, lab và inference chưa kiểm.
Buổi chiều bắt đầu chuẩn bị/pin Docker–Containerlab–FRR và lab tam giác khi
được giao và có quyền phù hợp; thứ tự đầy đủ trong bàn giao. Chưa triển khai
backlog chiều, không commit/push.
