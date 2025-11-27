from typing import List, Any, Dict
from pydantic import BaseModel


class Artifact(BaseModel):
    def to_json(self) -> Dict[str, Any]:
        return self.dict()

class Stock(Artifact):
    ticker: List[str]
    date: List[str]

    close_price: List[float]
    return_1d: List[float]
    return_30d: List[float]
    return_120d: List[float]
    return_360d: List[float]




    # Compute the future return 