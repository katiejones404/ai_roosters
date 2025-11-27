from typing import List, Any, Dict
from pydantic import BaseModel


class Artifact(BaseModel):
    def to_json(self) -> Dict[str, Any]:
        return self.dict()

class Paragraph(Artifact):
    index: List[int]
    title: List[str]
    description: List[str]
    url: List[str]


class Sentiment(Artifact):
    index: List[int]
    title: List[str]
    description: List[str]
    url: List[str]

    
    sentiment_mean: List[float]
    sentiment_max: List[float]
    sentiment_min: List[float]

    num_articles: List[int]
    num_neg_articles: List[int]
    num_pos_articles: List[int]

    # use ":" not "=" for type hints
    prob_pos_mean: List[float]
    prob_neg_mean: List[float]
    prob_neu_mean: List[float]
    prob_pos_max: List[float]
    prob_neg_max: List[float]