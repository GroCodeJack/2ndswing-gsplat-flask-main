from flask import Flask, jsonify, request, render_template
from picamera2 import Picamera2
import time
from datetime import datetime
import RPi.GPIO as gp
import os
import cv2
from ctypes import CDLL
import shutil
import glob
import subprocess
import requests
import asyncio
import aiohttp
from flask_socketio import SocketIO, emit
import threading
import re

app = Flask(__name__)
socketio = SocketIO(app, async_mode="threading")  # Ensure async mode

gp.setwarnings(False)
gp.setmode(gp.BOARD)

buzzer = 18

#sensor
sensor_pin = 15
gp.setup(sensor_pin,gp.IN, pull_up_down=gp.PUD_DOWN)

# stepper/driver
direction_pin   = 38
pulse_pin       = 40
cw_direction    = 0 
ccw_direction   = 1 
steps           = 375 #prev 480

metal_detected_count = 1  # Global counter
step_counter = 0

gp.setup(direction_pin, gp.OUT)
gp.setup(pulse_pin, gp.OUT)
gp.output(direction_pin,cw_direction)
gp.setup(buzzer, gp.OUT)

# camera - might not be needed?  TODO: test removal
gp.setup(7, gp.OUT)
gp.setup(11, gp.OUT)
gp.setup(12, gp.OUT)

if not os.path.exists('static/captures'):
    os.makedirs('static/captures')

IMAGE_DIR = os.path.join(app.static_folder, 'captures')

REMOTE_PI_URL = "http://192.168.10.221:5002/capture"

# Global variable to track current scan folder
current_scan_folder = None
scan_in_progress = False

# NEW ── carousel reset state ────────────────────────────────────────────────
reset_in_progress: bool = False  # True while reset thread is running
stop_reset_flag: bool = False    # Signal for the reset thread to stop
reset_thread: threading.Thread | None = None

def get_usb_mounts():
    """Get list of mounted USB drives"""
    try:
        user = os.getlogin()
        usb_path = f'/media/{user}'
        if os.path.exists(usb_path):
            return [os.path.join(usb_path, d) for d in os.listdir(usb_path) 
                   if os.path.ismount(os.path.join(usb_path, d))]
        return []
    except Exception as e:
        print(f"Error getting USB mounts: {e}")
        return []

def validate_and_prepare_usb(folder_name):
    """Check USB is mounted, create scan folder, return path"""
    usb_mounts = get_usb_mounts()
    if not usb_mounts:
        raise Exception("No USB drive detected")
    
    usb_path = usb_mounts[0]  # Use first USB drive
    scan_folder = os.path.join(usb_path, folder_name)
    
    # Create folder if it doesn't exist
    os.makedirs(scan_folder, exist_ok=True)
    
    # Test write permissions
    test_file = os.path.join(scan_folder, "test.txt")
    try:
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
    except Exception as e:
        raise Exception(f"USB drive not writable: {str(e)}")
    
    return scan_folder

def isValidFolderName(name):
    """Validate folder name for filesystem compatibility"""
    # Allow letters, numbers, underscores, hyphens
    pattern = r'^[a-zA-Z0-9_-]+$'
    return bool(re.match(pattern, name)) and len(name) <= 50

def get_latest_images(count=8):
    """Get the latest captured images"""
    try:
        images = [f for f in os.listdir(IMAGE_DIR) if f.endswith('.jpg')]
        # Sort by modification time (newest first)
        images.sort(key=lambda f: os.path.getmtime(os.path.join(IMAGE_DIR, f)), reverse=True)
        return images[:count]
    except Exception as e:
        print(f"Error getting latest images: {e}")
        return []

