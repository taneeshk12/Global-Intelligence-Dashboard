import os
import pandas as pd
from neo4j import GraphDatabase

URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
AUTH = (os.environ.get("NEO4J_USER", "neo4j"), os.environ.get("NEO4J_PASSWORD", "password"))
DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "gdelt_events.csv")
BATCH_SIZE = 5000

def load_data(driver, batch):
    query = """
    UNWIND $batch AS row
    
    // Merge Actor 1
    MERGE (a1:Actor {name: row.Actor1Name})
    ON CREATE SET a1.country_code = row.Actor1CountryCode
    ON MATCH SET a1.country_code = coalesce(row.Actor1CountryCode, a1.country_code)

    // Merge Actor 2
    MERGE (a2:Actor {name: row.Actor2Name})
    ON CREATE SET a2.country_code = row.Actor2CountryCode
    ON MATCH SET a2.country_code = coalesce(row.Actor2CountryCode, a2.country_code)

    // Create the Economic Event relationship
    CREATE (a1)-[:ECONOMIC_EVENT {
        date: toInteger(row.SQLDATE),
        event_code: row.EventCode,
        goldstein: toFloat(row.GoldsteinScale),
        tone: toFloat(row.AvgTone)
    }]->(a2)
    """
    with driver.session() as session:
        session.run(query, batch=batch)

def verify_load(driver):
    query = """
    MATCH (n:Actor)
    WITH count(n) AS node_count
    MATCH ()-[r:ECONOMIC_EVENT]->()
    RETURN node_count, count(r) AS rel_count
    """
    with driver.session() as session:
        result = session.run(query).single()
        print("\n--- Verification ---")
        print(f"Total Actor Nodes: {result['node_count']}")
        print(f"Total ECONOMIC_EVENT Relationships: {result['rel_count']}")
        print("--------------------")

def main():
    print(f"Loading data from {DATA_FILE}")
    if not os.path.exists(DATA_FILE):
        print("Data file not found. Please run Step 1 first.")
        return

    # Read CSV, fill NaN values with None so Neo4j driver can handle them
    df = pd.read_csv(DATA_FILE).where(pd.notnull(pd.read_csv(DATA_FILE)), None)
    
    # Convert to list of dicts for batch processing
    records = df.to_dict('records')
    total_records = len(records)
    print(f"Total records to load: {total_records}")

    print("Connecting to Neo4j...")
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        # Batch the load
        for i in range(0, total_records, BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]
            load_data(driver, batch)
            print(f"Loaded batch {i // BATCH_SIZE + 1} / {(total_records + BATCH_SIZE - 1) // BATCH_SIZE} ({len(batch)} records)")
        
        print("\nLoad complete. Running verification...")
        verify_load(driver)

if __name__ == "__main__":
    main()
