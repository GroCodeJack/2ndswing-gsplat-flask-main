# Arducam 3D Camera System Architecture

## Overview

The Arducam 3D Camera System is a distributed Raspberry Pi-based imaging solution designed for 3D object capture and analysis. The system consists of multiple cameras mounted on a rotating carousel, controlled by a Flask web application with real-time image capture, processing, and management capabilities.

## High-Level Architecture

The system operates as a **distributed multi-camera setup** with the following components:

- **Main Pi (Controller)**: Runs the primary Flask web application, controls the carousel rotation, and manages the main camera array
- **Remote Pi (Secondary)**: Handles additional cameras and transfers captured images to the main controller
- **Web Interface**: Bootstrap-based UI for system control and image management
- **Hardware Integration**: GPIO-controlled stepper motor for carousel rotation, buzzer feedback, and camera multiplexing

## Key Folders and Modules

### `/arducam/` - Root Project Directory
- **`app/`** - Main Flask application
  - `main.py` - Primary Flask server with all API endpoints and hardware control
  - `templates/` - HTML templates for the web interface
    - `index.html` - Main control interface with camera controls and image management
    - `layout.html` - Base template with Bootstrap styling
  - `static/` - Static assets
    - `style.css` - Custom styling for the web interface
    - `captures/` - Directory for storing captured images
  - `lib/` - Hardware libraries
    - `libarducam_vcm.so` - Arducam VCM (Voice Coil Motor) control library
  - `multi_cameras_auto_focus.py` - Auto-focus calibration utility for multiple cameras
  - `.flaskenv` - Flask environment configuration

- **`capture.py`** - Secondary Pi capture server for remote cameras
- **`notes.txt`** - Development notes and configuration settings
- **`install_pivariety_pkgs.sh`** - Installation script for Pi-specific packages
- **`packages.txt`** - System package dependencies
- **`venv/`** - Python virtual environment

## Main Data and Control Flow

### Camera Capture Flow
1. **User Interface**: Web interface triggers capture via AJAX calls
2. **Camera Selection**: I2C commands configure camera multiplexer for specific camera
3. **GPIO Control**: GPIO pins control camera selection and multiplexer channels
4. **Image Capture**: `libcamera-still` captures high-resolution images with camera-specific settings
5. **File Storage**: Images saved to `static/captures/` with timestamped filenames
6. **Remote Transfer**: Secondary Pi transfers images to main controller via HTTP POST

### Carousel Control Flow
1. **Rotation Command**: Web interface sends rotation parameters
2. **Stepper Control**: GPIO pins control stepper motor direction and pulse signals
3. **Step Counting**: Global counter tracks carousel position
4. **Synchronized Capture**: Rotation and capture operations run concurrently
5. **Feedback**: Buzzer provides audio feedback on completion

### Image Management Flow
1. **File Listing**: API endpoint lists all captured images
2. **USB Detection**: System scans for mounted USB drives
3. **Batch Operations**: Users can select multiple images for download/deletion
4. **Transfer**: Images copied to USB drive with progress tracking
5. **Cleanup**: Optional deletion of transferred images

### Real-time USB Transfer Flow
1. **Folder Naming**: User prompted to name scan folder when starting scan
2. **USB Validation**: System checks USB drive availability and write permissions
3. **Folder Creation**: Creates named folder on USB drive for scan
4. **Real-time Transfer**: Images transferred to USB folder immediately after each capture cycle
5. **Progress Tracking**: Frontend shows scan progress and transfer status
6. **Error Handling**: Graceful handling of USB disconnection and transfer failures

## Build and Deploy Pipeline

### System Dependencies
```bash
# Core system packages
sudo apt-get update
sudo apt-get install python3-flask python3-pip

# Python dependencies
pip install flask-socketio RPi.GPIO aiohttp

# Camera libraries
sudo apt install libcamera-tools libcamera-apps
```

### Environment Variables
- `FLASK_APP=main.py` - Flask application entry point
- Network configuration for Pi communication:
  - Main Pi: `192.168.11.178:5002` (work) / `192.168.12.198:5001` (home)
  - Remote Pi: `192.168.11.148:5002` (work) / `192.168.12.220:5002` (home)

### Hardware Configuration
- **GPIO Pins**:
  - Buzzer: Pin 18
  - Sensor: Pin 15
  - Stepper Direction: Pin 38
  - Stepper Pulse: Pin 40
  - Camera Multiplexer: Pins 7, 11, 12
- **I2C Camera Control**: Channel selection via `i2cset` commands
- **Camera Settings**: Per-camera autofocus, shutter, and gain configurations

## Development and Testing

### Starting the Development Server
```bash
# Activate virtual environment
source venv/bin/activate

# Run main application
flask run --host=192.168.11.178 --port=5002

# Run secondary capture server
python capture.py
```

### Testing Procedures
1. **Camera Testing**: Individual camera capture via web interface
2. **Carousel Testing**: Single-step and full rotation testing
3. **Auto-focus Calibration**: Run `multi_cameras_auto_focus.py` for lens calibration
4. **Network Testing**: Verify communication between main and remote Pi
5. **USB Transfer**: Test image download to external storage

### Key API Endpoints
- `GET /` - Main web interface
- `POST /capture` - Capture from main cameras
- `POST /captureRemote` - Trigger remote camera capture
- `POST /rotate` - Full carousel rotation with capture and real-time USB transfer
- `POST /rotateOneStep` - Single step rotation
- `POST /resetCarousel` - Reset carousel position
- `GET /list_images` - List captured images
- `POST /download_images` - Download images to USB
- `POST /delete_images` - Delete selected images
- `GET /check_usb` - Check USB drive status and available space
- `POST /create_scan_folder` - Create folder on USB for new scan
- `GET /scan_status` - Get current scan progress and status

## External Services and Dependencies

### Hardware Services
- **libcamera**: Raspberry Pi camera interface
- **RPi.GPIO**: GPIO control library
- **I2C**: Camera multiplexer communication
- **Stepper Motor**: Carousel rotation control

### Software Dependencies
- **Flask**: Web framework
- **Flask-SocketIO**: Real-time communication
- **aiohttp**: Asynchronous HTTP client
- **OpenCV**: Image processing (auto-focus utility)
- **requests**: HTTP client for inter-Pi communication

### Network Services
- **HTTP Server**: Flask web server on port 5002
- **Inter-Pi Communication**: HTTP POST for image transfer
- **USB Storage**: Automatic detection and mounting

## Configuration Notes

### Camera Settings
Each camera has specific lens position, shutter, and gain settings optimized for different materials:
- **Driver settings**: Higher gain (3.0-3.5) for better detail
- **Iron settings**: Lower gain (2.0) for metal detection

### Network Configuration
The system supports both home and work network configurations with different IP addresses for main and remote Pi units.

### File Management
- Images stored with timestamped filenames: `cam{number}_{timestamp}.jpg`
- Real-time transfer to USB folders during scanning
- Automatic cleanup after successful transfer
- USB drive detection and mounting
- Progress tracking for large file transfers
- Organized folder structure on USB: `/media/user/usb_drive/scan_name/`

### New USB Transfer Features
- **Folder Naming**: User prompts for scan folder names
- **Real-time Transfer**: Images transferred immediately after capture
- **USB Status Monitoring**: Continuous USB drive availability checking
- **Progress Tracking**: Real-time scan progress display
- **Error Recovery**: Graceful handling of USB disconnection
- **Duplicate Prevention**: Avoids transferring same image multiple times 