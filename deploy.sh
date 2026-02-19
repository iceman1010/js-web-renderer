#!/bin/bash
set -e

echo "Deploying js-web-renderer to whisper1..."
ssh whisper1 "cd /opt/js-web-renderer && git fetch origin master && git reset --hard origin/master"
ssh whisper1 "sudo chgrp -R js-web-render /opt/js-web-renderer && sudo chmod -R g+rw /opt/js-web-renderer"
echo "Deployment complete!"
