# Development inputs — chặng 03

Đúng ba ca ban đầu: static, OSPF, path+regression. Đây là 3/8 dev;
còn thiếu 1 static, 1 OSPF, 2 eBGP/prefix, 1 path+regression để đủ 2/nhóm.
24 eval chưa được tạo. Không dùng eval để sửa prompt.

Topology tương đối trong mỗi input trỏ tới `topologies/triangle3.json`.
Oracle do người thiết kế viết độc lập, ở `data/oracles/dev/`, chỉ evaluator đọc.
Không có model payload builder; chưa có phép thử payload thực tế.
Input chỉ chứa yêu cầu công khai, không chứa oracle hoặc solution configs.

Mọi traffic check là một chiều; chiều về là check riêng. `all_paths` yêu cầu
mọi đường forwarding khả dụng khớp toàn bộ chuỗi node (không cho đường ECMP
né R2). Ping đơn thuần không chứng minh đường đi. Probe path cần kết hợp
traceroute/forwarding evidence với ánh xạ IP/interface trong topology.

OSPF yêu cầu single-area 0, cost 10 trên link router, LAN passive; oracle RIB
đòi route OSPF tới LAN xa với next hop nêu rõ. Adapter phải kiểm RIB thực và
OSPF area; không suy protocol/area từ ping hoặc chuỗi config. Chưa có adapter.
Unsupported/missing evidence phải giữ environment_error, không cho pass.

Cấu hình nền static và path+regression: `reference_configs/CASE_ID/base/`.
Model sau này chỉ nhận base, topology và input; `solution/` chỉ evaluator đọc.
Nền path+regression đã có route H3↔H2; đáp án thêm route H1↔H2.
OSPF base/reference pending; chưa dùng ca này gọi model.
