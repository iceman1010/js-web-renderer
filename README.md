# JS Web Renderer

A tool for fetching JavaScript-rendered HTML content using Selenium and headless Chromium.

## Purpose

Many modern websites use JavaScript frameworks (React, Vue, Angular, etc.) that render content in the browser. Traditional HTTP clients (curl, wget, WebFetch) only retrieve the initial HTML skeleton and miss the dynamically rendered content.

This tool uses Selenium WebDriver with headless Chromium to:
- Load the page in a real browser environment
- Wait for JavaScript to execute and render content
- Extract the final rendered HTML
- Capture browser console logs (errors, warnings, etc.)
- Take full-page screenshots
- Execute custom JavaScript on the page
- Capture network requests (XHR, fetch, resources, etc.)
- Fill form inputs and click elements (for login flows, etc.)

## Installation

The tool is installed at `/opt/js-web-renderer/` with the following structure:

```
/opt/js-web-renderer/
├── bin/
│   └── fetch-rendered.py    # Main executable
├── lib/                      # Reserved for future Python modules
└── README.md                 # This file
```

A symlink is created at `/usr/local/bin/js-web-renderer` for easy access.

## Requirements

- Python 3
- Selenium (`pip3 install selenium --user`)
- Chromium browser (installed via snap)
- Chromium ChromeDriver (chromium-chromedriver package)

## Usage

```bash
js-web-renderer <URL> [options]
```

### Options

| Option | Description |
|--------|-------------|
| `--console`, `-c` | Show browser console logs (errors, warnings, etc.) |
| `--only-console` | Show only console logs, no HTML output |
| `--screenshot FILE` | Save a screenshot to FILE (PNG format) |
| `--only-screenshot` | Only take screenshot, no HTML output (saves to /tmp/screenshot.png if no path given) |
| `--wait N` | Wait N seconds for JS to render (default: 5) |
| `--width W` | Browser viewport width in pixels (default: 1280) |
| `--height H` | Browser viewport height in pixels (default: 900) |
| `--exec-js CODE` | Execute JavaScript after page load, before wait |
| `--exec-js-file FILE` | Execute JavaScript from a file after page load, before wait |
| `--post-js CODE` | Execute JavaScript after wait completes |
| `--post-js-file FILE` | Execute JavaScript from a file after wait completes |
| `--post-wait N` | Wait N seconds after post-js/actions (for page navigation) |
| `--network-log` | Capture and display network requests (appended after HTML) |
| `--only-network` | Show only network requests, no HTML output |
| `--type SEL::VALUE` | Type VALUE into element matching CSS SELector (can repeat) |
| `--click SEL` | Click element matching CSS SELector (can repeat) |
| `--profile DIR` | Use persistent Chrome profile directory (for session persistence) |

### Examples

Fetch rendered HTML:
```bash
js-web-renderer https://example.com
```

Fetch HTML with console logs:
```bash
js-web-renderer https://example.com --console
```

Show only console errors (useful for debugging):
```bash
js-web-renderer https://example.com --only-console
```

Take a screenshot:
```bash
js-web-renderer https://example.com --screenshot /tmp/page.png
```

Take only a screenshot (no HTML output):
```bash
js-web-renderer https://example.com --only-screenshot --screenshot /tmp/page.png
```

Custom viewport size:
```bash
js-web-renderer https://example.com --width 1920 --height 1080 --screenshot /tmp/page.png
```

Longer wait for slow-loading pages:
```bash
js-web-renderer https://example.com --wait 10
```

Execute JavaScript to click a button after the page renders:
```bash
js-web-renderer https://example.com --wait 3 --post-js "document.querySelector('button.download').click();"
```

Execute JavaScript from a file:
```bash
js-web-renderer https://example.com --exec-js-file /tmp/setup.js --post-js-file /tmp/interact.js
```

Capture network requests to find API calls or download URLs:
```bash
js-web-renderer https://example.com --only-network --wait 5
```

Combine JS execution with network capture (e.g., click download and see resulting requests):
```bash
js-web-renderer https://app.example.com/share/TOKEN --only-network --wait 3 \
  --post-js "document.querySelector('[aria-label=Download]').click();"
```

Login to a website using native Selenium input (more reliable for React forms):
```bash
js-web-renderer https://app.put.io/files --wait 3 \
  --type "input[name=username]::myuser" \
  --type "input[name=password]::mypassword" \
  --click "button[type=submit]" \
  --post-wait 10 \
  --screenshot /tmp/after-login.png
```

Persistent session (login once, stay logged in on subsequent runs):
```bash
# First run: login and save session to profile
js-web-renderer https://app.put.io/files --wait 3 \
  --profile /tmp/putio-profile \
  --type "input[name=username]::myuser" \
  --type "input[name=password]::mypassword" \
  --click "button[type=submit]" \
  --post-wait 10

# Subsequent runs: already logged in, no credentials needed
js-web-renderer https://app.put.io/files --wait 3 \
  --profile /tmp/putio-profile \
  --screenshot /tmp/files.png
```

