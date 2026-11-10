# Project instructions

## Nguồn và mục tiêu

Dự án A1, NT539.R11, Nhóm 12: sinh cấu hình định tuyến FRR từ intent tiếng Việt,
kiểm chứng và tự sửa, so sánh định lượng với LLM one-pass.
Đọc `docs/source-review.md`, `references/assignment.txt`, `references/proposal.txt`
trước khi thiết kế. PDF/DOCX cùng tên là bản gốc để đối chiếu.
Đề cuối kỳ quyết định yêu cầu môn; proposal hiện tại quyết định cam kết của nhóm.
Slide và bài mẫu trong ZIP không tự bổ sung hoặc thay đổi phạm vi A1.
Khi có mâu thuẫn, ghi rõ bằng chứng thay vì âm thầm đổi yêu cầu.

## Cam kết phải giữ

- IPv4, static, OSPF, eBGP/prefix policy, path constraints, regression.
  VLAN và packet-filter ACL ngoài phạm vi; prefix filtering không là firewall.
- 32 ca: 8 dev + 24 eval, chia đều 4 nhóm tác vụ; dự kiến 2 dev + 6 eval/nhóm.
  Không sửa prompt dựa vào eval. Oracle và reference configs phải độc lập với
  cấu hình LLM; oracle/đáp án tham chiếu không được lọt vào payload gửi model.
- 3 phương pháp riêng: one-pass, pass/fail feedback, structured-error feedback.
  Dùng cùng input/model/generation settings và cùng oracle để chấm. Baseline chỉ
  sinh một lần; evaluation vẫn kiểm chứng cấu hình baseline nhưng không trả lỗi để sửa.
- Lần sinh đầu: repair_count=0. Tối đa 5 lần sửa sau đó, tức tối đa 6 lần sinh.
  Hai agent là hai quỹ đạo riêng; mốc 1/3/5 lấy trong từng quỹ đạo, không phải ba
  mẫu độc lập. Prompt/chính sách không được phụ thuộc tổng ngân sách.
- Mỗi ca/phương pháp 3 lượt, lab sạch; 3-router và 6-router chạy tuần tự.
  Model 4B lượng tử hóa là hướng pilot, 6–8B là khảo sát; chưa chốt model/tag/context.
- Ba tool dự kiến: syntax_checker, batfish_verifier, lab_ping_tester.
  Dữ liệu JSON đúng schema không chứng minh cấu hình FRR đúng cú pháp hay định tuyến đúng.
  Chỉ áp cấu hình đã qua kiểm tra cú pháp lên lab riêng, chờ hội tụ có timeout.
  Kiểm tra đường đi cần bằng chứng đường đi, không chỉ ping thành công.
- Trạng thái cuối pass/fail/environment_error; chỉ pass khi đủ kiểm tra bắt buộc
  có bằng chứng. Unimplemented, missing dependency, timeout/lỗi hạ tầng không được
  tính là pass. Tính năng tool không hỗ trợ phải ghi rõ coverage, không âm thầm bỏ check.
- Lưu cấu hình thất bại, bằng chứng theo vòng, lỗi có cấu trúc, token thực, thời gian
  LLM/tool/tổng. Trường chưa đo để null/unavailable, không giả token=0.
  Bất đồng Batfish/lab phải được giữ, không chọn bên có lợi.
- Thống kê ghép cặp theo ca, bootstrap CI 95% theo ca trong từng nhóm tác vụ,
  10.000 mẫu; giữ cả ba lượt và các phương pháp của cùng ca trong cụm lấy mẫu.
  Không coi 72 lượt là 72 bài toán độc lập; công bố mẫu số và environment errors.

## Quy tắc triển khai

- Tôn trọng task buổi hiện tại. Python đơn giản, ít dependency; chưa cần UI,
  database, Kubernetes, multi-agent framework hay fine-tuning.
- Kiểm tra máy thật bằng lệnh đọc có timeout. Phần cứng trong proposal chỉ là
  khai báo, chưa được xác minh trong phiên này.
- Chưa có ủy quyền cài hệ thống/chạy lab trong session-01: không sudo, thay Docker,
  NVIDIA driver, firewall, network namespace/route host; không tải model/image lớn,
  gọi API trả phí hay chỉnh global Codex config. Không sửa ngoài repo.
- Bước cần quyền hoặc thiếu dependency: ghi blocker cụ thể, tiếp tục phần offline
  độc lập. Chỉ hỏi khi câu trả lời thực sự chặn công việc được giao.
- Không tự tạo commit/push. Cuối buổi cập nhật README, tests và handoff thực tế.
  Giữ các chỉnh sửa sẵn có của người dùng. Không reset/clean hoặc force push.
- Không đưa references, secrets, models, raw runs vào Git. Commit benchmark, oracle,
  reference configs và fixtures nhỏ. Results tổng hợp nhỏ có thể theo dõi trong Git.
- Phân biệt rõ unit/contract test, smoke test có fixture, và kiểm chứng lab thật.
  Không tuyên bố baseline/agent đã hoạt động nếu mới có schema/fixture.
