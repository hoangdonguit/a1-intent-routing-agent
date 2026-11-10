# Rà soát nguồn ngày 2026-11-10

## Nguồn chính đã đọc

1. `NT539.R11_DeTai_CuoiKy.pdf`: A1 là vòng sinh–kiểm chứng–sửa; baseline bắt buộc
   LLM sinh một lần. Chỉ số bắt buộc: intent success, syntax validity, số lần sửa,
   token và thời gian. Checkpoint buổi 9 cần prototype, tập kiểm thử và baseline.
   Rubric: bài toán 15%, hệ thống/agent 25%, evaluation 30%, giới hạn/rủi ro 15%,
   trình bày/phản biện 15%. Sản phẩm cuối gồm code/README, báo cáo 6–10 trang,
   slide và video/demo.
2. `Group12_Proposal.docx` đang có trong nguồn dự án, tiêu đề PROPOSAL A1,
   “Sinh cấu hình định tuyến từ intent có kiểm chứng tự động”. Đã đọc toàn bộ
   đoạn và bảng metric. Đây là bản dùng cho công việc này, không suy từ tên các
   phiên bản cũ trong lịch sử chat.
3. `Tài liệu học tập.zip`: đã kiểm kê 26 tệp nội dung, trích text PDF/PPTX,
   xem mục markdown notebook và rà nội dung liên quan tới môn hiện tại/A1.
   Đọc kỹ ba slide R11 trong thư mục Slide Thầy (Giới thiệu/Buổi1, Buổi2 ML,
   Buổi3 DL). Các bài lab mang mã O11 và đồ án SVM/DT/RF là tài liệu tham khảo
   ML, không phải đặc tả A1. Không kiểm toán từng dòng code của đồ án mẫu vì
   không dùng code đó cho dự án này.

## Điểm ảnh hưởng trực tiếp đến triển khai

- Đề lấy VLAN/ACL làm ví dụ. Proposal chủ động giới hạn định tuyến; giữ lời giải
  thích này, không tự thêm firewall/VLAN vào backlog bắt buộc.
- Ba phương pháp và cả topology 6 router/eBGP/prefix là cam kết cuối kỳ trong
  proposal hiện tại. Chỉ hoãn chúng khỏi session-01, không hạ thành tùy chọn.
- Model thứ hai đánh giá đầy đủ mới là mở rộng theo pilot. Chưa chọn tên model
  cụ thể chỉ từ mức 4B hoặc phần cứng được mô tả.
- Slide Buổi2 nhấn mạnh tách dữ liệu phát triển/đánh giá; dùng dev để chọn prompt,
  giữ eval riêng. Không cần huấn luyện RF/SVM hay neural network cho A1.
- Agent ở đây là vòng điều phối model và tool. Codex đang viết phần mềm;
  Codex không tự trở thành model thực nghiệm Ollama của dự án.
- Thiết kế chi tiết có thể chốt tại checkpoint; buổi sáng nên làm giao diện dữ liệu,
  kiểm tra đầu vào và ba ca dev trước, tránh framework nặng.

## Đóng gói nguồn

`references/` có đề PDF + text, proposal DOCX + text, nguyên bản ba slide R11 +
text, danh mục ZIP và checksum SHA-256. Không chứa toàn bộ ZIP 76 MiB hoặc bài mẫu.
Thư mục này bị Git bỏ qua để không tự đưa tài liệu lớp học lên repository.
Khi cần tài liệu còn lại, người dùng có thể đặt ZIP gốc vào `references/`.
