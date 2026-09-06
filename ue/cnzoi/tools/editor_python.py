"""Run a local script through Epic's Python remote execution on this project."""
import argparse
import json
from pathlib import Path
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("script", type=Path)
args = parser.parse_args()
sys.path.insert(0, "C:/Program Files/Epic Games/UE_5.8/Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python")
import remote_execution

remote = remote_execution.RemoteExecution()
remote.start()
try:
    for _ in range(30):
        nodes = [n for n in remote.remote_nodes if n.get("project_name", "").lower() == "cnzoi"]
        if nodes:
            break
        time.sleep(0.1)
    if len(nodes) != 1:
        raise RuntimeError(f"Expected one cnzoi editor, found {remote.remote_nodes}")
    remote.open_command_connection(nodes[0]["node_id"])
    result = remote.run_command(args.script.read_text(encoding="utf-8"), raise_on_failure=True)
    print(json.dumps(result, ensure_ascii=False))
finally:
    remote.stop()
