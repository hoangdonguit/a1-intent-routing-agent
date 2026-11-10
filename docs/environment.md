# Môi trường quan sát — chặng 01

Ngày 2026-11-10, Asia/Ho_Chi_Minh (+07:00). Audit bắt đầu khoảng 09:10,
đo máy lúc 09:11:44; hoàn tất lúc 09:13 (+07:00), trong timebox 7 phút. Chỉ chạy lệnh đọc, mỗi
probe có timeout 3–10 giây. Không cài đặt, tải model/image hay khởi chạy lab.

## Kết quả thực tế

| Thành phần | Quan sát |
| --- | --- |
| Repo | `/home/xuandong/4_Ai_UngDung/Doan/a1-intent-routing-agent`, nhánh main theo origin/main; HEAD `84e6fcc`; working tree sạch trước audit |
| OS | Ubuntu 24.04.5 LTS, x86_64; Docker báo kernel 7.0.0-42-generic |
| Python | python3 3.12.3 |
| CPU | Intel Core i5-11400H @ 2.70 GHz, 1 socket, 6 core, 12 thread |
| RAM | free -h: tổng 23 GiB, available khoảng 16 GiB tại thời điểm đo |
| Swap | 34 GiB, dùng 0 B tại thời điểm đo |
| Disk chứa repo | /dev/nvme1n1p2 tại /home: 469 G tổng, 153 G dùng, 293 G còn, 35% |
| GPU | NVIDIA GeForce RTX 2050, 4096 MiB VRAM; driver 580.178.04; nvidia-smi truy cập được |
| Docker | /usr/bin/docker, client và server 29.1.3, API 1.52; docker version đọc được daemon bằng tài khoản hiện tại |
| Containerlab | Không tìm thấy trong PATH; containerlab version báo No such file or directory |
| Ollama CLI | Không tìm thấy trong PATH; ollama --version báo No such file or directory |
| Ollama service | GET http://127.0.0.1:11434/api/version thất bại kết nối (curl exit 7); không xác minh endpoint khác |
| FRR / Batfish | Không tìm thấy vtysh hoặc batfish trong PATH; chưa kiểm package, image hay service, chưa kết luận toàn máy không có |

CPU/GPU quan sát phù hợp mô tả proposal; RAM 23 GiB là số hệ điều hành báo,
không suy từ khai báo 24 GB. Chưa đo hiệu năng model hoặc khả năng đồng thời
chạy lab; VRAM 4 GiB chưa chứng minh model 4B/6–8B chạy được.

## Lệnh đọc dùng để tái kiểm

Chạy tại repo; không cần in environment/auth hoặc danh sách model/container:

```sh
timeout 5s date -Is
timeout 5s git status --short --branch
timeout 5s git log -1 --format='%h %s'
timeout 5s python3 --version
timeout 5s lscpu
timeout 5s free -h
timeout 5s df -h .
timeout 5s cat /etc/os-release
timeout 5s bash -c 'for c in docker containerlab ollama nvidia-smi vtysh batfish; do command -v "$c" || true; done'
timeout 10s nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
timeout 10s docker version --format '{{json .}}'
timeout 5s containerlab version
timeout 5s ollama --version
timeout 5s curl --noproxy '*' --max-time 3 -sS http://127.0.0.1:11434/api/version
```

Các probe độc lập đã chạy; lỗi dependency ở trên là kết quả thật, không phải
pass. Lệnh sandbox đầu tiên thất bại `bwrap: loopback: Failed RTM_NEWADDR:
Operation not permitted`; sau khi được cấp quyền chạy ngoài sandbox, các lệnh
đọc máy thành công theo từng kết quả nêu trên. Không dùng sudo hoặc đổi hệ thống.

## Blocker và hướng xử lý

- Lab thật bị chặn bởi Containerlab chưa có trong PATH; FRR/Batfish và image
  chưa được xác minh. Bước tiếp theo khi được giao: kiểm phiên bản/coverage,
  đề xuất cài đặt riêng và xin quyền trước thay đổi hệ thống/tải image.
- Chạy model bị chặn bởi Ollama CLI thiếu và endpoint mặc định không truy cập
  được. Cần xác minh cách phục vụ model, chốt model/tag/context/settings và
  pilot bộ nhớ sau khi được ủy quyền; không tải model trong audit.
- Python standard library có sẵn cho công việc offline; chưa kiểm venv/pip
  hay dependency dự án, chưa chạy unit test, fixture smoke test hoặc lab test.
- Docker daemon truy cập được chỉ chứng minh API đọc hoạt động; chưa kiểm
  tạo container, network, quyền lab hoặc tương thích FRR/Batfish.

## Bàn giao giới hạn chặng 01

Đã đọc nguồn và tạo requirements/environment; không có baseline, agent,
schema, topology hay kết quả định tuyến thực nghiệm. Không thực hiện prompt
02–04 theo yêu cầu người dùng. Không commit/push. Khi được giao tiếp, bắt đầu
`docs/prompts/02-foundation.md`.

## Tái kiểm chặng 04 — 2026-11-10 13:11:49 (+07:00)

`timeout 55s python3 scripts/preflight.py` hoàn tất exit 0 với Python 3.12.3.
Docker client/server 29.1.3 available; RTX 2050 4096 MiB, driver 580.178.04;
RAM tổng 24,903,290,880 byte, available 16,933,900,288 byte; /home còn 293G.
Containerlab/Ollama CLI/vtysh missing trong PATH, Ollama service unavailable
(curl exit 7 tại localhost:11434). Batfish, FRR image/syntax, quyền tạo
container/network, model inference và lab connectivity chưa kiểm.
Không cài đặt, deploy hoặc thay cấu hình hệ thống trong lần tái kiểm.
