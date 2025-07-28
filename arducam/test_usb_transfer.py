#!/usr/bin/env python3
"""
Test script for USB transfer functionality
"""

import os
import sys
import shutil
from datetime import datetime

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from main import get_usb_mounts, validate_and_prepare_usb, isValidFolderName, get_latest_images

def test_usb_functions():
    """Test USB-related functions"""
    print("Testing USB transfer functionality...")
    
    # Test 1: Check USB mounts
    print("\n1. Testing USB mount detection...")
    usb_mounts = get_usb_mounts()
    if usb_mounts:
        print(f"✓ USB drives found: {usb_mounts}")
    else:
        print("✗ No USB drives detected")
        return False
    
    # Test 2: Validate folder name
    print("\n2. Testing folder name validation...")
    test_names = ["test_scan", "scan-123", "invalid name", "a" * 60, ""]
    for name in test_names:
        is_valid = isValidFolderName(name)
        print(f"  '{name}': {'✓' if is_valid else '✗'}")
    
    # Test 3: Create test folder
    print("\n3. Testing folder creation...")
    try:
        test_folder = validate_and_prepare_usb("test_scan")
        print(f"✓ Test folder created: {test_folder}")
        
        # Clean up
        if os.path.exists(test_folder):
            shutil.rmtree(test_folder)
            print("✓ Test folder cleaned up")
        
    except Exception as e:
        print(f"✗ Error creating test folder: {e}")
        return False
    
    # Test 4: Check for existing images
    print("\n4. Testing image detection...")
    images = get_latest_images(5)
    if images:
        print(f"✓ Found {len(images)} recent images")
        for img in images[:3]:  # Show first 3
            print(f"  - {img}")
    else:
        print("ℹ No recent images found (this is normal if no scans have been run)")
    
    print("\n✓ All tests completed successfully!")
    return True

if __name__ == "__main__":
    test_usb_functions() 