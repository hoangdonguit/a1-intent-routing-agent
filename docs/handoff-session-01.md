# Bàn giao cuối session-01 — chặng 04

Ngày 2026-11-10, chặng 04 bắt đầu khoảng 13:11 (+07:00); kiểm tra thực tế
lúc 13:11:49; kiểm cuối lúc 13:13:27, kết thúc khoảng 13:14. Đây là mốc đóng phần việc “buổi sáng” theo yêu cầu, không phải
khẳng định các chặng đã chạy liên tục trong 45 phút. Đã dừng sau kiểm tra/bàn
giao, chưa triển khai backlog buổi chiều. Lịch sử các chặng được giữ bên dưới.

## Sản phẩm đã có

- `src/a1_intent_routing/{contracts.py,__main__.py,__init__.py}`, pyproject.toml:
  dataclass/parser, CLI kiểm input/oracle, trạng thái và bản ghi vòng chạy.
- `topologies/triangle3.json`: ba router tam giác, ba host, IP/link/gateway rõ.
- `data/dev/`: đúng ba input static, OSPF, path_regression; `data/oracles/dev/`:
  oracle độc lập, traffic hai chiều/path và OSPF RIB/area/next hop.
- `reference_configs/dev_{static,path_regression}_01/{base,solution}/`:
  cấu hình thủ công R1/R2/R3, phân biệt nền/đáp án, tất cả UNVERIFIED.
- `tests/test_contracts.py`, `tests/test_dev_cases.py`: 14 unit/contract tests;
  `scripts/preflight.py`: đọc dependency/phần cứng với timeout từng probe.
- README, architecture, requirements, environment, source-review và các README
  dữ liệu/reference mô tả phạm vi và giới hạn. Chặng 04 chỉ cập nhật README,
  handoff và ghi nhận preflight mới trong environment; không mở rộng tính năng.

## Lệnh đã chạy và kết quả

Từ root repo, Python 3.12.3 hiện có; không cài dependency:

```sh
timeout 30s env PYTHONPATH=src python3 -m unittest discover -s tests -v
timeout 10s env PYTHONPATH=src python3 -m a1_intent_routing check-inputs data/dev --oracle-dir data/oracles/dev
timeout 55s python3 scripts/preflight.py
timeout 10s git diff --check
timeout 10s git diff --stat
timeout 10s git diff -- README.md
timeout 10s git status --short
timeout 10s git ls-files
timeout 10s git ls-files --others --exclude-standard
timeout 10s git check-ignore references/assignment.txt models/probe.gguf runs/probe.json .env
```

- 14 tests đạt (0.035s), exit 0; fixtures và validation dữ liệu offline,
  không là smoke test verifier hoặc lab. Tests môi trường không cho pass giả.
- Ba input và oracle nạp thành công, exit 0. CLI thực tế dùng input paths và
  `--oracle-dir`; topology lấy tương đối từ input. Không dùng hai option
  `--topology`/`--cases` của ví dụ prompt 04 vì CLI hiện không hỗ trợ chúng.
- Preflight exit 0, không timeout; exit 0 chỉ nghĩa script hoàn tất báo cáo.
  CPU i5-11400H, 6 core/12 thread; RAM 24,903,290,880 byte, available khoảng
  16.93 GB tại thời điểm đo; disk /home còn 293G; RTX 2050 4096 MiB,
  driver 580.178.04. Docker client/server 29.1.3 available.
- Containerlab, Ollama CLI, vtysh: missing trong PATH. Ollama service:
  unavailable, curl exit 7, không kết nối 127.0.0.1:11434.
- Git diff whitespace check đạt. Rà cả source/data/reference mới vì các file
  này còn untracked, không xuất hiện trong git diff mặc định.
- Git status vẫn có README modified và các thư mục/file triển khai untracked;
  chưa stage/commit/push. `git ls-files` không có references/models/raw runs
  hoặc file secrets; các đường dẫn kiểm ignore đều bị bỏ qua. Không sửa Git
  identity/global config. Không in giá trị bí mật ra báo cáo.

