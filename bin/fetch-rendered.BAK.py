#!/usr/bin/env python3
"""
Fetch JavaScript-rendered HTML using Selenium and headless Chromium.
Usage: js-web-renderer <URL> [options]

Options:
    --console, -c        Show browser console logs (errors, warnings, etc.)
    --only-console       Show only console logs, no HTML
    --screenshot FILE    Save a screenshot to FILE (PNG format)
    --only-screenshot    Only take screenshot, no HTML output
    --wait N             Wait N seconds for JS to render (default: 5)
    --width W            Browser viewport width (default: 1280)
    --height H           Browser viewport height (default: 900)
    --exec-js CODE       Execute JavaScript after page load (before wait)
    --exec-js-file FILE  Execute JavaScript from file after page load
    --post-js CODE       Execute JavaScript after wait completes
    --post-js-file FILE  Execute JavaScript from file after wait
    --post-wait N        Wait N seconds after post-js (for navigation, etc.)
    --network-log        Capture and display network requests (performance log)
    --only-network       Show only network requests, no HTML
    --type SEL::VALUE    Type VALUE into element matching CSS SELector (can repeat)
    --click SEL          Click element matching CSS SELector (can repeat)
    --profile DIR        Use persistent Chrome profile directory (for session persistence)
"""
import sys
import os
import pwd
if "XDG_RUNTIME_DIR" not in os.environ:
    os.environ["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def fetch_rendered(url, wait_seconds=5, capture_console=False, screenshot_path=None,
                   width=1280, height=900, exec_js=None, post_js=None,
                   capture_network=False, type_actions=None, click_actions=None,
                   post_wait_seconds=0, profile_dir=None):
    # Set up Chrome options for headless mode
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument(f"--window-size={width},{height}")

    # Use persistent profile directory if specified (enables session persistence)
    if profile_dir:
        os.makedirs(profile_dir, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={profile_dir}")
        print(f"[profile] Using {profile_dir}", file=sys.stderr)

    # Enable browser logging for console and/or network capture
    logging_prefs = {}
    if capture_console:
        logging_prefs["browser"] = "ALL"
    if capture_network:
        logging_prefs["performance"] = "ALL"
    if logging_prefs:
        chrome_options.set_capability("goog:loggingPrefs", logging_prefs)

    # Set up the Chrome driver service
    service = Service("/snap/bin/chromium.chromedriver")

    driver = None
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_window_size(width, height)

        # Load the page
        driver.get(url)

        # Execute pre-wait JavaScript if provided
        js_result = None
        if exec_js:
            js_result = driver.execute_script(exec_js)
            if js_result is not None:
                print(f"[exec-js result] {js_result}", file=sys.stderr)

        # Wait for JavaScript to render
        time.sleep(wait_seconds)

        # Perform type actions using Selenium's send_keys (more reliable for React)
        if type_actions:
            for selector, value in type_actions:
                try:
                    element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    element.clear()
                    element.send_keys(value)
                    print(f"[type] {selector} = {value[:20]}{'...' if len(value) > 20 else ''}", file=sys.stderr)
                except Exception as e:
                    print(f"[type error] {selector}: {e}", file=sys.stderr)

        # Perform click actions
        if click_actions:
            for selector in click_actions:
                try:
                    element = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    element.click()
                    print(f"[click] {selector}", file=sys.stderr)
                except Exception as e:
                    print(f"[click error] {selector}: {e}", file=sys.stderr)

        # Execute post-wait JavaScript if provided
        post_js_result = None
        if post_js:
            post_js_result = driver.execute_script(post_js)
            if post_js_result is not None:
                print(f"[post-js result] {post_js_result}", file=sys.stderr)

        # Wait after post-js for navigation/loading to complete
        if post_wait_seconds > 0:
            time.sleep(post_wait_seconds)

        # Get the rendered HTML
        html = driver.page_source

        # Get current URL (useful after redirects)
        current_url = driver.current_url
        print(f"[current url] {current_url}", file=sys.stderr)

        # Get console logs if requested
        console_logs = []
        if capture_console:
            console_logs = driver.get_log("browser")

        # Get network logs if requested
        network_requests = []
        if capture_network:
            perf_logs = driver.get_log("performance")
            for entry in perf_logs:
                try:
                    msg = json.loads(entry["message"])["message"]
                    method = msg.get("method", "")
                    params = msg.get("params", {})
                    if method == "Network.requestWillBeSent":
                        req = params.get("request", {})
                        network_requests.append({
                            "type": "request",
                            "url": req.get("url", ""),
                            "method": req.get("method", ""),
                            "resource_type": params.get("type", ""),
                        })
                    elif method == "Network.responseReceived":
                        resp = params.get("response", {})
                        network_requests.append({
                            "type": "response",
                            "url": resp.get("url", ""),
                            "status": resp.get("status", 0),
                            "mime": resp.get("mimeType", ""),
                            "headers": resp.get("headers", {}),
                        })
                except (json.JSONDecodeError, KeyError):
                    continue

        # Take screenshot if requested
        if screenshot_path:
            # Get full page height
            total_height = driver.execute_script("return document.body.scrollHeight")
            driver.set_window_size(width, total_height)
            time.sleep(0.5)  # Brief wait for resize
            driver.save_screenshot(screenshot_path)

        return html, console_logs, network_requests

    finally:
        if driver:
            driver.quit()

def format_console_logs(logs):
    """Format console logs for readable output."""
    output = []
    for entry in logs:
        level = entry.get("level", "INFO")
        message = entry.get("message", "")
        output.append(f"[{level}] {message}")
    return "\n".join(output)

def format_network_requests(requests):
    """Format network requests for readable output."""
    output = []
    for entry in requests:
        if entry["type"] == "request":
            output.append(f"[{entry['method']}] {entry['url']}  ({entry['resource_type']})")
        elif entry["type"] == "response":
            location = entry.get("headers", {}).get("location", entry.get("headers", {}).get("Location", ""))
            line = f"  -> {entry['status']} {entry['mime']}  {entry['url']}"
            if location:
                line += f"\n     Location: {location}"
            output.append(line)
    return "\n".join(output)

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help"]:
        print(__doc__, file=sys.stderr)
        sys.exit(1 if len(sys.argv) < 2 else 0)

    url = None
    show_console = False
    only_console = False
    screenshot_path = None
    only_screenshot = False
    wait_seconds = 5
    width = 1280
    height = 900
    exec_js = None
    post_js = None
    capture_network = False
    only_network = False
    type_actions = []
    click_actions = []
    post_wait_seconds = 0
    profile_dir = None

    # Parse arguments
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg in ["--console", "-c"]:
            show_console = True
        elif arg == "--only-console":
            show_console = True
            only_console = True
        elif arg == "--screenshot" and i + 1 < len(sys.argv):
            i += 1
            screenshot_path = sys.argv[i]
        elif arg == "--only-screenshot":
            only_screenshot = True
        elif arg == "--wait" and i + 1 < len(sys.argv):
            i += 1
            wait_seconds = int(sys.argv[i])
        elif arg == "--width" and i + 1 < len(sys.argv):
            i += 1
            width = int(sys.argv[i])
        elif arg == "--height" and i + 1 < len(sys.argv):
            i += 1
            height = int(sys.argv[i])
        elif arg == "--exec-js" and i + 1 < len(sys.argv):
            i += 1
            exec_js = sys.argv[i]
        elif arg == "--exec-js-file" and i + 1 < len(sys.argv):
            i += 1
            with open(sys.argv[i], "r") as f:
                exec_js = f.read()
        elif arg == "--post-js" and i + 1 < len(sys.argv):
            i += 1
            post_js = sys.argv[i]
        elif arg == "--post-js-file" and i + 1 < len(sys.argv):
            i += 1
            with open(sys.argv[i], "r") as f:
                post_js = f.read()
        elif arg == "--post-wait" and i + 1 < len(sys.argv):
            i += 1
            post_wait_seconds = int(sys.argv[i])
        elif arg == "--network-log":
            capture_network = True
        elif arg == "--only-network":
            capture_network = True
            only_network = True
        elif arg == "--type" and i + 1 < len(sys.argv):
            i += 1
            # Format: selector::value (using :: to avoid conflicts with = in CSS selectors)
            if "::" in sys.argv[i]:
                selector, value = sys.argv[i].split("::", 1)
                type_actions.append((selector, value))
            else:
                print(f"Error: --type requires format 'selector::value'", file=sys.stderr)
        elif arg == "--click" and i + 1 < len(sys.argv):
            i += 1
            click_actions.append(sys.argv[i])
        elif arg == "--profile" and i + 1 < len(sys.argv):
            i += 1
            profile_dir = sys.argv[i]
        elif not arg.startswith("-"):
            url = arg
        i += 1

    if not url:
        print("Error: URL required", file=sys.stderr)
        sys.exit(1)

    # If only-screenshot but no path specified, generate one
    if only_screenshot and not screenshot_path:
        screenshot_path = "/tmp/screenshot.png"

    try:
        html, console_logs, network_requests = fetch_rendered(
            url,
            wait_seconds,
            show_console or only_console,
            screenshot_path,
            width,
            height,
            exec_js,
            post_js,
            capture_network,
            type_actions if type_actions else None,
            click_actions if click_actions else None,
            post_wait_seconds,
            profile_dir,
        )

        if screenshot_path:
            print(f"Screenshot saved to: {screenshot_path}", file=sys.stderr)

        # Determine output
        if only_screenshot:
            pass
        elif only_network:
            if network_requests:
                print(format_network_requests(network_requests))
            else:
                print("No network requests captured.")
        elif only_console:
            if console_logs:
                print(format_console_logs(console_logs))
            else:
                print("No console messages captured.")
        else:
            print(html)
            if show_console and console_logs:
                print("\n" + "="*60)
                print("BROWSER CONSOLE LOGS:")
                print("="*60)
                print(format_console_logs(console_logs))
            if capture_network and network_requests:
                print("\n" + "="*60)
                print("NETWORK REQUESTS:")
                print("="*60)
                print(format_network_requests(network_requests))

    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        sys.exit(1)
