# USB Transfer Feature

## Overview

The Arducam 3D Camera System now supports real-time USB transfer during scanning, eliminating the need for manual image downloads after each scan.

## How It Works

### Before (Old Workflow)
1. Run 30-minute scan
2. Wait for scan to complete
3. Manually download images to USB (10 minutes)
4. Remove USB drive
5. Repeat for next scan

### After (New Workflow)
1. Plug in USB drive
2. Click "Run it" and enter folder name
3. System automatically transfers images to USB during scan
4. Remove USB drive with organized folders
5. Repeat for next scan

## Features

### Real-time Transfer
- Images are transferred to USB immediately after each capture cycle
- No waiting time after scan completion
- Automatic folder creation on USB drive

### Folder Organization
- Each scan creates a named folder on the USB drive
- Folder structure: `/media/user/usb_drive/scan_name/`
- Images organized by timestamp and camera number

### USB Status Monitoring
- Real-time USB drive availability checking
- Available space display
- Automatic error handling for USB disconnection

### Progress Tracking
- Real-time scan progress display
- Transfer status updates
- Error notifications

## Usage

### Starting a Scan
1. Ensure USB drive is plugged in
2. Check USB status indicator (should show green)
3. Click "Run it" button
4. Enter folder name when prompted
5. Monitor progress during scan
6. Scan completes with images already on USB

### Folder Naming Rules
- Use only letters, numbers, underscores, and hyphens
- Maximum 50 characters
- Examples: `morning_scan_1`, `test-object-123`, `production_run`

### USB Requirements
- Must be mounted at `/media/user/`
- Must have write permissions
- Should have sufficient free space (check status indicator)

## Error Handling

### USB Disconnection
- System detects USB removal during scan
- Scan continues but images remain on Pi
- Reconnect USB to resume transfers
- Check scan status for current progress

### Insufficient Space
- System checks available space before starting
- Warning displayed if space is low
- Transfer stops if space runs out during scan

### Invalid Folder Names
- System validates folder names
- Error message for invalid characters
- Automatic retry with corrected name

## API Endpoints

### New Endpoints
- `GET /check_usb` - Check USB drive status
- `POST /create_scan_folder` - Create scan folder on USB
- `GET /scan_status` - Get current scan progress

### Modified Endpoints
- `POST /rotate` - Now includes folder name parameter and real-time USB transfer

## Testing

Run the test script to verify USB functionality:
```bash
cd arducam
python test_usb_transfer.py
```

## Troubleshooting

### USB Not Detected
1. Check USB drive is properly mounted
2. Verify drive has correct permissions
3. Try refreshing USB status
4. Check system logs for mount errors

### Transfer Failures
1. Check available space on USB drive
2. Verify USB drive is not read-only
3. Check file system compatibility
4. Monitor system logs for transfer errors

### Scan Interruptions
1. Check USB connection stability
2. Verify network connectivity (for remote Pi)
3. Monitor system resources
4. Check for hardware issues

## Benefits

- **Time Savings**: Eliminates 10-minute download wait
- **Efficiency**: Continuous scanning throughout the day
- **Organization**: Automatic folder structure on USB
- **Reliability**: Real-time error detection and handling
- **Convenience**: No manual intervention required during scans 