Kiểm cuối bằng script Python có timeout 10s trên file tracked và untracked
không bị ignore: không phát hiện trailing whitespace hoặc các mẫu private key,
AWS access key, GitHub/OpenAI token đã kiểm. Đây là rà mẫu giới hạn, không là
chứng nhận không có mọi loại secret. `git diff --check` và status đã tái kiểm
sau khi cập nhật tài liệu; không có lỗi whitespace.

## Giới hạn và blocker

Chưa có model payload builder, orchestrator, ba verifier hoặc inference.
Chưa xác minh FRR syntax, Batfish service/API/coverage, image FRR, quyền tạo
container/network và lab connectivity. Docker available không chứng minh các
mục này hoạt động. Cấu hình tham chiếu static/path+regression còn UNVERIFIED;
base/solution OSPF pending. Oracle chưa được kiểm bằng cấu hình đúng và lỗi gieo.
Không gọi cấu hình thủ công là kết quả baseline LLM one-pass.

Schema kiểm quan hệ dữ liệu, không chứng minh routing/OSPF hội tụ. Dataclass
chỉ có invariant tối thiểu; coverage và artifact phải được verifier kiểm thật.
Chưa có test payload end-to-end; khi có builder phải kiểm oracle/solution không
lọt vào model. Còn 5 dev + 24 eval để đủ 8/24 và cân bằng bốn nhóm; chưa tạo eval.

## Thứ tự việc chiều — chỉ kế hoạch

1. Dựa preflight, chuẩn bị Docker/Containerlab/FRR, pin phiên bản và lab tam giác;
   xử lý quyền/cài đặt theo ủy quyền riêng. Chưa tải image/model hoặc deploy.
2. Hoàn thiện reference OSPF; xác minh oracle bằng config đúng và lỗi gieo.
   Kiểm regression trước/sau thay đổi, reset lab sạch, hội tụ và timeout.
3. Pilot syntax_checker, lab_ping_tester và Batfish FRR compatibility; ghi coverage,
   unsupported và bất đồng. Cân tài nguyên RAM/VRAM trước Batfish cùng Ollama.
4. Pilot model 4B lượng tử hóa theo VRAM thực 4 GiB; pin tag/context/settings,
   thử vài cặp intent Việt–Anh trên dev. Codex viết code không là model thực nghiệm.
5. Chạy one-pass đầu tiên với token/thời gian/log thật; sau đó hai quỹ đạo sửa
   pass/fail và structured-error độc lập, tối đa 5 sửa sau lần sinh đầu.
6. Hoàn thiện 8 dev/24 eval và topology 6 router/eBGP/prefix theo proposal;
   giữ eval ngoài chỉnh prompt. Thống kê ghép cặp/bootstrap CI khi đủ dữ liệu.

---

# Bàn giao sau chặng 02 (chưa hoàn thành toàn session-01)

2026-11-10, khoảng 09:14–09:23 (+07:00), trong timebox 13 phút của chặng 02.
Người dùng chỉ giao chặng 02 rồi dừng; không thực hiện prompt 03 hoặc 04.
Các thay đổi chặng 01 được giữ nguyên, README được cập nhật trạng thái mới.

## Đã có

- pyproject.toml, package src/a1_intent_routing chạy bằng PYTHONPATH=src.
- Dataclass/parser topology, CaseInput, CaseOracle tách biệt, NetworkCheck,
  StructuredError, ToolResult và RunRecord. Chính sách chiều đi/về, ECMP,
  repair_count 0..5, null cho đo lường chưa có được ghi trong architecture.md.
- CLI check-inputs kiểm dữ liệu và quan hệ topology, lỗi có file/field và exit 1;
  tập input rỗng không được coi hợp lệ. Oracle chỉ nạp bằng option evaluator.
- scripts/preflight.py chỉ đọc, subprocess argv list, timeout mỗi probe,
  báo dependency thiếu/unavailable, không cài đặt hoặc khởi chạy dịch vụ/lab.
- Các thư mục data/dev, topologies, reference_configs có README nêu trạng thái
  pending, chưa chứa ba ca dev hay topology/reference configs chặng 03.

## Kiểm tra đã chạy

```sh
timeout 30s env PYTHONPATH=src python3 -m unittest discover -s tests -v
timeout 55s python3 scripts/preflight.py
timeout 5s env PYTHONPATH=src python3 -m a1_intent_routing check-inputs data/dev
timeout 5s git diff --check
```

