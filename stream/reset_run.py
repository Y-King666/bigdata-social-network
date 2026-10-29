"""Reset the live replay to its start point.

Run id increments so the replay and the stream job both rebuild their state.
The start time is fixed at the configured default (2020-01-22 00:00:00).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config


def main():
    ctl = config.read_control()
    ctl["schema"] = config.CONTROL_SCHEMA
    ctl["run_id"] = int(ctl.get("run_id") or 0) + 1
    ctl["start_time"] = config.DEFAULT_START
    ctl["paused"] = False
    config.write_json(config.CONTROL, ctl)
    try:
        os.remove(config.ACK)
    except OSError:
        pass
    print("run_id =", ctl["run_id"])
    print("start_time =", ctl["start_time"])


if __name__ == "__main__":
    main()
