# Đợt BGP giới hạn: origination, export và BGP plan — 2026-11-20

## Kết luận hiện tại — đóng pilot 2026-11-21

**Pilot đã hoàn tất6/6trajectory,6initial call,0repair.** Cả6 IR/schema và rendered FRR syntax đều pass; lab6/6fail; Batfish6/6origination coverageerror; verdict cuối0pass/0fail/6environment_error. Restorepass, không còn runner. Renderer và sender-export grader đã có10control đúng kỳ vọng, nhưng chưa có bằng chứng hybrid cải thiện intent success hoặc hiệu quả tự sửa. Không chạy lại cùng pilot để chọn đáp án đẹp; không mở thêm phiên bản prompt trong đợt này.

Kết quả này đóng đợt thử nghiệm, **không đồng nghĩa đồ án sẵn sàng nộp**. Chức năng đã triển khai, tính đúng của tool trên controls và hiệu quả model là ba cột riêng. Primary structured288/Vietnamese216/B0 không đổi.

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
| Origination (chẩn đoán A, hỗ trợ proposal §4/6) |8 biến thể, capture và provenance |Source/CLI/API có evidence; 8runtime contrasts đã có RIB/advertisement; parser import-check chưa hỗ trợ |Không gọi model |
| No-export (proposal §2/4, thử B) |Sender advertised + peer-bound OUT policy, grader riêng |Offline counterexample xác nhận điểm yếu legacy; 10/10control calibration đúng kỳ vọng |Chưa đo với grader mới |
| Sinh–kiểm chứng–sửa (A1 đề; proposal §4/5) |IR/renderer/short history/stagnation/checkpoint opt-in |186 tests +4 offline control; lab controls đã đạt |0call hybrid tại mốc đóng calibration, chưa có full pass hay repair gain mới |
| Thống kê pilot (proposal §5/6, phạm vi nhỏ mới) |Round/hash/token/time và mốc null |Summary kiểm tra; chưa có dữ liệu model |1repeat không đủ kết luận tổng quát/CI |
| Sản phẩm cuối (đề; proposal §7) |Mã và launcher/report này |Fresh-host, demo/video, review bộ nộp còn thiếu |Không lấy model fail làm BLOCKED vô hạn |

Sau tối đa6trajectory/26call kết thúc, báo cả negative và coverage/disagreement. Nếu có tín hiệu tốt thì mới chuẩn bị đối chứng đủ8dev trước freeze/chọn phương pháp; không mở eval trong đợt này. Nếu không, handoff lấy đúng một reproducer/payload/feedback/version, không chuyển toàn bộ lịch sử. Bảng nghiệm thu toàn đồ án vẫn ở [acceptance](../acceptance/README.md); các kết quả18/11 giữ nguyên, không được gọi là đã sửa engine hoặc đã nâng score.

## Cập nhật sau calibration root và revision2

Lần1 đã restore pass, model calls0. Positive BGP01/BGP02 **full pass với grader mới**; wrong-ASN, self-neighbor và missing-peer fail đúng. Negative missing-originate ban đầu nhắm R5 vốn không originate: cấu hình không thay đổi và pass. Đây là lỗi fixture của đợt này; không sửa verdict hoặc coi thành fail. Control thay thế xóa originate H3 ở R6, lưu output mới.

Connected diagnostic gặp `ip link add lo` trong syntax namespace đã tồn tại; sửa syntax checker chỉ bỏ tạo dummy cho interface `lo`, vẫn thêm địa chỉ và kiểm tra daemon. Static diagnostic bị BGP-only scope chặn; revision2 chỉ cho static backing trong diagnostic này, không mở scope cho candidate pilot. Connected sau sửa qua syntax; assertion địa chỉ loopback ghi nhận thêm127.0.0.1/8 nên aggregate lab fail vẫn được giữ. Điều đó không xóa được evidence connected/main-RIB thực tế, và không được gọi full pass.

Run bổ sung `runs/bgp-plan-study-20261120-02` giữ nguyên tám variant cấu hình, chỉ chấm lại connected/static vì execution trước không hợp lệ. Tái dùng5control đã đạt và4diagnostic absent/learned; hash3674file evidence, config và verdict được kiểm tra trước chạy. Manifest/output cũ giữ tại chỗ. `ops/bgp_plan_continue.py` ghi lý do thay đổi và retires control vô hiệu; renderer/schema/model/options/feedback không đổi. Launcher trong báo cáo hiện trỏ revision2. Không chạy lại campaign primary.

