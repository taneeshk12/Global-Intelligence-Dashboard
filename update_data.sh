#!/bin/bash
set -e

# This script is meant to be run on a schedule (e.g. monthly via cron)
echo "=========================================="
echo " Updating GDELT Knowledge Graph Data"
echo "=========================================="

if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "ERROR: GOOGLE_APPLICATION_CREDENTIALS is not set."
    exit 1
fi

echo -e "\n[1/2] Pulling latest 6 months of data from BigQuery..."
cd ingestion
python pull_gdelt_events.py
cd ..

echo -e "\n[2/2] Loading graph and recalculating PageRank..."
cd graph
python load_neo4j.py
python centrality.py
cd ..

echo -e "\n=========================================="
echo " Data Update Complete!"
echo "=========================================="
