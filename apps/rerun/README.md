# Combined Video + LIDAR Visualization (Rerun)

This script (`apps/rerun/rerun_video_lidar_stream.py`) streams live video and LIDAR from the robot via WebRTC (or plays back from CSV) and logs to the Rerun viewer.

- **Video stream**: `camera/image`
- **Single-frame LIDAR**: `lidar/points`
- **Accumulated LIDAR cloud**: `lidar/accumulated_points`

## Prerequisites

- Install project dependencies and activate your virtual environment.
- Example (adjust to your environment):

```bash
source /Users/juhasch/git/go2_webrtc_connect/.venv/bin/activate
```

## Quick start

- **Live (WebRTC)**

```bash
python apps/rerun/rerun_video_lidar_stream.py
```

- **CSV playback**

```bash
python apps/rerun/rerun_video_lidar_stream.py \
  --csv-read apps/webxr/test.lidarlog
```

## Point cloud accumulation

Enable a rolling 3D map by accumulating recent LIDAR frames with voxel deduplication and optional height filtering.

- **Enable**: `--accumulation`
- **Key options**:
  - **--max-clouds N**: Max clouds to keep in the buffer (default 30)
  - **--max-age SEC**: Max age of clouds (default 2.0)
  - **--voxel-size M**: Voxel grid size for deduplication (default 0.05)
  - **--min-height M**, **--max-height M**: Z filter range (defaults 0.2–1.0)
  - **--publish-rate HZ**: Rate limit accumulated publishes (default 10.0)
  - **--no-height-filter**: Disable the Z filter

- **Live example**

```bash
python apps/rerun/rerun_video_lidar_stream.py \
  --accumulation --max-clouds 60 --max-age 3.0 --voxel-size 0.05 \
  --min-height 0.1 --max-height 1.5 --publish-rate 5
```

- **CSV example**

```bash
python apps/rerun/rerun_video_lidar_stream.py \
  --csv-read apps/webxr/test.lidarlog \
  --accumulation --max-clouds 60 --max-age 3.0 --voxel-size 0.05
```

## All CLI options

- **General**
  - **--version**: Print script version
  - **--csv-read PATH**: Read LIDAR frames from CSV instead of WebRTC
  - **--csv-write**: Save received frames to a CSV file
  - **--skip-mod N**: Process every Nth LIDAR message (default 1)
  - **--minYValue INT**, **--maxYValue INT**: Y-axis filter range (defaults -1000, 1000)
  - **--disable-video**: Disable video stream
  - **--disable-lidar**: Disable LIDAR stream
  - **--no-y-filter**: Disable Y-axis filtering for display
  - **--debug**: Extra debug prints

- **Accumulation**
  - **--accumulation**: Enable accumulated point cloud
  - **--max-clouds INT**: Max clouds to retain (default 30)
  - **--max-age FLOAT**: Max age in seconds (default 2.0)
  - **--voxel-size FLOAT**: Voxel size in meters (default 0.05)
  - **--min-height FLOAT**: Min Z height (default 0.2)
  - **--max-height FLOAT**: Max Z height (default 1.0)
  - **--publish-rate FLOAT**: Publish rate in Hz (default 10.0)
  - **--no-height-filter**: Disable height (Z) filter

## Rerun entities

- **camera/image**: RGB frames from the robot
- **lidar/points**: Unique points from the current frame
- **lidar/accumulated_points**: Downsampled, height-filtered accumulation of recent frames

## Tips

- **Sparse or missing points?** Try `--no-height-filter` or widen `--min-height/--max-height`.
- **Too dense?** Increase `--voxel-size` or lower `--max-clouds`/`--max-age`.
- **CPU load high?** Reduce `--publish-rate` and/or increase `--skip-mod`.
- **Field-of-view cropping?** Use `--no-y-filter` or adjust `--minYValue/--maxYValue`.