9 unit/contract tests đạt, fixture hai node tạo tạm bởi tests. Kiểm dữ liệu đúng,
lỗi subnet/IP/interface/path, enums, ID trùng, tách oracle, lỗi môi trường,
repair limit và probe timeout/missing. Không phải kiểm chứng routing/lab.
Preflight thật lúc 09:19:59: CPU/RAM/disk/GPU và Docker available; Containerlab,
Ollama CLI, vtysh missing trong PATH; Ollama localhost:11434 unavailable (curl 7).
Batfish service/image/coverage chưa kiểm. Lệnh check-inputs data/dev exit 1 vì
chưa có *.input.json, đúng kỳ vọng. git diff --check không báo lỗi whitespace.
Không pip install, tải package/model/image, sudo, thay network host, commit/push.

## Pending và bước tiếp khi được giao

Bắt đầu docs/prompts/03-dev-cases.md: topology tam giác, đúng ba ca dev và oracle
riêng, reference configs UNVERIFIED. Cần bổ sung metadata gateway/OSPF/RIB có
kiểm tra khi ca yêu cầu; hợp đồng hiện chỉ kiểm link IPv4 và traffic/path.
Chưa có model payload builder, orchestrator, syntax checker, Batfish hay lab tester.
Dataclass chỉ bảo vệ invariant tối thiểu lúc khởi tạo; artifact path không chứng
minh bằng chứng thật. Verifier sau này phải kiểm coverage/bằng chứng bắt buộc,
ECMP và trạng thái cuối, không dựa riêng vào schema.

Blocker lab/model vẫn như docs/environment.md; không cần giải quyết chúng để
viết ca offline. Chỉ cài hệ thống hoặc chạy lab khi có ủy quyền mới phù hợp.

## Bàn giao sau chặng 03 — 2026-11-10

Chặng 03 đã hoàn thành; dừng trước chặng 04 theo yêu cầu mới. Phần bàn giao
chặng 02 phía trên là lịch sử, trạng thái hiện tại được cập nhật tại đây.

- Có topologies/triangle3.json, sáu node/sáu link, gateway host được validation.
- Đúng ba input dev: static, OSPF, path_regression; ba oracle riêng tại
  data/oracles/dev. Mỗi chiều là check riêng; path all_paths cấm ECMP né đường
  yêu cầu. OSPF có property RIB protocol/next hop/area, chưa có adapter kiểm thật.
- Static và path_regression có base/solution thủ công, đủ ba router mỗi bộ.
  Base regression giữ H3↔H2; solution thêm H1↔H2. Tất cả UNVERIFIED.
- OSPF reference/base configs pending. Chưa có payload builder nên chưa test
  payload; chỉ kiểm hợp đồng tách input/oracle, không tuyên bố chống rò payload
  đã được kiểm chứng end-to-end.
- README, architecture và hướng dẫn dữ liệu/reference đã cập nhật. Các thay đổi
  sẵn có từ chặng trước được giữ; không commit/push.

Kiểm tra thực tế chặng 03:

```sh
timeout 30s env PYTHONPATH=src python3 -m unittest discover -s tests -v
timeout 5s env PYTHONPATH=src python3 -m a1_intent_routing check-inputs data/dev --oracle-dir data/oracles/dev
timeout 5s git diff --check
```

14 unit/contract tests đạt; ba input và oracle nạp được, CLI exit 0;
whitespace check đạt. Đây là validation dữ liệu offline, không chứng minh FRR
syntax, forwarding, OSPF hội tụ hoặc oracle đúng bằng lab.

Không tạo eval, chạy/giả LLM, deploy lab, tải dependency/model/image hay thay host.
Các blocker môi trường chặng trước chưa tái kiểm; không có bằng chứng mới về lab.
Khi được giao tiếp: chặng 04 theo prompt riêng; seeded broken configs và kiểm
oracle bằng lab vẫn dành cho buổi sau. Còn 5 dev + 24 eval, eBGP/prefix và topology
6 router trong backlog cuối kỳ, không bị loại khỏi phạm vi.
