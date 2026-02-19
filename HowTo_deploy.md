# How to Deploy and Test

## Deployment

### Quick Deploy

```bash
./deploy.sh
```

This will:
1. Pull latest code from GitHub on whisper1 server
2. Fix group permissions for js-web-render group

### Manual Deploy

```bash
# On the server
cd /opt/js-web-renderer
git fetch origin master
git reset --hard origin/master

# Fix permissions
sudo chgrp -R js-web-render /opt/js-web-renderer
sudo chmod -R g+rw /opt/js-web-renderer
```

## Testing

### Manual CLI Tests

```bash
# Test basic render
ssh whisper1 "python3 /opt/js-web-renderer/bin/fetch-rendered.py https://example.com --wait 3"

# Test screenshot
ssh whisper1 "python3 /opt/js-web-renderer/bin/fetch-rendered.py https://example.com --screenshot /tmp/test.png --wait 3"

# Test network capture
ssh whisper1 "python3 /opt/js-web-renderer/bin/fetch-rendered.py https://example.com --only-network --wait 3"

# Test help
ssh whisper1 "python3 /opt/js-web-renderer/bin/fetch-rendered.py --help"
```

### Automated Tests

The CLI is tested as part of the js-web-renderer-REST-API test suite. See that repository for automated tests.

```bash
cd ../js-web-renderer-REST-API
pip3 install pytest pytest-asyncio httpx
export API_KEY="your-api-key"
export TEST_BASE_URL="http://whisper1:9000"
pytest tests/test_cli.py -v
```

## Troubleshooting

### Chromium not found

```bash
# Check chromium is installed
ssh whisper1 "which chromium"

# Check chromedriver
ssh whisper1 "which chromium-chromedriver"
```

### Permission denied errors

```bash
# Fix permissions
ssh whisper1 "sudo chgrp -R js-web-render /opt/js-web-renderer"
ssh whisper1 "sudo chmod -R g+rw /opt/js-web-renderer"
ssh whisper1 "sudo chmod +x /opt/js-web-renderer/bin/fetch-rendered.py"
```

### Browser not starting

```bash
# Check logs
ssh whisper1 "python3 /opt/js-web-renderer/bin/fetch-rendered.py https://example.com --wait 3" 2>&1
```
