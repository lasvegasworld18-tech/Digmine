"""Pure, bounded rule engine shared by live play and strategy evaluation. No financial state."""
import copy
import hashlib
import operator
from strategy_models import Strategy, GameState

OPS = {'lt': operator.lt, 'lte': operator.le, 'gt': operator.gt,
       'gte': operator.ge, 'eq': operator.eq, 'neq': operator.ne}
ACTION_STAGE = {'mine': 'digging', 'survey': 'surveying', 'deeper': 'surveying',
                'shallower': 'surveying', 'return': 'hauling', 'refine': 'refining',
                'rest': 'basecamp', 'repair': 'repairing'}

def condition(field, value, op='lte'):
    return {'field': field, 'operator': op, 'value': value}

def rule(id, name, conditions, action):
    return {'id': id, 'name': name, 'enabled': True, 'match': 'all',
            'groups': [{'match': 'all', 'conditions': conditions}], 'action': action}

def preset(key='balanced'):
    configs = {
        'balanced': dict(name='Wayfinder', target_depth=3, risk=40, haul_threshold=75, energy_reserve=30, repair_threshold=30, ore_priority='balanced'),
        'prospector': dict(name='Deep Prospector', target_depth=5, risk=75, haul_threshold=90, energy_reserve=18, repair_threshold=18, ore_priority='rich'),
        'guardian': dict(name='Steady Hand', target_depth=2, risk=15, haul_threshold=50, energy_reserve=45, repair_threshold=45, ore_priority='balanced'),
        'hauler': dict(name='Freight Runner', target_depth=2, risk=35, haul_threshold=65, energy_reserve=25, repair_threshold=25, ore_priority='volume'),
    }
    config = configs.get(key, configs['balanced']).copy()
    config['rules'] = [
        rule('protect-haul', 'Protect the haul', [condition('cargo', 35, 'gte'), condition('energy', 25)], 'return'),
        rule('maintain-tools', 'Keep tools sharp', [condition('tool', config['repair_threshold'])], 'repair'),
        rule('rich-seam', 'Work a rich seam', [condition('quality', 80, 'gte'), condition('energy', 45, 'gte'), condition('cargo', config['haul_threshold'], 'lt')], 'mine'),
    ]
    return Strategy(**config).model_dump()

def matches(rule, state):
    groups = []
    for group in rule['groups']:
        values = [OPS[c['operator']](state[c['field']], c['value']) for c in group['conditions']]
        groups.append(all(values) if group['match'] == 'all' else any(values))
    return all(groups) if rule['match'] == 'all' else any(groups)

def choose(config, state):
    # Hard safety and transport commitments cannot be bypassed by custom rules.
    if state['returning']:
        return 'refine', 'Delivery commitment: unload the cart.'
    if state['energy'] <= 8:
        return 'rest', 'Safety override: energy is critically low.'
    if state['tool'] <= 8:
        return 'repair', 'Safety override: tool integrity is critically low.'
    if state['cargo'] >= 100:
        return 'return', 'Safety override: the cart is full.'
    for r in config['rules']:
        if r['enabled'] and matches(r, state):
            return r['action'], f"Rule: {r['name']}"
    if state['cargo'] >= config['haul_threshold']:
        return 'return', 'Haul threshold reached.'
    if state['energy'] < config['energy_reserve']:
        return 'rest', 'Preserving the energy reserve.'
    if state['tool'] < config['repair_threshold']:
        return 'repair', 'Preventive tool maintenance.'
    if state['depth'] < config['target_depth']:
        return 'deeper', 'Working toward the target depth.'
    if state['depth'] > config['target_depth']:
        return 'shallower', 'Returning to the target depth.'
    if state['quality'] < 40:
        return 'survey', 'Searching for a better vein.'
    return 'mine', 'Working the current vein.'

def score(state):
    return max(0, state['banked_points'] + state['exploration_points'] - state['penalties'])

