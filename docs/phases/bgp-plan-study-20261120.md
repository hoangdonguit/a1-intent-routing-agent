# Đợt BGP giới hạn: origination, export và BGP plan — 2026-11-20

## Kết luận hiện tại

Đã triển khai nhánh **hybrid opt-in**, chưa đổi raw-FRR mặc định và chưa có kết quả model mới. Hai control đúng do renderer tạo qua FRR parser/daemon và Batfish offline; control đảo policy fail đúng kỳ vọng. Control sender cho phép/receiver chặn vẫn pass bộ kiểm offline cũ, vì vậy phép kiểm export phía sender là bổ sung cần calibration thật, không được gọi là đã nghiệm thu chỉ nhờ unit test. Lab có root và pilot còn chờ launcher; không suy rằng model BGP02 phải pass mọi lần mới hoàn thành đồ án.

Nguồn: bản đã nộp `/home/xuandong/4_Ai_UngDung/Doan/docs/Group12_Proposal.pdf`, 3 trang, SHA256 `28cb9b5b018abad999c8775e1b3a1a357fea70cad08e9b3658bd46dcd5cf73a4`; đề `/home/xuandong/4_Ai_UngDung/Doan/docs/NT539.R11_DeTai_CuoiKy.pdf`, mục A1 và yêu cầu sản phẩm/rubric, SHA256 `518fac5a9aac95f0be10535635061086dbf41fa94e204074f326160fdf8b87bf`. Đã đọc lại toàn bộ proposal và phần đề liên quan. DOCX lịch sử không bổ sung cam kết. Proposal §1 không mặc định agent tốt hơn baseline; §3/7 coi 6–8B là mở rộng; Việt–Anh dev và B0 SyNET gốc vẫn là cam kết. Hybrid này là thử nghiệm mở rộng biểu diễn, không thay primary hay B0.

## A. Origination: bằng chứng đã có và phần chưa chứng minh

Image pin: `batfish/batfish@sha256:105a13d2f6581c7eb82cc36c413c09cdb81044f210f9155f5bf1d148aa726dbb`; image ID `sha256:b77e52fd1ab80efcb33b47b3405bf8d899a14edc5d536ba679a77e9838c68dc9`; label version `2026.11.09.3904`, tag `8dfc9d8`, truy thành commit `8dfc9d8dc4b4b7713ef9da4cbc21006c6bc017d9`. Health bằng truy vấn thật đã pass.

`FrrConversions.java` ở commit người dùng cung cấp `735d69e0fbdf7ea9427fcff4855bb51f52a81fc2` và commit từ image label có nội dung byte-identical, SHA256 `be2822d2c91ef1ed6ab0952dc29f0b5f2f2d0e49acad56da369f0313c8f96294`. Source có unconditional network, main-RIB independent policy và DiscardNextHop. Đây là provenance source/label, **chưa chứng minh binary hoặc semantics runtime tương đương**. [URL và hash](../../results/bgp-plan-study-20261120/source-provenance.json).

Đã chuẩn bị tám biến thể: connected/static chính xác với next-hop liền kề/no backing/learned-BGP × import-check on/off. Hai biến thể learned-BGP giữ counterexample transit đã quan sát, nhằm phân biệt trường hợp chỉ có route BGP. Peering/policy và các router khác cố định. Connected thêm loopback R2 trong cả cấu hình và topology diagnostic của Batfish; không sửa topology primary. Không xóa network candidate, không thay lab vào kết quả Batfish, không bỏ coverage guard v5.

CLI probe trên FRR pin `10.7.1_git`: running-config/main-RIB/BGP-RIB/advertised-routes JSON được nhận. `show bgp ipv4 unicast import-check-table json` trả unknown command; ghi unavailable, không biến exit0/JSON rỗng thành bằng chứng đúng. Raw probe: `runs/bgp-plan-study-20261120/cli-probe/`. Launcher lưu CLI mọi router và query main/BGP RIB R2 riêng cho mỗi biến thể. Chưa có kết luận cơ chế runtime trước khi đọc kết quả lab. Không fork engine trong đợt này.

## B. Export: phân biệt ba phát biểu

