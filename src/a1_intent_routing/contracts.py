"""JSON contracts and offline topology checks, not FRR or intent verification."""
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from typing import Any, Literal

TASK_GROUPS = {"static", "ospf", "ebgp_prefix", "path_regression"}
Status = Literal["pass", "fail", "environment_error"]


class InputError(ValueError):
    """Invalid input, with a JSON field path."""


def require(condition: bool, path: str, message: str) -> None:
    if not condition:
        raise InputError(f"{path}: {message}")


def obj(value: Any, path: str, keys: set[str], optional: set[str] = frozenset()) -> dict:
    require(isinstance(value, dict), path, "expected object")
    require(not (keys - value.keys()), path, f"missing fields: {sorted(keys - value.keys())}")
    require(not (value.keys() - keys - optional), path,
            f"unknown fields: {sorted(value.keys() - keys - optional)}")
    return value


def string(value: Any, path: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), path, "expected nonempty string")
    return value


def array(value: Any, path: str) -> list:
    require(isinstance(value, list), path, "expected array")
    return value


def ipv4(value: Any, path: str, interface: bool = False):
    string(value, path)
    if interface:
        require("/" in value, path, "IPv4 interface must include prefix length")
    try:
        return IPv4Interface(value) if interface else IPv4Address(value)
    except ValueError as exc:
        raise InputError(f"{path}: invalid IPv4 {'interface' if interface else 'address'}: {value}") from exc


@dataclass(frozen=True)
class Interface:
    name: str
    ipv4: str


@dataclass(frozen=True)
class Node:
    name: str
    kind: Literal["router", "host"]
    interfaces: tuple[Interface, ...]
    gateway: str | None = None


@dataclass(frozen=True)
class Endpoint:
    node: str
    interface: str

    @classmethod
    def parse(cls, raw: Any, path: str) -> "Endpoint":
        raw = obj(raw, path, {"node", "interface"})
        return cls(*(string(raw[k], f"{path}.{k}") for k in ("node", "interface")))


@dataclass(frozen=True)
class Link:
    a: Endpoint
    b: Endpoint


@dataclass(frozen=True)
class Topology:
    topology_id: str
    nodes: tuple[Node, ...]
    links: tuple[Link, ...]

    @property
    def interfaces(self) -> dict[Endpoint, IPv4Interface]:
        return {Endpoint(n.name, i.name): IPv4Interface(i.ipv4)
                for n in self.nodes for i in n.interfaces}

    @classmethod
    def from_dict(cls, raw: Any) -> "Topology":
        raw = obj(raw, "$", {"topology_id", "nodes", "links"})
        topology_id = string(raw["topology_id"], "$.topology_id")
        nodes, names, ips = [], set(), set()
        for index, item in enumerate(array(raw["nodes"], "$.nodes")):
            p = f"$.nodes[{index}]"
            item = obj(item, p, {"name", "kind", "interfaces"}, {"gateway"})
            name = string(item["name"], p + ".name")
            require(name not in names, p + ".name", "duplicate node")
            names.add(name)
            require(item["kind"] in ("router", "host"), p + ".kind", "expected router or host")
            interfaces, seen = [], set()
            for j, iface in enumerate(array(item["interfaces"], p + ".interfaces")):
                q = f"{p}.interfaces[{j}]"
                iface = obj(iface, q, {"name", "ipv4"})
                iname = string(iface["name"], q + ".name")
                require(iname not in seen, q + ".name", "duplicate interface")
                seen.add(iname)
                address = ipv4(iface["ipv4"], q + ".ipv4", True)
                require(address.ip not in ips, q + ".ipv4", "duplicate address")
                require(address.network.prefixlen >= 31 or
                        address.ip not in (address.network.network_address, address.network.broadcast_address),
                        q + ".ipv4", "network/broadcast address is not a usable interface address")
                ips.add(address.ip)
                interfaces.append(Interface(iname, iface["ipv4"]))
            require(bool(interfaces), p + ".interfaces", "must not be empty")
            gateway = item.get("gateway")
            if gateway is not None:
                require(item["kind"] == "host", p + ".gateway", "gateway is host-only")
                ipv4(gateway, p + ".gateway")
            nodes.append(Node(name, item["kind"], tuple(interfaces), gateway))
        require(bool(nodes), "$.nodes", "must not be empty")
        links, used, networks = [], set(), []
        lookup = {Endpoint(n.name, i.name): IPv4Interface(i.ipv4) for n in nodes for i in n.interfaces}
        for index, item in enumerate(array(raw["links"], "$.links")):
            p = f"$.links[{index}]"
            item = obj(item, p, {"a", "b"})
            a, b = (Endpoint.parse(item[k], p + "." + k) for k in ("a", "b"))
            for key, endpoint in (("a", a), ("b", b)):
                require(endpoint in lookup, p + "." + key, "unknown node/interface")
                require(endpoint not in used, p + "." + key, "interface already linked")
            require(a.node != b.node, p, "self link is not allowed")
            require(lookup[a].network == lookup[b].network, p, "link endpoints must share the same subnet")
            net = lookup[a].network
            require(not any(net.overlaps(other) for other in networks), p, "subnet overlaps another link")
            networks.append(net)
            used.update((a, b))
            links.append(Link(a, b))
        require(bool(links), "$.links", "must not be empty")
        kinds = {n.name: n.kind for n in nodes}
        for node in nodes:
            if node.gateway is None:
                continue
            peers = [b for link in links for a, b in ((link.a, link.b), (link.b, link.a))
                     if a.node == node.name and kinds[b.node] == "router"]
            require(any(str(lookup[peer].ip) == node.gateway for peer in peers),
                    f"$.nodes.{node.name}.gateway", "gateway must be a directly linked router address")
        return cls(topology_id, tuple(nodes), tuple(links))


