"""确认 Weibo-COV 推文的 CSV 能否被标准解析器正确读出。

裸分割时有约 4% 的行字段数超过 10。脚本区分"正文中未加引号的逗号"与
"地理字段整体加引号"两种情况，避免入库时字段错位。
"""

import gzip
import os
import sys

import pandas as pd

import spark_env

DATA_DIR = spark_env.DATA_DIR
EXTRACT_BYTES = 64 * 1024 * 1024
TAR_BLOCK = 512
OUT_PATH = os.path.join(DATA_DIR, "_probe_weibo_cov_sample.csv")


def extract_sample() -> int:
    src = os.path.join(DATA_DIR, "weibo-cov.csv.tar.gz")
    written = 0
    with gzip.open(src, "rb") as fin, open(OUT_PATH, "wb") as fout:
        fin.read(TAR_BLOCK)
        while written < EXTRACT_BYTES:
            chunk = fin.read(1 << 22)
            if not chunk:
                break
            fout.write(chunk)
            written += len(chunk)
    return written


def main() -> int:
    n = extract_sample()
    print(f"extracted {n:,} bytes -> {OUT_PATH}", flush=True)

    with open(OUT_PATH, "rb") as f:
        raw = f.read()
    raw_lines = raw.count(b"\n")
    quoted = raw.count(b'"')
    print(f"raw newlines: {raw_lines:,}   quote chars: {quoted:,}", flush=True)

    wide = []
    for line in raw.split(b"\n"):
        if line.count(b",") > 9 and len(wide) < 4:
            wide.append(line.decode("utf-8", "ignore")[:400])
    print("\n--- 逗号数 > 9 的行样本 ---", flush=True)
    for w in wide:
        print("   ", w, flush=True)

    print("\n--- pandas 标准解析 ---", flush=True)
    try:
        df = pd.read_csv(OUT_PATH, encoding="utf-8", on_bad_lines="warn", low_memory=False)
        print("shape:", df.shape, flush=True)
        print("columns:", list(df.columns), flush=True)
        print(df.head(3).to_string()[:1200], flush=True)
    except Exception as exc:
        print("parse failed:", type(exc).__name__, exc, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
