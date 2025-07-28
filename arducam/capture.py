# this is from secondary rpi.
# no need to create a separate repo.  for now.....
from flask import Flask, jsonify, request
from datetime import datetime
import os
import RPi.GPIO as gp  # Assuming you're using GPIO pins to control the multiplexer
import requests

app = Flask(__name__)

# Setup GPIO
gp.setwarnings(False)
gp.setmode(gp.BOARD)
gp.setup(7, gp.OUT)
gp.setup(11, gp.OUT)
gp.setup(12, gp.OUT)

# Directory for storing captured images
CAPTURE_DIR = "static/captures"
os.makedirs(CAPTURE_DIR, exist_ok=True)  # Ensure capture directory exists

# Main Pi endpoint for image upload
MAIN_PI_URL = "http://192.168.11.178:5002/upload"

@app.route('/capture', methods=['POST'])
def capture_images():
    try:
        filenames = []

        print('Start testing the camera E')
        i2c = "i2cset -y 10 0x24 0x24 0x02"
        os.system(i2c)
        gp.output(7, False)
        gp.output(11, False)
        gp.output(12, True)
        filename = capture(5)
        filenames.append(filename)

        print('Start testing the camera D') 
        i2c = "i2cset -y 10 0x24 0x24 0x12"
        os.system(i2c)
        gp.output(7, True)
        gp.output(11, False)
        gp.output(12, True)
        filename = capture(4)
        filenames.append(filename)

        print('Start testing the camera C')
        i2c = "i2cset -y 10 0x24 0x24 0x22"
        os.system(i2c)
        gp.output(7, False)
        gp.output(11, True)
        gp.output(12, False)
        filename = capture(3)
        filenames.append(filename)

        print('Start testing the camera B')
        i2c = "i2cset -y 10 0x24 0x24 0x32"
        os.system(i2c)
        gp.output(7, True)
        gp.output(11, True)
        gp.output(12, False)
        filename = capture(2)
        filenames.append(filename)

        # Transfer images after capturing
        transfer_images()

        return jsonify({'status': 'success', 'images': filenames})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# def capture(cam):
#     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#     filename = f'capture_cam{cam}_{timestamp}.jpg'
#     filepath = os.path.join(CAPTURE_DIR, filename)

#     # Base command for libcamera-still
#     cmd = f"libcamera-still --nopreview "

#     if cam == 2:
#         cmd += "--autofocus-mode manual --lens-position 5.0 --shutter 50000 --gain 3.0 "
#     elif cam == 3:
#         cmd += "--autofocus-mode manual --lens-position 5.5 --shutter 50000 --gain 3.5 "    
#     elif cam == 4:
#         cmd += "--autofocus-mode manual --lens-position 5.5 --shutter 50000 --gain 3.5 "
#     elif cam == 5:
#         cmd += "--autofocus-mode manual --lens-position 6.5 --shutter 50000 --gain 3.5 "
    
#     # Add output file location
#     cmd += f"-o {filepath}"

#     os.system(cmd)
#     return filename

def capture(cam: int) -> str:
    """
    Take a quick JPEG using libcamera-still “immediate” mode.
    Returns the filename (full path) that was written.
    """
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"cam{cam}_{ts}.jpg"
    path = os.path.join(CAPTURE_DIR, name)

    # ── base options ───────────────────────────────────────────
    #  -t 1            run for 1 ms (needed because -t 0 disables stills)
    #  --immediate     skip the 2 s preview + auto-tuning cycle
    #  -n              no preview window
    #  -q 85           jpeg quality
    #  -r              *don’t* save a RAW alongside the JPEG
    #  --mode 1920:1080:10  HD Bayer/binning mode → much lighter than 4656×3496
    base = (
        "libcamera-still -t 1 --immediate -n -q 85 "
        "--mode 4656:3496:10 "
    )

    # ── per-camera lens / exposure presets ─────────────────────
    per_cam = {
        2: "--autofocus-mode manual --lens-position 5.0 --shutter 50000 --gain 3.0",
        3: "--autofocus-mode manual --lens-position 5.5 --shutter 50000 --gain 3.5",
        4: "--autofocus-mode manual --lens-position 5.5 --shutter 50000 --gain 3.5",
        5: "--autofocus-mode manual --lens-position 6.5 --shutter 50000 --gain 3.5",
    }[cam]

    os.system(f"{base}{per_cam} -o {path}")
    return name            # caller keeps behaviour the same


def transfer_images():
    """Transfers images to the Main Pi and deletes them after successful upload."""
    files = []
    
    # Gather all images
    for filename in os.listdir(CAPTURE_DIR):
        file_path = os.path.join(CAPTURE_DIR, filename)
        if filename.endswith(".jpg"):
            files.append(("images", open(file_path, "rb")))

    if not files:
        print("No images to transfer.")
        return

    try:
        response = requests.post(MAIN_PI_URL, files=files)
        if response.status_code == 200:
            print("Images transferred successfully, deleting local copies...")
            cleanup_local_images()
        else:
            print(f"Error transferring images: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Transfer failed: {e}")
    finally:
        for _, file in files:
            file.close()  # Close file handles

def cleanup_local_images():
    """Deletes all images from the remote Pi after successful transfer."""
    for filename in os.listdir(CAPTURE_DIR):
        file_path = os.path.join(CAPTURE_DIR, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
            print(f"Deleted: {file_path}")

if __name__ == '__main__':
    app.run(host='192.168.11.148', port=5002, debug=True)  # Allow external requests