[Bằng chứng RIB/advertisement đã trích](../../results/bgp-plan-study-20261120/origination-observed.json): ở absent-on, FRR có entry local không valid, không quảng bá; absent-off entry valid/best và quảng bá tới ba peer, main RIB R2 vẫn không có prefix. Batfish cả hai đều trả BGP BEST với next-hop discard và main RIB rỗng; parser báo không nhận cú pháp import-check. Learned-BGP/on có route học thực sự trong main RIB FRR nhưng BF chọn local discard và không có route main ở R2. Đây là quan sát runtime cụ thể, phù hợp đầu mối source unconditional network; chưa phải chứng minh mọi hành vi origination của binary. Giữ guardv5 và reproducer, không sửa snapshot để giả đồng thuận.

Đã commit/push code `caf2dbf` và báo cáo đầu `2725b74` lên origin/main; revision2 sẽ có commit riêng sau checks. Bảy thay đổi staged ban đầu vẫn giữ nguyên blob. Các chỉnh sửa README/progress/troubleshooting/acceptance trên tài liệu làm việc cũ giữ local để tránh gom công việc khác vào commit này.

### Đóng calibration revision2

[Calibration summary](../../results/bgp-plan-study-20261120/calibration.json): **10/10control đúng kỳ vọng**, hai positive full pass và tám negative fail, đã restore pass. Có5control tái dùng hash-verified,5control mới; control no-op cũ không nằm trong mười control hợp lệ. Masked sender-allow/receiver-deny: legacy full pass, grader mới fail; R4 quảng bá192.168.2.0/24 tới10.6.3.1 và10.6.4.2, bound export policy OUT trả PERMIT. Đây là bằng chứng tính đúng phép kiểm mới, không phải hiệu quả model.

| Nguồn / phần | Đã triển khai chức năng | Đã kiểm chứng công cụ | Hiệu quả model đo được |
|---|---|---|---|
| A origination / proposal§4/6 |8biến thể và captures |FRR runtime và BF RIB có tương phản; giữ parser/coverage/loopback assertion failures |Không áp dụng model |
| B no-export / proposal§2/4 |Sender advertised + peer-bound OUT |Positive/negative và masked-import control đã qua calibration |Chưa đo model bằng grader mới |
| C/D/E hybrid / mở rộng opt-in |IR/renderer/history/stagnation/session |186test +2test summary,9test mới chạy trong gói commit riêng;10control đúng |0call ở thời điểm đóng calibration; không tuyên bố repair gain |
| Bàn giao cuối / đề và PDF§7 |Code/launcher/report/checkpoint |Fresh-host/demo-video/review bộ nộp chưa nghiệm thu |Pilot đủ6trajectory còn phải hoàn tất |

Với cửa sổ mở máy còn ngắn, dùng một call rồi restore:

```bash
sudo runs/batfish-venv/bin/python ops/bgp_plan_study.py resume --pilot --seconds 1200 --calls 1
```

Đây chỉ là phần đầu pilot. Toàn bộ pilot có trần26call; nếu mỗi call dùng hết900giây thì riêng generation đã6,5giờ. Không tự chạy trọn số đó trong phiên mở máy này. Các phiên sau dùng launcher resume, vẫn trần2call/phiên và checkpoint chung, không sinh lại phần đã lưu.

### Pilot call đầu đã hoàn tất; dừng phiên ở checkpoint

[Summary](../../results/bgp-plan-study-20261120/pilot-first-call.json): BGP01–B1 initial,1generation,0repair. IR schema **pass**, rendered FRR syntax **pass**, protocolscope **pass**, lab **fail**, Batfish **environment_error** (origination coveragev5), export scope **pass/not-applicable** vì BGP01 không có deny-export intent. Verdict cuối **environment_error**,0disagreement được ghi. Không lấy cú pháp render đúng làm raw-FRR model syntax accuracy.

Model chọn thêm originate H2 tại R2 và có13/13peer thiếu import hoặc export policy; FRR ghi Established nhưng peerState Policy và không đạt convergence. Không sửa các quyết định đó trong renderer. Coverageerror không biến thành lời nhắc để sinh lại B1. Không gọi kết quả này là bằng chứng renderer cải thiện intent success hoặc A2 tự sửa tốt hơn.