async def transfer_latest_images_to_usb(usb_path):
    """Transfer latest captured images to USB folder"""
    try:
        # Check if USB is still mounted
        if not os.path.exists(usb_path):
            print(f"USB path no longer exists: {usb_path}")
            return 0
        
        # Get latest images (last 8 images - 4 from each Pi)
        latest_images = get_latest_images(8)
        
        transferred_count = 0
        for img in latest_images:
            src_path = os.path.join(IMAGE_DIR, img)
            dest_path = os.path.join(usb_path, img)
            
            if os.path.exists(src_path):
                try:
                    # Check if file already exists on USB (avoid duplicates)
                    if not os.path.exists(dest_path):
                        shutil.copy2(src_path, dest_path)
                        transferred_count += 1
                        print(f"Transferred: {img}")
                    else:
                        print(f"File already exists on USB: {img}")
                except Exception as e:
                    print(f"Error transferring {img}: {e}")
                    continue
        
        print(f"Transferred {transferred_count} images to USB folder: {usb_path}")
        return transferred_count
    except Exception as e:
        print(f"Error transferring images to USB: {e}")
        return 0

@app.route('/check_usb', methods=['GET'])
def check_usb():
    """Check if USB is mounted and writable"""
    try:
        usb_mounts = get_usb_mounts()
        if not usb_mounts:
            return jsonify({'status': 'error', 'message': 'No USB drive detected'})
        
        usb_path = usb_mounts[0]
        # Test write permissions
        test_file = os.path.join(usb_path, "test.txt")
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            return jsonify({
                'status': 'success', 
                'usb_path': usb_path,
                'available_space': shutil.disk_usage(usb_path).free
            })
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'USB drive not writable: {str(e)}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/create_scan_folder', methods=['POST'])
def create_scan_folder():
    """Create folder on USB for new scan"""
    try:
        data = request.get_json()
        folder_name = data.get('folder_name')
        
        if not folder_name:
            return jsonify({'status': 'error', 'message': 'Folder name is required'})
        
        if not isValidFolderName(folder_name):
            return jsonify({'status': 'error', 'message': 'Invalid folder name. Use only letters, numbers, and underscores.'})
        
        scan_folder = validate_and_prepare_usb(folder_name)
        
        # Store current scan folder globally
        global current_scan_folder
        current_scan_folder = scan_folder
        
        return jsonify({'status': 'success', 'scan_folder': scan_folder})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/scan_status', methods=['GET'])
def scan_status():
    """Get current scan status"""
    global scan_in_progress, current_scan_folder, step_counter
    return jsonify({
        'scan_in_progress': scan_in_progress,
        'current_scan_folder': current_scan_folder,
        'step_counter': step_counter
    })

@app.route("/")
def index():
    user = {'username': 'JackO'}
    return render_template('index.html', title='Arducam', user=user)
 
