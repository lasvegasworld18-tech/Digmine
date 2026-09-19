"""Deterministic, server-owned expedition clock. No game state affects financial rights."""
import asyncio
import logging
import time
from datetime import datetime, timezone
from game_worker import game_defaults, migrate, advance_game

STAGES = ['basecamp', 'surveying', 'digging', 'hauling', 'refining', 'repairing']
STEP_SECONDS = 18
CREW = [
    ('Flint', 'brass', 'Methodical'), ('Moss', 'sage', 'Curious'),
    ('Copper', 'copper', 'Optimistic'), ('Echo', 'ice', 'Observant'),
    ('Pip', 'brass', 'Cheerful'), ('Bramble', 'sage', 'Patient'),
    ('Rivet', 'copper', 'Practical'), ('Nova', 'ice', 'Adventurous'),
    ('Dusty', 'brass', 'Thoughtful'), ('Fern', 'sage', 'Resourceful'),
    ('Ember', 'copper', 'Determined'), ('Atlas', 'ice', 'Steady'),
]
REPORTS = {
    'basecamp': ['Back at basecamp. Packing supplies for the next expedition.', 'A fresh lantern and a clear route. Ready for another shift.'],
    'surveying': ['Checking the rock face. There is a promising seam ahead.', 'Survey markers are down. This tunnel is worth a closer look.'],
    'digging': ['Found a seam. Pickaxe out, taking it one careful swing at a time.', 'The rock is giving way. Collecting ore from this vein.'],
    'hauling': ['The cart is full. Heading back to the refinery.', 'Ore secured. Taking the rails back to the furnace.'],
    'refining': ['Delivery complete. Sorting this haul at the refinery.', 'The furnace is warm. Another batch of ore delivered.'],
    'repairing': ['Sharpening the pickaxe. A little care goes a long way.', 'Checking the tools before heading underground again.'],
}

def iso(timestamp=None):
    return datetime.fromtimestamp(timestamp or time.time(), timezone.utc).isoformat()

def ore_for(step):
    cycles, phase = divmod(step, 6)
    blocks, remainder = divmod(cycles, 4)
    return blocks * 18 + sum(3 + i for i in range(remainder)) + (3 + cycles % 4 if phase >= 3 else 0)

def make_agent(agent_id, name, avatar, preference, personality, is_bot=False, offset=0):
    now = time.time()
    return dict(id=agent_id, name=name, avatar=avatar, preference=preference,
                personality=personality, is_bot=is_bot, status='active' if is_bot else 'ready',
                stage='basecamp', step=0, stage_started_at=now - offset,
                started_at=now - offset, elapsed_before=0.0, ore=0, expeditions=0,
                discoveries=[], created_at=iso(now), revision=0, **game_defaults(preference))

async def seed(db):
    await db.agents.create_index('id', unique=True)
    await db.agents.create_index('owner', unique=True, sparse=True)
    await db.events.create_index('id', unique=True)
    await db.events.create_index([('created_at', -1)])
    await db.sessions.create_index('token_hash', unique=True)
    for i, (name, avatar, personality) in enumerate(CREW):
        preference = ['balanced', 'careful', 'deep'][i % 3]
        agent = make_agent(f'crew-{i + 1:02}', name, avatar, preference, personality, True, i * 9)
        await db.agents.update_one({'id': agent['id']}, {'$setOnInsert': agent}, upsert=True)
        await db.agents.update_one({'id': agent['id'], 'is_bot': True}, {'$set': {'preference': preference}})
    await migrate(db)

async def advance(db, agent):
    if not agent['is_bot']:
        return await advance_game(db, agent)
    now = time.time()
    elapsed = agent['elapsed_before'] + now - agent['started_at']
    target = int(elapsed // STEP_SECONDS)
    if target <= agent['step']:
        return
    # Unique event ids make retries/recovery idempotent. Retain the recent catch-up window.
    for step in range(max(agent['step'] + 1, target - 35), target + 1):
        stage = STAGES[step % 6]
        message = REPORTS[stage][(step // 6 + len(agent['name'])) % 2]
        if stage == 'surveying' and agent['preference'] == 'deep':
            message = 'Following the deeper seam. Marking a route through the crystal gallery.'
        elif stage == 'surveying' and agent['preference'] == 'careful':
            message = 'Checking the supports first. Taking the steady route through the west shaft.'
        event = dict(id=f"{agent['id']}:{step}", agent_id=agent['id'], name=agent['name'],
                     avatar=agent['avatar'], is_bot=agent['is_bot'], stage=stage,
                     message=message, created_at=iso(agent['started_at'] + step * STEP_SECONDS - agent['elapsed_before']))
        await db.events.update_one({'id': event['id']}, {'$setOnInsert': event}, upsert=True)
    cycles = target // 6
    discoveries = [name for threshold, name in [(1, 'pyrite'), (3, 'quartz'), (6, 'azurite')] if cycles >= threshold]
    await db.agents.update_one({'id': agent['id'], 'revision': agent['revision'], 'status': 'active'}, {'$set': {
        'step': target, 'stage': STAGES[target % 6], 'stage_started_at': agent['started_at'] + target * STEP_SECONDS - agent['elapsed_before'],
        'ore': ore_for(target), 'expeditions': cycles, 'discoveries': discoveries,
    }, '$inc': {'revision': 1}})

async def worker(db, state):
    while True:
        try:
            async for agent in db.agents.find({'$or': [{'status': 'active'}, {'contest.status': 'active'}]}, {'_id': 0}):
                await advance(db, agent)
            state.last_tick = time.time()
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception('Expedition worker will retry on next tick')
        await asyncio.sleep(2)