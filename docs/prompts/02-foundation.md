# Chặng 02 — Khung Python và hợp đồng dữ liệu (13 phút)

Tạo mã tối giản với Python standard library (JSON, argparse, dataclasses,
ipaddress, unittest), chưa cần dependency ngoài hoặc cài package.

1. Tạo pyproject.toml, src/a1_intent_routing/, tests/, data/dev/, topologies/,
   reference_configs/, scripts/. Chỉ tạo module/file có công dụng trong buổi này.
2. Tạo schema/kiểu cho topology (node/interface/link/IP), CaseInput, CaseOracle
   tách riêng, và ToolResult/RunRecord. Trường cần có: case_id, task_group,
   split, intent, topology; oracle có source/destination, reachability,
   required path, regression checks. Chỉ định rõ chiều đi/chiều về và cách xử lý
   ECMP. Ràng buộc người dùng yêu cầu là input; cấu hình đáp án/oracle bí mật là
   tài liệu dành cho evaluator, không đưa vào model input.
3. RunRecord dự kiến giữ method, model/settings, attempt_index/repair_count,
   status, syntax/intent/regression checks, structured errors
   (device/property/expected/observed), artifacts và token/time. Chưa đo để null.
   Chưa cần hiện thực mọi schema nâng cao hay bộ điều phối buổi này.
4. CLI dùng `python -m a1_intent_routing check-inputs`: nạp JSON và kiểm tra
   node/interface tồn tại, IP/subnet, source/destination và cạnh của required path,
   case_id duy nhất, split/group hợp lệ. Báo đường dẫn/trường sai; exit khác 0
   cho input không hợp lệ. Thành công chỉ là input_valid, không phải intent pass.
5. Viết scripts/preflight.py dùng lệnh chỉ đọc, timeout và argv list, không shell=True.
   In báo cáo dependency/máy đủ để định hướng buổi chiều, không biến sự thiếu
   công cụ tùy chọn sáng nay thành lỗi code hoặc tuyên bố lab đã chạy.

Ghi giao diện dự kiến ba tool vào docs/architecture.md (có một Mermaid gọn).
Chưa tạo fake verifier trả pass hoặc framework tổng quát nhiều tầng. Không tải
package chỉ để tạo scaffold. Có thể chạy bằng PYTHONPATH=src.
