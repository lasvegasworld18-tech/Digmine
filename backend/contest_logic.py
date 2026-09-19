from datetime import datetime, timedelta, timezone
from strategy_models import LeaderboardRow

ACTION_BUDGET = 600

def season_info(now=None):
    now = now or datetime.now(timezone.utc)
    start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return {'id': start.strftime('%Y-%m-%d'), 'name': 'Brass Hollow Open',
            'starts_at': start.isoformat(), 'ends_at': end.isoformat(), 'ends_ts': end.timestamp(),
            'action_budget': ACTION_BUDGET, 'decision_seconds': 18, 'prize_status': 'to_be_announced',
            'prize_amount': None, 'prize_asset': None, 'funding_source': 'Separate project or sponsor pool',
            'holder_pool_used': False, 'wallet_verification_required_for_prizes': True,
            'rules_version': 'brass-hollow-v1'}

def row_from_agent(agent):
    c = agent['contest']
    return dict(agent_id=agent['id'], name=agent['name'], avatar=agent['avatar'],
                strategy_name=agent.get('strategy_name', 'Wayfinder'), score=c['score'],
                delivered=c['delivered'], actions_used=c['actions_used'], incidents=c['incidents'],
                status=c['status'], entered_at=c['entered_at'])

async def archive_entry(db, agent):
    if not agent.get('contest'):
        return
    row = row_from_agent(agent)
    row['season_id'] = agent['contest']['season_id']
    row['id'] = f"{agent['id']}:{row['season_id']}"
    await db.contest_archive.update_one({'id': row['id']}, {'$set': row}, upsert=True)

async def leaderboard(db, season_id, limit=100):
    live = await db.agents.find({'is_bot': False, 'contest.season_id': season_id}, {'_id': 0}).to_list(10000)
    archive = await db.contest_archive.find({'season_id': season_id}, {'_id': 0}).to_list(10000)
    rows = {row['agent_id']: row for row in archive}
    rows.update({a['id']: row_from_agent(a) for a in live})
    ordered = sorted(rows.values(), key=lambda r: (-r['score'], -r['delivered'], r['actions_used'], r['entered_at'], r['agent_id']))
    return [LeaderboardRow(rank=i + 1, **{k: v for k, v in row.items() if k in LeaderboardRow.model_fields and k != 'rank'}) for i, row in enumerate(ordered[:limit])], len(ordered)