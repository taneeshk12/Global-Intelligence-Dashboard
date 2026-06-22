import os
import time
import json
import requests
from kafka import KafkaConsumer
from neo4j import GraphDatabase

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:29092")
TOPIC = "gdelt-events"
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
API_URL = os.getenv("API_URL", "http://api:8000")

MERGE_QUERY = """
MERGE (a1:Actor {name: $actor1_name})
ON CREATE SET a1.country_code = $actor1_country, a1.lat = $actor1_lat, a1.long = $actor1_long
ON MATCH SET a1.lat = coalesce(a1.lat, $actor1_lat), a1.long = coalesce(a1.long, $actor1_long)
MERGE (a2:Actor {name: $actor2_name})
ON CREATE SET a2.country_code = $actor2_country, a2.lat = $actor2_lat, a2.long = $actor2_long
ON MATCH SET a2.lat = coalesce(a2.lat, $actor2_lat), a2.long = coalesce(a2.long, $actor2_long)
CREATE (a1)-[:ECONOMIC_EVENT {
    event_code: $event_code,
    tone: $avg_tone,
    date: $date,
    num_articles: $num_articles,
    source_url: $source_url
}]->(a2)
"""

PAGERANK_QUERY = """
CALL gds.pageRank.write('gdelt_graph', {
  maxIterations: 20,
  dampingFactor: 0.85,
  writeProperty: 'pagerank'
})
YIELD nodePropertiesWritten, ranIterations
"""

LOUVAIN_QUERY = """
CALL gds.louvain.write('gdelt_graph', {
  writeProperty: 'community'
})
YIELD nodePropertiesWritten
"""

ANOMALY_QUERY = """
MATCH (a1:Actor {name: $actor1_name})-[r:ECONOMIC_EVENT]-(a2:Actor {name: $actor2_name})
RETURN avg(toFloat(r.tone)) as avg_historical_tone, count(r) as event_count
"""

def get_consumer():
    while True:
        try:
            consumer = KafkaConsumer(
                TOPIC,
                bootstrap_servers=[KAFKA_BROKER],
                value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                auto_offset_reset='latest'
            )
            print("Connected to Kafka Consumer")
            return consumer
        except Exception as e:
            print(f"Waiting for Kafka: {e}")
            time.sleep(5)

def get_neo4j_driver():
    while True:
        try:
            driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            driver.verify_connectivity()
            print("Connected to Neo4j")
            return driver
        except Exception as e:
            print(f"Waiting for Neo4j: {e}")
            time.sleep(5)

def recalculate_pagerank(driver):
    print("Recalculating PageRank...")
    with driver.session() as session:
        # Drop existing graph if exists
        try:
            session.run("CALL gds.graph.drop('gdelt_graph')")
        except Exception:
            pass
            
        # Re-project
        session.run("""
        CALL gds.graph.project(
            'gdelt_graph',
            'Actor',
            'ECONOMIC_EVENT'
        )
        """)
        
        # Run PR and Louvain
        session.run(PAGERANK_QUERY)
        session.run(LOUVAIN_QUERY)
    print("PageRank and Louvain communities updated.")

if __name__ == "__main__":
    consumer = get_consumer()
    driver = get_neo4j_driver()
    
    events_since_last_pr = 0
    PR_BATCH_SIZE = 500
    
    print("Consumer is listening for live events...")
    for message in consumer:
        event = message.value
        
        # 1. Insert into Neo4j
        try:
            with driver.session() as session:
                session.run(MERGE_QUERY,
                            actor1_name=event["Actor1Name"],
                            actor1_country=event["Actor1CountryCode"],
                            actor1_lat=event.get("Actor1Geo_Lat"),
                            actor1_long=event.get("Actor1Geo_Long"),
                            actor2_name=event["Actor2Name"],
                            actor2_country=event["Actor2CountryCode"],
                            actor2_lat=event.get("Actor2Geo_Lat"),
                            actor2_long=event.get("Actor2Geo_Long"),
                            event_code=event["EventCode"],
                            avg_tone=event["AvgTone"],
                            date=event["SQLDATE"],
                            num_articles=event.get("NumArticles", 1),
                            source_url=event.get("SOURCEURL", ""))
        except Exception as e:
            print(f"Error inserting to Neo4j: {e}")
            continue

        # 1.5. Anomaly Detection
        try:
            with driver.session() as session:
                result = session.run(ANOMALY_QUERY, 
                                     actor1_name=event["Actor1Name"], 
                                     actor2_name=event["Actor2Name"]).single()
                if result and result["event_count"] > 5:
                    avg_hist = result["avg_historical_tone"]
                    if avg_hist is not None and event["AvgTone"] < -5.0 and event["AvgTone"] < (avg_hist - 4.0):
                        event["is_anomaly"] = True
                    else:
                        event["is_anomaly"] = False
                else:
                    event["is_anomaly"] = False
        except Exception as e:
            print(f"Anomaly detection error: {e}")
            event["is_anomaly"] = False

        # 2. Notify API WebSocket Endpoint
        try:
            requests.post(f"{API_URL}/internal/live-event", json=event, timeout=2)
        except Exception as e:
            print(f"Failed to notify API: {e}")
            
        # 3. Check if we need to recalculate PageRank
        events_since_last_pr += 1
        if events_since_last_pr >= PR_BATCH_SIZE:
            recalculate_pagerank(driver)
            events_since_last_pr = 0
