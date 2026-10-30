"""Portable ESD state records, using the shared structural script merger."""
from dataclasses import replace

from . import esd,esd_merge,formats

MAX_NODES = 100000
MAX_DEPTH = 64
MAX_ARGUMENT = 16 * 1024 * 1024


def supported(relative):
    return (bool(relative.parts) and relative.parts[0].lower() in ('chr','script','menu')
            and relative.name.lower().removesuffix('.dcx').endswith('.esd'))


def parse(raw):
    return esd.parse(formats.inflate(raw) if raw.startswith(b'DCX\0') else raw)


def validate_original(raw):
    esd.validate_writable(parse(raw))


def _integer(value,bits=64):
    if type(value) is not int or not -(2**(bits-1)) <= value < 2**(bits-1):
        raise ValueError('Invalid ESD record integer')
    return value


def _hex(value):
    if type(value) is not str or len(value) > MAX_ARGUMENT*2:
        raise ValueError('Invalid ESD argument byte string')
    data = bytes.fromhex(value)
    if len(data) > MAX_ARGUMENT:
        raise ValueError('ESD argument exceeds its size limit')
    return data


def _list(value):
    if type(value) is not list or len(value) > MAX_NODES:
        raise ValueError('Invalid ESD record list')
    return value


def _spend(budget):
    budget[0] -= 1
    if budget[0] < 0:
        raise ValueError('Too many portable ESD commands or conditions')


def _commands(value,budget):
    result = []
    for command in _list(value):
        _spend(budget)
        if type(command) is not list or len(command) != 3:
            raise ValueError('Invalid ESD command record')
        args = []
        for arg in _list(command[2]):
            _spend(budget)
            args.append(_hex(arg))
        result.append(esd.Command(_integer(command[0],32),_integer(command[1],32),args))
    return result


def _conditions(value,budget,depth=0):
    if depth > MAX_DEPTH:
        raise ValueError('Portable ESD conditions are nested too deeply')
    result = []
    for condition in _list(value):
        _spend(budget)
        if type(condition) is not list or len(condition) != 4:
            raise ValueError('Invalid ESD condition record')
        target = None if condition[0] is None else _integer(condition[0])
        result.append(esd.Condition(target,_hex(condition[1]),_commands(condition[2],budget),
                                    _conditions(condition[3],budget,depth+1)))
    return result


def _state(value,identity,budget):
    if value is None:
        return None
    if (type(value) is not dict or set(value) != {'id','entry','exit','while','conditions'}
            or _integer(value['id']) != identity):
        raise ValueError('Invalid ESD state identity')
    return esd.State(identity,_commands(value['entry'],budget),_commands(value['exit'],budget),
                     _commands(value['while'],budget),_conditions(value['conditions'],budget))


def _dump_commands(commands,budget):
    result = []
    for command in commands:
        _spend(budget)
        args = []
        for arg in command.args:
            _spend(budget)
            if len(arg)>MAX_ARGUMENT:
                raise ValueError('ESD argument exceeds its portable size limit')
            args.append(arg.hex())
        result.append([command.bank,command.id,args])
    return result


def _dump_conditions(conditions,budget,depth=0):
    if depth > MAX_DEPTH:
        raise ValueError('ESD conditions exceed the portable nesting limit')
    result = []
    for condition in conditions:
        _spend(budget)
        if len(condition.evaluator)>MAX_ARGUMENT:
            raise ValueError('ESD evaluator exceeds its portable size limit')
        result.append([condition.target_state,condition.evaluator.hex(),_dump_commands(condition.pass_commands,budget),
                       _dump_conditions(condition.subconditions,budget,depth+1)])
    return result


def _dump_state(state,budget):
    if state is None:
        return None
    return {'id':state.id,'entry':_dump_commands(state.entry_commands,budget),
            'exit':_dump_commands(state.exit_commands,budget),'while':_dump_commands(state.while_commands,budget),
            'conditions':_dump_conditions(state.conditions,budget)}