@dataclass(frozen=True)
class TrafficEndpoint:
    node: str
    interface: str
    ip: str

    @classmethod
    def parse(cls, raw: Any, path: str, topology: Topology) -> "TrafficEndpoint":
        raw = obj(raw, path, {"node", "interface", "ip"})
        endpoint = Endpoint(*(string(raw[k], path + "." + k) for k in ("node", "interface")))
        require(endpoint in topology.interfaces, path, "unknown node/interface")
        address = ipv4(raw["ip"], path + ".ip")
        require(address == topology.interfaces[endpoint].ip, path + ".ip", "IP must match the named interface")
        return cls(endpoint.node, endpoint.interface, raw["ip"])


@dataclass(frozen=True)
class NetworkCheck:
    source: TrafficEndpoint
    destination: TrafficEndpoint
    reachability: bool
    required_path: tuple[str, ...]
    direction: Literal["forward"]
    ecmp: Literal["all_paths", "any_path"]

    @classmethod
    def parse(cls, raw: Any, path: str, topology: Topology) -> "NetworkCheck":
        raw = obj(raw, path, {"source", "destination", "reachability", "required_path", "direction", "ecmp"})
        source = TrafficEndpoint.parse(raw["source"], path + ".source", topology)
        destination = TrafficEndpoint.parse(raw["destination"], path + ".destination", topology)
        require(type(raw["reachability"]) is bool, path + ".reachability", "expected boolean")
        require(raw["direction"] == "forward", path + ".direction", "use forward; encode reverse traffic as a separate check")
        require(raw["ecmp"] in ("all_paths", "any_path"), path + ".ecmp", "expected all_paths or any_path")
        route = array(raw["required_path"], path + ".required_path")
        names = {n.name for n in topology.nodes}
        for j, name in enumerate(route):
            string(name, f"{path}.required_path[{j}]")
            require(name in names, f"{path}.required_path[{j}]", "unknown node")
        if route:
            require(raw["reachability"], path + ".required_path", "cannot require path for unreachable traffic")
            require(len(route) >= 2 and route[0] == source.node and route[-1] == destination.node,
                    path + ".required_path", "full node path must start at source and end at destination")
            require(len(set(route)) == len(route), path + ".required_path", "path must not contain loops")
            edges = {frozenset((link.a.node, link.b.node)) for link in topology.links}
            for j, (a, b) in enumerate(zip(route, route[1:])):
                require(frozenset((a, b)) in edges, f"{path}.required_path[{j}:{j+2}]", "nodes are not adjacent")
        return cls(source, destination, raw["reachability"], tuple(route), raw["direction"], raw["ecmp"])


@dataclass(frozen=True)
class RoutingCheck:
    """Required control-plane property; not a result from a verifier."""
    node: str
    protocol: str
    prefix: str
    next_hop: str
    area: str | None = None

    @classmethod
    def parse(cls, raw: Any, path: str, topology: Topology) -> "RoutingCheck":
        raw = obj(raw, path, {"node", "protocol", "prefix", "next_hop"}, {"area"})
        require(raw["node"] in {n.name for n in topology.nodes if n.kind == "router"},
                path + ".node", "expected topology router")
        require(raw["protocol"] in ("static", "ospf"), path + ".protocol", "expected static or ospf")
        try:
            prefix = IPv4Network(raw["prefix"], strict=True)
        except (ValueError, TypeError) as exc:
            raise InputError(f"{path}.prefix: invalid IPv4 network") from exc
        require(prefix in {i.network for i in topology.interfaces.values()},
                path + ".prefix", "prefix must identify a topology subnet")
        hop = ipv4(raw["next_hop"], path + ".next_hop")
        lookup = topology.interfaces
        peers = [b for link in topology.links for a, b in ((link.a, link.b), (link.b, link.a))
                 if a.node == raw["node"]]
        require(any(lookup[b].ip == hop for b in peers), path + ".next_hop", "next hop must be directly linked")
        area = raw.get("area")
        if raw["protocol"] == "ospf":
            require(area == "0.0.0.0", path + ".area", "single-area cases require area 0.0.0.0")
        else:
            require(area is None, path + ".area", "area is OSPF-only")
        return cls(raw["node"], raw["protocol"], str(prefix), str(hop), area)


