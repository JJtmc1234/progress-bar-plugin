"""Tests for bin/agentd.py with a fake `claude` and a fake channel.py. python3 tests/agentd_test.py"""
import importlib.util, json, os, stat, sys, tempfile, time, unittest

BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bin')
FAKE_CLAUDE = """#!/usr/bin/env python3
import sys, json
if '--input-format' not in sys.argv:
    print('big' if 'BIGTASK' in ' '.join(sys.argv) else 'small'); sys.exit()
for line in sys.stdin:
    t = json.loads(line)['message']['content']
    print(json.dumps({'type': 'result', 'result': 'got: ' + t}), flush=True)
"""


def wait(cond, secs=5):
    end = time.time() + secs
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        os.environ['PB_AGENTD_HOME'] = os.path.join(self.d, 'agentd')
        os.environ['PB_CHANNEL_HOME'] = os.path.join(self.d, 'channel')
        fc = os.path.join(self.d, 'claude')
        open(fc, 'w').write(FAKE_CLAUDE)
        os.chmod(fc, 0o755)
        spec = importlib.util.spec_from_file_location('agentd', os.path.join(BIN, 'agentd.py'))
        self.m = m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        os.makedirs(m.HOME, exist_ok=True)
        m.cfg = dict(m.DEFAULTS, channel='x', claude=fc, max_agents=3, max_workers=2)
        self.said = []
        m.say = lambda text, who='agentd': self.said.append((who, text)) or True

    def tearDown(self):
        for a in list(self.m.agents):
            self.m.stop_agent(a)

    def test_task_pivot_and_result(self):
        m = self.m
        m.handle('/task --small write a haiku')
        aid = next(iter(m.agents))
        self.assertTrue(wait(lambda: (aid, 'got: write a haiku') in self.said))
        m.handle('@%s now make it longer' % aid)
        self.assertTrue(wait(lambda: (aid, 'got: now make it longer') in self.said))

    def test_unknown_agent_and_help(self):
        self.m.handle('@a0000 hi')
        self.m.handle('hello')
        self.assertIn('no running agent', self.said[0][1])
        self.assertIn('/task', self.said[1][1])

    def test_plain_text_and_all_reach_every_agent_and_agents_can_read_chat(self):
        m = self.m
        m.handle('/task --small one'); m.handle('/task --small two')
        ids = list(m.agents)
        m.handle('change of plan')
        for i in ids:
            self.assertTrue(wait(lambda i=i: (i, 'got: [chat from the collaborator]\nchange of plan') in self.said))
        m.handle('@all stop now')
        self.assertTrue(wait(lambda: (ids[0], 'got: [chat from the collaborator]\nstop now') in self.said))
        lines = m.serve({'op': 'read', 'id': ids[0], 'n': 10})['lines']
        self.assertTrue(any('collaborator: change of plan' in l for l in lines))
        self.assertFalse(m.serve({'op': 'read', 'id': 'zzzz'})['ok'])

    def test_big_task_spawns_coordinator_with_capped_workers(self):
        m = self.m
        m.handle('/task BIGTASK do many things')
        cid = next(iter(m.agents))
        self.assertEqual(m.agents[cid].role, 'coordinator')
        w1 = m.serve({'op': 'spawn', 'id': cid, 'text': 'piece 1'})['id']
        m.serve({'op': 'spawn', 'id': cid, 'text': 'piece 2'})
        self.assertFalse(m.serve({'op': 'spawn', 'id': cid, 'text': 'piece 3'})['ok'])
        # a worker's result goes to the coordinator, which answers to the chat
        self.assertTrue(wait(lambda: (cid, 'got: [worker %s finished]\ngot: piece 1' % w1) in self.said))

    def test_worker_cannot_spawn_and_limit(self):
        m = self.m
        m.handle('/task --small a')
        aid = next(iter(m.agents))
        self.assertFalse(m.serve({'op': 'spawn', 'id': aid, 'text': 'x'})['ok'])
        m.handle('/task --small b'); m.handle('/task --small c'); m.handle('/task --small d')
        self.assertTrue(any('limit' in t for _, t in self.said))

    def test_post_and_paused(self):
        m = self.m
        m.handle('/task --small a')
        aid = next(iter(m.agents))
        self.assertTrue(m.serve({'op': 'post', 'id': aid, 'text': 'hello group'})['ok'])
        self.assertIn((aid, 'hello group'), self.said)
        self.assertFalse(m.serve({'op': 'post', 'id': 'zzzz', 'text': 'x'})['ok'])
        open(m.PAUSED, 'w').close()
        m.handle('/task --small b')
        self.assertTrue(any('paused' in t for _, t in self.said))

    def test_inbound_skips_history_then_reads_new_peer_lines(self):
        m = self.m
        chat = os.path.join(m.CH, 'x'); os.makedirs(chat)
        def entry(i, d='in', ok=True):
            p = os.path.join(chat, 'chat-%s.md' % i)
            open(p, 'w').write('/task hi ' + i)
            return {'id': i, 'channel': 'x', 'dir': d, 'chat': True, 'verified': ok, 'path': p}
        idx = os.path.join(m.CH, 'index.json')
        json.dump([entry('old1')], open(idx, 'w'))
        m.channel_cmd = lambda *a, **k: (0, '')
        st = {}
        self.assertEqual(m.inbound(st), [])
        json.dump([entry('old1'), entry('new1'), entry('mine', 'out'), entry('bad', ok=False)], open(idx, 'w'))
        self.assertEqual([t for _, t in m.inbound(st)], ['/task hi new1'])
        self.assertEqual(m.inbound(st), [])


if __name__ == '__main__':
    unittest.main()