Chi phí duy nhất đã đo:3129input/1923outputtoken; API208.424giây, HTTP208.425giây, tool99.776giây. Tổng hai thành phần đo được308.201giây; end-to-end bao gồm overhead/preflight/restore chưa đo riêng để null, không giả bằng tổng đó. Context thực12288 đã xác minh. Restorepass, không còn runner của phiên. Còn5trajectory chưa sinh; đối tượng pending0round trong state không phải một lượt đã quan sát.

Minimal handoff của quan sát này: `runs/bgp-plan-study-20261120-02/pilot/dev_ebgp_prefix_01--B1/round-0/` chứa payload,preflight,raw-response,ir,configs,evaluation,record; summary Git lưu hash. B1 không có feedback gửi model. Expected: toàn bộ intent/regression qua syntax/BF/lab. Observed: schema/syntax qua nhưng model chọn mạng sai và chạm vùng coverage. A1/A2 chưa chạy nên **không có feedback/repair mới để bàn giao hoặc kết luận**. Không cần lặp lại10control hay8variant đã đóng.

Sau mở máy: `bash ops/run_bgp_plan_study.sh resume` tiếp tục A1 của BGP01, không sinh lại B1 đã lưu. Vẫn tối đa2call/phiên. Không chạy cả25call tối đa còn lại một cách không giới hạn. Các bước bàn giao còn thiếu: hoàn tất6trajectory pilot trước kết luận hiệu quả; đối chứng8dev nếu có tín hiệu tốt; fresh-host reproduction, demo/video và review bộ nộp. Model fail/coverage không làm toàn đồ án BLOCKED vĩnh viễn; primary và score cũ không thay đổi.

## 2026-11-21 — BGP01 B1/A1/A2 đã có kết quả, không retry

[Summary/hash](../../results/bgp-plan-study-20261120/pilot-progress-20261121.json):3/6trajectory đã quan sát, cả ba BGP01 đều environment_error ở initial; raw IR/syntax/scope pass, lab fail và Batfish origination coverageerror. Messages/options, semantic candidate và toàn bộ config hash giống nhau. A1/A2 chưa gửi feedback hoặc thực hiện repair vì quy tắc đã khóa dừng ở coverageerror. Không dùng kết quả này để kết luận structured feedback kém; phép so sánh hiệu quả sửa chưa được quan sát.

Đây không phải lỗi Ollama/Batfish bị sập sau mở máy. Model tiếp tục chọn nonconnected originate tại R2, thiếu policy/peer và không đáp ứng intent trên lab; coveragev5 giữ trạng thái chưa mô hình hóa thay vì ép một verdict thuận lợi. Tổng3call:9387input/5769outputtoken, API552.538giây; có restorepass. Giữ cả ba kết quả, không tái sinh cùng payload để tìm đáp án khác.

`bash ops/finish_bgp_plan_pilot.sh` hoàn tất đúng các trajectory BGP02 chưa sinh, không mở lại BGP01. Wrapper không đổi model/schema/renderer/grader/feedback/stopping policy: mỗi child vẫn trần2call/1800giây, tổngtrần26call. Có log từng session và STOP giữ nguyên giữa các session; không tiến triển/restorefail/inflight không chắc chắn thì dừng. Chỉ việc khởi động lại launcher mới xóa STOP theo hành động resume rõ ràng. Launcher có thể chạy nhiều phiên, thời gian tùy số vòng thực sự sinh; vẫn dùng lệnh stop/status hiện có khi cần ngắt.

Trong phiên công cụ21/11, `sudo -n true` yêu cầu mật khẩu nên không tự thực hiện lab root; đã chuẩn bị launcher để người dùng chạy Terminal. Các checks offline và tổng hợp vẫn thực hiện độc lập. Phải hoàn tất3trajectory BGP02 còn lại trước khi đóng pilot hoặc thiết kế phiên bản mới; không âm thầm đổi chính sách để làm A1/A2 sửa trên cùng run đã freeze.

## Kết thúc pilot — bằng chứng và handoff tối thiểu

[Summary cuối, hash và chi phí từng trajectory](../../results/bgp-plan-study-20261120/pilot-final.json). Mẫu số2ca dev ×3phương pháp ×1repeat =6trajectory; tổng6generation, không dùng hết trần26vì cả6 dừng ởcoverage. Raw IR6/6valid; rendered syntax6/6valid; lab0/6pass; full0/6pass; final6environment_error. Hiệu quả sửa **unavailable**, không phải0%: số quỹ đạo tới bước feedback/repair là0. Một repeat không đủ để kết luận tổng quát; không bootstrap hoặc nhập vào score primary.

