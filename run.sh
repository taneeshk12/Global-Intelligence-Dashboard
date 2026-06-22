#!/bin/bash
set -e

echo "=========================================="
echo " Starting GDELT Knowledge Graph Stack"
echo "=========================================="

echo "=========================================="
echo " Starting GDELT Knowledge Graph Servers"
echo "=========================================="

echo -e "\nStarting Docker containers (Neo4j, API, Frontend)..."
docker compose up -d

echo -e "\n=========================================="
echo " Success! Servers are running."
echo " Dashboard: http://localhost:8080"
echo " API Docs:  http://localhost:8000/docs"
echo "=========================================="
echo " Note: Data updates are now handled separately."
