import asyncio
import hashlib
import logging
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from models import AgentCreate, AgentOut, EventOut, WorldOut, SessionOut, MeOut, ActionIn
from engine import seed, worker, make_agent, advance, iso
from game_worker import game_defaults
from strategy_routes import make_strategy_router

load_dotenv(Path(__file__).parent / '.env')
client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app):
    app.state.last_tick = 0
    await seed(db)
    task = asyncio.create_task(worker(db, app.state))
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    client.close()

app = FastAPI(title='MINEPX', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.environ['CORS_ORIGINS'].split(','),
                   allow_credentials=False, allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'])
api = APIRouter(prefix='/api')

async def owner(authorization: Optional[str]):
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Agent access is required. Please refresh and try again.')
    digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
    session = await db.sessions.find_one({'token_hash': digest}, {'_id': 0})
    if not session:
        raise HTTPException(401, 'Your agent access could not be verified.')
    return session['id']

@api.get('/health')
async def health():
    return {'status': 'ok', 'worker_online': time.time() - app.state.last_tick < 15}

@api.post('/session', response_model=SessionOut)
async def session():
    token = secrets.token_urlsafe(32)
    await db.sessions.insert_one({'id': str(uuid.uuid4()), 'token_hash': hashlib.sha256(token.encode()).hexdigest(), 'created_at': iso()})
    return SessionOut(token=token)

@api.get('/world', response_model=WorldOut)
async def world():
    agents = await db.agents.find({}, {'_id': 0, 'owner': 0}).sort('created_at', 1).to_list(250)
    totals = await db.agents.aggregate([{'$group': {'_id': None, 'ore': {'$sum': '$ore'}, 'expeditions': {'$sum': '$expeditions'}, 'active': {'$sum': {'$cond': [{'$eq': ['$status', 'active']}, 1, 0]}}, 'bots': {'$sum': {'$cond': ['$is_bot', 1, 0]}}}}]).to_list(1)
    total = totals[0] if totals else {}
    return WorldOut(agents=[AgentOut(**a) for a in agents], active_agents=total.get('active', 0),
                    crew_bots=total.get('bots', 0), ore_collected=total.get('ore', 0), expeditions=total.get('expeditions', 0),
                    server_time=time.time(), worker_online=time.time() - app.state.last_tick < 15)

@api.get('/agent', response_model=MeOut)
async def my_agent(authorization: Optional[str] = Header(None)):
    uid = await owner(authorization)
    agent = await db.agents.find_one({'owner': uid}, {'_id': 0})
    return MeOut(agent=AgentOut(**agent) if agent else None)

@api.post('/agent', response_model=AgentOut, status_code=201)
async def create_agent(data: AgentCreate, authorization: Optional[str] = Header(None)):
    uid = await owner(authorization)
    personality = {'balanced': 'Curious', 'deep': 'Adventurous', 'careful': 'Methodical'}[data.preference]
    agent = make_agent(str(uuid.uuid4()), data.name, data.avatar, data.preference, personality)
    agent.update(game_defaults(data.preference, data.strategy_preset))
    agent['owner'] = uid
    try:
        await db.agents.insert_one(agent.copy())
    except DuplicateKeyError:
        raise HTTPException(409, 'You already have an agent. Your crew member is waiting for you.')
    event = dict(id=f"{agent['id']}:created", agent_id=agent['id'], name=agent['name'], avatar=agent['avatar'], is_bot=False,
                 stage='basecamp', message='Made it to basecamp. Supplies packed and ready for the first expedition.', created_at=iso())
    await db.events.insert_one(event)
    return AgentOut(**agent)

@api.post('/agent/action', response_model=AgentOut)
async def action(data: ActionIn, authorization: Optional[str] = Header(None)):
    uid = await owner(authorization)
    agent = await db.agents.find_one({'owner': uid}, {'_id': 0})
    if not agent:
        raise HTTPException(404, 'Create your agent before starting an expedition.')
    now = time.time()
    if data.action == 'pause':
        if agent['status'] != 'active':
            raise HTTPException(409, 'Your agent is not currently mining.')
        await advance(db, agent)
        agent = await db.agents.find_one({'owner': uid}, {'_id': 0})
        changes = {'status': 'paused', 'elapsed_before': agent['elapsed_before'] + now - agent['started_at']}
    else:
        expected = 'ready' if data.action == 'start' else 'paused'
        if agent['status'] != expected:
            raise HTTPException(409, 'The agent state has changed. Please refresh and try again.')
        changes = {'status': 'active', 'started_at': now, 'stage_started_at': now - (agent['elapsed_before'] % 18)}
    result = await db.agents.update_one({'owner': uid, 'revision': agent['revision']}, {'$set': changes, '$inc': {'revision': 1}})
    if not result.modified_count:
        raise HTTPException(409, 'Your agent just changed tasks. Please try again.')
    updated = await db.agents.find_one({'owner': uid}, {'_id': 0})
    return AgentOut(**updated)

@api.get('/journal', response_model=list[EventOut])
async def journal(agent_id: Optional[str] = None, limit: int = Query(30, ge=1, le=100)):
    query = {'agent_id': agent_id} if agent_id else {}
    events = await db.events.find(query, {'_id': 0}).sort('created_at', -1).limit(limit).to_list(limit)
    return [EventOut(**e) for e in events]

@api.get('/rewards')
async def rewards():
    return {'status': 'awaiting_verification', 'asset': 'GLD', 'network': 'Solana', 'platform': 'Stonk.fun',
            'distribution_basis': 'pro_rata_holdings', 'agent_required': False, 'contest_affects_holder_share': False,
            'period_hours': None, 'finances': None, 'pool_balance': None, 'estimated': None, 'claimable': None,
            'fee_allocation': None, 'fee_received': None, 'transactions': [],
            'contracts': {'MINEPX': None, 'GLD': None, 'vault': None}}

@api.post('/rewards/claim')
async def claim():
    raise HTTPException(409, 'GLD claims are not available. Official Solana mint, Stonk.fun support, and settlement rules must be verified first.')

app.include_router(api)
app.include_router(make_strategy_router(db, owner))