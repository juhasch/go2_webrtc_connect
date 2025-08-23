import asyncio
import contextlib
import time
import csv
import argparse
from dataclasses import dataclass
from typing import Optional, Dict, Any

from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.constants import RTC_TOPIC


def _extract_robot_timestamp_seconds(message: Dict[str, Any]) -> Optional[float]:
    """
    Best-effort extraction of a robot-provided timestamp (seconds since epoch) from a message.

    Supports structures like:
    - {"header": {"stamp": {"sec": int, "nanosec": int}}}
    - {"stamp": {"sec": int, "nanosec": int}}
    - {"header": {"stamp": float}} or {"stamp": float}
    Returns None if not found.
    """
    def _get_stamp(container: Dict[str, Any]) -> Optional[Any]:
        if not isinstance(container, dict):
            return None
        if "header" in container and isinstance(container["header"], dict) and "stamp" in container["header"]:
            return container["header"]["stamp"]
        if "stamp" in container:
            return container["stamp"]
        return None

    stamp = _get_stamp(message)
    if stamp is None:
        return None

    if isinstance(stamp, dict):
        sec = stamp.get("sec")
        nsec = stamp.get("nanosec") or stamp.get("nsec")
        if isinstance(sec, (int, float)) and isinstance(nsec, (int, float)):
            return float(sec) + float(nsec) * 1e-9
        if isinstance(sec, (int, float)) and (nsec is None):
            return float(sec)
    if isinstance(stamp, (int, float)):
        return float(stamp)

    return None


@dataclass
class RunningStats:
    count: int = 0
    mean: float = 0.0
    m2: float = 0.0
    min_value: float = float("inf")
    max_value: float = float("-inf")

    def add(self, value: float) -> None:
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2
        if value < self.min_value:
            self.min_value = value
        if value > self.max_value:
            self.max_value = value

    @property
    def variance(self) -> float:
        if self.count < 2:
            return 0.0
        return self.m2 / (self.count - 1)

    @property
    def stddev(self) -> float:
        return self.variance ** 0.5


@dataclass
class DriftEstimator:
    """
    Online linear regression to estimate mapping:
        local_time = a + b * robot_time
    Drift rate ~= (b - 1). Positive means local clock runs faster.
    """
    n: int = 0
    sum_x: float = 0.0
    sum_y: float = 0.0
    sum_xx: float = 0.0
    sum_xy: float = 0.0

    def add(self, robot_time: float, local_time: float) -> None:
        self.n += 1
        self.sum_x += robot_time
        self.sum_y += local_time
        self.sum_xx += robot_time * robot_time
        self.sum_xy += robot_time * local_time

    def slope(self) -> Optional[float]:
        if self.n < 2:
            return None
        denom = (self.n * self.sum_xx - self.sum_x * self.sum_x)
        if denom == 0:
            return None
        return (self.n * self.sum_xy - self.sum_x * self.sum_y) / denom

    def intercept(self) -> Optional[float]:
        b = self.slope()
        if b is None:
            return None
        return (self.sum_y - b * self.sum_x) / self.n

    def drift_rate(self) -> Optional[float]:
        b = self.slope()
        if b is None:
            return None
        return b - 1.0


