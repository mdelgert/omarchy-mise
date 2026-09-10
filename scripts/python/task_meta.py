#!/usr/bin/env python3
import json
import os
import platform
import sys

payload = {
    "implementation": "python",
    "python_version": platform.python_version(),
    "executable": sys.executable,
    "task_name": os.getenv("MISE_TASK_NAME"),
    "task_dir": os.getenv("MISE_TASK_DIR"),
    "project_root": os.getenv("MISE_PROJECT_ROOT"),
    "original_cwd": os.getenv("MISE_ORIGINAL_CWD"),
    "cwd": os.getcwd(),
    "platform": platform.platform(),
}

print(json.dumps(payload, indent=2))
