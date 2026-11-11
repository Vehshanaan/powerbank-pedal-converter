"""校验原理图网表与 design.py 期望连接是否一致。

用法：python check_netlist.py [netlist 路径]
退出码 0 = OK，1 = 不一致。
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design as D  # noqa: E402
import klib  # noqa: E402

DEFAULT = os.path.normpath(os.path.join(HERE, "..", "V1_USBC_9V", "V1_USBC_9V_netlist.net"))


def _match_paren(text, start):
    depth = 0
    for k in range(start, len(text)):
        ch = text[k]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return k
    return -1


def parse_nets(text):
    """返回 {网络名(去掉前导/): {(ref, pin)}}。"""
    m = re.search(r"^[ \t]*\(nets[ \t]*$", text, re.M)
    if not m:
        return {}
    end = _match_paren(text, text.index("(", m.start()))
    block = text[text.index("(", m.start()):end + 1]
    nets = {}
    for nm in re.finditer(r"\(net\b", block):
        sub = block[nm.start():_match_paren(block, nm.start()) + 1]
        name = re.search(r'\(name "([^"]*)"\)', sub)
        if not name:
            continue
        key = name.group(1).lstrip("/")
        nodes = {(a.group(1), a.group(2)) for a in
                 re.finditer(r'\(node\s*\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', sub)}
        nets.setdefault(key, set()).update(nodes)
    return nets


def expected_nets():
    libs = klib.Libraries()
    expected = {}
    for p in D.PARTS:
        pins = libs.pins(p["lib"])
        for key, net in p["pins"].items():
            hit = [q for q in pins if q[0] == key] or \
                  [q for q in pins if q[1] == key or q[1].replace("~", "") == key]
            if not hit:
                raise SystemExit(f"{p['ref']}: pin {key} not found")
            expected.setdefault(net, set()).add((p["ref"], hit[0][0]))
    return expected


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    text = open(path, encoding="utf-8").read()
    found = parse_nets(text)
    expected = expected_nets()
    ok = True
    for net, want in sorted(expected.items()):
        got = found.get(net, set())
        if got != want:
            ok = False
            print(f"MISMATCH {net}: missing {sorted(want - got)} extra {sorted(got - want)}")
    for name, nodes in sorted(found.items()):
        if name.startswith("unconnected-") or (name.startswith("Net-(") and name not in expected):
            ok = False
            print(f"STRAY {name}: {sorted(nodes)}")
    print(f"{'OK' if ok else 'FAILED'}: {len(expected)} nets / {len(found)} nets in netlist")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
