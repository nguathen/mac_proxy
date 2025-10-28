#!/bin/bash
# debug_start.sh - Script debug cho autostart

cd /Volumes/Ssd/Projects/mac_proxy

echo "=== DEBUG START SCRIPT ===" >> logs/debug.log
echo "Date: $(date)" >> logs/debug.log
echo "User: $(whoami)" >> logs/debug.log
echo "PWD: $(pwd)" >> logs/debug.log
echo "PATH: $PATH" >> logs/debug.log
echo "=========================" >> logs/debug.log

# Test các command cơ bản
echo "Testing basic commands..." >> logs/debug.log
which bash >> logs/debug.log 2>&1
which haproxy >> logs/debug.log 2>&1

# Test script start_all.sh
echo "Testing start_all.sh..." >> logs/debug.log
if [ -f "./start_all.sh" ]; then
    echo "start_all.sh exists" >> logs/debug.log
    ls -la ./start_all.sh >> logs/debug.log
else
    echo "start_all.sh NOT FOUND" >> logs/debug.log
fi

# Thử chạy start_all.sh với error handling
echo "Running start_all.sh..." >> logs/debug.log
bash ./start_all.sh >> logs/debug.log 2>&1
echo "Exit code: $?" >> logs/debug.log

echo "=== END DEBUG ===" >> logs/debug.log
