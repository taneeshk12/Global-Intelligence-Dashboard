import os
import time
import requests
import zipfile
import io
import json
import pandas as pd
from kafka import KafkaProducer

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:29092")
TOPIC = "gdelt-events"

economic_codes = ["061", "071", "102", "122", "162"]

# GDELT v2 format has no headers. We define the ones we care about based on their index.
# The full schema has 61 columns, but we only need a few.
GDELT_COLUMNS = [
    "GLOBALEVENTID", "SQLDATE", "MonthYear", "Year", "FractionDate", 
    "Actor1Code", "Actor1Name", "Actor1CountryCode", "Actor1KnownGroupCode", "Actor1EthnicCode", 
    "Actor1Religion1Code", "Actor1Religion2Code", "Actor1Type1Code", "Actor1Type2Code", "Actor1Type3Code",
    "Actor2Code", "Actor2Name", "Actor2CountryCode", "Actor2KnownGroupCode", "Actor2EthnicCode", 
    "Actor2Religion1Code", "Actor2Religion2Code", "Actor2Type1Code", "Actor2Type2Code", "Actor2Type3Code",
    "IsRootEvent", "EventCode", "EventBaseCode", "EventRootCode", "QuadClass", 
    "GoldsteinScale", "NumMentions", "NumSources", "NumArticles", "AvgTone", 
    "Actor1Geo_Type", "Actor1Geo_FullName", "Actor1Geo_CountryCode", "Actor1Geo_ADM1Code", "Actor1Geo_Lat", "Actor1Geo_Long", "Actor1Geo_FeatureID",
    "Actor2Geo_Type", "Actor2Geo_FullName", "Actor2Geo_CountryCode", "Actor2Geo_ADM1Code", "Actor2Geo_Lat", "Actor2Geo_Long", "Actor2Geo_FeatureID",
    "ActionGeo_Type", "ActionGeo_FullName", "ActionGeo_CountryCode", "ActionGeo_ADM1Code", "ActionGeo_Lat", "ActionGeo_Long", "ActionGeo_FeatureID",
    "DATEADDED", "SOURCEURL"
]

def get_producer():
    while True:
        try:
            producer = KafkaProducer(
                bootstrap_servers=[KAFKA_BROKER],
                value_serializer=lambda x: json.dumps(x).encode('utf-8')
            )
            print("Connected to Kafka")
            return producer
        except Exception as e:
            print(f"Waiting for Kafka: {e}")
            time.sleep(5)

def fetch_latest_gdelt():
    try:
        response = requests.get("http://data.gdeltproject.org/gdeltv2/lastupdate.txt")
        if response.status_code == 200:
            # First line, third column is the export CSV URL
            lines = response.text.strip().split('\n')
            if lines:
                parts = lines[0].split(' ')
                if len(parts) == 3:
                    return parts[2]
    except Exception as e:
        print(f"Error checking gdelt: {e}")
    return None

def process_url(url, producer):
    print(f"Downloading {url}...")
    try:
        response = requests.get(url)
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            csv_filename = z.namelist()[0]
            with z.open(csv_filename) as f:
                # Read CSV without passing names, so it uses integer columns
                df = pd.read_csv(f, sep='\t', header=None, dtype=str)
                
                # Filter for non-null actors (Index 6=Actor1Name, 16=Actor2Name)
                df = df.dropna(subset=[6, 16])
                
                if df.empty:
                    print("No valid dyadic events found in this batch.")
                    return
                
                events_sent = 0
                
                def safe_float(val):
                    if pd.isna(val): return None
                    try:
                        return float(val)
                    except ValueError:
                        return None
                        
                for _, row in df.iterrows():
                    # Extract fields safely using column index
                    event = {
                        "Actor1Name": row[6],
                        "Actor2Name": row[16],
                        "Actor1CountryCode": row[7] if pd.notna(row[7]) else "N/A",
                        "Actor2CountryCode": row[17] if pd.notna(row[17]) else "N/A",
                        "Actor1Geo_Lat": safe_float(row[40]),
                        "Actor1Geo_Long": safe_float(row[41]),
                        "Actor2Geo_Lat": safe_float(row[47]),
                        "Actor2Geo_Long": safe_float(row[48]),
                        "ActionGeo_Lat": safe_float(row[56]),
                        "ActionGeo_Long": safe_float(row[57]),
                        "NumArticles": int(row[33]) if pd.notna(row[33]) and str(row[33]).isdigit() else 1,
                        "SOURCEURL": row[60] if pd.notna(row[60]) else "",
                        "EventCode": str(row[26]),
                        "AvgTone": safe_float(row[34]) or 0.0,
                        "SQLDATE": str(row[1])
                    }
                    producer.send(TOPIC, value=event)
                    events_sent += 1
                    
                producer.flush()
                print(f"Sent {events_sent} events to Kafka.")
    except Exception as e:
        import traceback
        print(f"Error processing URL: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    producer = get_producer()
    last_processed_url = None
    
    print("Starting GDELT Kafka Producer. Polling every 1 minute...")
    while True:
        latest_url = fetch_latest_gdelt()
        if latest_url and latest_url != last_processed_url:
            print(f"New data found! {latest_url}")
            process_url(latest_url, producer)
            last_processed_url = latest_url
        else:
            print(f"No new data. Checked {time.strftime('%X')}")
            
        time.sleep(60)
