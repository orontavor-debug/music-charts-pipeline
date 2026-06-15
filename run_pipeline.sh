#!/bin/bash

cd /Users/orontavor/Desktop/bootcamp/music-charts-pipeline

/Users/orontavor/Desktop/bootcamp/music-charts-pipeline/venv/bin/python pipeline.py >> pipeline.log 2>&1

if [ $? -ne 0 ]; then
    osascript -e 'display notification "Check pipeline.log for details." with title "Music Charts Pipeline FAILED" sound name "Basso"'
else
    osascript -e 'display notification "300 rows loaded into Postgres." with title "Music Charts Pipeline OK"'
fi
