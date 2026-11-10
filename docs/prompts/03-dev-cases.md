# Chặng 03 — Topology và ba ca development (18 phút)

1. Viết topologies/triangle3.json: R1/R2/R3 nối tam giác, H1/H2/H3 mỗi host nối
   một router, subnet không chồng lấn, interface/link/gateway ánh xạ rõ ràng.
   Đây là topology dữ liệu, chưa phải lab đã được deploy.
2. Viết đúng 3 ca dev ban đầu, thuộc 3 trong 4 nhóm để giữ kế hoạch cân bằng:
   - dev_static_01: static routing, H1 tới H2, chỉ định rõ return path.
   - dev_ospf_01: OSPF single-area, connectivity có oracle về OSPF/RIB khi phù hợp.
   - dev_path_regression_01: H1 tới H2 qua R2, đồng thời giữ H3 tới H2; ghi rõ
     đường đi, chiều kiểm tra và regression không được làm mất.
   Nhóm eBGP/prefix chưa có trong session này nhưng vẫn nằm trong backlog bắt buộc.
3. Mỗi ca có input và oracle riêng, đều do người thiết kế viết trước khi dùng LLM.
   Chọn địa chỉ/hướng đi cụ thể, nhất quán với topology; không dùng oracle chỉ
   là tên file cấu hình hoặc so khớp chuỗi lệnh. Tham chiếu property mạng.
4. Viết baseline/reference FRR configs thủ công tối thiểu cho ca static và
   path+regression nếu đủ thời gian. Đặt ở reference_configs/<case_id>/, phân biệt
   nền và đáp án. Mark UNVERIFIED cho đến khi syntax/lab được kiểm chứng thật;
   không gọi reference config là kết quả LLM one-pass. OSPF configs có thể pending.
5. Viết một số unit/contract tests có giá trị: input sai subnet/link/node bị từ chối,
   required path không kề nhau bị từ chối, 3 ca đúng nạp được, oracle không nằm
   trong hàm dựng model payload (nếu đã có hàm đó), lỗi môi trường không thành pass.
   Đừng viết test chỉ assert file tồn tại hoặc sao chép lại hằng số implementation.
6. Không sinh 24 ca eval, không chạy/giả LLM, không viết full routing simulator.
   Seeded broken configs và kiểm chứng oracle bằng lab sẽ làm buổi chiều.

Khi sát timebox, ưu tiên input/oracle hợp lệ và test; cấu hình tham chiếu còn
thiếu phải được ghi pending rõ ràng, không kéo dài để hoàn thành cho đủ hình thức.
