from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Literal, Optional
from strategy_models import GameState, ContestProgress

class AgentCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=2, max_length=24, pattern=r'^[A-Za-z0-9 _-]+$')
    avatar: Literal['brass', 'sage', 'copper', 'ice'] = 'brass'
    preference: Literal['balanced', 'deep', 'careful'] = 'balanced'
    strategy_preset: Literal['balanced', 'prospector', 'guardian', 'hauler'] = 'balanced'

    @field_validator('name')
    @classmethod
    def valid_name(cls, value):
        value = ' '.join(value.split())
        if len(value) < 2:
            raise ValueError('Choose a name with at least two characters.')
        return value

class AgentOut(BaseModel):
    id: str
    name: str
    avatar: str
    preference: str
    personality: str
    is_bot: bool
    status: str
    stage: str
    step: int
    stage_started_at: float
    ore: int
    expeditions: int
    discoveries: list[str]
    created_at: str
    previous_stage: str = 'basecamp'
    strategy_name: str = 'Wayfinder'
    strategy_version: int = 1
    game: GameState = Field(default_factory=GameState)
    contest: Optional[ContestProgress] = None

class EventOut(BaseModel):
    id: str
    agent_id: str
    name: str
    avatar: str
    is_bot: bool
    stage: str
    message: str
    created_at: str

class WorldOut(BaseModel):
    agents: list[AgentOut]
    active_agents: int
    crew_bots: int
    ore_collected: int
    expeditions: int
    server_time: float
    worker_online: bool

class SessionOut(BaseModel):
    token: str

class MeOut(BaseModel):
    agent: Optional[AgentOut]

class ActionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['start', 'pause', 'resume']