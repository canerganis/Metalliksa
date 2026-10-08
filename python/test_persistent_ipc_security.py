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
        expected = os.path.realpath(HERE / "xrd_peak_deconvolution.py")
        for ref in ("python/xrd_peak_deconvolution.py", "xrd_peak_deconvolution.py", "  python/xrd_peak_deconvolution.py "):
            self.assertTrue(ipc._same_dir(ipc.resolve_script_path(str(HERE), ref), expected), ref)

    def test_traversal_absolute_drive_unc_backslash_variants_are_400(self):
        bad = [
            "python/../../outside/pwn.py", "python/../xrd_peak_deconvolution.py", "../xrd_peak_deconvolution.py",
            "python/../python/xrd_peak_deconvolution.py", "./xrd_peak_deconvolution.py", "python/./xrd_peak_deconvolution.py",
            "..", "python/..", "python/", "python/.py", "/etc/passwd", "/python/xrd_peak_deconvolution.py",
            "C:/Windows/win.ini", "C:xrd_peak_deconvolution.py", "c:\\x.py", "//server/share/x.py",
            "\\\\server\\share\\x.py", "python\\..\\..\\x.py", "python\\xrd_peak_deconvolution.py",
            "python/sub/xrd_peak_deconvolution.py", "tools/xrd_peak_deconvolution.py", "xrd_peak_deconvolution.py.",
            "xrd_peak_deconvolution.py::$DATA", "xrd_peak_deconvolution.py\x00.txt", "xrd_peak_deconvolution", "POURBA~1.PY",
            "python/xrd_peak_deconvolution.pyc", "%2e%2e/xrd_peak_deconvolution.py", "a" * 300 + ".py",
        ]
        for ref in bad:
            self.assertEqual(_status(ipc.resolve_script_path, str(HERE), ref)[0], 400, ref)

    def test_non_string_or_empty_is_400(self):
        for ref in (None, "", "   ", 7, ["python/xrd_peak_deconvolution.py"], {"x": 1}):
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
        outside = os.path.join(tempfile.gettempdir(), "elsewhere", "xrd_peak_deconvolution.py")

        def fake_realpath(p, *a, **k):
            return outside if os.path.basename(str(p)) == "xrd_peak_deconvolution.py" else real(p, *a, **k)

        with mock.patch.object(ipc.os.path, "realpath", side_effect=fake_realpath):
            self.assertEqual(_status(ipc.resolve_script_path, str(HERE), "python/xrd_peak_deconvolution.py"),
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
        # The scan must see the real route table (7 scripts since the 2026-10-09 slim-modules removal), so an
        # empty or partial match can never make the equality below pass vacuously.
        self.assertGreaterEqual(len(found), 7, found)
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
VECTOR_REQ_MAC = "5126140a5094ef571795f7d658d319574d706efc1a2e62e61447f90f99006e3f"
VECTOR_RESP_BODY = b'{"stdout": "x"}'
VECTOR_RESP_MAC = "fd337f36ff1dc00192e77387e339bb7e347c8eb7b00eee2e5147479b42bd3d77"


def _now_ms():
    return int(time.time() * 1000)


def _auth_fields(method, path, body, token=TOKEN, ts=None, nonce=None, length=None):
    """(ts, nonce, digest, mac) for a request whose body is `body`."""
    ts = ts or str(_now_ms())
    nonce = nonce or secrets.token_hex(16)
    digest = ipc.body_digest(body)
    length = len(body) if length is None else length
    return ts, nonce, digest, ipc.request_mac(token, method, path, ts, nonce, length, digest)


def _read_line(stream, timeout):
    """readline with a deadline (a hung daemon must not hang the test run)."""
    out = []
    t = threading.Thread(target=lambda: out.append(stream.readline()), daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise AssertionError(f"no line within {timeout}s")
    return out[0]


class MutualAuthTest(unittest.TestCase):
    def test_cross_language_vectors(self):
        # Same vectors as tests/persistent-ipc-auth.test.ts (computed with plain hmac/hashlib).
        self.assertEqual(ipc.request_mac(VECTOR_TOKEN, "POST", "/execute", "1700000000000", VECTOR_NONCE,
                                         len(VECTOR_REQ_BODY), ipc.body_digest(VECTOR_REQ_BODY)), VECTOR_REQ_MAC)
        self.assertEqual(ipc.response_mac(VECTOR_TOKEN, VECTOR_NONCE, 200, len(VECTOR_RESP_BODY),
                                          ipc.body_digest(VECTOR_RESP_BODY)), VECTOR_RESP_MAC)

    def test_head_verification_needs_no_body_and_accepts_once(self):
        nonces = ipc.NonceCache()
        ts, nonce, digest, mac = _auth_fields("POST", "/execute", b'{"a": 1}')
        ipc.verify_request(TOKEN, "POST", "/execute", ts, nonce, mac, 8, digest, nonces)
        self.assertEqual(_status(ipc.verify_request, TOKEN, "POST", "/execute", ts, nonce, mac, 8, digest, nonces),
                         (401, "REPLAYED_REQUEST"))

    def test_any_change_or_wrong_token_is_401(self):
        ts, nonce, digest, mac = _auth_fields("POST", "/execute", b'{"a": 1}')
        other = ipc.body_digest(b'{"a": 2}')
        cases = [
            (TOKEN, "POST", "/execute", ts, nonce, mac, 8, other),
            (TOKEN, "POST", "/execute", ts, nonce, mac, 9, digest),
            (TOKEN, "POST", "/execute", ts, nonce, mac, 64 * 2 ** 20, digest),
            (TOKEN, "POST", "/run", ts, nonce, mac, 8, digest),
            (TOKEN, "GET", "/execute", ts, nonce, mac, 8, digest),
            (TOKEN, "POST", "/execute", str(int(ts) + 1), nonce, mac, 8, digest),
            (TOKEN, "POST", "/execute", ts, secrets.token_hex(16), mac, 8, digest),
            ("0" * 64, "POST", "/execute", ts, nonce, mac, 8, digest),
            (None, "POST", "/execute", ts, nonce, mac, 8, digest),
            ("", "POST", "/execute", ts, nonce, mac, 8, digest),
        ]
        for case in cases:
            self.assertEqual(_status(ipc.verify_request, *case, ipc.NonceCache())[0], 401, case[1:7])

    def test_failed_mac_does_not_burn_the_nonce(self):
        nonces = ipc.NonceCache()
        ts, nonce, digest, mac = _auth_fields("POST", "/execute", b"{}")
        self.assertEqual(_status(ipc.verify_request, TOKEN, "POST", "/execute", ts, nonce, "f" * 64, 2, digest,
                                 nonces)[0], 401)
        ipc.verify_request(TOKEN, "POST", "/execute", ts, nonce, mac, 2, digest, nonces)

    def test_stale_or_future_timestamps_are_401(self):
        for delta in (-ipc.MAX_CLOCK_SKEW_MS - 1000, ipc.MAX_CLOCK_SKEW_MS + 1000):
            ts, nonce, digest, mac = _auth_fields("GET", "/status", b"", ts=str(_now_ms() + delta))
            self.assertEqual(_status(ipc.verify_request, TOKEN, "GET", "/status", ts, nonce, mac, 0, digest,
                                     ipc.NonceCache()), (401, "STALE_REQUEST"))

    def test_replay_at_the_exact_edge_of_the_window_is_refused(self):
        # First seen at t0 with ts = t0 + skew; ts stays acceptable until t0 + 2 * skew.
        nonces = ipc.NonceCache()
        t0 = 10 ** 12
        ts, nonce, digest, mac = _auth_fields("GET", "/status", b"", ts=str(t0 + ipc.MAX_CLOCK_SKEW_MS))
        ipc.verify_request(TOKEN, "GET", "/status", ts, nonce, mac, 0, digest, nonces, now_ms=t0)
        for later in (t0 + 1, t0 + ipc.MAX_CLOCK_SKEW_MS, t0 + 2 * ipc.MAX_CLOCK_SKEW_MS):
            self.assertEqual(_status(ipc.verify_request, TOKEN, "GET", "/status", ts, nonce, mac, 0, digest,
                                     nonces, now_ms=later), (401, "REPLAYED_REQUEST"), later - t0)
        self.assertEqual(_status(ipc.verify_request, TOKEN, "GET", "/status", ts, nonce, mac, 0, digest, nonces,
                                 now_ms=t0 + 2 * ipc.MAX_CLOCK_SKEW_MS + 1), (401, "STALE_REQUEST"))

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

    def test_body_is_streamed_and_hash_checked(self):
        body = b"x" * 200_000
        digest = ipc.body_digest(body)
        stream = io.BytesIO(body)
        sizes = []

        def read(n):
            sizes.append(n)
            return stream.read(n)

        self.assertEqual(ipc.read_body_checked(read, len(body), digest, time.monotonic() + 10), body)
        self.assertLessEqual(max(sizes), 64 * 1024)  # never asks for the declared length at once
        self.assertEqual(_status(ipc.read_body_checked, io.BytesIO(body).read, len(body), "0" * 64,
                                 time.monotonic() + 10), (400, "BODY_HASH_MISMATCH"))
        self.assertEqual(_status(ipc.read_body_checked, io.BytesIO(b"x" * 10).read, 20, digest,
                                 time.monotonic() + 10), (400, "TRUNCATED_BODY"))
        self.assertEqual(_status(ipc.read_body_checked, io.BytesIO(body).read, len(body), digest,
                                 time.monotonic() - 1), (408, "REQUEST_TIMEOUT"))


class HeaderCheckTest(unittest.TestCase):
    HOSTS = ipc.allowed_host_headers("127.0.0.1", 5055)

    def _check(self, pairs, require_json=True):
        return _status(ipc.check_http_headers, _headers(pairs), allowed_hosts=self.HOSTS, require_json=require_json)

    def _ok(self, **override):
        ts, nonce, digest, mac = _auth_fields("POST", "/execute", b"{}")
        base = {"Host": "127.0.0.1:5055", "X-Metallix-Ts": ts, "X-Metallix-Nonce": nonce, "X-Metallix-Mac": mac,
                "X-Metallix-Body-Sha256": digest, "Content-Type": "application/json"}
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
               {"X-Metallix-Body-Sha256": None}, {"X-Metallix-Body-Sha256": "0" * 63},
               {"X-Metallix-Ts": "abc"}, {"X-Metallix-Ts": "-5"}, {"X-Metallix-Nonce": "0" * 31},
               {"X-Metallix-Nonce": "A" * 32}, {"X-Metallix-Mac": "0" * 63}, {"X-Metallix-Mac": "Z" * 64}]
        for override in bad:
            self.assertEqual(self._check(self._ok(**override))[0], 401, override)
        self.assertEqual(self._check(self._ok() + [("X-Metallix-Nonce", "1" * 32)])[0], 401)  # duplicate
        self.assertEqual(self._check(self._ok(**{"X-Metallix-Ts": str(_now_ms() - 10 ** 6)})),
                         (401, "STALE_REQUEST"))
        # A bearer token alone (the first scheme) is not accepted.
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


class ExecRequestValidationTest(unittest.TestCase):
    def test_shapes(self):
        ok = ipc.validate_exec_request({"script": "python/xrd_peak_deconvolution.py", "payload": {"a": 1}})
        self.assertEqual(ok, ("python/xrd_peak_deconvolution.py", {"a": 1}, [], 15000))
        self.assertEqual(ipc.validate_exec_request({"script": "x.py", "args": None, "timeoutMs": 2500.7})[2:],
                         ([], 2500))
        for req in ([], "x", {"args": "a b"}, {"args": [1]}, {"args": ["a"] * 65}, {"timeoutMs": "1"},
                    {"timeoutMs": 0}, {"timeoutMs": -5}, {"timeoutMs": True}, {"timeoutMs": 10 ** 9}):
            self.assertEqual(_status(ipc.validate_exec_request, req)[0], 400, req)


class StartupConfigTest(unittest.TestCase):
    def test_token_required(self):
        for token in (None, "", "short", "x" * 31):
            with self.assertRaises(SystemExit) as ctx:
                ipc.validate_startup_config("127.0.0.1", token)
            self.assertIn("METALLIX_IPC_TOKEN", str(ctx.exception.code))
        ipc.validate_startup_config("127.0.0.1", "x" * 32)

    def test_only_loopback_hosts(self):
        for host in ("0.0.0.0", "::", "[::]", "", "192.168.1.10", "example.com"):
            with self.assertRaises(SystemExit) as ctx:
                ipc.validate_startup_config(host, TOKEN)
            self.assertIn("only loopback", str(ctx.exception.code))
        for host in ("127.0.0.1", "127.0.0.5", "localhost", "::1", "[::1]"):
            ipc.validate_startup_config(host, TOKEN)
        self.assertFalse(hasattr(ipc, "ALLOW_REMOTE"))

    def test_token_is_neither_in_environment_nor_a_module_global(self):
        self.assertNotIn("METALLIX_IPC_TOKEN", os.environ)
        self.assertFalse(hasattr(ipc, "IPC_TOKEN"))
        module_strings = [v for v in vars(ipc).values() if isinstance(v, str) and len(v) >= 32]
        self.assertNotIn(TOKEN, module_strings)

    def test_pool_start_method_is_a_fresh_interpreter(self):
        ctx = ipc._pool_mp_context()
        if os.name == "nt":
            self.assertEqual(ctx.get_start_method(), "spawn")
        elif "forkserver" in __import__("multiprocessing").get_all_start_methods():
            self.assertEqual(ctx.get_start_method(), "forkserver")

    def test_worker_guard_recognises_the_main_script_reimport(self):
        # The real proof is ServiceIntegrationTest (exactly one warm-up per daemon); this pins the
        # two conditions under which parent_process() is still None during the re-import.
        self.assertFalse(ipc._is_pool_worker_process())
        with mock.patch.object(ipc, "__name__", "__mp_main__"):
            self.assertTrue(ipc._is_pool_worker_process())
        proc = __import__("multiprocessing").current_process()
        with mock.patch.object(proc, "_inheriting", True, create=True):
            self.assertTrue(ipc._is_pool_worker_process())


class PoolTimeoutTest(unittest.TestCase):
    def test_timed_out_running_job_is_killed_when_alone(self):
        reg = ipc.ConcurrentModuleRegistry(ipc.SCRIPT_DIR, num_workers=1)
        try:
            self.assertEqual(reg.prewarm_pool(), 1)
            old_procs = list(reg.pool._processes.values())
            future = reg.pool.submit(ipc._worker_noop, 60)
            time.sleep(1.0)  # running, not cancellable
            with reg.stats_lock:
                reg.active_jobs = 1
            self.assertEqual(reg._abandon(future), "worker terminated and pool recycled")
            for proc in old_procs:
                proc.join(15)
                self.assertFalse(proc.is_alive())
            self.assertIsNotNone(reg.pool)
            self.assertIsInstance(reg.pool.submit(ipc._worker_noop, 0).result(timeout=120), int)
        finally:
            reg.shutdown()

    def test_abandon_cancels_pending_and_leaves_shared_pool_alone(self):
        reg = object.__new__(ipc.ConcurrentModuleRegistry)
        reg.stats_lock = threading.Lock()
        pending = mock.Mock()
        pending.cancel.return_value = True
        self.assertEqual(reg._abandon(pending), "job cancelled before it started")
        running = mock.Mock()
        running.cancel.return_value = False
        reg.active_jobs = 3
        reg._terminate_workers = mock.Mock()
        self.assertEqual(reg._abandon(running), "job left running: 2 other job(s) share the pool")
        reg._terminate_workers.assert_not_called()

    def test_worker_death_mid_job_is_not_rerun(self):
        reg = object.__new__(ipc.ConcurrentModuleRegistry)
        reg.script_dir = str(HERE)
        reg.stats_lock = threading.Lock()
        reg.fallback_lock = threading.Lock()
        reg.request_count = 0
        reg.active_jobs = 0
        reg.total_duration_ms = 0.0
        reg.compiled_code = {}
        future = mock.Mock()
        future.result.side_effect = ipc.BrokenProcessPool("worker died")
        reg.pool = mock.Mock()
        reg.pool.submit.return_value = future
        reg._init_pool = mock.Mock()
        with mock.patch.object(ipc, "_worker_run_script") as in_process:
            res = reg.execute_script("python/xrd_peak_deconvolution.py", {"element": "Fe"})
        self.assertEqual(res["exitCode"], 1)
        self.assertIn("not re-run", res["stderr"])
        self.assertEqual(reg.pool.submit.call_count, 1)
        in_process.assert_not_called()


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


def _raw_request(port, method, path, headers, body=None, host="127.0.0.1"):
    conn = http.client.HTTPConnection(host, port, timeout=120)
    conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
    data = body.encode("utf-8") if isinstance(body, str) else body
    if data is not None and "Content-Length" not in headers:
        headers = dict(headers, **{"Content-Length": str(len(data))})
    for key, value in headers.items():
        conn.putheader(key, value)
    conn.endheaders(data)
    res = conn.getresponse()
    raw = res.read()
    meta = {"acao": res.getheader("Access-Control-Allow-Origin"), "mac": res.getheader("X-Metallix-Mac"),
            "digest": res.getheader("X-Metallix-Body-Sha256")}
    conn.close()
    try:
        parsed = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        parsed = raw.decode("utf-8", "replace")
    return res.status, parsed, meta, raw


def _signed(port, method, path, body, token=TOKEN, host=None, ctype="application/json", ts=None, nonce=None,
            sign_body=None):
    data = body.encode("utf-8") if isinstance(body, str) else (body or b"")
    signed = data if sign_body is None else sign_body.encode("utf-8")
    ts, nonce, digest, mac = _auth_fields(method, path, signed, token=token, ts=ts, nonce=nonce)
    headers = {"Host": host or f"127.0.0.1:{port}", "X-Metallix-Ts": ts, "X-Metallix-Nonce": nonce,
               "X-Metallix-Body-Sha256": digest, "X-Metallix-Mac": mac}
    if ctype:
        headers["Content-Type"] = ctype
    return headers


def _response_ok(test, headers, status, meta, raw):
    test.assertEqual(meta["digest"], ipc.body_digest(raw))
    test.assertEqual(meta["mac"], ipc.response_mac(TOKEN, headers["X-Metallix-Nonce"], status, len(raw), meta["digest"]))


def _attack_matrix(port, traversal_script="python/../../outside/pwn.py"):
    """(name, method, path, headers, body, expected status) for attacker-shaped requests (signed fresh)."""
    host = f"127.0.0.1:{port}"
    traversal = json.dumps({"script": traversal_script, "payload": {}})
    legit = json.dumps({"script": "python/xrd_peak_deconvolution.py", "payload": {"element": "Fe"}})

    def s(body, **kw):
        return _signed(port, "POST", "/execute", body, **kw)

    swapped = s(legit)  # signed for `legit`, body below is the traversal (same length is not needed:
    return [            # the length is covered by the MAC as well)
        ("cross-origin text/plain POST (browser)", "POST", "/execute",
         {"Host": host, "Origin": "https://evil.example", "Content-Type": "text/plain"}, traversal, 403),
        ("DNS rebinding Host", "POST", "/execute", s(legit, host=f"evil.example:{port}"), legit, 403),
        ("Origin even when signed", "POST", "/execute", dict(s(legit), Origin="https://evil.example"), legit, 403),
        ("no authentication", "POST", "/execute", {"Host": host, "Content-Type": "application/json"}, legit, 401),
        ("old bearer token scheme", "POST", "/execute",
         {"Host": host, "Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"}, legit, 401),
        ("signed with the wrong token", "POST", "/execute", s(legit, token="0" * 64), legit, 401),
        ("signed head, body swapped for traversal", "POST", "/execute", swapped, traversal, 401),
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
         s(json.dumps({"script": "python/xrd_peak_deconvolution.py", "args": "-c x"})),
         json.dumps({"script": "python/xrd_peak_deconvolution.py", "args": "-c x"}), 400),
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
            status, parsed, meta, _ = _raw_request(self.port, method, path, headers, body)
            self.assertEqual(status, expected, (name, parsed))
            self.assertIsNone(meta["acao"], name)
        self.assertEqual(self.reg.calls, [])

    def test_legit_request_reaches_registry_and_response_is_signed(self):
        body = json.dumps({"script": "python/xrd_peak_deconvolution.py", "payload": {"element": "Fe"}, "id": 7})
        headers = _signed(self.port, "POST", "/execute", body, host=f"localhost:{self.port}",
                          ctype="application/json; charset=utf-8")
        status, parsed, meta, raw = _raw_request(self.port, "POST", "/execute", headers, body)
        self.assertEqual((status, parsed["stdout"], parsed["id"], meta["acao"]), (200, "stub-ran", 7, None))
        _response_ok(self, headers, 200, meta, raw)
        self.assertEqual(self.reg.calls, [("python/xrd_peak_deconvolution.py", {"element": "Fe"}, [], 15000)])
        status, parsed, _, _ = _raw_request(self.port, "POST", "/execute", headers, body)
        self.assertEqual((status, parsed["code"]), (401, "REPLAYED_REQUEST"))
        self.assertEqual(len(self.reg.calls), 1)
        get_headers = _signed(self.port, "GET", "/status", b"", ctype=None)
        status, parsed, meta, raw = _raw_request(self.port, "GET", "/status", get_headers)
        self.assertEqual((status, parsed), (200, {"status": "online"}))
        _response_ok(self, get_headers, 200, meta, raw)

    def test_signed_head_with_wrong_body_bytes_is_400_and_not_run(self):
        body = json.dumps({"script": "python/xrd_peak_deconvolution.py"})
        evil = body.replace("xrd_peak_deconvolution", "xrd_peak_deconvolutioN")  # same length, different bytes
        self.assertEqual(len(body), len(evil))
        headers = _signed(self.port, "POST", "/execute", body)
        status, parsed, meta, raw = _raw_request(self.port, "POST", "/execute", headers, evil)
        self.assertEqual((status, parsed["code"]), (400, "BODY_HASH_MISMATCH"))
        _response_ok(self, headers, 400, meta, raw)  # authenticated head: the refusal is signed
        self.assertEqual(self.reg.calls, [])

    def test_unauthenticated_rejections_are_not_signed(self):
        status, _, meta, _ = _raw_request(self.port, "POST", "/execute",
                                          _signed(self.port, "POST", "/execute", "{}", token="0" * 64), "{}")
        self.assertEqual((status, meta["mac"]), (401, None))

    def test_warmup_requires_auth(self):
        status, _, _, _ = _raw_request(self.port, "POST", "/warmup",
                                       {"Host": f"127.0.0.1:{self.port}", "Content-Type": "application/json"}, "{}")
        self.assertEqual(status, 401)
        self.assertEqual(self.reg.calls, [])

    def test_oversized_declared_body_is_413_before_reading(self):
        headers = dict(_signed(self.port, "POST", "/execute", b"{}"), **{"Content-Length": str(ipc.MAX_BODY_BYTES + 1)})
        status, parsed, _, _ = _raw_request(self.port, "POST", "/execute", headers, None)
        self.assertEqual((status, parsed["code"]), (413, "PAYLOAD_TOO_LARGE"))

    def test_preauth_memory_stays_bounded_against_large_declared_bodies(self):
        """An attacker without the token declares 64 MiB and holds the connection: the head MAC
        fails before any body read, so nothing near the declared size is ever allocated."""
        import tracemalloc
        tracemalloc.start()
        try:
            base = tracemalloc.get_traced_memory()[0]
            conns = []
            for _ in range(4):
                s = socket.create_connection(("127.0.0.1", self.port), timeout=20)
                h = _signed(self.port, "POST", "/execute", b"x")
                h["X-Metallix-Mac"] = "0" * 64
                head = (f"POST /execute HTTP/1.1\r\nContent-Length: {ipc.MAX_BODY_BYTES}\r\n"
                        + "".join(f"{k}: {v}\r\n" for k, v in h.items()) + "\r\n")
                s.sendall(head.encode() + b"x")
                conns.append(s)
            replies = [s.recv(100).split(b"\r\n", 1)[0] for s in conns]
            peak = tracemalloc.get_traced_memory()[1] - base
        finally:
            tracemalloc.stop()
            for s in conns:
                s.close()
        self.assertTrue(all(r.endswith(b"401 Unauthorized") for r in replies), replies)
        self.assertLess(peak, 4 * 2 ** 20, f"peak traced allocation {peak} bytes")
        self.assertEqual(self.reg.calls, [])

    def test_unauthenticated_connections_are_bounded_and_time_boxed(self):
        with mock.patch.object(ipc, "PREAUTH_DEADLINE_S", 1.5):
            idle = [socket.create_connection(("127.0.0.1", self.port), timeout=20) for _ in range(ipc.PREAUTH_SLOTS)]
            try:
                time.sleep(0.3)
                extra = socket.create_connection(("127.0.0.1", self.port), timeout=20)
                t0 = time.time()
                self.assertEqual(extra.recv(10), b"")  # no slot left: closed without reading
                self.assertLess(time.time() - t0, 1.0)
                extra.close()
                t0 = time.time()
                for s in idle:  # held open with nothing sent: cut at the pre-auth deadline
                    self.assertEqual(s.recv(10), b"")
                self.assertLess(time.time() - t0, 6)
            finally:
                for s in idle:
                    s.close()
            # Slots are released: a legit request goes through again.
            body = json.dumps({"script": "python/xrd_peak_deconvolution.py"})
            status, _, _, _ = _raw_request(self.port, "POST", "/execute",
                                           _signed(self.port, "POST", "/execute", body), body)
            self.assertEqual(status, 200)

    def test_ipv6_loopback(self):
        try:
            httpd6 = ipc.make_http_server("::1", 0, TOKEN, self.reg)
        except OSError as exc:
            self.skipTest(f"IPv6 loopback unavailable: {exc}")
        port6 = httpd6.server_address[1]
        threading.Thread(target=httpd6.serve_forever, daemon=True).start()
        try:
            body = json.dumps({"script": "python/xrd_peak_deconvolution.py"})
            headers = _signed(port6, "POST", "/execute", body, host=f"[::1]:{port6}")
            status, parsed, meta, raw = _raw_request(port6, "POST", "/execute", headers, body, host="::1")
            self.assertEqual((status, parsed["stdout"]), (200, "stub-ran"))
            _response_ok(self, headers, 200, meta, raw)
        finally:
            httpd6.shutdown()
            httpd6.server_close()


def _unix_send(path, request=None, token=TOKEN, ts=None, nonce=None, raw=None, body_override=None, head_override=None):
    """Sends one v2 frame (or raw bytes); returns (head dict, body bytes, nonce)."""
    if raw is None:
        body = json.dumps(request).encode("utf-8")
        ts, nonce, digest, mac = _auth_fields("UNIX", "/", body, token=token, ts=ts, nonce=nonce)
        head = {"v": 2, "ts": ts, "nonce": nonce, "len": len(body), "sha256": digest, "mac": mac}
        head.update(head_override or {})
        raw = json.dumps(head).encode("utf-8") + b"\n" + (body if body_override is None else body_override)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(20)
        s.connect(path)
        s.sendall(raw)
        buf = b""
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
    head_line, _, rest = buf.partition(b"\n")
    reply = json.loads(head_line)
    return reply, rest[:reply["len"]], nonce


@unittest.skipIf(os.name == "nt" or not hasattr(socket, "AF_UNIX"), "UNIX socket channel is POSIX only")
class UnixSocketTest(unittest.TestCase):
    def setUp(self):
        self.path, self.private_dir = ipc.create_socket_path(None)
        self.reg = _StubRegistry()
        self.server = ipc.UnixIPCServer(self.path, self.reg, TOKEN, self.private_dir)
        self.server.start()

    def tearDown(self):
        self.server.stop()

    def _verified(self, reply, body, nonce):
        self.assertEqual(reply["sha256"], ipc.body_digest(body))
        self.assertEqual(reply["mac"], ipc.response_mac(TOKEN, nonce, reply["status"], len(body), reply["sha256"]))
        return json.loads(body)

    def test_socket_and_directory_are_owner_only(self):
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.private_dir).st_mode), 0o700)
        self.server.stop()
        self.assertFalse(os.path.exists(self.private_dir))

    def test_authentication_required_and_responses_signed(self):
        req = {"action": "execute", "script": "python/xrd_peak_deconvolution.py", "payload": {}}
        bad = [dict(head_override={"mac": "0" * 64}), dict(token="0" * 64), dict(ts=str(_now_ms() - 10 ** 6)),
               dict(head_override={"v": 1}),
               dict(raw=(json.dumps({"token": TOKEN, **req}) + "\n").encode())]
        for kw in bad:
            reply, _, _ = _unix_send(self.path, req, **kw)
            self.assertEqual(reply["status"], 401, kw)
            self.assertNotIn("mac", reply)
        self.assertEqual(self.reg.calls, [])
        nonce = secrets.token_hex(16)
        reply, body, _ = _unix_send(self.path, req, nonce=nonce)
        self.assertEqual(reply["status"], 200)
        self.assertEqual(self._verified(reply, body, nonce)["stdout"], "stub-ran")
        reply, _, _ = _unix_send(self.path, req, nonce=nonce)  # replay
        self.assertEqual(reply["status"], 401)
        self.assertEqual(len(self.reg.calls), 1)

    def test_body_swapped_under_signed_head_is_refused(self):
        req = {"action": "execute", "script": "python/xrd_peak_deconvolution.py"}
        body = json.dumps(req).encode()
        swapped = body.replace(b"xrd_peak_deconvolution", b"xrd_peak_deconvolutioN")
        reply, rbody, nonce = _unix_send(self.path, req, body_override=swapped)
        self.assertEqual(reply["status"], 400)
        self.assertEqual(self._verified(reply, rbody, nonce)["code"], "BODY_HASH_MISMATCH")
        self.assertEqual(self.reg.calls, [])

    def test_traversal_rejected_on_socket_with_signed_4xx(self):
        reply, body, nonce = _unix_send(self.path, {"action": "execute", "script": "python/../../x/pwn.py"})
        self.assertEqual(reply["status"], 400)
        self.assertEqual(self._verified(reply, body, nonce)["code"], "INVALID_SCRIPT_PATH")
        self.assertEqual(self.reg.calls, [])

    def test_oversized_head_and_declared_body_are_refused_unread(self):
        reply, _, _ = _unix_send(self.path, raw=b"x" * (ipc.MAX_HEAD_BYTES + 10))
        self.assertEqual(reply["status"], 413)
        reply, _, _ = _unix_send(self.path, {"action": "ping"}, head_override={"len": ipc.MAX_BODY_BYTES + 1})
        self.assertEqual(reply["status"], 413)

    def test_unauthenticated_connections_are_bounded_and_time_boxed(self):
        with mock.patch.object(ipc, "PREAUTH_DEADLINE_S", 1.5):
            idle = []
            try:
                for _ in range(ipc.PREAUTH_SLOTS):
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.settimeout(20)
                    s.connect(self.path)
                    idle.append(s)
                time.sleep(0.3)
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as extra:
                    extra.settimeout(20)
                    extra.connect(self.path)
                    self.assertEqual(extra.recv(10), b"")
                t0 = time.time()
                for s in idle:
                    reply = s.recv(4096)
                    self.assertIn(b'"status": 408', reply)
                self.assertLess(time.time() - t0, 6)
            finally:
                for s in idle:
                    s.close()


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
    if os.name != "nt":
        # The daemon runs in its own session: also stop anything it left behind (forkserver, workers)
        # so no straggler keeps the stdout/stderr pipes open.
        try:
            os.killpg(proc.pid, 9)
        except OSError:
            pass
    for stream in (proc.stdin, proc.stdout, proc.stderr):
        try:
            stream.close()
        except (OSError, ValueError, AttributeError):
            pass


