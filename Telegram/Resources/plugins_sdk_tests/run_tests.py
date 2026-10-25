# Runs the plugin SDK tests with a fake native module, no app build needed.
# Usage: python run_tests.py  (Python 3.11, same as the bundled runtime)

import os
import subprocess
import sys

here = os.path.dirname(os.path.abspath(__file__))
sdk = os.path.join(here, "..", "plugins_sdk")
fixtures = os.path.join(here, "fixtures")
runs = [
    ["test_sdk.py", sdk],
    ["check_plugin.py", sdk, os.path.join(fixtures, "test_plugin.plugin")],
    ["test_hooks.py", sdk, os.path.join(here, "..", "..", "SourceFiles", "mtproto", "scheme", "api.tl")],
    ["test_lme.py", sdk, os.path.join(fixtures, "local_message_editor.plugin")],
]
failed = 0
for script, *args in runs:
    code = subprocess.call(
        [sys.executable, "-I", "-B", "-X", "utf8", os.path.join(here, script), *args])
    failed += code != 0
sys.exit(failed)
