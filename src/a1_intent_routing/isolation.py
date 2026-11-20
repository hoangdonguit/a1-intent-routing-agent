"""Explain outside-lab inventory changes without ignoring host-route fields."""
from collections import Counter
import json


def _difference(before, after):
    # Route listing order is not routing state. Preserve every field and duplicates.
    left = Counter(json.dumps(row, sort_keys=True) for row in before)
    right = Counter(json.dumps(row, sort_keys=True) for row in after)
    return {'removed': [json.loads(s) for s in sorted((left - right).elements())],
            'added': [json.loads(s) for s in sorted((right - left).elements())]}


def isolation_changes(before, after):
    routes = _difference(before['routes'], after['routes'])
    other = {key: {'before': before['other'].get(key), 'after': after['other'].get(key)}
             for key in sorted(set(before['other']) | set(after['other']))
             if before['other'].get(key) != after['other'].get(key)}
    networks = _difference(before['networks'], after['networks'])
    unchanged = not other and not any(routes.values()) and not any(networks.values())
    return {'other_resources_unchanged': unchanged,
            'outside_changes': {'containers': other, 'networks': networks, 'host_routes': routes}}