BGP01 ba initial request/options và candidate giống nhau. BGP02 request/options vẫn giống giữa ba mode, nhưng B1 khác A1/A2 ở prefix trong rules p3/p5/p6/p7; A1 và A2 có semantic candidate giống nhau. Đây là biến thiên initial output quan sát được, **không phải hiệu quả feedback**: chưa có feedback gửi model ở cả sáu lượt. Không đổi seed/temperature và không chọn output thuận lợi hơn.

BGP02 cả14peer thiếu export attachment, R2 model originate thêm192.168.3.0/24 không nối trực tiếp. FRR default deny giải thích việc không quảng bá H2, vì vậy export assertion có thểpass trong khi kết nối cần giữ vẫnfail. Không coi export riêngpass là đáp ứng toàn intent; reachability/prefix/peering vẫn được giữ. BGP01 có13peer entries và policy thiếu, cùng nonconnected originateH2 tạiR2. Renderer giữ nguyên các quyết định này.

Ba điểm kết luận:

1. Chức năng: IR/schema/renderer, feedback/history/stopping, checkpoint và restore đã triển khai. Raw-FRR mặc định không đổi.
2. Tool: renderer có positive/negative thực; sender-allow/receiver-deny bị grader mới bắt; giới hạn origination BF có8variant/evidence và guardv5. Không tuyên bố engine đã sửa.
3. Model: chỉ chứng minh initial IR/syntax hợp lệ; chưa có fullpass, fail→feedback→repair→fullpass hoặc cải thiện intent/regression. Controller đã khóa dừng trêncoverage nên pilot không nhận diện được tác động của feedback.

**Handoff ngắn cho công cụ khác (không cần cả repo lịch sử):**

- Đọc `schemas/bgp-plan-v1.json`, `prompts/bgp-plan-v1.txt`, `src/a1_intent_routing/bgp_plan.py`, `bgp_plan_feedback.py`, `bgp_origin_coverage.py`, `ops/bgp_plan_study.py`; pins/versions/hash trong manifest và summary cuối.
- Model4B digest/options không đổi. Input public BGP02 ở `data/benchmark/dev/dev_ebgp_prefix_02/public.json`, topology/base đi kèm; không gửi oracle/reference cho model.
- Candidate tối thiểu: `runs/bgp-plan-study-20261120-02/pilot/dev_ebgp_prefix_02--B1/round-0/` có payload/raw-response/IR/rendered config/evaluation. Expected: giữ reachability và no-exportH2 đồng thời. Observed: syntaxpass, exportpass do defaultdeny, labfail, BFcoverageerror do networkR2. Feedback/repair mới không tồn tại; không bịa payload feedback để gọi là evidence đã chạy.
- Engine reproducer: absent-on/off và learned-bgp-on trong `runs/bgp-plan-study-20261120/origination/`, BF/lab captures được trích ở `origination-observed.json`. Cần giữ rõ valid/local/learned route và advertised-prefix, không chỉ membership trong BGP RIB.
- Đã đóng10control và8variant; không yêu cầu chạy lại. Các hướng raw-FRRv1/v4/v9/v10, context/literal/compiler và hybridplanv1 đã có hồ sơ âm/giới hạn; không tiếp tục nối chỉ dẫn FRR để cứu cùngrun.
- Hai ý tưởng cần thiết kế/phê duyệt như **phương pháp phiên bản mới**, chưa triển khai/chưa chứng minh: validation quyết định bằng public topology và semantics FRR để bắt các vi phạm hỗ trợ được trước coverage gate (không tự điền đáp án; không mặc định nonconnected origin là sai); hoặc controller cho sửa lỗi lab đã chứng minh ngay cả khi còn coverage chưa hỗ trợ, vẫn giữ finalenvironment_error cho tới đủ kiểm tra. Phải chốt quy tắc trước pilot khác, giữgrader/oracle/primary cũ; không sửa sáu verdict này.

Không mở rộng8dev/eval để chọn phương pháp trong đợt này vì chưa có tín hiệu cải thiện full intent. Việc còn thiếu của bộ nộp: đối chiếu acceptance toàn dự án, fresh-host reproduction, review báo cáo/slide/demo-video. Kết quả model âm không phải lý do BLOCKED toàn đồ án vĩnh viễn; còn quyết định phương pháp tiếp theo cần một thiết kế có thể kiểm chứng riêng.
