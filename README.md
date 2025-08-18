# Full Unitree Go2 WebRTC Driver

This repository contains a Python implementation of the WebRTC driver to connect to the Unitree Go2 Robot. WebRTC is used by the Unitree Go APP and provides high-level control through it. Therefore, no jailbreak or firmware manipulation is required. It works out of the box for Go2 AIR/PRO/EDU models.


```
% export ROBOT_IP=192.168.0.197
% python examples/data_channel/move_test.py
🔌 Initializing robot connection...
🔗 Connecting to robot...
🕒 WebRTC connection        : 🟡 started       (16:43:29)
Decoder set to: LibVoxelDecoder
🕒 Signaling State          : 🟡 have-local-offer (16:43:29)
🕒 ICE Gathering State      : 🟡 gathering     (16:43:29)
🕒 ICE Gathering State      : 🟢 complete      (16:43:29)
🕒 ICE Connection State     : 🔵 checking      (16:43:30)
🕒 Peer Connection State    : 🔵 connecting    (16:43:30)
🕒 Signaling State          : 🟢 stable        (16:43:30)
🕒 ICE Connection State     : 🟢 completed     (16:43:30)
🕒 Peer Connection State    : 🟢 connected     (16:43:30)
🕒 Data Channel Verification: ✅ OK            (16:43:30)
✅ Connected to robot successfully!
```

## Supported Versions

The currently supported firmware packages are:
- 1.1.1 - 1.1.7 (latest available)
- 1.0.19 - 1.0.25

## Audio and Video Support

There are video (recvonly) and audio (sendrecv) channels in WebRTC that you can connect to. Check out the examples in the `/example` folder.

## Lidar support

There is a lidar decoder built in, so you can handle decoded PoinClouds directly. Check out the examples in the `/example` folder.

## Connection Methods

The driver supports three types of connection methods:

1. **AP Mode**: Go2 is in AP mode, and the WebRTC client is connected directly to it:

    ```python
    Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)
    ```

2. **STA-L Mode**: Go2 and the WebRTC client are on the same local network. An IP or Serial number is required:

    ```python
    Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip="192.168.8.181")
    ```

    You can also specify the IP as environment variable:

    ```bash
    export ROBOT_IP="192.168.8.181"
    ```

    If the IP is unknown, you can specify only the serial number, and the driver will try to find the IP using the special Multicast discovery feature available on Go2:

    ```python
    Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA, serialNumber="B42D2000XXXXXXXX")
    ```

3. **STA-T mode**: Remote connection through remote Unitrees TURN server. Could control your Go2 even being on the diffrent network. Requires username and pass from Unitree account

    ```python
    Go2WebRTCConnection(WebRTCConnectionMethod.Remote, serialNumber="B42D2000XXXXXXXX", username="email@gmail.com", password="pass")
    ```

## Multicast scanner
The driver has a built-in Multicast scanner to find the Unitree Go2 on the local network and connect using only the serial number.

You can use the scanner from the command line after installation:

```sh
go2-scanner
```

This will scan for available Go2 robots on your local network and display their IP addresses and serial numbers.


## Installation

### From Source (Recommended)

```sh
# Install system dependencies (Ubuntu/Debian)
sudo apt update
sudo apt install python3-pip portaudio19-dev

# Install from GitHub
pip install git+https://github.com/legion1581/go2_webrtc_connect.git

# Or clone and install locally
git clone https://github.com/legion1581/go2_webrtc_connect.git
cd go2_webrtc_connect
pip install .
```

### Development Installation

For development work, install in editable mode with development dependencies:

```sh
git clone https://github.com/legion1581/go2_webrtc_connect.git
cd go2_webrtc_connect
pip install -e ".[dev]"
```

### Optional Dependencies

Install additional dependencies for specific use cases:

```sh
# For examples and visualization
pip install ".[examples]"

# For documentation generation
pip install ".[docs]"

# All optional dependencies
pip install ".[dev,docs,examples,apps]"
```

## Usage 
Example programs are located in the /example directory.

See [troubleshooting](troubleshooting.md) when you have problems connecting to the robot.

### Thanks

A big thank you to TheRoboVerse community! Visit us at [TheRoboVerse](https://theroboverse.com) for more information and support.

Special thanks to the [tfoldi WebRTC project](https://github.com/tfoldi/go2-webrtc) and [abizovnuralem](https://github.com/abizovnuralem) for adding LiDAR support and [MrRobotow](https://github.com/MrRobotoW) for providing a plot LiDAR example.

 
### Support

If you like this project, please consider buying me a coffee:

<a href="https://www.buymeacoffee.com/legion1581" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>