## How It Works

1. Launches Chromium in headless mode (no GUI)
2. Sets viewport to specified dimensions
3. Navigates to the specified URL
4. Executes `--exec-js` / `--exec-js-file` JavaScript (if provided)
5. Waits for JavaScript to render (configurable with `--wait`)
6. Performs `--type` actions using Selenium's native send_keys
7. Performs `--click` actions using Selenium's native click
8. Executes `--post-js` / `--post-js-file` JavaScript (if provided)
9. Waits for navigation if `--post-wait` is specified
10. Optionally captures console logs
11. Optionally captures network requests (via Chrome DevTools performance log)
12. Optionally takes a full-page screenshot
13. Extracts the final page source
14. Outputs current URL to stderr (useful for detecting redirects)
15. Outputs results to stdout/file

## Use Cases

- Debugging JavaScript errors on web pages
- Reading JavaScript-rendered documentation sites
- Taking screenshots of web pages for testing/documentation
- Scraping single-page applications (SPAs)
- Testing web applications
- Extracting data from React/Vue/Angular sites
- Intercepting network requests to discover API endpoints and download URLs
- Automating button clicks and form interactions on JS-heavy pages
- Automated login flows for React/Vue/Angular applications

## Troubleshooting

**Error: ChromeDriver not found**
- Ensure chromium-chromedriver is installed: `sudo apt install chromium-chromedriver`

**Error: Module 'selenium' not found**
- Install Selenium: `pip3 install selenium --user`

**Page content is incomplete**
- Increase wait time: `--wait 10`

**Screenshot is cut off**
- The tool automatically resizes to capture full page height

**ChromeDriver hangs or won't connect**
- Check for stale chromedriver processes: `ps aux | grep chromedriver`
- Kill any stale processes and retry
- Ensure `/var` has free disk space (chromedriver needs temp space)

**Login form not working (React/Vue/Angular)**
- Use `--type` and `--click` options instead of `--post-js` for form interactions
- Selenium's native send_keys is more reliable for React controlled inputs

## Changelog

### 2026-01-29
- Added `--profile DIR` for persistent Chrome profile (enables session persistence across runs)

### 2026-01-28
- Added `--type SEL::VALUE` for native Selenium input typing (uses `::` separator)
- Added `--click SEL` for native Selenium click actions
- Added `--post-wait N` for waiting after actions/post-js (useful for login redirects)
- Added current URL output to stderr (helps detect navigation/redirects)
- Uses WebDriverWait for reliable element interaction

### 2026-01-28 (earlier)
- Added `--exec-js` and `--exec-js-file` flags for executing JavaScript after page load
- Added `--post-js` and `--post-js-file` flags for executing JavaScript after wait
- Added `--network-log` and `--only-network` flags for capturing network requests
- Network capture uses Chrome DevTools performance logging to show request URLs, methods, response status, and MIME types

### 2026-01-24
- Added `--console` and `--only-console` flags for browser console log capture
- Added `--screenshot` and `--only-screenshot` flags for taking screenshots
- Added `--width` and `--height` flags for custom viewport dimensions
- Screenshots now capture full page height automatically

### 2026-01-04
- Initial release
- Basic HTML fetching with headless Chromium

## Maintenance

Installed: 2026-01-04
Last Updated: 2026-02-19
Chromium Version: 143.0.7499.146
Selenium Version: 4.39.0

## Deployment

### GitHub Repository

The project is hosted at: https://github.com/iceman1010/js-web-renderer

### Local Deploy Script

The project includes a `deploy.sh` script for deploying to the production server (whisper1):

```bash
# Deploy to whisper1 server
./deploy.sh
```

The script will:
1. Pull latest code from GitHub on the server
2. Fix group permissions for the js-web-render group

### Manual Deployment

```bash
# On the server
cd /opt/js-web-renderer
git fetch origin master
git reset --hard origin/master
sudo chgrp -R js-web-render /opt/js-web-renderer
sudo chmod -R g+rw /opt/js-web-renderer
```

## Testing

The CLI tool is tested as part of the js-web-renderer-REST-API test suite. See the REST API repository for test scripts.

### Running CLI Tests Manually

```bash
# Test basic render
python3 /opt/js-web-renderer/bin/fetch-rendered.py https://example.com --wait 3

# Test screenshot
python3 /opt/js-web-renderer/bin/fetch-rendered.py https://example.com --screenshot /tmp/test.png --wait 3

# Test network capture
python3 /opt/js-web-renderer/bin/fetch-rendered.py https://example.com --only-network --wait 3

# Test help
python3 /opt/js-web-renderer/bin/fetch-rendered.py --help
```
