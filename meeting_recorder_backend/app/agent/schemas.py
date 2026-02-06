from pydantic import BaseModel
from typing import List



class MeetingInsights(BaseModel):
    summary:str
    key_points: List[str]
    action_items: List[str]
    decisions: List[str]

class ChatResponse(BaseModel):
    answer: str