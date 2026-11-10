# Topology dữ liệu

`triangle3.json`: R1/R2/R3 nối tam giác; H1/H2/H3 nối eth3 của router tương ứng.
Link router dùng /30 riêng, LAN dùng 192.168.1/2/3.0/24; host .10, gateway .1.
Interface là ánh xạ dự kiến cho lab riêng, chưa có deployment/Containerlab YAML.
Validator kiểm gateway là địa chỉ router kề trực tiếp và subnet link không chồng lấn.
