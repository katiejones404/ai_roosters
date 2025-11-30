
from __future__ import annotations 

import logging 
import os 
from typing import Any, Dict, List, Callable, Type, Optional 

from datetime import datetime 

import pandas as pd 
import psycopg2 
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline 

logger = logging.getLogger("pipeline")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_handler)

# Configures device to use cpu 

def select_device() -> int: 

    # returning -1 means it uses cpu  - device_id = -1 
    return -1 

# Pydantic BaseModel 

try: 
    from pydantic import BaseModel
except ImportError: 
    class BaseModel: 
        model_fields: Dict[str, Any] = {}

    def __init_subclass_(cls, **kwargs: Any):
        super().__init_subclass_(**kwargs)

    def __init__(self, **data: Any):
        for k, v in data.items():
            setattr(self, k, v)
    
    def model_dump(self) -> Dict[str, Any]:
        return self.__dict__.copy()
    
class Artifact(BaseModel):
    def to_json(self) -> Dict[str, Any]:

        if hasattr(self, "model_dump"):
            return self.model_dump()
        if hasattr(self, "dict"):
            return self.dict()
        
        return self.dict__.copy()
        
class Stage: 
     
    def __init__(
        self,
        name: str,
        input_schema: Type[Artifact],
        output_schema: Type[Artifact],
        compute_fn: Callable[[Artifact], Artifact],
    ):
        self.name = name
        self.input_schema = input_schema
        self.output_schema = output_schema
        self.compute_fn = compute_fn

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[{self.name}] Validating input...")
        artifact_in = self.input_schema(**input_data)

        logger.info(f"[{self.name}] Computing...")
        artifact_out = self.compute_fn(artifact_in)

        logger.info(f"[{self.name}] Validating output...")
        artifact_valid = self.output_schema(**artifact_out.to_json())

        logger.info(f"[{self.name}] Completed successfully.")
        return artifact_valid.to_json()
    
class Pipeline:
    def __init__(self, name: str, stages: List[Stage]):
        self.name = name
        self.stages = stages

    def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Pipeline '{self.name}' starting...")
        for s in self.stages:
            data = s.run(data)
        logger.info(f"Pipeline '{self.name}' completed.")
        return data
    
class DataArtifact(Artifact):

    # Input artifact for the ingest pipeline 

    csv_path: str
    


class IngestArtifact(Artifact): 

    published_at: List[str]
    title: List[str]
    description: List[str]
    url: List[str]



class SentimentArtifact(IngestArtifact):

    sentiment: List[str]
    sentiment_score: List[float]
    prob_pos: List[float]
    prob_neg: List[float]
    prob_neu: List[float]


class DBArtifact(Artifact):

    num_articles: int 



# Stage 1: Loads CSV into Ingest Artifact 
def load_csv_to_articles(artifact: DataArtifact) -> IngestArtifact: 

    logger.info(f"loading CSV from {artifact.csv_path}")
    df = pd.read_csv(artifact.csv_path)

    # Files that are required to be intaked. 
    required_cols = ["published_at", "title", "description", "url"]

    for col in required_cols: 
        if col not in df.columns: 
            raise ValueError(f"CSV must contain columns: {required_cols}")
        
    df["published_at"] = pd.to_datetime(df["published_at"])

    return IngestArtifact(
        published_at=df["published_at"].dt.strftime("%Y-%m-%dT%H:%M:%S %z").tolist(),
        title=df["title"].fillna("").tolist(),
        # fillna to avoid NaN issues 
        description=df["description"].fillna("").tolist(),
        url=df["url"].fillna("").tolist(),
    )

LoadStage = Stage(
    name = "LoadCSV", 
    input_schema = DataArtifact,
    output_schema = IngestArtifact,  
    compute_fn = load_csv_to_articles, 
)

# Stage 2: Sentiment Analysis 

_FINBERT_MODEL_ID = "ProsusAI/finbert"

def get_finbert_pipeline():

    if not hasattr(get_finbert_pipeline, "finbert"):
        logger.info(" Loading FinBERT model...")
        model = AutoModelForSequenceClassification.from_pretrained(_FINBERT_MODEL_ID)
        device_id = select_device()
        tokenizer = AutoTokenizer.from_pretrained(_FINBERT_MODEL_ID)

        get_finbert_pipeline.finbert = pipeline(
            task = "sentiment-analysis",
            model = model, 
            tokenizer = tokenizer, 
            device = device_id, 
            top_k = None, 
            truncation = True, 
            max_length = 512, 
        )
        logger.info(
            f"Finbert model loaded on device_id={device_id}"
        )
    return get_finbert_pipeline.finbert 

