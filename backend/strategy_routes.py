import time
import uuid
from fastapi import APIRouter, Header, HTTPException, Query
from typing import Optional
from models import AgentOut
from strategy_models import StrategyOut, StrategySave, StrategyPreview, GameState, LeaderboardOut, StrategyVersion
from strategies import preset, evaluate
from game_worker import advance_game, stamp, LOCKS
from contest_logic import season_info, leaderboard, archive_entry

def make_strategy_router(db, owner):
    router = APIRouter(prefix='/api')

    async def owned(authorization):
        uid = await owner(authorization)
        agent = await db.agents.find_one({'owner': uid}, {'_id': 0})
        if not agent:
            raise HTTPException(404, 'Create an agent before configuring a strategy.')
        return agent

    async def envelope(agent):
        history = await db.strategy_history.find({'agent_id': agent['id']}, {'_id': 0}).sort('version', -1).limit(8).to_list(8)
        return StrategyOut(strategy=agent['strategy'], version=agent['strategy_version'],
                           updated_at=agent['strategy_updated_at'], history=[StrategyVersion(**v) for v in history])

    @router.get('/strategy/presets')
    async def presets():
        return [{'id': key, 'label': preset(key)['name'], 'description': description, 'strategy': preset(key)} for key, description in [
            ('balanced', 'Adaptable depth, measured risk, regular deliveries.'),
            ('prospector', 'Deeper veins and richer ore, with sharper trade-offs.'),
            ('guardian', 'Healthy tools, steady energy, smaller frequent hauls.'),
            ('hauler', 'High-volume mining with a fast return schedule.')]]

    @router.get('/agent/strategy', response_model=StrategyOut)
    async def get_strategy(authorization: Optional[str] = Header(None)):
        return await envelope(await owned(authorization))

    @router.post('/agent/strategy', response_model=StrategyOut)
    async def save_strategy(data: StrategySave, authorization: Optional[str] = Header(None)):
        agent = await owned(authorization)
        await advance_game(db, agent)
        async with LOCKS[agent['id']]:
            agent = await db.agents.find_one({'id': agent['id']}, {'_id': 0})
            if data.expected_version != agent['strategy_version']:
                raise HTTPException(409, 'A newer strategy was saved in another tab. Reload the strategy before saving.')
            if agent['status'] == 'active' and int((agent['elapsed_before'] + time.time() - agent['started_at']) // 18) > agent['decision_cursor']:
                raise HTTPException(409, 'Your miner is catching up on saved decisions. Please try again shortly.')
            config = data.strategy.model_dump()
            version, now = agent['strategy_version'] + 1, stamp()
            changes = {'strategy': config, 'strategy_name': config['name'], 'strategy_version': version,
                       'strategy_updated_at': now, 'preference': 'deep' if config['target_depth'] >= 4 else 'careful' if config['target_depth'] <= 2 else 'balanced'}
            result = await db.agents.update_one({'id': agent['id'], 'strategy_version': data.expected_version, 'revision': agent['revision']}, {'$set': changes, '$inc': {'revision': 1}})
            if not result.modified_count:
                raise HTTPException(409, 'Your agent changed tasks. Please try saving again.')
            await db.strategy_history.update_one({'id': f"{agent['id']}:{version}"}, {'$setOnInsert': {
                'id': f"{agent['id']}:{version}", 'agent_id': agent['id'], 'version': version,
                'name': config['name'], 'saved_at': now, 'strategy': config}}, upsert=True)
            await db.events.insert_one({'id': f"{agent['id']}:strategy:{version}", 'agent_id': agent['id'],
                'name': agent['name'], 'avatar': agent['avatar'], 'is_bot': False, 'stage': agent['stage'],
                'message': f"Strategy updated to {config['name']} v{version}. New rules apply to the next decision; existing score and resources are retained.", 'created_at': now})
            return await envelope({**agent, **changes})

    @router.post('/agent/strategy/evaluate')
    async def evaluate_strategy(data: StrategyPreview, authorization: Optional[str] = Header(None)):
        await owned(authorization)
        return evaluate(data.strategy.model_dump(), data.decisions)

    @router.get('/contest/leaderboard', response_model=LeaderboardOut)
    async def get_leaderboard(season_id: Optional[str] = Query(None, pattern=r'^\d{4}-\d{2}-\d{2}$'), limit: int = Query(100, ge=1, le=100)):
        season = season_info()
        requested = season_id or season['id']
        if requested != season['id']:
            from datetime import datetime, timezone
            try:
                date = datetime.strptime(requested, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            except ValueError:
                raise HTTPException(422, 'Choose a valid season start date.')
            season = season_info(date)
            if season['id'] != requested:
                raise HTTPException(422, 'A contest season starts on a Monday in UTC.')
        entries, total = await leaderboard(db, requested, limit)
        return LeaderboardOut(season=season, entries=entries, total=total)

    @router.post('/contest/enter', response_model=AgentOut)
    async def enter_contest(authorization: Optional[str] = Header(None)):
        agent = await owned(authorization)
        await advance_game(db, agent)
        async with LOCKS[agent['id']]:
            agent = await db.agents.find_one({'id': agent['id']}, {'_id': 0})
            season, now = season_info(), time.time()
            if agent['is_bot']:
                raise HTTPException(403, 'Resident crew bots cannot enter contests.')
            if agent.get('contest') and agent['contest']['season_id'] == season['id']:
                raise HTTPException(409, 'Your agent already entered this season. There are no resets or repeat entries.')
            await archive_entry(db, agent)
            c = {'season_id': season['id'], 'entered_at': stamp(now), 'entered_ts': now,
                 'ends_at': season['ends_ts'], 'status': 'active', 'actions_used': 0, 'score': 0,
                 'delivered': 0, 'banked_points': 0, 'exploration_points': 0, 'penalties': 0, 'incidents': 0, 'completed_at': None}
            # Fresh resource budget, unchanged lifetime progress and immutable previous season results.
            changes = {'contest': c, 'game': GameState().model_dump(), 'status': 'active',
                       'started_at': now, 'elapsed_before': agent['decision_cursor'] * 18,
                       'stage': 'basecamp', 'previous_stage': 'basecamp', 'stage_started_at': now}
            result = await db.agents.update_one({'id': agent['id'], 'revision': agent['revision']}, {'$set': changes, '$inc': {'revision': 1}})
            if not result.modified_count:
                raise HTTPException(409, 'Your agent changed tasks. Please enter again.')
            await db.events.insert_one({'id': f"{agent['id']}:contest:{season['id']}", 'agent_id': agent['id'],
                'name': agent['name'], 'avatar': agent['avatar'], 'is_bot': False, 'stage': 'basecamp',
                'message': 'Entered the Brass Hollow Open. Fresh supplies, 600 decisions, and a strategy of my own.', 'created_at': stamp(now)})
            return AgentOut(**{**agent, **changes})

    return router