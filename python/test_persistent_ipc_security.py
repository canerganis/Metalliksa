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


VECTOR_TOKEN = "k" * 64
VECTOR_NONCE = "0123456789abcdef0123456789abcdef"
VECTOR_REQ_BODY = b'{"script":"python/pourbaix_solver.py"}'
VECTOR_REQ_MAC = "00622ace5f176a373bda15f2e964903e74d6457c8a60d5907f17b10e34773ffe"
VECTOR_RESP_BODY = b'{"stdout": "x"}'
VECTOR_RESP_MAC = "3baf7d40b3db8b160d35c8e4caf1338cad617f030cb908dd06c0e87bd128973c"


def _now_ms():
    return int(time.time() * 1000)


def _auth_fields(method, path, body, token=TOKEN, ts=None, nonce=None):
    ts = ts or str(_now_ms())
    nonce = nonce or secrets.token_hex(16)
    return ts, nonce, ipc.request_mac(token, method, path, ts, nonce, body)


class MutualAuthTest(unittest.TestCase):
    def test_cross_language_vectors(self):
        # Same vectors as tests/persistent-ipc-auth.test.ts (computed with plain hmac/hashlib).
        self.assertEqual(ipc.request_mac(VECTOR_TOKEN, "POST", "/execute", "1700000000000", VECTOR_NONCE,
                                         VECTOR_REQ_BODY), VECTOR_REQ_MAC)
        self.assertEqual(ipc.response_mac(VECTOR_TOKEN, VECTOR_NONCE, 200, VECTOR_RESP_BODY), VECTOR_RESP_MAC)

    def test_verify_accepts_exact_request_once(self):
        nonces = ipc.NonceCache()
        body = b'{"a": 1}'
        ts, nonce, mac = _auth_fields("POST", "/execute", body)
        ipc.verify_request(TOKEN, "POST", "/execute", ts, nonce, mac, body, nonces)
        self.assertEqual(_status(ipc.verify_request, TOKEN, "POST", "/execute", ts, nonce, mac, body, nonces),
                         (401, "REPLAYED_REQUEST"))

    def test_any_change_or_wrong_token_is_401(self):
        body = b'{"a": 1}'
        ts, nonce, mac = _auth_fields("POST", "/execute", body)
        cases = [
            (TOKEN, "POST", "/execute", ts, nonce, mac, b'{"a": 2}'),
            (TOKEN, "POST", "/run", ts, nonce, mac, body),
            (TOKEN, "GET", "/execute", ts, nonce, mac, body),
            (TOKEN, "POST", "/execute", str(int(ts) + 1), nonce, mac, body),
            (TOKEN, "POST", "/execute", ts, secrets.token_hex(16), mac, body),
            ("0" * 64, "POST", "/execute", ts, nonce, mac, body),
            (None, "POST", "/execute", ts, nonce, mac, body),
            ("", "POST", "/execute", ts, nonce, mac, body),
        ]
        for case in cases:
            self.assertEqual(_status(ipc.verify_request, *case, ipc.NonceCache())[0], 401, case[:5])

    def test_failed_mac_does_not_burn_the_nonce(self):
        nonces = ipc.NonceCache()
        body = b"{}"
        ts, nonce, mac = _auth_fields("POST", "/execute", body)
        self.assertEqual(_status(ipc.verify_request, TOKEN, "POST", "/execute", ts, nonce, "f" * 64, body, nonces)[0], 401)
        ipc.verify_request(TOKEN, "POST", "/execute", ts, nonce, mac, body, nonces)

    def test_stale_or_future_timestamps_are_401(self):
        for delta in (-ipc.MAX_CLOCK_SKEW_MS - 1000, ipc.MAX_CLOCK_SKEW_MS + 1000):
            ts, nonce, mac = _auth_fields("GET", "/status", b"", ts=str(_now_ms() + delta))
            self.assertEqual(_status(ipc.verify_request, TOKEN, "GET", "/status", ts, nonce, mac, b"", ipc.NonceCache()),
                             (401, "STALE_REQUEST"))

    def test_mac_compare_is_constant_time(self):
        with mock.patch.object(ipc.hmac, "compare_digest", wraps=ipc.hmac.compare_digest) as cd:
            self.assertTrue(ipc.macs_equal("a" * 64, "a" * 64))
            self.assertFalse(ipc.macs_equal("b" * 64, "a" * 64))
        self.assertEqual(cd.call_count, 2)
        for bad in (None, 5, "A" * 64, "a" * 63, "g" * 64):
            self.assertFalse(ipc.macs_equal(bad, "a" * 64))

    def test_nonce_cache_fails_closed_when_full(self):
        cache = ipc.NonceCache(ttl_ms=10_000, max_entries=2)
        self.assertTrue(cache.add_if_new("a" * 32, 0))
        self.assertTrue(cache.add_if_new("b" * 32, 0))
        self.assertFalse(cache.add_if_new("c" * 32, 1))      # full of live entries
        self.assertTrue(cache.add_if_new("c" * 32, 20_000))  # expired entries purged
        self.assertFalse(cache.add_if_new("c" * 32, 20_001))  # replay


