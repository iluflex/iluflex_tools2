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

