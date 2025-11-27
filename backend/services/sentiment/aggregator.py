from typing import List, Dict, Any
from pydantic import BaseModel


class Artifact(BaseModel):
    def to_json(self) -> Dict[str, Any]:
        return self.dict()
    

class Snapshot(Artifact):
    # identifiers (aligned across lists)
    ticker: List[str]
    date: List[str]

    # price side (from Stock / PriceSentiment)
    close_price: List[float]
    return_1d: List[float]
    return_30d: List[float]
    return_120d: List[float]
    return_360d: List[float]

    behavior_30d: List[str]
    behavior_120d: List[str]
    behavior_360d: List[str]

    # article sentiment side (from Sentiment)
    sentiment_mean: List[float]
    sentiment_max: List[float]
    sentiment_min: List[float]

    num_articles: List[int]
    num_neg_articles: List[int]
    num_pos_articles: List[int]

    prob_pos_mean: List[float]
    prob_neg_mean: List[float]
    prob_neu_mean: List[float]
    prob_pos_max: List[float]
    prob_neg_max: List[float]