@app.route('/rotate', methods=['POST'])
async def rotate_carousel():
    global metal_detected_count
    global step_counter
    global current_scan_folder
    global scan_in_progress
    
    try:
        if scan_in_progress:
            return jsonify({'status': 'error', 'message': 'Scan already in progress'})
        
        scan_in_progress = True
        step_counter = 0

        data = request.get_json()
        step_counter_limit = data.get('step_counter_limit', 24000)
        folder_name = data.get('folder_name')
        
        print(f"Step counter limit: {step_counter_limit}")
        print(f"Folder name: {folder_name}")

        # Validate folder name
        if not folder_name:
            return jsonify({'status': 'error', 'message': 'Folder name is required'})
        
        if not isValidFolderName(folder_name):
            return jsonify({'status': 'error', 'message': 'Invalid folder name. Use only letters, numbers, and underscores.'})

        # Validate USB and create scan folder
        try:
            scan_folder = validate_and_prepare_usb(folder_name)
            current_scan_folder = scan_folder
            print(f"Scan folder created: {scan_folder}")
        except Exception as e:
            scan_in_progress = False
            return jsonify({'status': 'error', 'message': f'USB setup failed: {str(e)}'})

        metal_detected_count = 1
        filenames = []
        print('Rotating and capturing with USB transfer...')

        try:
            while step_counter < step_counter_limit:
                print(f"Step {step_counter + 1} of {step_counter_limit}")
                
                # Run both capture tasks concurrently
                capture_task = asyncio.create_task(capture_images())
                remote_capture_task = asyncio.create_task(trigger_capture_on_remote())

                # Wait for both tasks to complete
                await asyncio.gather(capture_task, remote_capture_task)

                # Transfer images to USB immediately after capture
                if current_scan_folder:
                    transferred_count = await transfer_latest_images_to_usb(current_scan_folder)
                    print(f"Transferred {transferred_count} images to USB")

                # After the capture is complete, rotate the carousel
                rotate_carousel_one_step()

            return jsonify({'status': 'success', 'images': filenames, 'scan_folder': current_scan_folder})
        except Exception as e:
            print(f"Error during scan: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Scan interrupted: {str(e)}'})
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        scan_in_progress = False
        sound_buzzer(3)
 
# ──────────────────────────── Carousel Reset Thread ─────────────────────────

def _reset_carousel_worker(direction: int = 1):
    """Background thread that continuously steps the carousel until told to stop."""
    global stop_reset_flag, reset_in_progress, step_counter
    try:
        print("[ResetThread] started")
        gp.output(direction_pin, direction)
        # Continuous stepping until stop flag is set
        while not stop_reset_flag:
            gp.output(pulse_pin, gp.HIGH)
            time.sleep(0.001)
            gp.output(pulse_pin, gp.LOW)
            time.sleep(0.001)
            step_counter -= 1  # we are unwinding the counter
        print("[ResetThread] stop signal received – exiting thread")
    finally:
        reset_in_progress = False
        stop_reset_flag = False

@app.route('/resetCarousel', methods=['POST'])
def start_reset_carousel():
    """Start carousel reset in background thread."""
    global reset_in_progress, stop_reset_flag, reset_thread

    if reset_in_progress:
        return jsonify({'status': 'error', 'message': 'Reset already running'}), 400

    data = request.get_json(silent=True) or {}
    direction = int(data.get('direction', 1))  # 1 = CCW (unwind) by default

    # Prepare and start thread
    stop_reset_flag = False
    reset_in_progress = True
    reset_thread = threading.Thread(target=_reset_carousel_worker, args=(direction,), daemon=True)
    reset_thread.start()
    print("[API] resetCarousel started thread")
    return jsonify({'status': 'started'})

@app.route('/stopReset', methods=['POST'])
def stop_reset_carousel():
    """Signal the reset thread to stop."""
    global stop_reset_flag, reset_in_progress, reset_thread
    if not reset_in_progress:
        return jsonify({'status': 'error', 'message': 'No reset in progress'}), 400

    stop_reset_flag = True
    return jsonify({'status': 'stopping'})

@app.route('/resetStatus', methods=['GET'])
def reset_status():
    """Return whether reset is running."""
    return jsonify({'reset_in_progress': reset_in_progress})


@app.route('/rotateOneStep', methods=['POST'])
def rotate_carousel_one_step():
    global metal_detected_count
    global step_counter
    #step_counter = 0

    try:
        filenames = []
        print('rotate carousel one step a')

        if request and request.method == 'POST':
            print('Checking request...')
            if request.is_json:
                data = request.get_json()
                direction = data.get('direction', 0)  # Get direction from request
                print(f"Direction from request: {direction}")
            else:
                print('Request is not JSON or invalid Content-Type')
                direction = 0
        else:
            print('No request context or non-POST request.')
            direction = 0

        print("Rotating carousel one step...")

        time.sleep(.1)
        gp.output(direction_pin, direction)

        for _ in range(steps):
            gp.output(pulse_pin, gp.HIGH)
            time.sleep(.001)
            gp.output(pulse_pin, gp.LOW)
            time.sleep(.001)
            step_counter += 1
            print(step_counter)

        return jsonify({'status': 'success', 'images': filenames})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


# Make capture_images() asynchronous
@app.route('/capture', methods=['POST'])
async def capture_images():
    try:
        filenames = []

        print('Start testing the camera A')
        i2c = "i2cset -y 10 0x24 0x24 0x02"
        await asyncio.to_thread(os.system, i2c)
        gp.output(7, False)
        gp.output(11, False)
        gp.output(12, True)
        filename = await asyncio.to_thread(capture, 1)
        filenames.append(filename)

        print('Start testing the camera F') 
        i2c = "i2cset -y 10 0x24 0x24 0x12"
        await asyncio.to_thread(os.system, i2c)
        gp.output(7, True)
        gp.output(11, False)
        gp.output(12, True)
        filename = await asyncio.to_thread(capture, 6)
        filenames.append(filename)

        print('Start testing the camera G')
        i2c = "i2cset -y 10 0x24 0x24 0x22"
        await asyncio.to_thread(os.system, i2c)
        gp.output(7, False)
        gp.output(11, True)
        gp.output(12, False)
        filename = await asyncio.to_thread(capture, 7)
        filenames.append(filename)

        print('Start testing the camera H')
        i2c = "i2cset -y 10 0x24 0x24 0x32"
        await asyncio.to_thread(os.system, i2c)
        gp.output(7, True)
        gp.output(11, True)
        gp.output(12, False)
        filename = await asyncio.to_thread(capture, 8)
        filenames.append(filename)

        return jsonify({'status': 'success', 'images': filenames})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
        

# Function to trigger capture on the remote Pi (async)
@app.route('/captureRemote', methods=['POST'])
async def trigger_capture_on_remote():
    print('Attempting to trigger remote capture...')
    try:
        filenames = []
        async with aiohttp.ClientSession() as session:
            print('Sending POST request to remote Pi...')
            async with session.post('http://192.168.10.221:5002/capture') as response:
                print(f"Response status: {response.status}")
                if response.status == 200:
                    print('Remote capture triggered successfully!')
                else:
                    print(f"Failed to trigger remote capture. HTTP Status: {response.status}")
                    print(f"Response text: {await response.text()}")
                return jsonify({'status': 'success', 'images': filenames})
    except aiohttp.ClientError as e:
        print(f"Client error occurred while triggering remote capture: {str(e)}")
    except Exception as e:
        print(f"Unexpected error occurred while triggering remote capture: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})

# def capture(cam):
#     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#     filename = f'capture_cam{cam}_{timestamp}.jpg'
    
#     # Base command for libcamera-still
#     cmd = f"libcamera-still --nopreview "
    
#     if cam == 1:
#         cmd += "--autofocus-mode manual --lens-position 5.0 --shutter 50000 --gain 3.0 "
#     if cam == 6:
#         cmd += "--autofocus-mode manual --lens-position 6.5 --shutter 50000 --gain 3.5 "    
#     if cam == 7:
#         cmd += "--autofocus-mode manual --lens-position 5.5 --shutter 50000 --gain 3.5 "
#     # Add --vflip for camera 4
#     if cam == 8:
#         cmd += "--autofocus-mode manual --lens-position 5.5 --shutter 50000 --gain 3.5 "
    
#     # Add output file location
#     cmd += f"-o static/captures/{filename}"
    
#     os.system(cmd)
#     return filename

def capture(cam):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"static/captures/cam{cam}_{ts}.jpg"

    # --immediate  : skip the default 2 s preview+analysis
    # -t 1         : one-millisecond run time (needed because -t 0 disables stills)
    # -n           : no preview window
    # -q 85        : sensible JPEG quality
    # -r           : *don’t* save RAW (drops the second stream)
    # --mode 1920:1080:10 : HD sensor binning → much lighter than 4656×3496
    # Manual lens/shutter/gain as you already have
    base = (
        "libcamera-still -t 1 --immediate -n -q 85 "
        "--mode 4656:3496:10 "
    )

    tuning = {
        1: "--lens-position 6.0 --shutter 50000 --gain 2.5",
        6: "--lens-position 6.5 --shutter 50000 --gain 3.0",
        7: "--lens-position 5.0 --shutter 50000 --gain 3.0",
        8: "--lens-position 5.5 --shutter 50000 --gain 3.0",
    }[cam]

    os.system(f"{base} {tuning} -o {fname}")
    return fname


@app.route("/list_images", methods=["GET"])
def list_images():
    images = [f for f in os.listdir(IMAGE_DIR) if f.endswith('.jpg')]
    # Sort by cam number first, then timestamp
    images.sort(key=lambda f: (
        int(f.split('_')[1][3:]),  # Extract camera number (e.g., cam2 -> 2)
        f.split('_')[2]            # Extract timestamp (e.g., 20250110_154243)
    ))
    return jsonify(images)

@app.route("/list_usb", methods=["GET"])
def list_usb():
    # Adjust path to suit your environment
    usb_mounts = [f'/media/{os.getlogin()}/{d}' for d in os.listdir('/media/' + os.getlogin())]
    return jsonify(usb_mounts)

@app.route("/delete_images", methods=["POST"])
def delete_images():
    selected_images = request.json.get('images', [])
    for img in selected_images:
        img_path = os.path.join(IMAGE_DIR, img)
        if os.path.exists(img_path):
            os.remove(img_path)
    return jsonify({"status": "success"})

@app.route("/check_existing_images", methods=["GET"])
def check_existing_images():
    """Check if there are any existing images in the captures directory"""
    try:
        if not os.path.exists(IMAGE_DIR):
            return jsonify({"has_images": False, "count": 0})
        
        images = [f for f in os.listdir(IMAGE_DIR) if f.endswith('.jpg')]
        return jsonify({"has_images": len(images) > 0, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clear_all_images", methods=["POST"])
def clear_all_images():
    """Clear all images from the captures directory"""
    try:
        if not os.path.exists(IMAGE_DIR):
            return jsonify({"status": "success", "message": "No images directory found", "deleted_count": 0})
        
        images = [f for f in os.listdir(IMAGE_DIR) if f.endswith('.jpg')]
        deleted_count = 0
        
        for img in images:
            img_path = os.path.join(IMAGE_DIR, img)
            try:
                os.remove(img_path)
                deleted_count += 1
            except Exception as e:
                print(f"Error deleting {img}: {e}")
        
        return jsonify({"status": "success", "deleted_count": deleted_count})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def download_images_thread(selected_images, usb_path, delete_after_download, app):
    try:
        total_files = len(selected_images)
        for index, img in enumerate(selected_images):
            src_path = os.path.join(IMAGE_DIR, img)
            dest_path = os.path.join(usb_path, img)
            shutil.copy(src_path, dest_path)

            progress = int(((index + 1) / total_files) * 100)
            socketio.emit('progress_update', {'progress': progress}, namespace='/')

            time.sleep(0.5)

        if delete_after_download:
            for img in selected_images:
                os.remove(os.path.join(IMAGE_DIR, img))

        socketio.emit('progress_update', {'progress': 100}, namespace='/')

    except Exception as e:
        socketio.emit('progress_error', {'message': str(e)})

    finally:
        with app.app_context():  # Use the correct app context
            sound_buzzer(2)


@app.route("/download_images", methods=["POST"])
def download_images():
    print('download_images')

    selected_images = request.json.get('images', [])
    usb_path = request.json.get('usb_path')
    delete_after_download = request.json.get('delete', False)

    print(f"Starting download of {len(selected_images)} images")

    # Run in background thread
    threading.Thread(target=download_images_thread, args=(selected_images, usb_path, delete_after_download, app), daemon=True).start()

    return jsonify({"status": "started"})  # Immediately respond to the client

@app.route('/upload', methods=['POST'])
def upload_images():
    try:
        for file in request.files.getlist("images"):
            if file.filename:
                save_path = os.path.join(IMAGE_DIR, file.filename)
                file.save(save_path)
                print(f"Saved: {save_path}")

        return {"status": "success", "message": "Images received"}, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

@app.route('/rotateAndRecord', methods=['POST'])
def rotate_and_record():
    global metal_detected_count
    try:
        filenames = []
        print('Rotate carousel and record video')

        direction = 0  # Default direction
        if request and request.method == 'POST' and request.is_json:
            data = request.get_json()
            direction = data.get('direction', 0)

        print(f"Direction: {direction}")
        gp.output(direction_pin, direction)

        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_video_filename = f"static/captures/video_cam1_{timestamp}.h264"
        mp4_video_filename = f"static/captures/video_cam1_{timestamp}.mp4"

        # Start recording video
        record_process = subprocess.Popen(
            ["libcamera-vid", "-t", "0", 
            "--lens-position", "6.0", 
            "--viewfinder-width", "1920", "--viewfinder-height", "1080",
            "-o", raw_video_filename], 
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        print(f"Recording started: {raw_video_filename}")

        # Rotate stepper motor
        for _ in range(3000):
            gp.output(pulse_pin, gp.HIGH)
            time.sleep(.001)
            gp.output(pulse_pin, gp.LOW)
            time.sleep(.001)

        # Stop recording
        record_process.terminate()
        print(f"Recording stopped: {raw_video_filename}")

        # Convert to .mp4 using ffmpeg
        convert_process = subprocess.run(
            ["ffmpeg", "-i", raw_video_filename, "-c:v", "copy", "-an", mp4_video_filename],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        if convert_process.returncode == 0:
            print(f"Video converted to: {mp4_video_filename}")
            os.remove(raw_video_filename)  # Delete original .h264 file
        else:
            print(f"Failed to convert {raw_video_filename} to .mp4")

        return jsonify({'status': 'success', 'video': mp4_video_filename})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/soundBuzzer', methods=['POST'])
def sound_buzzer(buzzCount=1):
    try:
        filenames = []
      
        # Rotate stepper motor
        for _ in range(buzzCount):
            gp.output(buzzer, gp.HIGH)
            time.sleep(.5)
            gp.output(buzzer, gp.LOW)
            time.sleep(.1)

        return jsonify({'status': 'success'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/diagnostics')
def diagnostics():
    """Show diagnostics dashboard"""
    return render_template('diagnostics.html', title='Diagnostics Dashboard')

@app.route('/diagnostics_data', methods=['GET'])
def diagnostics_data():
    """Get diagnostics data for dashboard"""
    global step_counter, scan_in_progress, steps
    
    try:
        # Calculate progress
        total_steps = 24000
        progress_percentage = min(100, (step_counter / total_steps) * 100) if scan_in_progress else 0
        
        # Calculate expected images per camera
        images_per_camera_expected = total_steps // steps if steps > 0 else 0
        
        # Count actual images per camera
        image_counts = {}
        latest_images = []
        
        if os.path.exists(IMAGE_DIR):
            all_images = [f for f in os.listdir(IMAGE_DIR) if f.endswith('.jpg')]
            
            # Count images per camera
            for cam_num in [1, 2, 3, 4, 5, 6, 7, 8]:
                count = len([img for img in all_images if img.startswith(f'cam{cam_num}_')])
                image_counts[f'cam{cam_num}'] = count
            
            # Get latest 8 images (most recent)
            if all_images:
                all_images.sort(key=lambda f: os.path.getmtime(os.path.join(IMAGE_DIR, f)), reverse=True)
                latest_images = all_images[:8]
        
        return jsonify({
            'scan_in_progress': scan_in_progress,
            'progress_percentage': round(progress_percentage, 1),
            'step_counter': step_counter,
            'total_steps': total_steps,
            'images_per_camera_expected': images_per_camera_expected,
            'image_counts': image_counts,
            'latest_images': latest_images
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    try:
        socketio.run(app, host='192.168.11.178', port=5002, debug=True, allow_unsafe_werkzeug=True)

        #TODO test and remove
        gp.output(7, False)
        gp.output(11, False)
        gp.output(12, True)
 
        gp.cleanup()

    except KeyboardInterrupt:
        gp.cleanup()