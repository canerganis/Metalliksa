"""Execution IDs can differ without changing the canonical LPBF input identity."""
import json
from pathlib import Path
import tempfile
import unittest
from lpbf_worker import Queue


class ExecutionScopeTests(unittest.TestCase):
    def test_repeat_runs_bypass_only_result_reuse(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1] / '.runtime') as directory:
            queue = Queue(Path(directory), start=False)
            self.addCleanup(queue.close)
            request = {'mode': 'screening'}

            ordinary = queue.submit(request)
            ordinary_again = queue.submit(request)
            repeats = [queue.submit(request, execution_scope='repeat') for _ in range(3)]

            self.assertEqual(ordinary['id'], ordinary_again['id'])
            self.assertTrue(ordinary_again['deduplicated'])
            ids = [entry['id'] for entry in repeats]
            self.assertEqual(len(set(ids)), 3)
            self.assertTrue(all(not entry['cacheHit'] for entry in repeats))

            submitted_bytes = [(queue.root / job_id / 'input.json').read_bytes() for job_id in ids]
            self.assertEqual(submitted_bytes, [submitted_bytes[0]] * 3)
            self.assertEqual(submitted_bytes[0], (queue.root / ordinary['id'] / 'input.json').read_bytes())
            self.assertNotIn('executionScope', json.loads(submitted_bytes[0]))
            with queue.connect() as connection:
                keys = [connection.execute('SELECT cache_key FROM jobs WHERE id=?', (job_id,)).fetchone()[0]
                        for job_id in ids]
            self.assertEqual(keys, [keys[0]] * 3)

            archived = []
            for job_id in ids:
                queue.update(job_id, status='running')
                queue.execute(job_id)
                state = queue.get(job_id)
                self.assertEqual(state['status'], 'completed', state.get('error'))
                archived.append(queue.capture(job_id))
            self.assertEqual([capture['jobId'] for capture in archived], ids)
            results = [json.loads(capture['resultJson']) for capture in archived]
            self.assertEqual(len({result['provenance']['inputHash'] for result in results}), 1)
            self.assertEqual(len({result['provenance']['executionInputHash'] for result in results}), 1)
            self.assertEqual(len({result['provenance']['implementationHash'] for result in results}), 1)
            self.assertEqual([capture['inputJson'] for capture in archived], [archived[0]['inputJson']] * 3)
            self.assertEqual([capture['materialJson'] for capture in archived], [archived[0]['materialJson']] * 3)
            cached = queue.submit(request)
            self.assertEqual(cached['id'], ids[-1])
            self.assertTrue(cached['cacheHit'])

    def test_unknown_execution_scope_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1] / '.runtime') as directory:
            queue = Queue(Path(directory), start=False)
            self.addCleanup(queue.close)
            with self.assertRaisesRegex(ValueError, 'execution scope'):
                queue.submit({'mode': 'screening'}, execution_scope='new-physics')


if __name__ == '__main__':
    unittest.main()