@dataclass(frozen=True)
class CaseInput:
    case_id: str
    task_group: str
    split: str
    intent: str
    topology: str
    constraints: tuple[NetworkCheck, ...]
    routing_requirements: tuple[RoutingCheck, ...] = ()

    @classmethod
    def from_dict(cls, raw: Any, topology: Topology) -> "CaseInput":
        raw = obj(raw, "$", {"case_id", "task_group", "split", "intent", "topology", "constraints"}, {"routing_requirements"})
        for key in ("case_id", "task_group", "split", "intent", "topology"):
            string(raw[key], "$." + key)
        require(raw["task_group"] in TASK_GROUPS, "$.task_group", "invalid task group")
        require(raw["split"] in ("dev", "eval"), "$.split", "expected dev or eval")
        constraints = tuple(NetworkCheck.parse(x, f"$.constraints[{i}]", topology)
                            for i, x in enumerate(array(raw["constraints"], "$.constraints")))
        require(bool(constraints), "$.constraints", "must include explicit traffic constraints")
        return cls(*(raw[k] for k in ("case_id", "task_group", "split", "intent", "topology")), constraints,
                   tuple(RoutingCheck.parse(x, f"$.routing_requirements[{i}]", topology)
                         for i, x in enumerate(array(raw.get("routing_requirements", []), "$.routing_requirements"))))


@dataclass(frozen=True)
class CaseOracle:
    case_id: str
    checks: tuple[NetworkCheck, ...]
    regression_checks: tuple[NetworkCheck, ...]
    routing_checks: tuple[RoutingCheck, ...] = ()

    @classmethod
    def from_dict(cls, raw: Any, topology: Topology) -> "CaseOracle":
        raw = obj(raw, "$", {"case_id", "checks", "regression_checks"}, {"routing_checks"})
        case_id = string(raw["case_id"], "$.case_id")
        groups = [tuple(NetworkCheck.parse(x, f"$.{key}[{i}]", topology)
                        for i, x in enumerate(array(raw[key], "$." + key)))
                  for key in ("checks", "regression_checks")]
        require(bool(groups[0]), "$.checks", "must not be empty")
        return cls(case_id, *groups,
                   tuple(RoutingCheck.parse(x, f"$.routing_checks[{i}]", topology)
                         for i, x in enumerate(array(raw.get("routing_checks", []), "$.routing_checks"))))


@dataclass(frozen=True)
class StructuredError:
    device: str | None
    property: str
    expected: Any
    observed: Any


@dataclass
class ToolResult:
    tool: str
    status: Status
    coverage: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    errors: list[StructuredError] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    elapsed_seconds: float | None = None

    def __post_init__(self):
        require(self.status in ("pass", "fail", "environment_error"), "ToolResult.status", "invalid status")
        require(self.status != "pass" or (bool(self.artifacts) and bool(self.coverage)
                and not self.errors and not self.unsupported), "ToolResult.status",
                "pass requires evidence, coverage, and no errors/unsupported required checks")


@dataclass
class RunRecord:
    case_id: str
    method: Literal["one_pass", "pass_fail", "structured_error"]
    model: str | None = None
    settings: dict[str, Any] = field(default_factory=dict)
    trial_index: int = 0
    attempt_index: int = 0
    repair_count: int = 0
    status: Status | None = None
    syntax_checks: list[ToolResult] = field(default_factory=list)
    intent_checks: list[ToolResult] = field(default_factory=list)
    regression_checks: list[ToolResult] = field(default_factory=list)
    errors: list[StructuredError] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None
    llm_seconds: float | None = None
    tool_seconds: float | None = None
    total_seconds: float | None = None

    def __post_init__(self):
        require(self.method in ("one_pass", "pass_fail", "structured_error"), "RunRecord.method", "invalid method")
        require(type(self.attempt_index) is int and type(self.repair_count) is int
                and 0 <= self.attempt_index == self.repair_count <= 5,
                "RunRecord.repair_count", "zero-based attempt_index must equal repair_count in 0..5")
        require(self.method != "one_pass" or self.repair_count == 0, "RunRecord.method", "one_pass cannot repair")
        require(type(self.trial_index) is int and 0 <= self.trial_index <= 2, "RunRecord.trial_index", "expected 0..2")
        require(self.status in (None, "pass", "fail", "environment_error"), "RunRecord.status", "invalid status")
        checks = self.syntax_checks + self.intent_checks + self.regression_checks
        require(not any(c.status == "environment_error" for c in checks) or self.status in (None, "environment_error"),
                "RunRecord.status", "environment errors must be retained")
        if self.status == "pass":
            require(bool(self.syntax_checks) and bool(self.intent_checks) and bool(self.regression_checks)
                    and all(c.status == "pass" for c in checks) and not self.errors,
                    "RunRecord.status", "pass requires evidence for syntax, intent and regression checks")
        for key in ("input_tokens", "output_tokens", "llm_seconds", "tool_seconds", "total_seconds"):
            value = getattr(self, key)
            require(value is None or (type(value) in (int, float) and value >= 0), "RunRecord." + key,
                    "must be null or nonnegative measured value")