Không có prefix trong RIB nhận chỉ chứng minh RIB nhận thiếu prefix tại thời điểm đo. Nó không chứng minh outbound policy deny, cũng không chứng minh sender chưa quảng bá. `sender-export-grader-v1`, tổng hợp bằng `bgp-hybrid-export-v1`, bổ sung:

- BGP session Established và advertised-routes từ đúng sender/peer; kiểm tra schema/counter, không chấp nhận `{}`.
- Prefix có sẵn ở BGP RIB của một router thực sự khai báo originate, tránh kiểm tra rỗng.
- `bgpPeerConfiguration` lấy chính Export_Policy gắn với Node/Remote_IP; gọi `testRoutePolicies` chiều OUT với route cụ thể. Không đoán tên map. Yêu cầu deny tại router khai báo originate; policy transit là diagnostic, tránh thêm điều kiện mọi transit phải deny.

API đã thử thật: policy OUT của reference BGP02 trả DENY cho prefix H2; API có sẵn trên image hiện tại. Probe: `runs/bgp-plan-session-20261120/policy-api-probe/`. Python policy trace không thay Batfish/lab.

Bộ mười control gồm hai positive và sai ASN, self-neighbor, thiếu peer, thiếu originate, leak, policy không gắn, đảo deny/permit và sender-allow/receiver-deny. Control cuối bắt buộc bộ kiểm legacy full pass nhưng grader mới fail; nếu không quan sát đúng, calibration dừng trước model. Không đổi verdict lịch sử.

## C. Vòng sửa lặp: payload thật

[Audit máy đọc được](../../results/bgp-plan-study-20261120/payload-audit.json) đọc request/raw-response/candidate/record của BGP02 vòng3–5. Options giống nhau; raw response file khác metadata nhưng assistant content và cả sáu candidate giống nhau, không router nào thay đổi. Vòng4–5 có messages khác hash nhưng bằng nhau sau chỉ chuẩn hóa đường dẫn. Vòng3–4 messages còn khác; error set đã lọc evidence giống nhau. Do đó chưa có bằng chứng feedback mạng thay đổi đáng kể mà model vẫn bỏ qua. Không gọi khác đường dẫn là chiến lược sửa mới.

Hybrid giữ tối đa hai lần thử trước; nếu context không đủ, bỏ đúng cặp cũ nhất rồi đo lại, không cắt public input. A1 user feedback chỉ literal `FAIL`. A2 tối đa sáu lỗi gốc, ưu tiên schema/syntax/scope rồi peer/export; kèm ID thiết bị/peer khi định vị được. Mỗi call đo tokenizer trước, xác minh context model thực sau call. Dừng ở pass, environment/coverage error, semantic candidate cycle hoặc hết5repair; `stagnated` là stop reason của fail. Mốc chưa sinh giữ null.

## D/E. Output contract, controls và pilot

`schemas/bgp-plan-v1.json`, `prompts/bgp-plan-v1.txt`, renderer/feedback v1 được version hóa. Model chọn ASN, peer, activate, originate, policy rules theo thứ tự và default action. Renderer chỉ giữ byte-prefix base công khai và hạ quyết định sang FRR. Validator kiểm tra cấu trúc/tham chiếu/IPv4, không sửa ASN/IP, thêm peer hay chuyển originate về đáp án. Control generator chỉ dùng cho evaluator; không đi vào model request. Không dùng reference làm base.

[Offline controls](../../results/bgp-plan-study-20261120/offline-controls.json):

| Control | FRR parser/daemon | Batfish legacy offline |
|---|---|---|
| BGP01 positive | pass | pass |
| BGP02 positive | pass | pass |
| BGP02 đảo deny/permit | pass | fail |
| BGP02 sender-allow/receiver-deny | pass | pass — thiếu phép kiểm export |

186 unit/contract tests pass; Bash syntax, Python compilation, health query và summary không nội suy vòng chưa sinh đã kiểm tra. Đây chưa là full lab calibration.

Pilot bị khóa sau calibration: hai BGP dev × B1/A1/A2 ×1repeat; tối đa6trajectory/26generation; B1 một call, agents tối đa5repair. Qwen4B digest `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`, context12288/output3072/temp0/seed539/top_k40/top_p0.9/repeat_penalty1.0, giữ cấu hình dev đã dùng. Không nâng model/context trong pilot. JSON Schema truyền qua `format` và validate lại client; grammar/API runtime chưa được chứng minh trước call đầu. Bị từ chối thì giữ environment error, không fallback sang contract khác.