def step(config, original, seed='brass-hollow-v1'):
    state = copy.deepcopy(original)
    action, reason = choose(config, state)
    draw = int(hashlib.sha256(f"{seed}:{state['decision']}".encode()).hexdigest()[:8], 16)
    roll = (draw % 10000) / 10000
    state['hazard'] = min(95, 5 + state['depth'] * 7 + config['risk'] // 3)
    if action == 'return' and not state['cargo']:
        action, reason = 'survey', reason + ' Empty cart; surveying instead.'
    if action == 'deeper' and state['depth'] == 5:
        action, reason = 'survey', reason + ' Depth limit reached; surveying instead.'
    if action == 'shallower' and state['depth'] == 1:
        action, reason = 'survey', reason + ' Already at the shallowest depth.'
    if action == 'mine':
        cost = 6 + state['depth'] + config['risk'] // 25
        state['energy'] -= cost
        state['tool'] -= 3 + state['depth'] + config['risk'] // 30
        chance = .015 + state['depth'] * .012 + config['risk'] * .001 - state['quality'] * .00015
        if roll < chance:
            lost = state['cargo'] // 3
            old = max(1, state['cargo'])
            state['cargo_value'] = state['cargo_value'] * (old - lost) // old
            state['cargo'] -= lost
            state['energy'] -= 10
            state['tool'] -= 10
            state['incidents'] += 1
            state['penalties'] += 25
            message = f'A loose seam set us back. Lost {lost} ore; 25 mining points deducted.'
        else:
            quantity = 6 + state['depth'] * 2 + config['risk'] // 20 + state['quality'] // 20
            value = 1 + state['depth']
            if config['ore_priority'] == 'volume':
                quantity += 7
                value = max(1, value - 1)
            elif config['ore_priority'] == 'rich':
                quantity = max(3, quantity - 4)
                value += 2
            quantity = min(100 - state['cargo'], quantity)
            state['cargo'] += quantity
            state['cargo_value'] += quantity * value
            state['mined'] += quantity
            message = f'Mined {quantity} ore at depth {state["depth"]}. Cart is {state["cargo"]}% full.'
        state['quality'] = max(15, state['quality'] - 7)
    elif action == 'refine':
        delivered, points = state['cargo'], state['cargo_value']
        state['delivered'] += delivered
        state['banked_points'] += points
        state['deliveries'] += 1
        state.update(cargo=0, cargo_value=0, returning=False, depth=1, quality=55)
        message = f'Delivered {delivered} ore to the refinery. Banked {points} mining points.'
    elif action == 'return':
        state['returning'] = True
        state['energy'] -= 7
        message = f'Taking {state["cargo"]} ore back to the refinery. Keeping this haul safe.'
    elif action == 'rest':
        state['energy'] = min(100, state['energy'] + 32)
        message = f'A breather at basecamp. Energy restored to {state["energy"]}%.'
    elif action == 'repair':
        state['tool'] = min(100, state['tool'] + 38)
        state['energy'] -= 3
        message = f'Pickaxe serviced. Tool integrity is {state["tool"]}%.'
    elif action in ('deeper', 'shallower'):
        state['depth'] += 1 if action == 'deeper' else -1
        state['energy'] -= 10 if action == 'deeper' else 4
        state['tool'] -= 3
        state['quality'] = 45 + draw % 41
        if state['depth'] > state['deepest']:
            state['exploration_points'] += 10
            state['deepest'] = state['depth']
        message = f'Reached depth {state["depth"]}. Vein quality reads {state["quality"]}%.'
    else:
        state['energy'] -= 5
        state['quality'] = min(100, state['quality'] + 20 + draw % 16)
        message = f'Survey complete. Located a vein with {state["quality"]}% quality.'
    state['energy'] = max(0, min(100, state['energy']))
    state['tool'] = max(0, min(100, state['tool']))
    state['decision'] += 1
    state['last_action'], state['last_reason'] = action, reason
    return state, ACTION_STAGE[action], message

def evaluate(config, decisions=120):
    state = GameState().model_dump()
    trace = []
    for i in range(decisions):
        state, stage, message = step(config, state, 'brass-hollow-evaluation-v1')
        if i < 6 or i >= decisions - 6:
            trace.append({'decision': i + 1, 'action': state['last_action'], 'reason': state['last_reason'],
                          'energy': state['energy'], 'tool': state['tool'], 'cargo': state['cargo'], 'message': message})
    return {'decisions': decisions, 'score': score(state), 'delivered': state['delivered'],
            'incidents': state['incidents'], 'energy': state['energy'], 'tool': state['tool'],
            'banked_points': state['banked_points'], 'exploration_points': state['exploration_points'],
            'penalties': state['penalties'], 'trace': trace}