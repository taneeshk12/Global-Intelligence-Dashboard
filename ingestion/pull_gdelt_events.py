import os
import pandas as pd
from google.cloud import bigquery
from datetime import datetime
from dateutil.relativedelta import relativedelta

# Configuration
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", None) # Optional, can be inferred from credentials
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "gdelt_events.csv")

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

def pull_data():
    # Authenticate via GOOGLE_APPLICATION_CREDENTIALS environment variable
    if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
        print("WARNING: GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
        print("Please set it to the path of your service account JSON key.")
    
    print("Connecting to BigQuery...")
    client = bigquery.Client(project=PROJECT_ID)

    # Calculate date 6 months ago (GDELT SQLDATE format: YYYYMMDD integer)
    six_months_ago = datetime.now() - relativedelta(months=6)
    date_int = int(six_months_ago.strftime("%Y%m%d"))
    
    # Specific CAMEO event codes for economic/trade activities
    # 061: Cooperate economically, 071: Provide economic aid, 
    # 102: Demand economic aid, 122: Reject economic cooperation, 162: Reduce or stop economic assistance
    economic_codes = ("061", "071", "102", "122", "162")

    print(f"Querying GDELT dataset for events since {date_int}...")
    
    # We use gdelt-bq.full.events as requested. 
    # Added LIMIT 100000 to keep the dataset weekend-project sized.
    query = f"""
    SELECT 
        Actor1Name, 
        Actor2Name, 
        Actor1CountryCode, 
        Actor2CountryCode, 
        EventRootCode, 
        EventCode, 
        GoldsteinScale, 
        AvgTone, 
        SQLDATE, 
        ActionGeo_CountryCode
    FROM 
        `gdelt-bq.full.events`
    WHERE 
        SQLDATE >= {date_int}
        AND EventCode IN {economic_codes}
        AND Actor1Name IS NOT NULL
        AND Actor2Name IS NOT NULL
    LIMIT 100000
    """

    # Run query and convert to pandas dataframe
    query_job = client.query(query)
    df = query_job.to_dataframe()

    print(f"Query completed. Retrieved {len(df)} rows.")

    # Drop rows where actors might be empty strings
    df = df[(df['Actor1Name'] != '') & (df['Actor2Name'] != '')]
    
    print(f"Rows after dropping empty actors: {len(df)}")
    
    print("\nData Sample:")
    print(df.head())

    # Save to CSV
    print(f"\nSaving data to {OUTPUT_FILE}...")
    df.to_csv(OUTPUT_FILE, index=False)
    print("Done!")

if __name__ == "__main__":
    pull_data()
