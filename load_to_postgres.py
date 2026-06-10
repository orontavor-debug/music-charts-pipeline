import pandas as pd
from sqlalchemy import create_engine

DB_USER = "orontavor"
DB_PASSWORD = ""
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "music_charts"

engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

df = pd.read_csv("global_chart.csv")

df.to_sql("raw_global_chart", engine, if_exists="replace", index=False)

print(f"Loaded {len(df)} rows into raw_global_chart table")