class TimestampComparator:
    def __init__(self, csv_path: Optional[str] = None) -> None:
        self.offset_stats = RunningStats()
        self.interarrival_robot_stats = RunningStats()
        self.interarrival_local_stats = RunningStats()
        self.drift_estimator = DriftEstimator()

        self.initial_offset: Optional[float] = None
        self.last_robot_ts: Optional[float] = None
        self.last_local_ts: Optional[float] = None

        self.csv_path = csv_path
        self.csv_file = None
        self.csv_writer = None
        if csv_path:
            self.csv_file = open(csv_path, "w", newline="")
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow([
                "index",
                "robot_ts_s",
                "local_ts_s",
                "offset_s",
                "drift_vs_initial_s",
                "dt_robot_s",
                "dt_local_s",
            ])

    def close(self) -> None:
        if self.csv_file:
            self.csv_file.flush()
            self.csv_file.close()
            self.csv_file = None

    def process(self, robot_ts_s: float, local_ts_s: float) -> None:
        offset = local_ts_s - robot_ts_s
        if self.initial_offset is None:
            self.initial_offset = offset

        drift_vs_initial = offset - self.initial_offset
        self.offset_stats.add(offset)

        if self.last_robot_ts is not None:
            self.interarrival_robot_stats.add(robot_ts_s - self.last_robot_ts)
        if self.last_local_ts is not None:
            self.interarrival_local_stats.add(local_ts_s - self.last_local_ts)

        self.last_robot_ts = robot_ts_s
        self.last_local_ts = local_ts_s

        self.drift_estimator.add(robot_ts_s, local_ts_s)

        if self.csv_writer is not None:
            self.csv_writer.writerow([
                self.offset_stats.count,
                f"{robot_ts_s:.9f}",
                f"{local_ts_s:.9f}",
                f"{offset:.9f}",
                f"{drift_vs_initial:.9f}",
                f"{(self.interarrival_robot_stats.mean if self.interarrival_robot_stats.count else 0.0):.9f}",
                f"{(self.interarrival_local_stats.mean if self.interarrival_local_stats.count else 0.0):.9f}",
            ])
            if self.csv_file:
                self.csv_file.flush()

    def summary(self) -> str:
        drift_rate = self.drift_estimator.drift_rate()
        drift_ppm = drift_rate * 1e6 if drift_rate is not None else None
        return (
            f"samples={self.offset_stats.count} "
            f"offset_s: mean={self.offset_stats.mean:.6f}, std={self.offset_stats.stddev:.6f}, "
            f"min={self.offset_stats.min_value:.6f}, max={self.offset_stats.max_value:.6f} | "
            f"dt_robot_s: mean={self.interarrival_robot_stats.mean:.3f}, std={self.interarrival_robot_stats.stddev:.3f} | "
            f"dt_local_s: mean={self.interarrival_local_stats.mean:.3f}, std={self.interarrival_local_stats.stddev:.3f} | "
            + (f"drift_rate={drift_rate:.9f} ({drift_ppm:.1f} ppm)" if drift_rate is not None else "drift_rate=NA")
        )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Compare robot timestamps with local time and estimate drift")
    parser.add_argument("--topic", type=str, default="ROBOTODOM", help="Topic key from RTC_TOPIC or raw topic string")
    parser.add_argument("--method", type=str, default="LocalSTA", help="Connection method name (e.g., LocalSTA, SoftAP)")
    parser.add_argument("--report-interval", type=float, default=2.0, help="Seconds between summary prints")
    parser.add_argument("--csv", type=str, default=None, help="Optional path to write CSV samples")
    parser.add_argument("--duration", type=float, default=0.0, help="Optional maximum duration to run (seconds); 0 means infinite")
    parser.add_argument("--verbose", action="store_true", help="Print per-sample details in addition to summaries")
    args = parser.parse_args()

    conn: Optional[Go2WebRTCConnection] = None
    comparator = TimestampComparator(csv_path=args.csv)

    # Resolve topic
    topic = RTC_TOPIC.get(args.topic, args.topic)

    # Resolve connection method
    method = getattr(WebRTCConnectionMethod, args.method, WebRTCConnectionMethod.LocalSTA)

    stop_event = asyncio.Event()

    try:
        conn = Go2WebRTCConnection(method)
        await conn.connect()

        def on_message(envelope: Dict[str, Any]) -> None:
            try:
                payload = envelope.get("data", envelope)
                robot_ts_s = _extract_robot_timestamp_seconds(payload)
                local_ts_s = time.time()
                if robot_ts_s is None:
                    return
                comparator.process(robot_ts_s, local_ts_s)
                if args.verbose:
                    offset = local_ts_s - robot_ts_s
                    print(f"idx={comparator.offset_stats.count} robot_ts={robot_ts_s:.9f}s local_ts={local_ts_s:.9f}s offset={offset:.6f}s")
            except Exception:
                # Avoid noisy logs by default
                pass

        conn.datachannel.pub_sub.subscribe(topic, on_message)

        async def reporter() -> None:
            start_time = time.time()
            while not stop_event.is_set():
                await asyncio.sleep(args.report_interval)
                print(comparator.summary())
                if args.duration and (time.time() - start_time) >= args.duration:
                    stop_event.set()

        reporter_task = asyncio.create_task(reporter())
        await stop_event.wait()
        reporter_task.cancel()
        with contextlib.suppress(Exception):
            await reporter_task

    finally:
        comparator.close()
        if conn is not None:
            try:
                await conn.disconnect()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


