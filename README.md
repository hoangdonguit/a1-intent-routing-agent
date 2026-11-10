# A1 Intent Routing Agent

Sinh cấu hình định tuyến từ intent có kiểm chứng tự động.
English: Intent-Based Routing Configuration with Automated Verification.

NT539.R11 — AI ứng dụng trong mạng và truyền thông, Nhóm 12.
Hoàng Xuân Đồng (23520297), Nguyễn Trường Huy (23520639).

## Trạng thái ban đầu

Đây là bộ tài liệu khởi tạo và giao việc; chưa có mã nguồn agent, chưa chạy lab,
chưa chọn model và chưa có số liệu thực nghiệm.

- Đọc `AGENTS.md`, `docs/source-review.md`, rồi `docs/session-01.md`.
- Chạy buổi sáng: mở Codex tại thư mục này, yêu cầu thực hiện `docs/session-01.md`.
- Các prompt thành phần nằm trong `docs/prompts/`.
- Tài liệu gốc và bản trích xuất cho Codex đọc nằm trong `references/`, chỉ giữ local.
- ZIP học tập 76 MiB không được chép toàn bộ vào bộ khởi tạo. Ba slide R11 liên quan
  được chép nguyên bản cùng bản text; có danh mục đầy đủ ZIP để tra cứu.

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
