# Bắt đầu trên Ubuntu của Đồng

Tên folder/repo: `a1-intent-routing-agent`.
Đường dẫn: `/home/xuandong/4_Ai_UngDung/Doan/a1-intent-routing-agent`.
Gói này chứa tài liệu và prompt; Codex sẽ viết code khi bạn chạy phiên buổi sáng.

## Tạo folder và giải nén

Tải `a1-intent-routing-agent-starter.zip` về Downloads, rồi mở một tab Terminal
mới (không dán lệnh bash vào ô Ask Codex to do anything):

```bash
mkdir -p /home/xuandong/4_Ai_UngDung/Doan
python3 -m zipfile -e "$HOME/Downloads/a1-intent-routing-agent-starter.zip" /home/xuandong/4_Ai_UngDung/Doan
cd /home/xuandong/4_Ai_UngDung/Doan/a1-intent-routing-agent
pwd
```

ZIP có sẵn thư mục gốc a1-intent-routing-agent. Nếu trình duyệt tải sang chỗ
khác, thay đường dẫn ZIP ở lệnh giải nén. Dùng trong folder mới để tránh ghi đè
thay đổi của một bản starter đã được chỉnh.

## Nối GitHub

Tạo repo trống `a1-intent-routing-agent` trên GitHub, không thêm README,
.gitignore hay license lúc tạo. URL dưới giả định chủ repo là hoangdonguit.
Chạy lần đầu trong folder vừa giải nén:

```bash
git init -b main
git add .
git diff --cached --stat
git commit -m "chore: initialize A1 project instructions and references guide"
git remote add origin https://github.com/hoangdonguit/a1-intent-routing-agent.git
git remote -v
git push -u origin main
```

Chỉ tiếp tục lệnh tiếp theo nếu lệnh trước thành công. Tài liệu references/ vẫn
ở máy nhưng không được add nhờ .gitignore. Nếu Git báo chưa đặt danh tính,
đặt `git config user.name` và `git config user.email` cho riêng repo bằng thông tin
GitHub của bạn rồi chạy lại commit; không cần thay cấu hình global.

## Chạy bốn chặng liên tiếp

```bash
codex "Đọc AGENTS.md và docs/session-01.md. Thực hiện lần lượt cả bốn chặng trong session-01, tự chuyển chặng sau khi kiểm tra xong, giữ timebox khoảng 45 phút, ghi handoff và dừng; không chỉ lập kế hoạch."
```

Không cần dán lại toàn bộ prompt dài: prompt đã ở file trong repo.
Mục tiêu 45 phút code + khoảng 5–10 phút setup, có thể nhanh/chậm theo máy,
tốc độ dịch vụ và các bước xác thực; prompt không là bộ hẹn giờ cứng của Codex.

## Nếu muốn tự giao từng chặng

Khởi động bằng `codex` trong repo, rồi gửi lần lượt, chỉ gửi bước kế sau khi bước
trước kết thúc; thay cách chạy liên tiếp bằng cách này, không chạy cả hai:

```text
Đọc AGENTS.md và thực hiện docs/prompts/01-audit.md. Chỉ làm chặng 01 rồi dừng.
```
```text
Tiếp tục thực hiện docs/prompts/02-foundation.md. Chỉ làm chặng 02 rồi dừng.
```
```text
Tiếp tục thực hiện docs/prompts/03-dev-cases.md. Chỉ làm chặng 03 rồi dừng.
```
```text
Thực hiện docs/prompts/04-check-and-handoff.md. Chạy kiểm tra, ghi handoff rồi dừng buổi sáng.
```

## Lưu code sau phiên

Mở tab terminal khác để chạy khi Codex đã kết thúc công việc:

```bash
cd /home/xuandong/4_Ai_UngDung/Doan/a1-intent-routing-agent
git status --short
git diff --stat
git add .
git diff --cached --stat
git commit -m "feat: add A1 input validation and initial development cases"
git push
```

## Buổi chiều

```bash
cd /home/xuandong/4_Ai_UngDung/Doan/a1-intent-routing-agent
codex resume --last
```

Nếu phiên gần nhất không đúng A1, dùng `codex resume` để chọn phiên; cũng có thể
mở `codex` mới rồi yêu cầu đọc AGENTS.md và docs/handoff-session-01.md trước khi
tiếp tục. Đừng giao triển khai lab chiều trước khi xem preflight và handoff sáng.
