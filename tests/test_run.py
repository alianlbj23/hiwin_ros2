"""Host-side tests for the controller discovery helpers in run.py (no Docker, no ROS needed).

    python3 -m pytest tests/
"""
import ipaddress
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run  # noqa: E402

WSL_IP_ADDR = """\
1: lo    inet 127.0.0.1/8 scope host lo\\       valid_lft forever preferred_lft forever
1: lo    inet 10.255.255.254/32 brd 10.255.255.254 scope global lo\\       valid_lft forever preferred_lft forever
2: eth0    inet 172.21.152.30/20 brd 172.21.159.255 scope global eth0\\       valid_lft forever preferred_lft forever
3: tailscale0    inet 100.116.25.34/32 scope global tailscale0\\       valid_lft forever preferred_lft forever
4: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0\\       valid_lft forever preferred_lft forever
5: enp3s0    inet 192.168.0.5/24 brd 192.168.0.255 scope global enp3s0\\       valid_lft forever preferred_lft forever
"""


@pytest.fixture
def listener():
    """A TCP server bound to 127.0.0.1 on a free port."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    yield srv.getsockname()[1]
    srv.close()


def test_host_networks_keeps_lan_interfaces_only():
    nets = run.host_networks(WSL_IP_ADDR)
    assert nets == [
        ("eth0", ipaddress.ip_network("172.21.144.0/20")),
        ("enp3s0", ipaddress.ip_network("192.168.0.0/24")),
    ]


def test_host_networks_ignores_garbage_lines():
    assert run.host_networks("garbage\n7: eth1    inet not-an-ip scope global eth1\n") == []
    assert run.host_networks("") == []


def test_tcp_port_open_true_for_listener_false_after_close(listener):
    assert run.tcp_port_open("127.0.0.1", listener, timeout=1.0) is True


def test_tcp_port_open_false_for_closed_port():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    srv.close()  # port is free again -> connection refused
    assert run.tcp_port_open("127.0.0.1", port, timeout=1.0) is False


def test_scan_network_returns_only_answering_hosts(listener):
    # 127.0.0.0/30 -> hosts 127.0.0.1 and 127.0.0.2; the server is bound to 127.0.0.1 only.
    found = run.scan_network(ipaddress.ip_network("127.0.0.0/30"), listener)
    assert found == ["127.0.0.1"]


def test_find_candidates_marks_saved_ip(monkeypatch, listener):
    monkeypatch.setattr(run, "neighbour_ips", lambda: [])
    monkeypatch.setattr(run, "host_networks", lambda *a, **k: [])
    monkeypatch.setattr(run, "HIWIN_COMMAND_PORT", listener)
    cands = run.find_candidates({"ROBOT_IP": "127.0.0.1"})
    assert list(cands) == ["127.0.0.1"]
    assert "saved in .env" in cands["127.0.0.1"] and "answers" in cands["127.0.0.1"]


def test_find_candidates_without_saved_ip_or_hosts(monkeypatch):
    monkeypatch.setattr(run, "neighbour_ips", lambda: [])
    monkeypatch.setattr(run, "host_networks", lambda *a, **k: [])
    assert run.find_candidates({"ROBOT_IP": ""}) == {}


def test_default_gateways_parses_route_output():
    out = "default via 172.21.144.1 dev eth0 proto kernel\ndefault via 192.168.0.254 dev enp3s0 metric 100\n"
    assert run.default_gateways(out) == {"172.21.144.1", "192.168.0.254"}
    assert run.default_gateways("") == set()
    assert run.default_gateways("default dev ppp0 scope link\n") == set()


def test_find_candidates_flags_gateway(monkeypatch, listener):
    monkeypatch.setattr(run, "neighbour_ips", lambda: ["127.0.0.1"])
    monkeypatch.setattr(run, "host_networks", lambda *a, **k: [])
    monkeypatch.setattr(run, "default_gateways", lambda *a, **k: {"127.0.0.1"})
    monkeypatch.setattr(run, "HIWIN_COMMAND_PORT", listener)
    cands = run.find_candidates({"ROBOT_IP": ""})
    assert "gateway" in cands["127.0.0.1"]


def test_valid_ip():
    assert run.valid_ip("192.168.0.1")
    assert not run.valid_ip("192.168.0.")
    assert not run.valid_ip("robot")
