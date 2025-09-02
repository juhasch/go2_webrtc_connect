# LIDAR PCD Recording

This script records LIDAR stream data from the Go2 robot and saves it in PCD (Point Cloud Data) format using the [pypcd](https://github.com/juhasch/pypcd) library.

## Features

- **Real-time LIDAR recording**: Captures live LIDAR data from the Go2 robot via WebRTC
- **PCD file output**: Saves point clouds in standard PCD format compatible with PCL and other tools
- **Multiple compression options**: Support for ASCII, binary, and binary_compressed formats
- **Frame accumulation**: Option to accumulate multiple frames before saving
- **Configurable filtering**: Y-value filtering to focus on specific areas
- **Timestamped files**: Each PCD file includes timestamp for easy organization

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements_pcd.txt
```

2. For compressed PCD support (recommended), also install:
```bash
pip install python-lzf
```

## Usage

### Basic Usage

Record LIDAR data and save every frame as a PCD file:

```bash
python record_lidar_pcd.py
```

### Advanced Options

```bash
python record_lidar_pcd.py \
    --output-dir my_lidar_data \
    --compression binary_compressed \
    --save-every 5 \
    --accumulate-frames 10 \
    --minYValue -500 \
    --maxYValue 500
```

### Command Line Arguments

- `--output-dir`: Output directory for PCD files (default: timestamped directory)
- `--compression`: PCD compression format: `ascii`, `binary`, or `binary_compressed` (default: `binary_compressed`)
- `--save-every`: Save PCD file every N frames (default: 1, save every frame)
- `--accumulate-frames`: Accumulate N frames before saving (0 = no accumulation, default: 0)
- `--skip-mod`: Skip messages using modulus (default: 1, no skipping)
- `--minYValue`: Minimum Y value for filtering (default: -1000)
- `--maxYValue`: Maximum Y value for filtering (default: 1000)
- `--no-y-filter`: Disable Y-value filtering to see full field of view

## Output

The script creates:
- A timestamped output directory (e.g., `lidar_recordings_20250130_143022/`)
- Individual PCD files for each frame (e.g., `lidar_frame_143022_123.pcd`)
- Accumulated point cloud files if accumulation is enabled (e.g., `lidar_accumulated_143022_456.pcd`)

## PCD File Format

Each PCD file contains:
- **Header**: Metadata about the point cloud (fields, count, size, type, width, height)
- **Data**: Point coordinates in X, Y, Z format
- **Compression**: Configurable compression for efficient storage

## Example Use Cases

### 1. High-Frequency Recording
```bash
# Save every frame for detailed analysis
python record_lidar_pcd.py --save-every 1
```

### 2. Accumulated Point Clouds
```bash
# Accumulate 20 frames for denser point clouds
python record_lidar_pcd.py --accumulate-frames 20 --save-every 20
```

### 3. Focused Area Recording
```bash
# Record only points in a specific Y range
python record_lidar_pcd.py --minYValue -200 --maxYValue 200
```

### 4. Efficient Storage
```bash
# Use compressed format and save every 10th frame
python record_lidar_pcd.py --compression binary_compressed --save-every 10
```

## Viewing PCD Files

### Using PCL (Point Cloud Library)
```bash
# Install PCL viewer
sudo apt install pcl-tools

# View a PCD file
pcl_viewer lidar_frame_143022_123.pcd
```

### Using CloudCompare
- Download [CloudCompare](https://www.danielgm.net/cc/)
- Open PCD files directly in the application

### Using Python with pypcd
```python
import pypcd

# Load a PCD file
pc = pypcd.PointCloud.from_path('lidar_frame_143022_123.pcd')

# Access point data
points = pc.pc_data
x_coords = points['x']
y_coords = points['y']
z_coords = points['z']

print(f"Point cloud has {len(points)} points")
```

## Performance Considerations

- **Binary compressed format** provides the best balance of file size and loading speed
- **Frame accumulation** reduces file count but increases memory usage
- **Y-value filtering** reduces file size by focusing on relevant areas
- **Skip modulus** can reduce processing load for high-frequency LIDAR data

## Troubleshooting

### Common Issues

1. **Import Error for pypcd**:
   ```bash
   pip install pypcd
   ```

2. **Compressed PCD Support**:
   ```bash
   pip install python-lzf
   ```

3. **Memory Issues with Large Accumulations**:
   - Reduce `--accumulate-frames` value
   - Use `--save-every` to save more frequently

4. **File Permission Errors**:
   - Ensure write permissions for the output directory
   - Check available disk space

### Logging

The script uses minimal logging by default. For debugging, modify the logging level in the script:
```python
logging.basicConfig(level=logging.INFO)  # or logging.DEBUG
```

## Integration with Other Tools

The generated PCD files can be used with:
- **ROS/ROS2**: Convert to PointCloud2 messages
- **Open3D**: Load and visualize point clouds
- **PyVista**: 3D visualization and analysis
- **MeshLab**: Point cloud processing and mesh generation
- **Blender**: 3D modeling and animation

## License

This script is based on the go2_webrtc_connect project and uses the pypcd library for PCD file handling.
