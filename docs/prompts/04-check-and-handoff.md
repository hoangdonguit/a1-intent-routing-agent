# Chặng 04 — Chạy kiểm tra và bàn giao (7 phút)

1. Chạy bằng Python hiện có, không cài dependency ngoài:
   - PYTHONPATH=src python3 -m unittest discover -s tests -v
   - PYTHONPATH=src python3 -m a1_intent_routing check-inputs --topology topologies/triangle3.json --cases data/dev
   - python3 scripts/preflight.py
   Nếu đã chọn CLI khác thì cập nhật lệnh trong README và handoff cho khớp thực tế.
   Bản thân các lệnh cần timeout; nếu thất bại, sửa trong timebox hoặc ghi nguyên lỗi.
2. Rà diff; git status; xác nhận references/models/raw runs/secrets không bị theo dõi.
   Không commit/push. Không sửa global Git identity.
3. Cập nhật README theo tính năng thật và lệnh chạy. Viết docs/handoff-session-01.md:
   thời gian, file đã làm, test đã chạy/kết quả, thiếu gì, UNVERIFIED nào,
   blocker thật và thứ tự việc chiều. Không bịa kết quả nếu lệnh chưa chạy.
4. Backlog chiều (chỉ ghi kế hoạch, không tự làm):
   a. Chuẩn bị Docker/Containerlab/FRR và lab tam giác dựa trên preflight; pin phiên bản.
   b. Xác minh reference oracle bằng cấu hình đúng và lỗi gieo, reset/hội tụ/timeout.
   c. Pilot syntax_checker, lab_ping_tester và Batfish FRR compatibility; ghi coverage
      và bất đồng. Cân nhắc tài nguyên trước khi chạy Batfish cùng Ollama.
   d. Chọn model 4B lượng tử hóa phù hợp VRAM thực, chốt tag/context/settings và vài
      cặp intent Việt–Anh ở dev. Codex viết code không phải model thực nghiệm.
   e. Chạy one-pass đầu tiên với log thật; rồi vòng sửa và hai loại feedback độc lập.
   f. Hoàn thiện 8 dev/24 eval và topology 6 router/eBGP/prefix theo proposal;
      giữ eval ngoài vòng chỉnh prompt. Thống kê/CI sau khi đủ dữ liệu.
5. Final ngắn bằng tiếng Việt: đã làm gì, lệnh kiểm tra và kết quả, giới hạn,
   bước đầu tiên buổi chiều. DỪNG tại đây.
