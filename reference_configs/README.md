# Cấu hình tham chiếu thủ công — UNVERIFIED

`dev_static_01/` và `dev_path_regression_01/` có `base/` và `solution/`, mỗi
thư mục chứa cấu hình đầy đủ R1/R2/R3 (solution là bản thay thế, không là patch).
Không phải output LLM one-pass và không được dùng làm số liệu baseline.
OSPF configs pending. Mọi config UNVERIFIED: chưa kiểm FRR syntax, Batfish hoặc lab.

Base giữ địa chỉ/interface cố định. Static base chỉ có mạng connected;
path+regression base thêm tuyến H3↔H2 qua R3–R2. Solution thêm tuyến H1↔H2
qua R1–R2, giữ nguyên tuyến regression. Các router không liên quan không cần
route tới tất cả LAN. Không có default route để che lỗi thiếu return route.

Lab sau này phải cấp IP/gateway host theo topology, bật IPv4 forwarding và daemon
zebra/staticd, chọn/pin phiên bản FRR, kiểm syntax rồi mới áp lên lab sạch.
Đây là yêu cầu triển khai pending, chưa được script thực hiện. Cần kiểm base
regression trước và sau thay đổi; oracle phải thử thêm lỗi gieo trong buổi sau.
Không gửi `solution/` hoặc oracle cho model.
