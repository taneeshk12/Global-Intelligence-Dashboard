import os
from neo4j import GraphDatabase

URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
AUTH = (os.environ.get("NEO4J_USER", "neo4j"), os.environ.get("NEO4J_PASSWORD", "password"))

def run_pagerank(driver):
    with driver.session() as session:
        # 1. Check if the projected graph already exists and drop it if so
        print("Ensuring a clean state for graph projection...")
        session.run("""
        CALL gds.graph.exists('gdelt_graph') YIELD exists
        WITH exists WHERE exists = true
        CALL gds.graph.drop('gdelt_graph') YIELD graphName
        RETURN graphName
        """)

        # 2. Project the graph into memory for GDS
        # 2. Project the graph into memory for GDS
        print("Projecting graph into memory...")
        session.run("""
        CALL gds.graph.project(
            'gdelt_graph',
            'Actor',
            'ECONOMIC_EVENT'
        )
        """)

        print("Running PageRank...")
        result = session.run("""
        CALL gds.pageRank.write('gdelt_graph', {
          maxIterations: 20,
          dampingFactor: 0.85,
          writeProperty: 'pagerank'
        })
        YIELD nodePropertiesWritten, ranIterations
        RETURN nodePropertiesWritten, ranIterations
        """).single()
        print(f"PageRank completed in {result['ranIterations']} iterations. Properties written: {result['nodePropertiesWritten']}")

        print("Running Louvain Modularity for Community Detection...")
        result_louvain = session.run("""
        CALL gds.louvain.write('gdelt_graph', {
          writeProperty: 'community'
        })
        YIELD nodePropertiesWritten
        RETURN nodePropertiesWritten
        """).single()
        print(f"Louvain completed. Properties written: {result_louvain['nodePropertiesWritten']}")

        # 4. Drop the in-memory graph as we no longer need it
        print("Cleaning up in-memory graph...")
        session.run("CALL gds.graph.drop('gdelt_graph')")

def print_top_actors(driver):
    print("\n--- Top 10 Actors by PageRank ---")
    query = """
    MATCH (a:Actor)
    WHERE a.pagerank IS NOT NULL
    RETURN a.name AS name, a.country_code AS country, a.pagerank AS score
    ORDER BY score DESC
    LIMIT 10
    """
    with driver.session() as session:
        results = session.run(query)
        for i, record in enumerate(results, 1):
            name = record["name"]
            country = record["country"] or "N/A"
            score = round(record["score"], 4)
            print(f"{i:2}. {name} ({country}) - Score: {score}")
    print("---------------------------------")

def main():
    print("Connecting to Neo4j...")
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        run_pagerank(driver)
        print_top_actors(driver)

if __name__ == "__main__":
    main()