def describe(spec,table):
    changes = []
    for group in _list(spec.get('groups')):
        for state in _list(group['states']):
            before,after = state['before'],state['after']
            changed = ([label for key,label in (('entry','Entry commands'),('exit','Exit commands'),
                        ('while','While commands'),('conditions','Conditions')) if before[key] != after[key]]
                       if before is not None and after is not None else [])
            changes.append({'table':table,'id':f"{group['id']}:{state['id']}",
                'label':f"State {group['id']}/{state['id']}",'fields':changed,
                'added':before is None,'removed':after is None})
    return changes


def create(before,after):
    a,b = parse(before),parse(after)
    esd.validate_writable(a)
    esd.validate_writable(b)
    if (a.name,a.dark_souls_count,a.long_format,a.unk) != (b.name,b.dark_souls_count,b.long_format,b.unk):
        raise ValueError('Changes to ESD file metadata cannot be exported as state edits')
    groups,budget = [],[MAX_NODES]
    for group in sorted(a.state_groups.keys()|b.state_groups.keys()):
        first,last = a.state_groups.get(group,{}),b.state_groups.get(group,{})
        if first == last and (group in a.state_groups) == (group in b.state_groups):
            continue
        states = []
        for key in sorted(first.keys()|last.keys()):
            if first.get(key) != last.get(key):
                _spend(budget)
                states.append({'id':key,'before':_dump_state(first.get(key),budget),
                               'after':_dump_state(last.get(key),budget)})
        groups.append({'id':group,'before':group in a.state_groups,'after':group in b.state_groups,'states':states})
        if len(groups)>MAX_NODES:
            raise ValueError('Too many portable ESD groups')
    return {'kind':'esd','darkSoulsCount':a.dark_souls_count,'groups':groups}


def materialize(original,spec,*,talk_options=True):
    if (type(spec) is not dict or set(spec) != {'kind','darkSoulsCount','groups'} or spec['kind'] != 'esd'
            or type(spec['darkSoulsCount']) is not int):
        raise ValueError('Invalid portable ESD format')
    document = parse(original)
    if document.dark_souls_count != spec['darkSoulsCount']:
        raise ValueError('The ESD format anchor does not match')
    groups = {key:dict(states) for key,states in document.state_groups.items()}
    seen,budget = set(),[MAX_NODES]
    for group in _list(spec['groups']):
        if (type(group) is not dict or set(group) != {'id','before','after','states'}
                or type(group['before']) is not bool or type(group['after']) is not bool):
            raise ValueError('Invalid ESD group record')
        identity = _integer(group['id'])
        if identity in seen:
            raise ValueError('Duplicate portable ESD group')
        seen.add(identity)
        if group['before'] and identity not in groups and group['after']:
            raise ValueError(f'ESD group {identity}: the group anchor is missing')
        states = dict(groups.get(identity,{}))
        seen_states = set()
        for change in _list(group['states']):
            _spend(budget)
            if type(change) is not dict or set(change) != {'id','before','after'}:
                raise ValueError('Invalid ESD state change')
            key = _integer(change['id'])
            if key in seen_states:
                raise ValueError('Duplicate portable ESD state')
            seen_states.add(key)
            before,after = (_state(change[side],key,budget) for side in ('before','after'))
            current = states.get(key)
            if before is None or after is None:
                if current not in (before,after):
                    raise ValueError(f'ESD {identity}/{key}: the added/removed state anchor does not match')
                if after is None:
                    states.pop(key,None)
                else:
                    states[key] = after
            else:
                if current is None:
                    raise ValueError(f'ESD {identity}/{key}: the state anchor is missing')
                result,conflicts = esd_merge.merge_records(before,[('Installed data',current),('Mod edit',after)],
                                                          talk_options=talk_options)
                if conflicts:
                    raise ValueError(f'ESD {identity}/{key}: the state edit conflicts with installed data')
                states[key] = result
        if group['after']:
            groups[identity] = states
        else:
            if states:
                raise ValueError(f'ESD group {identity}: removing it would discard installed states')
            groups.pop(identity,None)
    result = replace(document,state_groups=groups)
    if result == document:
        return original
    plain = result.to_bytes()  # Validate every final transition target.
    return formats.deflate(original,plain) if original.startswith(b'DCX\0') else plain
