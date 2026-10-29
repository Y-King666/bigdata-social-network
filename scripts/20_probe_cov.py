"""探查 Weibo-COV 推文包（tar.gz）的结构与规模。

两个包都是 GB 级，且 gzip 不可切分、tar 不能直接给 Spark 读取。脚本采用有界抽样：
确认字段数是否稳定、中文正文里有没有裸逗号导致错位、origin_weibo 与 geo_info
的填充率，用于选择解析与入库方案。
"""

import gzip
import os
import sys
import time
from collections import Counter

import spark_env

DATA_DIR = spark_env.DATA_DIR
SAMPLE_BYTES = 400 * 1024 * 1024
TAR_BLOCK = 512
EXPECTED_FIELDS = 10


def tar_size(header: bytes) -> int:
    """tar 的 size 字段：小文件用八进制，超过 8GB 时改用 base-256。"""
    raw = header[124:136]
    if raw[0] & 0x80:
        return int.from_bytes(raw, "big") & ((1 << 95) - 1)
    try:
        return int(raw.rstrip(b"\x00 ").decode("ascii"), 8)
    except ValueError:
        return -1


def probe(filename: str) -> None:
    path = os.path.join(DATA_DIR, filename)
    print("=" * 72, flush=True)
    print(f"{filename}  {os.path.getsize(path):,} bytes", flush=True)

    with gzip.open(path, "rb") as f:
        header = f.read(TAR_BLOCK)
        entry = header[:100].rstrip(b"\x00").decode("utf-8", "ignore")
        total = tar_size(header)
        print(f"  tar entry: {entry}   uncompressed size: {total:,} bytes "
              f"({total / 1024 ** 3:.2f} GB)", flush=True)

        t0 = time.time()
        consumed = 0
        rows = 0
        field_counts = Counter()
        has_origin = 0
        has_geo = 0
        repost_examples = []
        buf = b""
        while consumed < SAMPLE_BYTES:
            chunk = f.read(1 << 22)
            if not chunk:
                break
            consumed += len(chunk)
            buf += chunk
            *lines, buf = buf.split(b"\n")
            for line in lines:
                if not line:
                    continue
                rows += 1
                parts = line.split(b",")
                field_counts[len(parts)] += 1
                if len(parts) == EXPECTED_FIELDS:
                    if parts[8].strip():
                        has_origin += 1
                        if len(repost_examples) < 3:
                            repost_examples.append(line.decode("utf-8", "ignore")[:300])
                    if parts[9].strip():
                        has_geo += 1
        elapsed = time.time() - t0

    print(f"  抽样 {consumed / 1024 ** 3:.2f} GB 解压后字节，用时 {elapsed:.1f}s "
          f"({consumed / elapsed / 1024 ** 2:.0f} MB/s)", flush=True)
    print(f"  抽样行数: {rows:,}", flush=True)
    print(f"  字段数分布: {dict(field_counts.most_common(6))}", flush=True)
    malformed = rows - field_counts[EXPECTED_FIELDS]
    print(f"  字段数异常行: {malformed:,} ({malformed / rows:.3%})", flush=True)
    print(f"  origin_weibo 非空: {has_origin:,} ({has_origin / rows:.2%})", flush=True)
    print(f"  geo_info 非空    : {has_geo:,} ({has_geo / rows:.2%})", flush=True)
    if repost_examples:
        print("  转发样本:", flush=True)
        for ex in repost_examples:
            print("   ", ex, flush=True)


def main() -> int:
    for filename in ("weibo-cov.csv.tar.gz", "all-geo.csv.tar.gz"):
        probe(filename)
    print("\nPROBE_COV_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
