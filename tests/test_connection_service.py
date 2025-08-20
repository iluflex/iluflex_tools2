import importlib.util
from pathlib import Path


def _load_connection_service():
    services_path = Path(__file__).resolve().parents[1] / "iluflex_tools" / "core" / "services.py"
    spec = importlib.util.spec_from_file_location("_services", services_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ConnectionService


ConnectionService = _load_connection_service()


def test_listener_can_remove_itself_during_emit():
    cs = ConnectionService()
    events = []

    def listener(ev):
        events.append(ev["type"])
        cs.remove_listener(listener)

    cs.add_listener(listener)
    cs._emit({"type": "first"})
    # second emit should not trigger listener again
    cs._emit({"type": "second"})

    assert events == ["first"]


def test_listener_can_remove_other_during_emit():
    cs = ConnectionService()
    calls = []

    def l1(ev):
        calls.append("l1")
        cs.remove_listener(l2)

    def l2(ev):
        calls.append("l2")

    cs.add_listener(l1)
    cs.add_listener(l2)

    cs._emit({"type": "event"})
    # l2 should be removed for subsequent emits but still called once
    cs._emit({"type": "event2"})

    assert calls == ["l1", "l2", "l1"]


def test_recv_loop_parses_ascii_and_binary_messages():
    cs = ConnectionService()
    events = []

    def listener(ev):
        events.append(ev)

    cs.add_listener(listener)

    import socket, threading, time

    s1, s2 = socket.socketpair()
    cs._sock = s1
    cs.connected = True
    t = threading.Thread(target=cs._recv_loop, daemon=True)
    t.start()

    s2.sendall(b"HEL")
    s2.sendall(b"LO\rWOR")
    s2.sendall(b"LD\r")
    # binary message split across sends: A5 <opcode=0x01> <len=0x02> 'AB' <checksum=0xCD>
    s2.sendall(b"\xA5\x01\x02A")
    s2.sendall(b"B\xCD")
    time.sleep(0.1)
    s2.shutdown(socket.SHUT_RDWR)
    s2.close()
    t.join(timeout=1)

    rx_events = [ev["raw"] for ev in events if ev["type"] == "rx"]
    assert rx_events == [b"HELLO\r", b"WORLD\r", b"\xA5\x01\x02AB\xCD"]

