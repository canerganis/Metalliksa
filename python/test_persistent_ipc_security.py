"""Security tests for python/persistent_ipc_service.py (loopback IPC hardening).

Covers the request guards as pure functions (script containment, Host/Origin/auth/
Content-Type), the HTTP handler in-thread against a stub registry, the UNIX socket
(POSIX only) and a real subprocess integration run of the service with a token.

Run from python/: ``python -B -m unittest test_persistent_ipc_security``
"""

import email.message
import http.client
import io
import json
import os
import re
import secrets
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import persistent_ipc_service as ipc  # noqa: E402  (builds the global registry + pool)

TOKEN = secrets.token_hex(32)


def tearDownModule():
    ipc.registry.shutdown()


def _headers(pairs):
    msg = email.message.Message()
    for key, value in pairs:
        msg[key] = value
    return msg


def _status(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except ipc.IPCRequestRejected as rejected:
        return rejected.status, rejected.code
    return None


class ResolveScriptPathTest(unittest.TestCase):
    def test_accepts_route_forms_for_allowlisted_scripts(self):
        expected = os.path.realpath(HERE / "pourbaix_solver.py")
        for ref in ("python/pourbaix_solver.py", "pourbaix_solver.py", "  python/pourbaix_solver.py "):
            self.assertTrue(ipc._same_dir(ipc.resolve_script_path(str(HERE), ref), expected), ref)

    def test_traversal_absolute_drive_unc_backslash_variants_are_400(self):
        bad = [
            "python/../../outside/pwn.py", "python/../pourbaix_solver.py", "../pourbaix_solver.py",
            "python/../python/pourbaix_solver.py", "./pourbaix_solver.py", "python/./pourbaix_solver.py",
            "..", "python/..", "python/", "python/.py", "/etc/passwd", "/python/pourbaix_solver.py",
            "C:/Windows/win.ini", "C:pourbaix_solver.py", "c:\\x.py", "//server/share/x.py",
            "\\\\server\\share\\x.py", "python\\..\\..\\x.py", "python\\pourbaix_solver.py",
            "python/sub/pourbaix_solver.py", "tools/pourbaix_solver.py", "pourbaix_solver.py.",
            "pourbaix_solver.py::$DATA", "pourbaix_solver.py\x00.txt", "pourbaix_solver", "POURBA~1.PY",
            "python/pourbaix_solver.pyc", "%2e%2e/pourbaix_solver.py", "a" * 300 + ".py",
        ]
        for ref in bad:
            self.assertEqual(_status(ipc.resolve_script_path, str(HERE), ref)[0], 400, ref)

    def test_non_string_or_empty_is_400(self):
        for ref in (None, "", "   ", 7, ["python/pourbaix_solver.py"], {"x": 1}):
            self.assertEqual(_status(ipc.resolve_script_path, str(HERE), ref),
                             (400, "MISSING_SCRIPT"), ref)

    def test_existing_but_unlisted_files_are_403(self):
        for ref in ("python/persistent_ipc_service.py", "python/module_registry.py",
                    "python/test_persistent_ipc_security.py", "python/os.py",
                    "python/Pourbaix_Solver.py", "PYTHON_SOLVER.py"):
            self.assertEqual(_status(ipc.resolve_script_path, str(HERE), ref),
                             (403, "SCRIPT_NOT_ALLOWED"), ref)

    def test_allowlisted_but_missing_is_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(_status(ipc.resolve_script_path, tmp, "python/ghost.py", allowed={"ghost"}),
                             (404, "SCRIPT_NOT_FOUND"))

    def test_symlink_escape_is_403_and_symlinked_script_dir_is_fine(self):
        with tempfile.TemporaryDirectory() as tmp:
            scripts = Path(tmp) / "scripts"
            outside = Path(tmp) / "outside"
            scripts.mkdir()
            outside.mkdir()
            (outside / "evil.py").write_text("print('pwned')\n", encoding="utf-8")
            (scripts / "good.py").write_text("print('ok')\n", encoding="utf-8")
            try:
                os.symlink(outside / "evil.py", scripts / "evil.py")
                os.symlink(scripts, Path(tmp) / "linked_scripts", target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            self.assertEqual(
                _status(ipc.resolve_script_path, str(scripts), "python/evil.py", allowed={"evil", "good"}),
                (403, "SCRIPT_OUTSIDE_SCRIPT_DIR"))
            resolved = ipc.resolve_script_path(str(Path(tmp) / "linked_scripts"), "good.py", allowed={"good"})
            self.assertTrue(ipc._same_dir(resolved, os.path.realpath(scripts / "good.py")))

    def test_link_escape_branch_with_simulated_realpath(self):
        # Same branch as the symlink test, runnable without symlink privileges (Windows).
        real = os.path.realpath
        outside = os.path.join(tempfile.gettempdir(), "elsewhere", "pourbaix_solver.py")

        def fake_realpath(p, *a, **k):
            return outside if os.path.basename(str(p)) == "pourbaix_solver.py" else real(p, *a, **k)

        with mock.patch.object(ipc.os.path, "realpath", side_effect=fake_realpath):
            self.assertEqual(_status(ipc.resolve_script_path, str(HERE), "python/pourbaix_solver.py"),
                             (403, "SCRIPT_OUTSIDE_SCRIPT_DIR"))

    def test_execute_script_returns_rejection_without_running(self):
        reg = object.__new__(ipc.ConcurrentModuleRegistry)
        reg.script_dir = str(HERE)
        reg.pool = mock.Mock()
        res = reg.execute_script("python/../../outside/pwn.py", {}, [], 1000)
        self.assertEqual((res["exitCode"], res["status"], res["code"]), (1, 400, "INVALID_SCRIPT_PATH"))
        res = reg.execute_script("python/persistent_ipc_service.py", {}, [], 1000)
        self.assertEqual((res["status"], res["code"]), (403, "SCRIPT_NOT_ALLOWED"))
        reg.pool.submit.assert_not_called()


class AllowlistTest(unittest.TestCase):
    @staticmethod
    def _route_scripts():
        found = set()
        for ts in sorted((REPO / "routes").glob("*.ts")):
            text = ts.read_text(encoding="utf-8")
            for match in re.finditer(r"(?:handlePythonDispatch|runPythonScript)\(\s*\"python/([A-Za-z0-9_]+)\.py\"", text):
                found.add(match.group(1))
        return found

    def test_allowlist_equals_route_dispatched_scripts(self):
        found = self._route_scripts()
        # The scan must see the real route table (15 scripts at the time of writing), so an
        # empty or partial match can never make the equality below pass vacuously.
        self.assertGreaterEqual(len(found), 15, found)
        self.assertEqual(found - ipc.ALLOWED_SCRIPT_NAMES, set(), "route script missing from allowlist")
        self.assertEqual(ipc.ALLOWED_SCRIPT_NAMES - found, set(), "stale allowlist entry (no route uses it)")
        for name in ipc.ALLOWED_SCRIPT_NAMES:
            self.assertTrue((HERE / f"{name}.py").is_file(), name)
            ipc.resolve_script_path(str(HERE), f"python/{name}.py")

    def test_warm_only_and_service_modules_are_not_executable(self):
        self.assertNotIn("persistent_ipc_service", ipc.ALLOWED_SCRIPT_NAMES)
        for name in set(ipc.WARM_MODULE_NAMES) - ipc.ALLOWED_SCRIPT_NAMES:
            self.assertEqual(_status(ipc.resolve_script_path, str(HERE), f"python/{name}.py"),
                             (403, "SCRIPT_NOT_ALLOWED"), name)


class HeaderCheckTest(unittest.TestCase):
    HOSTS = ipc.allowed_host_headers("127.0.0.1", 5055)

    def _check(self, pairs, require_json=True, token=TOKEN):
        return _status(ipc.check_http_headers, _headers(pairs), token=token,
                       allowed_hosts=self.HOSTS, require_json=require_json)

    def _ok(self, **override):
        base = {"Host": "127.0.0.1:5055", "Authorization": f"Bearer {TOKEN}",
                "Content-Type": "application/json"}
        base.update(override)
        return [(k, v) for k, v in base.items() if v is not None]

    def test_legit_request_passes(self):
        self.assertIsNone(self._check(self._ok()))
        self.assertIsNone(self._check(self._ok(Host="localhost:5055")))
        self.assertIsNone(self._check(self._ok(Host="LOCALHOST:5055")))
        self.assertIsNone(self._check(self._ok(**{"Content-Type": "Application/JSON; charset=utf-8"})))
        self.assertIsNone(self._check(self._ok(**{"Content-Type": None}), require_json=False))

    def test_host_header_rebinding_is_403(self):
        for host in (None, "evil.example:5055", "evil.example", "127.0.0.1", "127.0.0.1:5056",
                     "127.0.0.1.nip.io:5055", "localhost", "0.0.0.0:5055", ""):
            self.assertEqual(self._check(self._ok(Host=host)), (403, "HOST_NOT_ALLOWED"), host)
        dup = self._ok() + [("Host", "evil.example:5055")]
        self.assertEqual(self._check(dup), (403, "HOST_NOT_ALLOWED"))

    def test_any_origin_is_403(self):
        for origin in ("https://evil.example", "null", "http://127.0.0.1:5055", "http://localhost:3000"):
            self.assertEqual(self._check(self._ok(Origin=origin)), (403, "ORIGIN_NOT_ALLOWED"), origin)

    def test_missing_or_wrong_token_is_401(self):
        for auth in (None, "", "Bearer", f"Basic {TOKEN}", f"Bearer {TOKEN}x", f"Bearer {TOKEN[:-1]}",
                     "Bearer " + "0" * 64, TOKEN, f"Bearer  {TOKEN.upper()}"):
            self.assertEqual(self._check(self._ok(Authorization=auth)), (401, "UNAUTHORIZED"), auth)
        dup = self._ok() + [("Authorization", "Bearer other")]
        self.assertEqual(self._check(dup), (401, "UNAUTHORIZED"))

    def test_unconfigured_token_fails_closed(self):
        self.assertEqual(self._check(self._ok(), token=None), (401, "UNAUTHORIZED"))
        self.assertEqual(self._check(self._ok(Authorization="Bearer "), token=""), (401, "UNAUTHORIZED"))

    def test_token_compare_is_constant_time(self):
        with mock.patch.object(ipc.hmac, "compare_digest", wraps=ipc.hmac.compare_digest) as cd:
            self.assertTrue(ipc.token_matches(TOKEN, TOKEN))
            self.assertFalse(ipc.token_matches("x" * 64, TOKEN))
        self.assertEqual(cd.call_count, 2)
        self.assertFalse(ipc.token_matches(None, TOKEN))
        self.assertFalse(ipc.token_matches(12345, TOKEN))

    def test_non_json_content_type_is_415(self):
        for ctype in (None, "text/plain", "text/plain;charset=UTF-8", "application/x-www-form-urlencoded",
                      "multipart/form-data; boundary=x", "application/jsonx", "application/json-patch+json"):
            self.assertEqual(self._check(self._ok(**{"Content-Type": ctype})),
                             (415, "UNSUPPORTED_MEDIA_TYPE"), ctype)

    def test_allowed_hosts_follow_bind_host(self):
        self.assertIn("127.0.0.2:9000", ipc.allowed_host_headers("127.0.0.2", 9000))
        self.assertIn("[::1]:9000", ipc.allowed_host_headers("::1", 9000))
        self.assertIn("127.0.0.1:9000", ipc.allowed_host_headers("::1", 9000))


class ExclusiveBindTest(unittest.TestCase):
    def test_second_process_cannot_bind_the_daemon_port(self):
        httpd = ipc.make_http_server("127.0.0.1", 0, TOKEN, None)
        try:
            port = httpd.server_address[1]
            if os.name == "nt":
                self.assertFalse(httpd.allow_reuse_address)
            with socket.socket() as squatter:
                squatter.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                with self.assertRaises(OSError):
                    squatter.bind(("127.0.0.1", port))
        finally:
            httpd.server_close()


class ExecRequestValidationTest(unittest.TestCase):
    def test_shapes(self):
        ok = ipc.validate_exec_request({"script": "python/pourbaix_solver.py", "payload": {"a": 1}})
        self.assertEqual(ok, ("python/pourbaix_solver.py", {"a": 1}, [], 15000))
        self.assertEqual(ipc.validate_exec_request({"script": "x.py", "args": None, "timeoutMs": 2500.7})[2:],
                         ([], 2500))
        for req in ([], "x", {"args": "a b"}, {"args": [1]}, {"args": ["a"] * 65}, {"timeoutMs": "1"},
                    {"timeoutMs": 0}, {"timeoutMs": -5}, {"timeoutMs": True}, {"timeoutMs": 10 ** 9}):
            self.assertEqual(_status(ipc.validate_exec_request, req)[0], 400, req)


class StartupConfigTest(unittest.TestCase):
    def test_token_required(self):
        for token in (None, "", "short", "x" * 31):
            with self.assertRaises(SystemExit) as ctx:
                ipc.validate_startup_config("127.0.0.1", token, False)
            self.assertIn("METALLIX_IPC_TOKEN", str(ctx.exception.code))
        ipc.validate_startup_config("127.0.0.1", "x" * 32, False)

    def test_non_loopback_needs_explicit_override(self):
        for host in ("0.0.0.0", "192.168.1.10", "::", "example.com"):
            with self.assertRaises(SystemExit) as ctx:
                ipc.validate_startup_config(host, TOKEN, False)
            self.assertIn("METALLIX_IPC_ALLOW_REMOTE", str(ctx.exception.code))
        err = io.StringIO()
        with mock.patch.object(sys, "stderr", err):
            ipc.validate_startup_config("0.0.0.0", TOKEN, True)
        self.assertIn("WARNING", err.getvalue())
        with self.assertRaises(SystemExit):  # the override never waives the token
            ipc.validate_startup_config("0.0.0.0", None, True)
        for host in ("127.0.0.1", "127.0.0.5", "localhost", "::1"):
            ipc.validate_startup_config(host, TOKEN, False)

    def test_token_is_not_left_in_environment(self):
        self.assertNotIn("METALLIX_IPC_TOKEN", os.environ)


class _StubRegistry:
    def __init__(self):
        self.script_dir = str(HERE)
        self.calls = []

    def execute_script(self, script, payload, args=None, timeout_ms=15000):
        self.calls.append((script, payload, args, timeout_ms))
        return {"stdout": "stub-ran", "stderr": "", "exitCode": 0}

    def get_status(self):
        return {"status": "online"}

    def warmup(self):
        self.calls.append(("warmup",))


def _raw_request(port, method, path, headers, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=120)
    conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
    data = body.encode("utf-8") if isinstance(body, str) else body
    if data is not None:
        headers = dict(headers, **{"Content-Length": str(len(data))})
    for key, value in headers.items():
        conn.putheader(key, value)
    conn.endheaders(data)
    res = conn.getresponse()
    raw = res.read().decode("utf-8", "replace")
    acao = res.getheader("Access-Control-Allow-Origin")
    conn.close()
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = raw
    return res.status, parsed, acao


def _attack_matrix(port, token):
    """(name, method, path, headers, body, expected status) for attacker-shaped requests."""
    host = f"127.0.0.1:{port}"
    auth = f"Bearer {token}"
    traversal = json.dumps({"script": "python/../../outside/pwn.py", "payload": {}})
    legit = json.dumps({"script": "python/pourbaix_solver.py", "payload": {"element": "Fe"}})
    js = "application/json"
    return [
        ("cross-origin text/plain POST (browser)", "POST", "/execute",
         {"Host": host, "Origin": "https://evil.example", "Content-Type": "text/plain"}, traversal, 403),
        ("DNS rebinding Host", "POST", "/execute",
         {"Host": f"evil.example:{port}", "Content-Type": js, "Authorization": auth}, legit, 403),
        ("Origin even with token", "POST", "/execute",
         {"Host": host, "Origin": "https://evil.example", "Content-Type": js, "Authorization": auth}, legit, 403),
        ("no token", "POST", "/execute", {"Host": host, "Content-Type": js}, legit, 401),
        ("wrong token", "POST", "/execute",
         {"Host": host, "Content-Type": js, "Authorization": "Bearer " + "0" * 64}, legit, 401),
        ("no token GET /status", "GET", "/status", {"Host": host}, None, 401),
        ("text/plain with token", "POST", "/execute",
         {"Host": host, "Content-Type": "text/plain", "Authorization": auth}, legit, 415),
        ("form with token", "POST", "/execute",
         {"Host": host, "Content-Type": "application/x-www-form-urlencoded", "Authorization": auth}, legit, 415),
        ("traversal with token", "POST", "/execute",
         {"Host": host, "Content-Type": js, "Authorization": auth}, traversal, 400),
        ("backslash traversal with token", "POST", "/execute",
         {"Host": host, "Content-Type": js, "Authorization": auth},
         json.dumps({"script": "python\\..\\..\\outside\\pwn.py"}), 400),
        ("absolute drive path with token", "POST", "/execute",
         {"Host": host, "Content-Type": js, "Authorization": auth}, json.dumps({"script": "C:/x/pwn.py"}), 400),
        ("UNC path with token", "POST", "/execute",
         {"Host": host, "Content-Type": js, "Authorization": auth}, json.dumps({"script": "//srv/share/pwn.py"}), 400),
        ("unlisted script with token", "POST", "/execute",
         {"Host": host, "Content-Type": js, "Authorization": auth},
         json.dumps({"script": "python/persistent_ipc_service.py"}), 403),
        ("non-list args with token", "POST", "/execute",
         {"Host": host, "Content-Type": js, "Authorization": auth},
         json.dumps({"script": "python/pourbaix_solver.py", "args": "-c x"}), 400),
        ("CORS preflight", "OPTIONS", "/execute",
         {"Host": host, "Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}, None, 501),
    ]


class InThreadHttpTest(unittest.TestCase):
    """The real handler class on an ephemeral port with a stub registry (no solver runs)."""

    @classmethod
    def setUpClass(cls):
        cls.reg = _StubRegistry()
        cls.httpd = ipc.make_http_server("127.0.0.1", 0, TOKEN, cls.reg)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        self.reg.calls.clear()

    def test_attacks_are_refused_before_any_execution(self):
        for name, method, path, headers, body, expected in _attack_matrix(self.port, TOKEN):
            status, parsed, acao = _raw_request(self.port, method, path, headers, body)
            self.assertEqual(status, expected, (name, parsed))
            self.assertIsNone(acao, name)
        self.assertEqual(self.reg.calls, [])

    def test_legit_request_reaches_registry(self):
        status, parsed, acao = _raw_request(
            self.port, "POST", "/execute",
            {"Host": f"localhost:{self.port}", "Content-Type": "application/json; charset=utf-8",
             "Authorization": f"Bearer {TOKEN}"},
            json.dumps({"script": "python/pourbaix_solver.py", "payload": {"element": "Fe"}, "id": 7}))
        self.assertEqual((status, parsed["stdout"], parsed["id"], acao), (200, "stub-ran", 7, None))
        self.assertEqual(self.reg.calls, [("python/pourbaix_solver.py", {"element": "Fe"}, [], 15000)])
        status, parsed, _ = _raw_request(self.port, "GET", "/status",
                                         {"Host": f"127.0.0.1:{self.port}", "Authorization": f"Bearer {TOKEN}"})
        self.assertEqual((status, parsed), (200, {"status": "online"}))

    def test_warmup_requires_auth(self):
        status, _, _ = _raw_request(self.port, "POST", "/warmup",
                                    {"Host": f"127.0.0.1:{self.port}", "Content-Type": "application/json"}, "{}")
        self.assertEqual(status, 401)
        self.assertEqual(self.reg.calls, [])


@unittest.skipIf(os.name == "nt" or not hasattr(socket, "AF_UNIX"), "UNIX socket channel is POSIX only")
class UnixSocketTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "ipc.sock")
        self.reg = _StubRegistry()
        self.server = ipc.UnixIPCServer(self.path, self.reg, TOKEN)
        self.server.start()

    def tearDown(self):
        self.server.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _send(self, req):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect(self.path)
            s.sendall(json.dumps(req).encode("utf-8") + b"\n")
            data = b""
            while b"\n" not in data:
                chunk = s.recv(65536)
                if not chunk:
                    break
                data += chunk
        return json.loads(data.split(b"\n", 1)[0])

    def test_socket_mode_is_owner_only(self):
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)

    def test_token_required(self):
        req = {"action": "execute", "script": "python/pourbaix_solver.py", "payload": {}}
        for token in (None, "", "0" * 64):
            body = dict(req) if token is None else dict(req, token=token)
            self.assertEqual(self._send(body)["status"], 401)
        self.assertEqual(self._send({"action": "status"})["status"], 401)
        self.assertEqual(self.reg.calls, [])
        self.assertEqual(self._send(dict(req, token=TOKEN))["stdout"], "stub-ran")

    def test_traversal_rejected_on_socket(self):
        res = self._send({"action": "execute", "token": TOKEN, "script": "python/../../x/pwn.py"})
        self.assertEqual((res["status"], res["exitCode"]), (400, 1))
        self.assertEqual(self.reg.calls, [])


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _kill_tree(proc):
    if proc.poll() is None:
        if os.name == "nt":  # pool workers would otherwise outlive TerminateProcess
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:
            proc.terminate()
        try:
            proc.wait(30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(30)
    for stream in (proc.stdout, proc.stderr):
        try:
            stream.close()
        except (OSError, ValueError, AttributeError):
            pass


def _spawn_service(extra_env, cwd):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", METALLIX_IPC_WORKERS="1")
    env.pop("METALLIX_IPC_TOKEN", None)
    env.pop("METALLIX_IPC_ALLOW_REMOTE", None)
    env.update(extra_env)
    return subprocess.Popen([sys.executable, "-B", str(HERE / "persistent_ipc_service.py")], cwd=str(cwd),
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")


class ServiceIntegrationTest(unittest.TestCase):
    """Starts the real service (cwd = repo root, as server/processOrchestrator.ts does)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.outside = Path(cls.tmp) / "outside"
        cls.outside.mkdir()
        cls.marker = cls.outside / "PWNED.txt"
        (cls.outside / "pwn.py").write_text(
            "import pathlib\npathlib.Path(__file__).with_name('PWNED.txt').write_text('x')\nprint('PWNED')\n",
            encoding="utf-8")
        cls.port = _free_port()
        cls.proc = _spawn_service({"METALLIX_IPC_TOKEN": TOKEN, "METALLIX_IPC_PORT": str(cls.port),
                                   "METALLIX_IPC_SOCK": os.path.join(cls.tmp, "ipc.sock")}, REPO)
        line = cls.proc.stdout.readline()
        if not line:
            err = cls.proc.stderr.read()
            _kill_tree(cls.proc)
            raise AssertionError(f"service did not start: {err[-2000:]}")
        cls.ready = json.loads(line)
        threading.Thread(target=cls.proc.stderr.read, daemon=True).start()  # drain

    @classmethod
    def tearDownClass(cls):
        _kill_tree(cls.proc)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_ready_message_has_no_token(self):
        self.assertEqual(self.ready["status"], "ready")
        self.assertTrue(self.ready["httpActive"])
        self.assertNotIn(TOKEN, json.dumps(self.ready))

    def test_attacks_fail_and_legit_request_succeeds(self):
        rel = os.path.relpath(self.outside / "pwn.py", REPO).replace(os.sep, "/")
        real_traversal = json.dumps({"script": "python/../" + rel})
        host = f"127.0.0.1:{self.port}"
        for name, method, path, headers, body, expected in _attack_matrix(self.port, TOKEN):
            if body and "outside/pwn.py" in body and "\\\\" not in body:
                body = real_traversal  # aim at a file that really exists
            status, parsed, acao = _raw_request(self.port, method, path, headers, body)
            self.assertEqual(status, expected, (name, parsed))
            self.assertIsNone(acao, name)
            self.assertFalse(self.marker.exists(), name)
        status, parsed, acao = _raw_request(
            self.port, "POST", "/execute",
            {"Host": host, "Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
            json.dumps({"script": "python/pourbaix_solver.py", "payload": {"element": "Fe"}, "timeoutMs": 60000}))
        self.assertEqual((status, acao), (200, None), parsed)
        self.assertEqual(parsed["exitCode"], 0, parsed.get("stderr"))
        self.assertTrue(json.loads(parsed["stdout"])["success"])
        self.assertFalse(self.marker.exists())


class ServiceStartupRefusalTest(unittest.TestCase):
    def _expect_refusal(self, extra_env, needle):
        proc = _spawn_service(dict(extra_env, METALLIX_IPC_PORT=str(_free_port()),
                                   METALLIX_IPC_SOCK=os.path.join(tempfile.gettempdir(), f"ipc-{os.getpid()}.sock")),
                              REPO)
        try:
            out, err = proc.communicate(timeout=180)
        finally:
            _kill_tree(proc)
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn('"ready"', out)
        self.assertIn(needle, err)

    def test_refuses_without_token(self):
        self._expect_refusal({}, "METALLIX_IPC_TOKEN")

    def test_refuses_non_loopback_without_override(self):
        self._expect_refusal({"METALLIX_IPC_TOKEN": TOKEN, "METALLIX_IPC_HOST": "0.0.0.0"},
                             "METALLIX_IPC_ALLOW_REMOTE")


if __name__ == "__main__":
    unittest.main()