Manifest local `runs/bgp-plan-study-20261120/manifest.json` khóa code/data/schema/prompt/feedback/grader/model/options. Có một manifest tiền triển khai được giữ riêng; chỉ bản cuối được dùng, chưa sinh model. Mỗi call lưu payload/preflight/raw IR/raw response/hash/config/render/evaluation/token/time. Phân biệt raw IR valid, rendered syntax valid, intent/regression/full pass. Summary cộng token thực, thiếu metric để null. Không nhập vào primary structured288/Vietnamese216, không sửa B0.

## Chạy, dừng và tiếp tục

Máy hiện tại đã có dependencies; thêm `jsonschema==4.10.3` vào repo venv, không cài system. Chưa nghiệm thu fresh-host. Script không tự tải weights/image hay đổi host route/driver/firewall.

```bash
cd /home/xuandong/4_Ai_UngDung/Doan/a1-intent-routing-agent
bash ops/run_bgp_plan_study.sh calibrate
# Chỉ khi calibration đạt; một phiên tối đa2call, không mở campaign nhiều giờ:
bash ops/run_bgp_plan_study.sh pilot
# Terminal thứ hai, yêu cầu dừng sau bước hiện tại và restore:
bash ops/run_bgp_plan_study.sh stop
bash ops/run_bgp_plan_study.sh status
# Sau mở máy, tiếp tục checkpoint, không sinh lại vòng đã lưu:
bash ops/run_bgp_plan_study.sh resume
```

Mỗi phiên có ngân sách1800giây, không bắt đầu call nếu còn dưới1100giây; call tối đa900giây, lab step/restore có timeout riêng. **Không phải hard deadline30phút**: bước đang chạy và restore có thể kéo dài phiên. Đừng bắt đầu pilot sát lúc tắt máy. Chỉ tắt khi status in `safe_to_power_off: True`. Stop không kill cứng giữa call; đợi call/tool hiện tại và restore. Nếu mất điện giữa call, runner chặn retry tự động để audit response không chắc chắn; giữ marker/run tại chỗ. Session/log/restore được ghi dưới run; lệnh không chạy lại campaign cũ.

## Nghiệm thu và điểm dừng

| Hạng mục / nguồn | Chức năng đã triển khai | Tính đúng công cụ đã kiểm chứng | Hiệu quả model đo được |
|---|---|---|---|
| Origination (chẩn đoán A, hỗ trợ proposal §4/6) |8 biến thể, capture và provenance |Source/CLI/API có evidence; runtime contrasts chờ root |Không gọi model |
| No-export (proposal §2/4, thử B) |Sender advertised + peer-bound OUT policy, grader riêng |Offline counterexample xác nhận điểm yếu legacy; full controls chờ root |Chưa đo với grader mới |
| Sinh–kiểm chứng–sửa (A1 đề; proposal §4/5) |IR/renderer/short history/stagnation/checkpoint opt-in |186 tests +4 offline control; lab còn thiếu |0call hybrid, chưa có full pass hay repair gain mới |
| Thống kê pilot (proposal §5/6, phạm vi nhỏ mới) |Round/hash/token/time và mốc null |Summary kiểm tra; chưa có dữ liệu model |1repeat không đủ kết luận tổng quát/CI |
| Sản phẩm cuối (đề; proposal §7) |Mã và launcher/report này |Fresh-host, demo/video, review bộ nộp còn thiếu |Không lấy model fail làm BLOCKED vô hạn |

Sau tối đa6trajectory/26call kết thúc, báo cả negative và coverage/disagreement. Nếu có tín hiệu tốt thì mới chuẩn bị đối chứng đủ8dev trước freeze/chọn phương pháp; không mở eval trong đợt này. Nếu không, handoff lấy đúng một reproducer/payload/feedback/version, không chuyển toàn bộ lịch sử. Bảng nghiệm thu toàn đồ án vẫn ở [acceptance](../acceptance/README.md); các kết quả18/11 giữ nguyên, không được gọi là đã sửa engine hoặc đã nâng score.
