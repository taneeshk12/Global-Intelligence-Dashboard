#!/bin/bash

# Configuration
NEO4J_CONTAINER="gdelt_neo4j"
NEO4J_USER=${NEO4J_USER:-neo4j}
NEO4J_PASSWORD=${NEO4J_PASSWORD:-password}

echo "Starting automated graph seeding..."
echo "Waiting for Neo4j to be fully online..."

# Wait until Neo4j is ready to accept Cypher queries
until docker exec $NEO4J_CONTAINER cypher-shell -u $NEO4J_USER -p "$NEO4J_PASSWORD" "RETURN 1" > /dev/null 2>&1; do
    echo "Neo4j is unavailable - sleeping"
    sleep 2
done

echo "Neo4j is up. Seeding GDS graphs..."

# 1. Project the Graph
echo "Projecting graph..."
docker exec $NEO4J_CONTAINER cypher-shell -u $NEO4J_USER -p "$NEO4J_PASSWORD" "CALL gds.graph.project('gdelt_graph', 'Actor', 'ECONOMIC_EVENT') YIELD graphName RETURN graphName"

# 2. Run PageRank
echo "Running PageRank..."
docker exec $NEO4J_CONTAINER cypher-shell -u $NEO4J_USER -p "$NEO4J_PASSWORD" "CALL gds.pageRank.write('gdelt_graph', {writeProperty: 'pagerank'}) YIELD nodePropertiesWritten RETURN nodePropertiesWritten"

# 3. Run Louvain Modularity for Blocs
echo "Running Louvain Modularity..."
docker exec $NEO4J_CONTAINER cypher-shell -u $NEO4J_USER -p "$NEO4J_PASSWORD" "CALL gds.louvain.write('gdelt_graph', {writeProperty: 'community'}) YIELD nodePropertiesWritten RETURN nodePropertiesWritten"

echo "Graph seeding complete! The dashboard is fully ready."
