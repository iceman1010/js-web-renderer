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
    --timeout N          Hard wall-clock timeout in seconds for the entire operation (default: 60)
"""
import sys
import os
import pwd
if "XDG_RUNTIME_DIR" not in os.environ:
    os.environ["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
import json
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time


def _build_chrome_options(width, height, capture_console, capture_network, profile_dir):
    """Build Chrome options — separated out so both fetch_rendered and the timeout
    wrapper can create a driver consistently."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument(f"--window-size={width},{height}")

    if profile_dir:
        os.makedirs(profile_dir, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={profile_dir}")
        print(f"[profile] Using {profile_dir}", file=sys.stderr)

    logging_prefs = {}
    if capture_console:
        logging_prefs["browser"] = "ALL"
    if capture_network:
        logging_prefs["performance"] = "ALL"
    if logging_prefs:
        chrome_options.set_capability("goog:loggingPrefs", logging_prefs)

    return chrome_options


def _fetch_rendered_inner(url, wait_seconds=5, capture_console=False, screenshot_path=None,
                          width=1280, height=900, exec_js=None, post_js=None,
                          capture_network=False, type_actions=None, click_actions=None,
                          post_wait_seconds=0, profile_dir=None,
                          _driver=None, _page_load_timeout=30, _script_timeout=15):
    """
    Core fetch logic — private. Do not call directly; use fetch_rendered() instead,
    which always enforces a hard wall-clock timeout via fetch_with_timeout().

    Accepts an optional pre-created _driver so that fetch_with_timeout() can hold
    the driver reference for emergency SIGKILL on timeout.
    _page_load_timeout and _script_timeout are applied to the driver here;
    the hard wall-clock deadline is enforced externally by fetch_with_timeout().
    """
    chrome_options = _build_chrome_options(width, height, capture_console, capture_network, profile_dir)
    service = Service("/snap/bin/chromium.chromedriver")

    driver = _driver
    driver_owned = driver is None  # only quit if we created it ourselves

    try:
        if driver is None:
            driver = webdriver.Chrome(service=service, options=chrome_options)

        driver.set_window_size(width, height)

        # Guard the initial page load — most common hang point
        driver.set_page_load_timeout(_page_load_timeout)
        # Guard individual execute_script() calls (e.g. exec_js with infinite loops)
        driver.set_script_timeout(_script_timeout)

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
        if driver and driver_owned:
            try:
                driver.quit()
            except Exception:
                pass


def fetch_with_timeout(url, total_timeout=60, **kwargs):
    """
    Runs _fetch_rendered_inner() under a hard wall-clock timeout.

    Layers of timeout protection:
      - total_timeout (this function)  — hard wall-clock deadline via threading
      - _page_load_timeout             — guards driver.get() blocking (default: 60% of total)
      - _script_timeout                — guards each execute_script() call (default: 15s)

    If total_timeout is exceeded, the chromedriver process is SIGKILLed directly,
    which unblocks any Selenium call that is stuck in IPC with Chrome.

    Raises TimeoutError if the deadline is exceeded, or re-raises any exception
    from fetch_rendered() otherwise.
    """
    # Warn if free memory looks too low to safely launch a Chrome instance.
    # Chrome typically needs 300-500MB; we warn at 512MB as a conservative threshold.
    # This is advisory only — the call proceeds regardless. For hard rejection,
    # put an is_mem_enough() guard in your REST API wrapper instead.
    _CHROME_MEM_WARN_MB = 512
    try:
        # MemAvailable (since kernel 3.14) is the most accurate measure of how much
        # RAM is actually available for a new process — it accounts for reclaimable
        # cache and buffers, unlike MemFree alone.
        meminfo = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, val = line.split(":", 1)
                meminfo[key.strip()] = int(val.split()[0])  # values are in kB
        mem_available_mb = meminfo.get("MemAvailable", meminfo.get("MemFree", 0)) / 1024
        if mem_available_mb < _CHROME_MEM_WARN_MB:
            print(
                f"[warn] only {mem_available_mb:.0f}MB of RAM available "
                f"(threshold: {_CHROME_MEM_WARN_MB}MB) — Chrome may fail or cause OOM",
                file=sys.stderr,
            )
    except Exception:
        pass  # never let a monitoring check break the actual fetch

    # Derive sub-timeouts from the total budget if not explicitly provided
    page_load_timeout = kwargs.pop("_page_load_timeout", int(total_timeout * 0.6))
    script_timeout    = kwargs.pop("_script_timeout",    min(15, int(total_timeout * 0.25)))

    # Build the driver up front so we hold the reference for emergency kill.
    # fetch_rendered() will skip creating its own driver when _driver is passed.
    width          = kwargs.get("width", 1280)
    height         = kwargs.get("height", 900)
    capture_console = kwargs.get("capture_console", False)
    capture_network = kwargs.get("capture_network", False)
    profile_dir    = kwargs.get("profile_dir", None)

    chrome_options = _build_chrome_options(width, height, capture_console, capture_network, profile_dir)
    service = Service("/snap/bin/chromium.chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)

    result_holder = {"result": None, "error": None}

    def _run():
        try:
            result_holder["result"] = _fetch_rendered_inner(
                url,
                _driver=driver,
                _page_load_timeout=page_load_timeout,
                _script_timeout=script_timeout,
                **kwargs,
            )
        except Exception as exc:
            result_holder["error"] = exc

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    thread.join(timeout=total_timeout)

    if thread.is_alive():
        # The thread is still blocked — force-kill Chrome at the OS level.
        # driver.service.process is the chromedriver subprocess; killing it
        # causes Chrome to exit too, which unblocks any pending IPC in the thread.
        print(f"[timeout] Hard timeout of {total_timeout}s exceeded for {url}, killing Chrome",
              file=sys.stderr)
        try:
            driver.service.process.kill()
        except Exception:
            pass
        # Also attempt a graceful quit in case the process is somehow still alive;
        # this is best-effort and may itself raise.
        try:
            driver.quit()
        except Exception:
            pass
        raise TimeoutError(
            f"fetch_rendered() exceeded {total_timeout}s wall-clock timeout for {url}"
        )

    # Normal completion — driver was already quit inside fetch_rendered's finally block.
    if result_holder["error"]:
        raise result_holder["error"]

    return result_holder["result"]


def fetch_rendered(url, total_timeout=60, **kwargs):
    """
    Public entry point — always enforces a hard wall-clock timeout.
    All calls go through fetch_with_timeout(), which SIGKILLs Chrome if the
    deadline is exceeded. The timeout covers driver startup, page load,
    JS execution, waits, and teardown combined.

    Args:
        url:           URL to fetch.
        total_timeout: Hard wall-clock deadline in seconds (default: 60).
        **kwargs:      All other arguments accepted by _fetch_rendered_inner()
                       (wait_seconds, capture_console, screenshot_path, width,
                        height, exec_js, post_js, capture_network, type_actions,
                        click_actions, post_wait_seconds, profile_dir).

    Returns:
        (html, console_logs, network_requests)

    Raises:
        TimeoutError: if total_timeout is exceeded.
    """
    return fetch_with_timeout(url, total_timeout=total_timeout, **kwargs)


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
    total_timeout = 60

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
        elif arg == "--timeout" and i + 1 < len(sys.argv):
            i += 1
            total_timeout = int(sys.argv[i])
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
        html, console_logs, network_requests = fetch_with_timeout(
            url,
            total_timeout=total_timeout,
            wait_seconds=wait_seconds,
            capture_console=show_console or only_console,
            screenshot_path=screenshot_path,
            width=width,
            height=height,
            exec_js=exec_js,
            post_js=post_js,
            capture_network=capture_network,
            type_actions=type_actions if type_actions else None,
            click_actions=click_actions if click_actions else None,
            post_wait_seconds=post_wait_seconds,
            profile_dir=profile_dir,
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

    except TimeoutError as e:
        print(f"Timeout: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        sys.exit(1)
