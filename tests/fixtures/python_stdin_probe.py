"""Test probe for server/processOrchestrator.ts executeViaAdHocSpawn: reports the interpreter's UTF-8 mode and the
stdin text as decoded by the DEFAULT text-mode stdin (not stdin.buffer), ASCII-escaped on stdout."""
import json
import sys

text = sys.stdin.read()
print(json.dumps({"utf8Mode": sys.flags.utf8_mode, "stdinEncoding": sys.stdin.encoding, "text": text}))
