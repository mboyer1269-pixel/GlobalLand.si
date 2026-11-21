import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser(description="Run the offline catalogue worked-example QA")
parser.add_argument("--images", type=Path)
args = parser.parse_args()
base = Path(__file__).resolve().parent
images = args.images.resolve() if args.images else base / "fixtures/before-images.csv"
with tempfile.TemporaryDirectory() as workspace:
    output = Path(workspace) / "after.csv"
    report = Path(workspace) / "report.json"
    result = subprocess.run([sys.executable, str(base / "transform.py"), "--variants", str(base / "fixtures/before-variants.csv"), "--images", str(images), "--out", str(output), "--report", str(report)])
    if result.returncode:
        if report.is_file():
            for finding in json.loads(report.read_text())["errors"]:
                print(finding, file=sys.stderr)
        sys.exit(result.returncode)
    if output.read_bytes() != (base / "fixtures/after-shopify.csv").read_bytes():
        sys.exit("Generated CSV differs from the worked example reference")
    sys.exit(subprocess.run([sys.executable, str(base / "verify_example.py"), str(base / "fixtures/before-variants.csv"), str(images), str(output)], cwd=base).returncode)
