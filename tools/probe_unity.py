import json, os, sys

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    import warehouse
except Exception as e:
    print("IMPORT_ERROR:", e)
    raise

m = warehouse.Warehouse()
m.setup()
m.epsilon_override = 0.05
m.auto_cycle_reset = False
outs = []
for _ in range(3):
    m.step()
    env = m.serialize_for_unity()
    outs.append({
        'tick': env['state']['ticks'],
        'robots': [ {'id': r['id'], 'heading': r['heading'], 'action': r['action']} for r in env['state']['robots'] ],
        'actions': env['state']['actions'],
        'episode_done': env['state']['episode_done'],
    })
print(json.dumps(outs, indent=2))
