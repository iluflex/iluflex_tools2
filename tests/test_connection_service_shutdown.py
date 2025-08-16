import subprocess
import sys
import json
import textwrap
import os


def test_multiple_instances_shutdown(tmp_path):
    script = tmp_path / "script.py"
    script.write_text(textwrap.dedent(
        """
        import atexit, json
        from iluflex_tools.core.services import ConnectionService

        class FakeSocket:
            def __init__(self):
                self.closed = 0
            def shutdown(self, how):
                pass
            def close(self):
                self.closed += 1

        svc1 = ConnectionService()
        svc2 = ConnectionService()
        fs1 = FakeSocket(); svc1._sock = fs1; svc1.connected = True
        fs2 = FakeSocket(); svc2._sock = fs2; svc2.connected = True

        atexit._run_exitfuncs()
        print(json.dumps({"svc1": fs1.closed, "svc2": fs2.closed}))
        atexit._run_exitfuncs()
        print(json.dumps({"svc1": fs1.closed, "svc2": fs2.closed}))
        """
    ))
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=True, env=env)
    lines = [ln for ln in result.stdout.strip().splitlines() if ln.startswith('{')]
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first == {"svc1": 1, "svc2": 1}
    assert second == {"svc1": 1, "svc2": 1}