def scores_dict(all_scores: List[Dict[str, float]]) -> Dict[str, float]: 

    d = {e["label"].lower(): float(e["score"]) for e in all_scores}
    for k in ("positive", "neutral", "negative"):
        d.setdefault(k, 0.0)
    return d 

def finbert_articles(artifact: IngestArtifact, ) -> SentimentArtifact: 
    logger.info("Starting sentiment analysis with FinBert...")

    if not artifact.description:
        return SentimentArtifact(
            published_at = artifact.published_at, 
            title = artifact.title, 
            description = artifact.description, 
            url = artifact.url, 
            sentiment = [],
            sentiment_score = [],
            prob_pos = [],
            prob_neg = [],
            prob_neu = [],
        )

    pipe = get_finbert_pipeline()
    results = pipe(artifact.description)

    sentiments: List[str] = []
    scores: List[float] = []
    prob_pos: List[float] = []
    prob_neg: List[float] = []
    prob_neu: List[float] = []

    for result in results: 
        score_map = scores_dict(result)
        label = max(score_map, key = score_map.get)

        pos = score_map["positive"]
        neg = score_map["negative"]
        neu = score_map["neutral"]

        sentiments.append(label)
        scores.append(pos - neg)
        prob_pos.append(pos)
        prob_neg.append(neg)
        prob_neu.append(neu)
    
    return SentimentArtifact(
        published_at = artifact.published_at, 
        title = artifact.title, 
        description = artifact.description, 
        url = artifact.url, 
        sentiment = sentiments, 
        sentiment_score = scores, 
        prob_pos = prob_pos, 
        prob_neg = prob_neg,
        prob_neu = prob_neu, 
    )

FinBERTStage = Stage( 
    name = "FinBERTSentiment", 
    input_schema = IngestArtifact,
    output_schema = SentimentArtifact, 
    compute_fn = finbert_articles, 
)

# Stage 3: Store into Database 
 

def write_articles_to_db(artifact: SentimentArtifact) -> DBArtifact: 
    logger.info("writing artices with sentiment info 'articles' table...")

    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql://stock_user:stock_pass@postgres:5432/stock_db", 
    )
    conn = psycopg2.connect(dsn)

    num_articles = 0 
    rows = zip(
        artifact.published_at,
        artifact.title, 
        artifact.description, 
        artifact.url,
        artifact.sentiment, 
        artifact.sentiment_score,
        artifact.prob_pos,
        artifact.prob_neg, 
        artifact.prob_neu,
    )

    with conn.cursor() as cur:
        for (
            published_at, 
            title, 
            description,
            url,
            sentiment, 
            sentiment_score,
            prob_pos, 
            prob_neg, 
            prob_neu,
        ) in rows: 
            num_articles += 1 
            cur.execute(
                """
                INSERT INTO articles (
                    published_at, 
                    title, 
                    description, 
                    url,
                    sentiment, 
                    sentiment_score,
                    prob_pos, 
                    prob_neg, 
                    prob_neu
                ) 
                VALUES (
                %(published_at)s,
                %(title)s,
                %(description)s,
                %(url)s,
                %(sentiment)s, 
                %(sentiment_score)s,
                %(prob_pos)s,
                %(prob_neg)s,
                %(prob_neu)s
               )
               ON CONFLICT (url)  DO UPDATE SET
                published_at    = EXCLUDED.published_at, 
                title           = EXCLUDED.title,
                description     = EXCLUDED.description, 
                sentiment       = EXCLUDED.sentiment, 
                sentiment_score = EXCLUDED.sentiment_score,
                prob_pos        = EXCLUDED.prob_pos, 
                prob_neg        = EXCLUDED.prob_neg, 
                prob_neu        = EXCLUDED.prob_neu;
            """,
            {
                "published_at": published_at, 
                "title": title, 
                "description": description,
                "url": url, 
                "sentiment": sentiment, 
                "sentiment_score": sentiment_score,
                "prob_pos": prob_pos, 
                "prob_neg": prob_neg, 
                "prob_neu": prob_neu,
            },
        )
    conn.commit()
    conn.close()

    return DBArtifact(num_articles = num_articles)

DBStage = Stage(
    name = "WriteArticlestoDB",
    input_schema = SentimentArtifact, 
    output_schema = DBArtifact, 
    compute_fn = write_articles_to_db,
)

finbert_ingest_pipeline = Pipeline(
    "FinbertCSVtoArticlesDB",
    [LoadStage, FinBERTStage, DBStage],
)

if __name__ == "__main__":

    csv_path = os.getenv("NEWS_CSV_PATH", "data/news_articles.csv")

    result = finbert_ingest_pipeline.run(
        { "csv_path": csv_path}

    )

    print("Pipeline result:", result)
    
                