class HeaderCheckTest(unittest.TestCase):
    HOSTS = ipc.allowed_host_headers("127.0.0.1", 5055)

    def _check(self, pairs, require_json=True):
        return _status(ipc.check_http_headers, _headers(pairs), allowed_hosts=self.HOSTS, require_json=require_json)

    def _ok(self, **override):
        ts, nonce, mac = _auth_fields("POST", "/execute", b"{}")
        base = {"Host": "127.0.0.1:5055", "X-Metallix-Ts": ts, "X-Metallix-Nonce": nonce, "X-Metallix-Mac": mac,
                "Content-Type": "application/json"}
        base.update(override)
        return [(k, v) for k, v in base.items() if v is not None]

    def test_well_formed_request_passes(self):
        self.assertIsNone(self._check(self._ok()))
        self.assertIsNone(self._check(self._ok(Host="localhost:5055")))
        self.assertIsNone(self._check(self._ok(Host="LOCALHOST:5055")))
        self.assertIsNone(self._check(self._ok(**{"Content-Type": "Application/JSON; charset=utf-8"})))
        self.assertIsNone(self._check(self._ok(**{"Content-Type": None}), require_json=False))

    def test_host_header_rebinding_is_403(self):
        for host in (None, "evil.example:5055", "evil.example", "127.0.0.1", "127.0.0.1:5056",
                     "127.0.0.1.nip.io:5055", "localhost", "0.0.0.0:5055", ""):
            self.assertEqual(self._check(self._ok(Host=host)), (403, "HOST_NOT_ALLOWED"), host)
        self.assertEqual(self._check(self._ok() + [("Host", "evil.example:5055")]), (403, "HOST_NOT_ALLOWED"))

    def test_any_origin_is_403(self):
        for origin in ("https://evil.example", "null", "http://127.0.0.1:5055", "http://localhost:3000"):
            self.assertEqual(self._check(self._ok(Origin=origin)), (403, "ORIGIN_NOT_ALLOWED"), origin)

    def test_missing_or_malformed_auth_fields_are_401(self):
        bad = [{"X-Metallix-Ts": None}, {"X-Metallix-Nonce": None}, {"X-Metallix-Mac": None},
               {"X-Metallix-Ts": "abc"}, {"X-Metallix-Ts": "-5"}, {"X-Metallix-Nonce": "0" * 31},
               {"X-Metallix-Nonce": "A" * 32}, {"X-Metallix-Mac": "0" * 63}, {"X-Metallix-Mac": "Z" * 64}]
        for override in bad:
            self.assertEqual(self._check(self._ok(**override))[0], 401, override)
        self.assertEqual(self._check(self._ok() + [("X-Metallix-Nonce", "1" * 32)])[0], 401)  # duplicate
        self.assertEqual(self._check(self._ok(**{"X-Metallix-Ts": str(_now_ms() - 10 ** 6)})),
                         (401, "STALE_REQUEST"))
        # A bearer token alone (the previous scheme) is no longer accepted.
        self.assertEqual(self._check([("Host", "127.0.0.1:5055"), ("Authorization", f"Bearer {TOKEN}"),
                                      ("Content-Type", "application/json")])[0], 401)

    def test_non_json_content_type_is_415(self):
        for ctype in (None, "text/plain", "text/plain;charset=UTF-8", "application/x-www-form-urlencoded",
                      "multipart/form-data; boundary=x", "application/jsonx", "application/json-patch+json"):
            self.assertEqual(self._check(self._ok(**{"Content-Type": ctype})),
                             (415, "UNSUPPORTED_MEDIA_TYPE"), ctype)

    def test_allowed_hosts_follow_bind_host(self):
        self.assertIn("127.0.0.2:9000", ipc.allowed_host_headers("127.0.0.2", 9000))
        self.assertIn("[::1]:9000", ipc.allowed_host_headers("::1", 9000))
        self.assertIn("127.0.0.1:9000", ipc.allowed_host_headers("::1", 9000))
        self.assertIn("192.0.2.7:9000", ipc.allowed_host_headers("192.0.2.7", 9000))


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

    def test_wildcards_are_always_refused(self):
        for host in ("0.0.0.0", "::", "[::]", ""):
            for allow in (False, True):
                with self.assertRaises(SystemExit) as ctx:
                    ipc.validate_startup_config(host, TOKEN, allow)
                self.assertIn("wildcard", str(ctx.exception.code))

    def test_non_loopback_needs_explicit_override(self):
        for host in ("192.168.1.10", "example.com"):
            with self.assertRaises(SystemExit) as ctx:
                ipc.validate_startup_config(host, TOKEN, False)
            self.assertIn("METALLIX_IPC_ALLOW_REMOTE", str(ctx.exception.code))
        err = io.StringIO()
        with mock.patch.object(sys, "stderr", err):
            ipc.validate_startup_config("192.168.1.10", TOKEN, True)
        self.assertIn("WARNING", err.getvalue())
        with self.assertRaises(SystemExit):  # the override never waives the token
            ipc.validate_startup_config("192.168.1.10", None, True)
        for host in ("127.0.0.1", "127.0.0.5", "localhost", "::1"):
            ipc.validate_startup_config(host, TOKEN, False)

    def test_token_is_neither_in_environment_nor_a_module_global(self):
        self.assertNotIn("METALLIX_IPC_TOKEN", os.environ)
        self.assertFalse(hasattr(ipc, "IPC_TOKEN"))
        module_strings = [v for v in vars(ipc).values() if isinstance(v, str) and len(v) >= 32]
        self.assertNotIn(TOKEN, module_strings)

    def test_pool_workers_start_from_a_fresh_interpreter(self):
        self.assertIn(ipc._pool_mp_context().get_start_method(), ("spawn", "forkserver"))
        if os.name != "nt" and "forkserver" in __import__("multiprocessing").get_all_start_methods():
            self.assertEqual(ipc._pool_mp_context().get_start_method(), "forkserver")
        with mock.patch.object(ipc.multiprocessing, "parent_process", return_value=object()):
            self.assertTrue(ipc._is_pool_worker_process())
        self.assertFalse(ipc._is_pool_worker_process())


