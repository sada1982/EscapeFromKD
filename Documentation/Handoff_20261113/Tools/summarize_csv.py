import argparse
import csv
import gzip
import json
import math
from pathlib import Path
import statistics

parser = argparse.ArgumentParser()
parser.add_argument("csv_file")
parser.add_argument("--skip", type=int, default=0)
parser.add_argument("--out")
args = parser.parse_args()
path = Path(args.csv_file)
opener = gzip.open if path.suffix == ".gz" else open
with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
    rows = list(csv.reader(stream))
headers = next((row for row in reversed(rows) if "FrameTime" in row), None)
if headers is None:
    raise RuntimeError("No FrameTime header found")
records = []
for row in rows:
    if not row or len(row) > len(headers) or row[0] == "EVENTS" or row[0].startswith("["):
        continue
    values = {}
    for name, value in zip(headers, row):
        try:
            number = float(value)
            if math.isfinite(number):
                values[name] = number
        except ValueError:
            pass
    if values.get("FrameTime", 0) > 0:
        records.append(values)
records = records[args.skip:]
if not records:
    raise RuntimeError("No positive FrameTime samples after skip")

def percentile(values, proportion):
    ordered = sorted(values)
    index = (len(ordered) - 1) * proportion
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)

frame_times = [row["FrameTime"] for row in records]
slow_count = max(1, math.ceil(len(frame_times) * 0.01))
slowest = sorted(frame_times, reverse=True)[:slow_count]
summary = {
    "file": str(path.resolve()),
    "sample_count": len(records),
    "skip_positive_frame_samples": args.skip,
    "mean_fps": 1000 / statistics.mean(frame_times),
    "one_percent_low_fps": 1000 / statistics.mean(slowest),
    "minimum_instantaneous_fps": 1000 / max(frame_times),
    "frames_over_16_667ms_percent": 100 * sum(value > 1000 / 60 for value in frame_times) / len(frame_times),
    "columns": {},
}
names = [
    "FrameTime", "GameThreadTime", "RenderThreadTime", "GPUTime", "RHIThreadTime",
    "GameThreadTime_CriticalPath", "RenderThreadTime_CriticalPath",
    "RHI/DrawCalls", "RHI/PrimitivesDrawn",
    "GPUMem/LocalBudgetMB", "GPUMem/LocalUsedMB",
    "GPUMem/SystemBudgetMB", "GPUMem/SystemUsedMB",
]
names += [name for name in headers if name.startswith("GPU/") and name not in names]
for name in names:
    values = [row.get(name, 0) for row in records] if name in headers else []
    if name.startswith("GPUMem/") or name in ("GPUTime", "RHIThreadTime"):
        values = [value for value in values if value > 0]
    if values:
        summary["columns"][name] = {
            "samples": len(values),
            "positive_samples": sum(value > 0 for value in values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "p95": percentile(values, 0.95),
            "p99": percentile(values, 0.99),
            "max": max(values),
        }
output = json.dumps(summary, ensure_ascii=False, indent=2)
if args.out:
    Path(args.out).write_text(output, encoding="utf-8")
print(output)

