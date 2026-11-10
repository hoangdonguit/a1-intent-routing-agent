# Yêu cầu A1 — audit chặng 01

Nguồn: `AGENTS.md`, `docs/source-review.md`, `references/assignment.txt`
(mục A1, mốc nộp và rubric), `references/proposal.txt` (mục 1–7 và bảng metric).
Đề môn quyết định yêu cầu môn; proposal quyết định cam kết nhóm. Audit ngày
2026-11-10 chỉ đọc nguồn và kiểm tra môi trường, chưa triển khai baseline/agent.

## Phạm vi và hợp đồng

- Intent tiếng Việt + topology JSON/YAML + cấu hình nền → cấu hình FRR từng
  router, bằng chứng kiểm chứng và trạng thái `pass`, `fail`, `environment_error`.
- IPv4, static routing, OSPF, eBGP, prefix-list/route-map, ràng buộc đường đi
  và bảo toàn kết nối cũ (regression). VLAN và ACL lọc gói ngoài phạm vi;
  prefix filtering không phải firewall.
- Tam giác 3 router và mạng đa đường 6 router nhiều AS, kèm 2–3 host Linux;
  chạy tuần tự. Topology 6 router/eBGP/prefix là cam kết cuối kỳ.
- Model 4B lượng tử hóa là hướng pilot; 6–8B cần khảo sát GPU/CPU. Chưa chốt
  model/tag, lượng tử hóa, context hoặc phiên bản tool; model thứ hai đánh giá
  đầy đủ là mở rộng theo pilot.

## Thiết kế so sánh và dữ liệu

Ba phương pháp riêng: (1) LLM one-pass, (2) agent nhận pass/fail,
(3) agent nhận lỗi có cấu trúc theo thiết bị/thuộc tính/kỳ vọng/quan sát.
Dùng cùng input, model, generation settings và oracle. Baseline chỉ sinh một
lần; bộ chấm vẫn kiểm chứng nhưng không trả lỗi cho baseline để sửa.

Lần sinh đầu có `repair_count=0`; tối đa 5 lần sửa sau đó, tối đa 6 lần sinh.
Hai agent có hai quỹ đạo riêng; lấy mốc sửa 1/3/5 trong từng quỹ đạo, dừng sớm
khi đạt. Các mốc không là mẫu độc lập; prompt/chính sách không phụ thuộc tổng
ngân sách sửa.

32 ca, cân bằng bốn nhóm static / OSPF / eBGP và prefix policy / đường đi và
regression: mỗi nhóm 2 dev + 6 eval, tổng 8 dev + 24 eval. Chỉ dùng dev để
chọn prompt; không chỉnh prompt dựa vào eval. Oracle và reference configs
viết độc lập trước cấu hình LLM và không được lọt vào payload model.
Mỗi ca/phương pháp chạy 3 lượt từ lab sạch. Khảo sát Việt–Anh tương đương
chỉ trên dev, không suy kết nguyên nhân từ vài ca.

## Các tầng kiểm tra

1. Schema validation chỉ kiểm tra cấu trúc/kiểu dữ liệu; JSON hợp lệ không
   chứng minh cú pháp FRR, intent hay connectivity đúng.
2. `syntax_checker` phải kiểm tra cú pháp FRR trên mọi router. Chỉ cấu hình
   vượt tầng này mới được áp vào lab riêng.
3. `batfish_verifier`: initIssues, routes, reachability, traceroute cho thuộc
   tính được hỗ trợ; ghi rõ coverage và tính năng không hỗ trợ.
4. `lab_ping_tester`: ping, traceroute, bảng tuyến, trạng thái OSPF/BGP sau
   chờ hội tụ có timeout; kiểm tra cả kết nối mới và regression. Ràng buộc
   đường đi cần bằng chứng đường đi, không chỉ ping thành công.

Chỉ `pass` khi đủ mọi kiểm tra bắt buộc có bằng chứng. Tool chưa triển khai,
thiếu dependency, timeout/lỗi hạ tầng không được tính pass. Giữ bất đồng
Batfish/lab thay vì chọn kết quả có lợi. Oracle cần được thử bằng cấu hình
đúng và lỗi gieo trước thí nghiệm.

## Metric và thống kê

- Syntax validity: bộ cấu hình cuối vượt cú pháp trên tất cả router; báo cáo
  thêm lần sinh đầu.
- Intent success: vượt toàn bộ điều kiện được hỗ trợ qua Batfish và lab;
  báo cáo thêm tỉ lệ đồng thời vượt regression, sửa thành công, phá hồi quy.
- Số lần sửa: trung bình mọi lượt và riêng lượt thành công, đếm từ 0.
- Token input/output thực của mọi lời gọi; thời gian LLM, tool và tổng từ
  nhận intent đến kết thúc; lưu tích lũy theo vòng. Chưa đo để null/unavailable,
  không giả token=0. Giữ cấu hình thất bại, lỗi cấu trúc và bằng chứng từng vòng.
- So sánh ghép cặp theo ca; chênh lệch tỉ lệ thành công, số ca tốt/ngang/kém,
  bootstrap CI 95% với 10.000 mẫu, lấy mẫu ca trong từng nhóm tác vụ và giữ
  cả ba lượt/các phương pháp của ca trong cùng cụm. Không coi 72 lượt eval
  mỗi phương pháp là 72 bài toán độc lập. CI chứa 0 không chứng minh tương đương.
- Công bố mẫu số, environment errors, lượt không chấm được và quy tắc retry;
  phân loại lỗi cú pháp, định tuyến, policy, hội tụ. Kết luận giới hạn trong
  benchmark/model đã chọn.

## Mốc và sản phẩm

Checkpoint buổi 9: prototype trên vài ca, tập kiểm thử, baseline và số liệu
sơ bộ. Cuối kỳ: code + README tái lập, báo cáo 6–10 trang, slide, video/demo;
đủ 32 ca, ba phương pháp, ba tool, hai topology và đánh giá định lượng.
Rubric: bài toán 15%, hệ thống 25%, evaluation 30%, giới hạn 15%, trình bày 15%.

Đề mô tả baseline “không kiểm chứng”; proposal làm rõ baseline không có vòng
phản hồi nhưng evaluator chấm cùng oracle. Đề dùng VLAN/ACL làm ví dụ, proposal
chọn phạm vi routing; không tự mở rộng sang firewall. Slide/bài ZIP không thêm
cam kết. Yêu cầu hiện tại chỉ hoàn thành chặng 01, dừng trước chặng 02.
