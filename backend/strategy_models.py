from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class Condition(StrictModel):
    field: Literal['energy', 'tool', 'cargo', 'depth', 'quality', 'hazard']
    operator: Literal['lt', 'lte', 'gt', 'gte', 'eq', 'neq'] = 'lte'
    value: int = Field(ge=0, le=100, strict=True)

    @model_validator(mode='after')
    def depth_range(self):
        if self.field == 'depth' and not 1 <= self.value <= 5:
            raise ValueError('Depth conditions must be between 1 and 5.')
        return self

class ConditionGroup(StrictModel):
    match: Literal['all', 'any'] = 'all'
    conditions: list[Condition] = Field(min_length=1, max_length=4)

class Rule(StrictModel):
    id: str = Field(min_length=1, max_length=40, pattern=r'^[A-Za-z0-9_-]+$')
    name: str = Field(min_length=2, max_length=36, pattern=r'^[A-Za-z0-9 _-]+$')
    enabled: bool = True
    match: Literal['all', 'any'] = 'all'
    groups: list[ConditionGroup] = Field(min_length=1, max_length=3)
    action: Literal['mine', 'survey', 'deeper', 'shallower', 'return', 'rest', 'repair']

class Strategy(StrictModel):
    name: str = Field(min_length=2, max_length=36, pattern=r'^[A-Za-z0-9 _-]+$')
    target_depth: int = Field(default=3, ge=1, le=5, strict=True)
    risk: int = Field(default=40, ge=0, le=100, strict=True)
    haul_threshold: int = Field(default=75, ge=20, le=100, strict=True)
    energy_reserve: int = Field(default=30, ge=10, le=70, strict=True)
    repair_threshold: int = Field(default=30, ge=10, le=80, strict=True)
    ore_priority: Literal['balanced', 'volume', 'rich'] = 'balanced'
    rules: list[Rule] = Field(default_factory=list, max_length=8)

    @model_validator(mode='after')
    def unique_rules(self):
        if len({rule.id for rule in self.rules}) != len(self.rules):
            raise ValueError('Every rule must have a unique ID.')
        return self

class StrategySave(StrictModel):
    expected_version: int = Field(ge=1, strict=True)
    strategy: Strategy

class StrategyPreview(StrictModel):
    strategy: Strategy
    decisions: int = Field(default=120, ge=30, le=300, strict=True)

class StrategyVersion(BaseModel):
    version: int
    name: str
    saved_at: str

class StrategyOut(BaseModel):
    strategy: Strategy
    version: int
    updated_at: str
    history: list[StrategyVersion] = Field(default_factory=list)

class GameState(BaseModel):
    energy: int = 100
    tool: int = 100
    cargo: int = 0
    cargo_value: int = 0
    depth: int = 1
    quality: int = 55
    hazard: int = 0
    returning: bool = False
    decision: int = 0
    mined: int = 0
    delivered: int = 0
    deliveries: int = 0
    banked_points: int = 0
    exploration_points: int = 0
    penalties: int = 0
    incidents: int = 0
    deepest: int = 1
    last_action: str = 'rest'
    last_reason: str = 'Ready for a new expedition.'

class ContestProgress(BaseModel):
    season_id: str
    entered_at: str
    entered_ts: float
    ends_at: float
    status: Literal['active', 'completed', 'closed'] = 'active'
    actions_used: int = 0
    score: int = 0
    delivered: int = 0
    banked_points: int = 0
    exploration_points: int = 0
    penalties: int = 0
    incidents: int = 0
    completed_at: Optional[str] = None

class LeaderboardRow(BaseModel):
    rank: int
    agent_id: str
    name: str
    avatar: str
    strategy_name: str
    score: int
    delivered: int
    actions_used: int
    incidents: int
    status: str
    entered_at: str

class LeaderboardOut(BaseModel):
    season: dict
    entries: list[LeaderboardRow]
    total: int