def _spawn_service(extra_env, cwd, stdin=subprocess.DEVNULL):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", METALLIX_IPC_WORKERS="2")
    for key in ("METALLIX_IPC_TOKEN", "METALLIX_IPC_ALLOW_REMOTE", "METALLIX_IPC_PORT", "METALLIX_IPC_SOCK",
                "METALLIX_IPC_HOST", "METALLIX_IPC_HTTP", "METALLIX_IPC_STDIN_WATCH"):
        env.pop(key, None)
    env.update(extra_env)
    return subprocess.Popen([sys.executable, "-B", str(HERE / "persistent_ipc_service.py")], cwd=str(cwd),
                            env=env, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace", start_new_session=(os.name != "nt"))


class ServiceIntegrationTest(unittest.TestCase):
    """Starts the real service (HTTP enabled; cwd = repo root, as server/processOrchestrator.ts does)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.outside = Path(cls.tmp) / "outside"
        cls.outside.mkdir()
        cls.marker = cls.outside / "PWNED.txt"
        (cls.outside / "pwn.py").write_text(
            "import pathlib\npathlib.Path(__file__).with_name('PWNED.txt').write_text('x')\nprint('PWNED')\n",
            encoding="utf-8")
        cls.proc = _spawn_service({"METALLIX_IPC_TOKEN": TOKEN, "METALLIX_IPC_HTTP": "1"}, REPO)
        cls.err_lines = []
        threading.Thread(target=lambda: cls.err_lines.extend(cls.proc.stderr), daemon=True).start()
        try:
            line = _read_line(cls.proc.stdout, 300)
        except AssertionError:
            _kill_tree(cls.proc)
            raise
        if not line:
            time.sleep(0.5)
            _kill_tree(cls.proc)
            raise AssertionError(f"service did not start: {''.join(cls.err_lines)[-2000:]}")
        cls.ready = json.loads(line)
        cls.port = cls.ready["httpPort"]

    @classmethod
    def tearDownClass(cls):
        _kill_tree(cls.proc)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_ready_message_announces_actual_channels_and_no_token(self):
        self.assertEqual(self.ready["status"], "ready")
        self.assertEqual(self.ready["protocol"], "metallix-ipc-v2")
        self.assertTrue(self.ready["httpActive"])
        self.assertIsInstance(self.port, int)
        self.assertGreater(self.port, 0)
        self.assertEqual(self.ready["http"], f"http://127.0.0.1:{self.port}")
        self.assertEqual(self.ready["workersStarted"], 2)  # pool started before readiness
        self.assertNotIn(TOKEN, json.dumps(self.ready))
        if os.name != "nt":
            self.assertTrue(self.ready["unixSocketActive"])
            sock_dir = os.path.dirname(self.ready["unixSocket"])
            self.assertEqual(stat.S_IMODE(os.stat(sock_dir).st_mode), 0o700)
        else:
            self.assertFalse(self.ready["unixSocketActive"])

    def test_attacks_fail_legit_request_succeeds_and_warm_up_ran_once(self):
        rel = os.path.relpath(self.outside / "pwn.py", REPO).replace(os.sep, "/")
        for name, method, path, headers, body, expected in _attack_matrix(self.port, "python/../" + rel):
            status, parsed, meta, _ = _raw_request(self.port, method, path, headers, body)
            self.assertEqual(status, expected, (name, parsed))
            self.assertIsNone(meta["acao"], name)
            self.assertFalse(self.marker.exists(), name)
        legit = json.loads((HERE / "golden" / "phase6b" / "xrd_peak_deconvolution" / "pv_single_no_ka2.json")
                           .read_text(encoding="utf-8"))["input"]
        body = json.dumps({"script": "python/xrd_peak_deconvolution.py", "payload": legit, "timeoutMs": 60000})
        headers = _signed(self.port, "POST", "/execute", body)
        status, parsed, meta, raw = _raw_request(self.port, "POST", "/execute", headers, body)
        self.assertEqual((status, meta["acao"]), (200, None), parsed)
        _response_ok(self, headers, 200, meta, raw)
        self.assertEqual(parsed["exitCode"], 0, parsed.get("stderr"))
        self.assertEqual(parsed["concurrency"], "process_pool")
        self.assertTrue(json.loads(parsed["stdout"])["success"])
        self.assertFalse(self.marker.exists())
        # The module warm-up runs once in the daemon, never again in a pool worker or forkserver.
        time.sleep(0.5)
        self.assertEqual(sum("Warming up" in line for line in self.err_lines), 1, "".join(self.err_lines)[-3000:])


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

    def test_refuses_non_loopback_and_wildcard_hosts(self):
        for host in ("0.0.0.0", "192.0.2.1"):
            self._expect_refusal({"METALLIX_IPC_TOKEN": TOKEN, "METALLIX_IPC_HOST": host,
                                  "METALLIX_IPC_ALLOW_REMOTE": "1"}, "only loopback")

    @unittest.skipIf(os.name == "nt", "UNIX socket is POSIX only")
    def test_refuses_socket_in_shared_tmp(self):
        code, out, err = self._run_to_exit({"METALLIX_IPC_TOKEN": TOKEN,
                                            "METALLIX_IPC_SOCK": f"/tmp/metallix-test-{os.getpid()}.sock"})
        self.assertNotEqual(code, 0)
        self.assertNotIn('"ready"', out)
        self.assertIn("METALLIX_IPC_SOCK", err)

    @unittest.skipIf(os.name == "nt", "the HTTP listener is the only channel on Windows")
    def test_posix_default_is_unix_socket_only(self):
        proc = _spawn_service({"METALLIX_IPC_TOKEN": TOKEN}, REPO)
        try:
            ready = json.loads(_read_line(proc.stdout, 300))
        finally:
            _kill_tree(proc)
        self.assertTrue(ready["unixSocketActive"])
        self.assertFalse(ready["httpActive"])
        self.assertIsNone(ready["httpPort"])

    def test_squatted_fixed_port_is_never_announced(self):
        with socket.socket() as squatter:
            squatter.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            squatter.bind(("127.0.0.1", 0))
            squatter.listen(5)
            port = squatter.getsockname()[1]
            env = {"METALLIX_IPC_TOKEN": TOKEN, "METALLIX_IPC_PORT": str(port), "METALLIX_IPC_HTTP": "1"}
            if os.name == "nt":
                # Exclusive bind fails and HTTP is the only channel: the daemon exits.
                code, out, err = self._run_to_exit(env)
                self.assertNotEqual(code, 0)
                self.assertNotIn('"ready"', out)
                self.assertIn("no IPC channel", err)
                self.assertNotIn("Warming up", err)  # no pool was created for a launch that failed
            else:
                proc = _spawn_service(env, REPO)
                try:
                    ready = json.loads(_read_line(proc.stdout, 300))
                finally:
                    _kill_tree(proc)
                self.assertFalse(ready["httpActive"])
                self.assertIsNone(ready["httpPort"])
                self.assertTrue(ready["unixSocketActive"])

    def test_exits_and_cleans_up_when_the_supervisor_is_gone(self):
        proc = _spawn_service({"METALLIX_IPC_TOKEN": TOKEN, "METALLIX_IPC_STDIN_WATCH": "1"}, REPO,
                              stdin=subprocess.PIPE)
        try:
            ready = json.loads(_read_line(proc.stdout, 300))
            proc.stdin.close()  # what the OS does when the Node process dies
            proc.wait(60)
            self.assertEqual(proc.returncode, 0)
            if ready.get("unixSocket"):
                self.assertFalse(os.path.exists(os.path.dirname(ready["unixSocket"])))
        finally:
            _kill_tree(proc)


if __name__ == "__main__":
    unittest.main()
