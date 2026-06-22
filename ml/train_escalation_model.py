import os
import pandas as pd
from google.cloud import bigquery
from datetime import datetime
from dateutil.relativedelta import relativedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import pickle

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", None)
MODEL_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(MODEL_DIR, "escalation_model.pkl")

def train():
    if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
        print("WARNING: GOOGLE_APPLICATION_CREDENTIALS not set.")
    
    # We will use the last 12 months for training
    start_date = datetime.now() - relativedelta(months=12)
    date_int = int(start_date.strftime("%Y%m%d"))
    
    # Query all events, grouped by MonthYear, Actor1CountryCode, Actor2CountryCode
    print(f"Querying GDELT from BigQuery since {date_int}...")
    query = f"""
    SELECT 
        MonthYear,
        Actor1CountryCode,
        Actor2CountryCode,
        AVG(GoldsteinScale) as avg_goldstein,
        COUNTIF(QuadClass = 1) as verbal_coop_count,
        COUNTIF(QuadClass = 2) as material_coop_count,
        COUNTIF(QuadClass = 3) as verbal_conflict_count,
        COUNTIF(QuadClass = 4) as material_conflict_count
    FROM 
        `gdelt-bq.full.events`
    WHERE 
        SQLDATE >= {date_int}
        AND Actor1CountryCode IS NOT NULL
        AND Actor2CountryCode IS NOT NULL
        AND Actor1CountryCode != Actor2CountryCode
    GROUP BY 
        MonthYear, Actor1CountryCode, Actor2CountryCode
    """
    
    client = bigquery.Client(project=PROJECT_ID)
    df = client.query(query).to_dataframe()
    print(f"Retrieved {len(df)} monthly dyadic interaction records.")
    
    # Sort by time
    df = df.sort_values(by=["Actor1CountryCode", "Actor2CountryCode", "MonthYear"])
    
    # Create target variable: Did material conflict occur in the NEXT month?
    # We shift the material_conflict_count backwards by 1 within each dyad group
    print("Engineering features and target...")
    df['target_next_month_conflict'] = df.groupby(['Actor1CountryCode', 'Actor2CountryCode'])['material_conflict_count'].shift(-1)
    
    # Drop rows where we don't have a next month to predict
    df = df.dropna(subset=['target_next_month_conflict'])
    
    # Convert target to binary classification (1 if > 0 else 0)
    df['target'] = (df['target_next_month_conflict'] > 0).astype(int)
    
    # Features
    features = [
        'avg_goldstein', 
        'verbal_coop_count', 
        'material_coop_count', 
        'verbal_conflict_count',
        'material_conflict_count' # current month's material conflict
    ]
    
    X = df[features].fillna(0)
    y = df['target']
    
    print(f"Dataset ready. Class balance: {y.value_counts().to_dict()}")
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training Random Forest Classifier...")
    # Use class_weight='balanced' because escalations are rare
    clf = RandomForestClassifier(n_estimators=100, class_weight='balanced', random_state=42)
    clf.fit(X_train, y_train)
    
    print("Evaluating Model...")
    y_pred = clf.predict(X_test)
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(classification_report(y_test, y_pred))
    
    print(f"Saving model to {MODEL_PATH}...")
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(clf, f)
        
    print("Done! Model is ready for inference.")

if __name__ == "__main__":
    train()