class ExclusiveBindTest(unittest.TestCase):
    def test_second_process_cannot_bind_the_daemon_port(self):
        httpd = ipc.make_http_server("127.0.0.1", 0, TOKEN, _StubRegistry())
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


@unittest.skipIf(os.name == "nt", "UNIX socket directory is POSIX only")
class SocketPathTest(unittest.TestCase):
    def test_default_is_private_0700_directory(self):
        path, private_dir = ipc.create_socket_path(None)
        try:
            self.assertEqual(os.path.dirname(path), private_dir)
            self.assertEqual(stat.S_IMODE(os.stat(private_dir).st_mode), 0o700)
        finally:
            shutil.rmtree(private_dir, ignore_errors=True)

    def test_explicit_path_in_shared_directory_is_refused(self):
        with self.assertRaises(SystemExit):
            ipc.create_socket_path("/tmp/metallix_python_ipc.sock")
        with tempfile.TemporaryDirectory() as tmp:
            os.chmod(tmp, 0o700)
            self.assertEqual(ipc.create_socket_path(os.path.join(tmp, "s.sock")), (os.path.join(tmp, "s.sock"), None))


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
    if data is not None and "Content-Length" not in headers:
        headers = dict(headers, **{"Content-Length": str(len(data))})
    for key, value in headers.items():
        conn.putheader(key, value)
    conn.endheaders(data)
    res = conn.getresponse()
    raw = res.read()
    acao = res.getheader("Access-Control-Allow-Origin")
    mac = res.getheader("X-Metallix-Mac")
    conn.close()
    try:
        parsed = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        parsed = raw.decode("utf-8", "replace")
    return res.status, parsed, acao, mac, raw


