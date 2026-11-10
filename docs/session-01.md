# Buổi sáng: nền tảng A1 trong khoảng 45 phút làm việc

Hãy THỰC HIỆN, không chỉ đưa kế hoạch. Đọc AGENTS.md và lần lượt thực hiện các
prompt 01 → 02 → 03 → 04 trong docs/prompts/. Không cần chờ xác nhận giữa chặng;
sau mỗi chặng báo ngắn những gì đã có và kiểm tra nào đã chạy.

Mục tiêu: 1 project Python tối giản có CLI kiểm tra đầu vào, topology 3 router,
3 ca dev và oracle riêng, tests offline, preflight máy thật, bàn giao buổi chiều.
Đây chưa phải prototype agent/checkpoint. Chưa chạy model, Batfish hay lab.

## Timebox chung

- Chặng 01: 7 phút, chặng 02: 13 phút, chặng 03: 18 phút, chặng 04: 7 phút.
- Ghi thời điểm bắt đầu và kiểm tra thời gian sau mỗi chặng, trước tác vụ dài.
  Nếu xong sớm thì kết thúc sớm, không chờ cho đủ phút.
- Đến phút 35, không mở rộng tính năng; đến phút 40, chuyển sang kiểm tra/bàn giao.
  Mục tiêu kết thúc khoảng phút 45; dự phòng tới 50 phút để lưu phần dang dở.
  Đây là timebox trong prompt, không phải cơ chế CLI bảo đảm cắt đúng phút.
- Mọi lệnh kiểm tra phải có timeout hợp lý; không mắc kẹt vào cài đặt/tải xuống.
  Nếu dependency thiếu, dùng Python standard library hoặc ghi blocker và tiếp tục.
- Không đánh đổi tính trung thực của kiểm chứng để hoàn thành checklist. Chưa
  làm được thì ghi pending và điều kiện tiếp tục, không trả pass giả.

## Điều kiện kết thúc

Có source/tests đã viết, lệnh chạy lại cụ thể, kết quả thật hoặc lỗi thật, và
docs/handoff-session-01.md ghi rõ bước tiếp theo. Tự dừng sau session-01,
không triển khai tiếp buổi chiều trong cùng yêu cầu này.
