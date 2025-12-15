#!/usr/bin/env python3
import asyncio
import subprocess
import time
import os
import sys
import gzip
import shutil
from pathlib import Path
from playwright.async_api import async_playwright

# Configuration
PORT = 8888
VALKEY_VERSION = os.getenv('VALKEY_VERSION', '8.1.0')
TIMEOUT_SECONDS = 20 * 60  # 20 minutes max wait for boot
CHECK_INTERVAL = 2  # Check every 2 seconds
MAX_STATE_SIZE_MB = 40  # Maximum compressed state size in MB
RESPONSE_TIMEOUT = 10  # Timeout for waiting for PING response

async def wait_for_boot_complete(page, timeout=TIMEOUT_SECONDS):
    """Wait for boot to complete by checking for server log data"""
    print("Waiting for boot process to complete...")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Check if server log has content (indicates boot complete)
            log_content = await page.locator('#log-terminal-container').inner_text()
            if log_content and len(log_content.strip()) > 0:
                print("Boot process completed!")
                return True
            
            # Alternative: Check for specific boot completion text
            # Adjust the selector/text based on actual page behavior
            await asyncio.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            await asyncio.sleep(CHECK_INTERVAL)
    
    print("Timeout waiting for boot to complete")
    return False

async def test_basic_functionality(page, valkey_version, compressed_state_path):
    """Test basic functionality of the Valkey image"""
    print("\nRunning basic functionality tests...")
    
    TOTAL_TESTS = 3
    tests_passed = 0
    
    # Test 1: Check if server log contains version
    print(f"\n1. Testing: Server log contains 'version={valkey_version}'")
    try:
        log_content = await page.locator('#log-terminal-container').inner_text()
        if f'version={valkey_version}' in log_content:
            print(f"   Version {valkey_version} found in server log")
            tests_passed += 1
        else:
            print(f"   Version {valkey_version} NOT found in server log")
            print(f"   Log preview: {log_content[:500]}...")
    except Exception as e:
        print(f"   Failed to check server log: {e}")
    
    # Test 2: Send PING and check for PONG response
    print(f"\n2. Testing: PING command responds with PONG")
    try:
        # Focus on the terminal
        terminal = page.locator('#terminal-container')
        await terminal.click()
        await asyncio.sleep(1)
        
        # Type the PING command
        await page.keyboard.type('PING\r')
        print("   Sent: valkey-cli PING")
        
        # Wait for response - access xterm.js buffer through serialAdapter
        pong_found = False
        for attempt in range(RESPONSE_TIMEOUT):  # Try for up to RESPONSE_TIMEOUT seconds
            try:
                # Access the xterm.js terminal buffer through the global serialAdapter
                terminal_text = await page.evaluate('''() => {
                    if (window.serialAdapter && window.serialAdapter.term) {
                        const term = window.serialAdapter.term;
                        const buffer = term.buffer.active;
                        let text = '';
                        
                        // Read all lines from the terminal buffer
                        for (let i = 0; i < buffer.length; i++) {
                            const line = buffer.getLine(i);
                            if (line) {
                                text += line.translateToString(true) + '\\n';
                            }
                        }
                        return text;
                    }
                    return 'serialAdapter not available';
                }''')
                
                print(f"   Attempt {attempt + 1}: Checking terminal buffer...")
                print(f"      Buffer length: {len(terminal_text)} chars")
                
                if 'PONG' in terminal_text:
                    pong_found = True
                    print(f"   PING command successful - received PONG")
                    tests_passed += 1
                    break
                    
            except Exception as e:
                print(f"   Attempt {attempt + 1} error: {e}")
            
            await asyncio.sleep(1) #wait before trying again

        if not pong_found:
            print(f"   PING command failed - PONG not found in response after {RESPONSE_TIMEOUT} seconds")
            
    except Exception as e:
        print(f"   Failed to test PING command: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 3: Check compressed state size
    print(f"\n3. Testing: Compressed state size is less than {MAX_STATE_SIZE_MB} MB")
    try:
        if os.path.exists(compressed_state_path):
            file_size_bytes = os.path.getsize(compressed_state_path)
            file_size_mb = file_size_bytes / (1024 * 1024)
            
            if file_size_mb < MAX_STATE_SIZE_MB:
                print(f"   Compressed state size is {file_size_mb:.2f} MB (< {MAX_STATE_SIZE_MB} MB)")
                tests_passed += 1
            else:
                print(f"   Compressed state size is {file_size_mb:.2f} MB (>= {MAX_STATE_SIZE_MB} MB)")
        else:
            print(f"   Compressed state file not found: {compressed_state_path}")
    except Exception as e:
        print(f"   Failed to check state size: {e}")
    
    # Summary
    print("\n" + "="*50)
    if tests_passed == TOTAL_TESTS:
        print("All tests passed!")
    else:
        print(f"Some tests failed! ({tests_passed}/{TOTAL_TESTS} passed)")
    print("="*50 + "\n")
    
    return tests_passed == TOTAL_TESTS

async def automate_state_save(valkey_version):
    """Main automation function"""
    
    # Start HTTP server
    print(f"Starting HTTP server on port {PORT}...")
    server_process = subprocess.Popen(
        ['python3', '-m', 'http.server', str(PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Give server time to start
    await asyncio.sleep(2)
    
    try:
        async with async_playwright() as p:
            # Launch browser
            print("Launching browser...")
            browser = await p.chromium.launch(headless=True)  # Set to True for headless
            
            # Setup download handling
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()
            
            # Navigate to image creator
            url = f'http://localhost:{PORT}/{VALKEY_VERSION}/image_creator.html'
            print(f"Navigating to {url}")
            await page.goto(url)
            
            # Wait for boot to complete
            boot_success = await wait_for_boot_complete(page, TIMEOUT_SECONDS)
            
            if not boot_success:
                raise Exception("Boot process did not complete in time")
            
            # Click "Download State" button
            print("Downloading state...")
            async with page.expect_download() as download_info:
                await page.click('button:has-text("Download State")')
                download = await download_info.value
            
            # Save the download
            download_filename = download.suggested_filename
            temp_path = f'/tmp/{download_filename}'
            await download.save_as(temp_path)
            print(f"State downloaded: {temp_path}")
            
            # Compress the file
            print("Compressing state file...")
            compressed_path = f'{temp_path}.gz'
            with open(temp_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            print(f"State compressed: {compressed_path}")
            
            # Run tests BEFORE closing browser
            # Run the tests AFTER saving the state so test commands don't appear in the saved snapshot, and to be able to check saved state size.
            tests_passed = await test_basic_functionality(page, valkey_version, compressed_path)
            
            if not tests_passed:
                print("Warning: Some tests failed, but continuing with file operations...")
            
            # Move to correct directory
            target_dir = Path(f'{valkey_version}/states')
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / f'{download_filename}.gz'
            shutil.move(compressed_path, target_path)
            print(f"State moved to: {target_path}")
            
            # Cleanup
            os.remove(temp_path)
            
            # Close browser
            await browser.close()
            
            if tests_passed:
                print("Automation completed successfully with all tests passing!")
            else:
                print("Automation completed but some tests failed!")
                sys.exit(1)
            
    finally:
        # Stop HTTP server
        print("Stopping HTTP server...")
        server_process.terminate()
        server_process.wait()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        VALKEY_VERSION = sys.argv[1]
    
    print(f"Automating state save for Valkey version: {VALKEY_VERSION}")
    asyncio.run(automate_state_save(VALKEY_VERSION))