def _signed(port, method, path, body, token=TOKEN, host=None, ctype="application/json", ts=None, nonce=None,
            sign_body=None):
    data = body.encode("utf-8") if isinstance(body, str) else (body or b"")
    ts, nonce, mac = _auth_fields(method, path, data if sign_body is None else sign_body.encode("utf-8"),
                                  token=token, ts=ts, nonce=nonce)
    headers = {"Host": host or f"127.0.0.1:{port}", "X-Metallix-Ts": ts, "X-Metallix-Nonce": nonce,
               "X-Metallix-Mac": mac}
    if ctype:
        headers["Content-Type"] = ctype
    return headers


def _attack_matrix(port, traversal_script="python/../../outside/pwn.py"):
    """(name, method, path, headers, body, expected status) for attacker-shaped requests (signed fresh)."""
    host = f"127.0.0.1:{port}"
    traversal = json.dumps({"script": traversal_script, "payload": {}})
    legit = json.dumps({"script": "python/pourbaix_solver.py", "payload": {"element": "Fe"}})

    def s(body, **kw):
        return _signed(port, "POST", "/execute", body, **kw)

    return [
        ("cross-origin text/plain POST (browser)", "POST", "/execute",
         {"Host": host, "Origin": "https://evil.example", "Content-Type": "text/plain"}, traversal, 403),
        ("DNS rebinding Host", "POST", "/execute", s(legit, host=f"evil.example:{port}"), legit, 403),
        ("Origin even when signed", "POST", "/execute", dict(s(legit), Origin="https://evil.example"), legit, 403),
        ("no authentication", "POST", "/execute", {"Host": host, "Content-Type": "application/json"}, legit, 401),
        ("old bearer token scheme", "POST", "/execute",
         {"Host": host, "Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"}, legit, 401),
        ("signed with the wrong token", "POST", "/execute", s(legit, token="0" * 64), legit, 401),
        ("signed body swapped for traversal", "POST", "/execute", s(traversal, sign_body=legit), traversal, 401),
        ("stale timestamp", "POST", "/execute", s(legit, ts=str(_now_ms() - 10 ** 6)), legit, 401),
        ("no authentication GET /status", "GET", "/status", {"Host": host}, None, 401),
        ("text/plain when signed", "POST", "/execute", s(legit, ctype="text/plain"), legit, 415),
        ("form when signed", "POST", "/execute", s(legit, ctype="application/x-www-form-urlencoded"), legit, 415),
        ("signed traversal", "POST", "/execute", s(traversal), traversal, 400),
        ("signed backslash traversal", "POST", "/execute",
         s(json.dumps({"script": "python\\..\\..\\outside\\pwn.py"})),
         json.dumps({"script": "python\\..\\..\\outside\\pwn.py"}), 400),
        ("signed drive path", "POST", "/execute", s(json.dumps({"script": "C:/x/pwn.py"})),
         json.dumps({"script": "C:/x/pwn.py"}), 400),
        ("signed UNC path", "POST", "/execute", s(json.dumps({"script": "//srv/share/pwn.py"})),
         json.dumps({"script": "//srv/share/pwn.py"}), 400),
        ("signed unlisted script", "POST", "/execute", s(json.dumps({"script": "python/persistent_ipc_service.py"})),
         json.dumps({"script": "python/persistent_ipc_service.py"}), 403),
        ("signed non-list args", "POST", "/execute",
         s(json.dumps({"script": "python/pourbaix_solver.py", "args": "-c x"})),
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
        for name, method, path, headers, body, expected in _attack_matrix(self.port):
            status, parsed, acao, _, _ = _raw_request(self.port, method, path, headers, body)
            self.assertEqual(status, expected, (name, parsed))
            self.assertIsNone(acao, name)
        self.assertEqual(self.reg.calls, [])

    def test_legit_request_reaches_registry_and_response_is_signed(self):
        body = json.dumps({"script": "python/pourbaix_solver.py", "payload": {"element": "Fe"}, "id": 7})
        headers = _signed(self.port, "POST", "/execute", body, host=f"localhost:{self.port}",
                          ctype="application/json; charset=utf-8")
        status, parsed, acao, mac, raw = _raw_request(self.port, "POST", "/execute", headers, body)
        self.assertEqual((status, parsed["stdout"], parsed["id"], acao), (200, "stub-ran", 7, None))
        self.assertEqual(mac, ipc.response_mac(TOKEN, headers["X-Metallix-Nonce"], 200, raw))
        self.assertEqual(self.reg.calls, [("python/pourbaix_solver.py", {"element": "Fe"}, [], 15000)])
        # The same request again is a replay.
        status, parsed, _, _, _ = _raw_request(self.port, "POST", "/execute", headers, body)
        self.assertEqual((status, parsed["code"]), (401, "REPLAYED_REQUEST"))
        self.assertEqual(len(self.reg.calls), 1)
        get_headers = _signed(self.port, "GET", "/status", b"", ctype=None)
        status, parsed, _, mac, raw = _raw_request(self.port, "GET", "/status", get_headers)
        self.assertEqual((status, parsed), (200, {"status": "online"}))
        self.assertEqual(mac, ipc.response_mac(TOKEN, get_headers["X-Metallix-Nonce"], 200, raw))

    def test_unauthenticated_rejections_are_not_signed(self):
        status, _, _, mac, _ = _raw_request(self.port, "POST", "/execute",
                                            _signed(self.port, "POST", "/execute", "{}", token="0" * 64), "{}")
        self.assertEqual((status, mac), (401, None))

    def test_warmup_requires_auth(self):
        status, _, _, _, _ = _raw_request(self.port, "POST", "/warmup",
                                          {"Host": f"127.0.0.1:{self.port}", "Content-Type": "application/json"}, "{}")
        self.assertEqual(status, 401)
        self.assertEqual(self.reg.calls, [])

    def test_oversized_body_is_413_before_reading(self):
        headers = dict(_signed(self.port, "POST", "/execute", b"{}"), **{"Content-Length": str(ipc.MAX_BODY_BYTES + 1)})
        status, parsed, _, _, _ = _raw_request(self.port, "POST", "/execute", headers, None)
        self.assertEqual((status, parsed["code"]), (413, "PAYLOAD_TOO_LARGE"))

    def test_idle_connection_is_closed(self):
        with mock.patch.object(ipc.MicroserviceHTTPHandler, "timeout", 0.5):
            with socket.create_connection(("127.0.0.1", self.port), timeout=10) as s:
                s.sendall(b"POST /execute HTTP/1.1\r\nHost: 127.0.0.1\r\n")  # never finishes the headers
                t0 = time.time()
                self.assertEqual(s.recv(1024), b"")
                self.assertLess(time.time() - t0, 8)


def _unix_frame(request, token=TOKEN, ts=None, nonce=None):
    body = json.dumps(request)
    ts, nonce, mac = _auth_fields("UNIX", "/", body.encode("utf-8"), token=token, ts=ts, nonce=nonce)
    return {"v": 1, "ts": ts, "nonce": nonce, "mac": mac, "body": body}


@unittest.skipIf(os.name == "nt" or not hasattr(socket, "AF_UNIX"), "UNIX socket channel is POSIX only")
class UnixSocketTest(unittest.TestCase):
    def setUp(self):
        self.path, self.private_dir = ipc.create_socket_path(None)
        self.reg = _StubRegistry()
        self.server = ipc.UnixIPCServer(self.path, self.reg, TOKEN, self.private_dir)
        self.server.start()

    def tearDown(self):
        self.server.stop()

    def _send_raw(self, data: bytes):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect(self.path)
            s.sendall(data)
            buf = b""
            while b"\n" not in buf:
                chunk = s.recv(65536)
                if not chunk:
                    break
                buf += chunk
        return json.loads(buf.split(b"\n", 1)[0])

    def _send(self, frame):
        return self._send_raw(json.dumps(frame).encode("utf-8") + b"\n")

    def _verified(self, frame, nonce):
        self.assertEqual(frame["mac"], ipc.response_mac(TOKEN, nonce, frame["status"], frame["body"].encode("utf-8")))
        return json.loads(frame["body"])

    def test_socket_and_directory_are_owner_only(self):
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.private_dir).st_mode), 0o700)
        self.server.stop()
        self.assertFalse(os.path.exists(self.private_dir))

    def test_authentication_required_and_responses_signed(self):
        req = {"action": "execute", "script": "python/pourbaix_solver.py", "payload": {}}
        for frame in ({"token": TOKEN, **req}, dict(_unix_frame(req), mac="0" * 64), _unix_frame(req, token="0" * 64),
                      dict(_unix_frame(req), body=json.dumps(dict(req, script="python/calphad_solver.py"))),
                      _unix_frame(req, ts=str(_now_ms() - 10 ** 6))):
            res = self._send(frame)
            self.assertEqual(res["status"], 401)
            self.assertNotIn("mac", res)
        self.assertEqual(self.reg.calls, [])
        frame = _unix_frame(req)
        res = self._send(frame)
        self.assertEqual(res["status"], 200)
        self.assertEqual(self._verified(res, frame["nonce"])["stdout"], "stub-ran")
        self.assertEqual(self._send(frame)["status"], 401)  # replay
        self.assertEqual(len(self.reg.calls), 1)

    def test_traversal_rejected_on_socket_with_signed_4xx(self):
        frame = _unix_frame({"action": "execute", "script": "python/../../x/pwn.py"})
        res = self._send(frame)
        self.assertEqual(res["status"], 400)
        self.assertEqual(self._verified(res, frame["nonce"])["code"], "INVALID_SCRIPT_PATH")
        self.assertEqual(self.reg.calls, [])

    def test_unterminated_oversized_frame_is_413(self):
        with mock.patch.object(ipc, "MAX_LINE_BYTES", 1024):
            res = self._send_raw(b"x" * 4096)
        self.assertEqual(res["status"], 413)

    def test_idle_connection_is_closed(self):
        with mock.patch.object(ipc, "CONNECTION_IDLE_TIMEOUT_S", 0.5):
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(10)
                s.connect(self.path)
                t0 = time.time()
                self.assertEqual(s.recv(1024), b"")
                self.assertLess(time.time() - t0, 8)


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
    for key in ("METALLIX_IPC_TOKEN", "METALLIX_IPC_ALLOW_REMOTE", "METALLIX_IPC_PORT", "METALLIX_IPC_SOCK",
                "METALLIX_IPC_HOST"):
        env.pop(key, None)
    env.update(extra_env)
    return subprocess.Popen([sys.executable, "-B", str(HERE / "persistent_ipc_service.py")], cwd=str(cwd),
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")


class ServiceIntegrationTest(unittest.TestCase):
    """Starts the real service with defaults (ephemeral port, private socket dir; cwd = repo root)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.outside = Path(cls.tmp) / "outside"
        cls.outside.mkdir()
        cls.marker = cls.outside / "PWNED.txt"
        (cls.outside / "pwn.py").write_text(
            "import pathlib\npathlib.Path(__file__).with_name('PWNED.txt').write_text('x')\nprint('PWNED')\n",
            encoding="utf-8")
        cls.proc = _spawn_service({"METALLIX_IPC_TOKEN": TOKEN}, REPO)
        line = cls.proc.stdout.readline()
        if not line:
            err = cls.proc.stderr.read()
            _kill_tree(cls.proc)
            raise AssertionError(f"service did not start: {err[-2000:]}")
        cls.ready = json.loads(line)
        cls.port = cls.ready["httpPort"]
        threading.Thread(target=cls.proc.stderr.read, daemon=True).start()  # drain

    @classmethod
    def tearDownClass(cls):
        _kill_tree(cls.proc)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_ready_message_announces_actual_channels_and_no_token(self):
        self.assertEqual(self.ready["status"], "ready")
        self.assertTrue(self.ready["httpActive"])
        self.assertIsInstance(self.port, int)
        self.assertGreater(self.port, 0)
        self.assertEqual(self.ready["http"], f"http://127.0.0.1:{self.port}")
        self.assertNotIn(TOKEN, json.dumps(self.ready))
        if os.name != "nt":
            self.assertTrue(self.ready["unixSocketActive"])
            sock_dir = os.path.dirname(self.ready["unixSocket"])
            self.assertEqual(stat.S_IMODE(os.stat(sock_dir).st_mode), 0o700)
        else:
            self.assertFalse(self.ready["unixSocketActive"])

    def test_attacks_fail_and_legit_request_succeeds(self):
        rel = os.path.relpath(self.outside / "pwn.py", REPO).replace(os.sep, "/")
        for name, method, path, headers, body, expected in _attack_matrix(self.port, "python/../" + rel):
            status, parsed, acao, _, _ = _raw_request(self.port, method, path, headers, body)
            self.assertEqual(status, expected, (name, parsed))
            self.assertIsNone(acao, name)
            self.assertFalse(self.marker.exists(), name)
        body = json.dumps({"script": "python/pourbaix_solver.py", "payload": {"element": "Fe"}, "timeoutMs": 60000})
        headers = _signed(self.port, "POST", "/execute", body)
        status, parsed, acao, mac, raw = _raw_request(self.port, "POST", "/execute", headers, body)
        self.assertEqual((status, acao), (200, None), parsed)
        self.assertEqual(mac, ipc.response_mac(TOKEN, headers["X-Metallix-Nonce"], 200, raw))
        self.assertEqual(parsed["exitCode"], 0, parsed.get("stderr"))
        self.assertTrue(json.loads(parsed["stdout"])["success"])
        self.assertFalse(self.marker.exists())


class ServiceStartupTest(unittest.TestCase):
    def _run_to_exit(self, extra_env):
        proc = _spawn_service(extra_env, REPO)
        try:
            out, err = proc.communicate(timeout=180)
        finally:
            _kill_tree(proc)
        return proc.returncode, out, err

    def _expect_refusal(self, extra_env, needle):
        code, out, err = self._run_to_exit(extra_env)
        self.assertNotEqual(code, 0)
        self.assertNotIn('"ready"', out)
        self.assertIn(needle, err)
        self.assertNotIn("Warming up", err)  # refused before any warm-up

    def test_refuses_without_token(self):
        self._expect_refusal({}, "METALLIX_IPC_TOKEN")

    def test_refuses_wildcard_even_with_override(self):
        self._expect_refusal({"METALLIX_IPC_TOKEN": TOKEN, "METALLIX_IPC_HOST": "0.0.0.0",
                              "METALLIX_IPC_ALLOW_REMOTE": "1"}, "wildcard")

    def test_refuses_non_loopback_without_override(self):
        self._expect_refusal({"METALLIX_IPC_TOKEN": TOKEN, "METALLIX_IPC_HOST": "192.0.2.1"},
                             "METALLIX_IPC_ALLOW_REMOTE")

    @unittest.skipIf(os.name == "nt", "UNIX socket is POSIX only")
    def test_refuses_socket_in_shared_tmp(self):
        code, out, err = self._run_to_exit({"METALLIX_IPC_TOKEN": TOKEN,
                                            "METALLIX_IPC_SOCK": f"/tmp/metallix-test-{os.getpid()}.sock"})
        self.assertNotEqual(code, 0)
        self.assertNotIn('"ready"', out)
        self.assertIn("METALLIX_IPC_SOCK", err)

    def test_squatted_fixed_port_is_never_announced(self):
        with socket.socket() as squatter:
            squatter.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            squatter.bind(("127.0.0.1", 0))
            squatter.listen(5)
            port = squatter.getsockname()[1]
            if os.name == "nt":
                # Exclusive bind fails and HTTP is the only channel: the daemon exits.
                code, out, err = self._run_to_exit({"METALLIX_IPC_TOKEN": TOKEN, "METALLIX_IPC_PORT": str(port)})
                self.assertNotEqual(code, 0)
                self.assertNotIn('"ready"', out)
                self.assertIn("no IPC channel", err)
                self.assertNotIn("Warming up", err)  # no pool was created for a launch that failed
            else:
                proc = _spawn_service({"METALLIX_IPC_TOKEN": TOKEN, "METALLIX_IPC_PORT": str(port)}, REPO)
                try:
                    ready = json.loads(proc.stdout.readline())
                finally:
                    _kill_tree(proc)
                self.assertFalse(ready["httpActive"])
                self.assertIsNone(ready["httpPort"])
                self.assertTrue(ready["unixSocketActive"])


if __name__ == "__main__":
    unittest.main()
