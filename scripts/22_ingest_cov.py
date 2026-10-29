"""把 Weibo-COV 的 tar.gz 推文包流式转成 Parquet。

两个包解压后合计约 37 GB，磁盘放不下中间 CSV，因此边解压边解析边写 Parquet。
tar 头部 512 字节需要跳过；包尾的 512 字节补零也要靠"已知原始长度"截断，
否则解析器会把填充块当成数据行。
"""

import gzip
import os
import sys
import time

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

import spark_env

DATA_DIR = spark_env.DATA_DIR
TAR_BLOCK = 512
ROWS_PER_FILE = 4_000_000

# tar 的 size 字段对超过 8 GB 的文件改用 base-256 编码，需单独解析。
SOURCES = {
    "weibo_cov": {
        "archive": "weibo-cov.csv.tar.gz",
        "out_dir": os.path.join(DATA_DIR, "cov_posts_parquet"),
    },
    "all_geo": {
        "archive": "all-geo.csv.tar.gz",
        "out_dir": os.path.join(DATA_DIR, "cov_geo_parquet"),
    },
}

COLUMN_TYPES = {
    "_id": pa.string(),
    "user_id": pa.string(),
    "crawl_time": pa.int64(),
    "created_at": pa.string(),
    "like_num": pa.int64(),
    "repost_num": pa.int64(),
    "comment_num": pa.int64(),
    "content": pa.string(),
    "origin_weibo": pa.string(),
    "geo_info": pa.string(),
}


class TarPayload:
    """按已知长度截断的只读流：跳过 tar 头，并丢弃包尾补零。"""

    def __init__(self, fh, skip: int, length: int):
        fh.read(skip)
        self._fh = fh
        self._left = length
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        if self._left <= 0:
            return b""
        if size is None or size < 0:
            size = self._left
        size = min(size, self._left)
        data = self._fh.read(size)
        self._left -= len(data)
        return data

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def writable(self) -> bool:
        return False

    def close(self) -> None:
        self.closed = True


def tar_size(header: bytes) -> int:
    raw = header[124:136]
    if raw[0] & 0x80:
        return int.from_bytes(raw, "big") & ((1 << 95) - 1)
    try:
        return int(raw.rstrip(b"\x00 ").decode("ascii"), 8)
    except ValueError:
        return -1


def ingest(name: str) -> None:
    spec = SOURCES[name]
    src = os.path.join(DATA_DIR, spec["archive"])
    out_dir = spec["out_dir"]
    os.makedirs(out_dir, exist_ok=True)
    for old in os.listdir(out_dir):
        os.remove(os.path.join(out_dir, old))

    print("=" * 72, flush=True)
    print(f"ingest {spec['archive']} -> {out_dir}", flush=True)

    t0 = time.time()
    with gzip.open(src, "rb") as fh:
        header = fh.read(TAR_BLOCK)
        total = tar_size(header)
        print(f"  declared uncompressed size: {total:,} bytes ({total / 1024 ** 3:.2f} GB)", flush=True)

        payload = TarPayload(fh, skip=0, length=total)
        stream = pa.PythonFile(payload, mode="r")
        reader = pacsv.open_csv(
            stream,
            read_options=pacsv.ReadOptions(block_size=1 << 26),
            convert_options=pacsv.ConvertOptions(column_types=COLUMN_TYPES),
        )

        writer = None
        part = 0
        rows_in_part = 0
        total_rows = 0
        last_report = time.time()

        while True:
            try:
                batch = reader.read_next_batch()
            except StopIteration:
                break
            if writer is None:
                writer = pq.ParquetWriter(
                    os.path.join(out_dir, f"part-{part:05d}.parquet"),
                    reader.schema,
                    compression="snappy",
                )
            writer.write_batch(batch)
            total_rows += batch.num_rows
            rows_in_part += batch.num_rows

            if rows_in_part >= ROWS_PER_FILE:
                writer.close()
                writer = None
                part += 1
                rows_in_part = 0

            if time.time() - last_report > 30:
                rate = total_rows / (time.time() - t0)
                print(f"  ... {total_rows:,} rows  ({rate:,.0f} rows/s)", flush=True)
                last_report = time.time()

        if writer is not None:
            writer.close()

    elapsed = time.time() - t0
    size = sum(
        os.path.getsize(os.path.join(out_dir, f))
        for f in os.listdir(out_dir)
    )
    print(f"  DONE rows={total_rows:,}  parts={part + 1}  parquet={size / 1024 ** 3:.2f} GB  "
          f"elapsed={elapsed / 60:.1f} min", flush=True)


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "weibo_cov"
    ingest(which)
    print("INGEST_COV_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
