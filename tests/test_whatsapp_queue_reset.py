# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from pathlib import Path

from services.whatsapp_queue.queue_v246 import (
    SafeWhatsAppQueue, PENDING, IN_FLIGHT, FAILED,
)


class TestWhatsAppQueueReset(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.queue_file = os.path.join(self.tmp_dir.name, "test_wa_queue.sqlite3")
        self.q = SafeWhatsAppQueue(self.queue_file)
        self.db_path = os.path.join(self.tmp_dir.name, "ogrenciler.db")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _sample_jobs(self):
        return [
            {"student_id": 1, "recipient": "05464416905", "message": "Ödev 1"},
            {"student_id": 2, "recipient": "05464416906", "message": "Ödev 2"},
            {"student_id": 3, "recipient": "05464416907", "message": "Ödev 3"},
        ]

    def test_cancel_batch(self):
        batch = self.q.create_batch(self.db_path, self._sample_jobs())
        self.assertEqual(self.q.counts(batch).get(PENDING), 3)
        self.assertEqual(self.q.current_batch(self.db_path), batch)

        # Cancel
        cancelled_count = self.q.cancel_batch(batch, "Test iptali")
        self.assertEqual(cancelled_count, 3)

        # After cancellation, no pending jobs exist, current_batch should be None
        self.assertIsNone(self.q.current_batch(self.db_path))
        counts = self.q.counts(batch)
        self.assertEqual(counts.get(PENDING, 0), 0)
        self.assertEqual(counts.get(FAILED, 0), 3)

    def test_purge_batch(self):
        batch = self.q.create_batch(self.db_path, self._sample_jobs())
        self.assertEqual(self.q.latest_batch(self.db_path), batch)

        # Purge
        self.q.purge_batch(batch)

        # Completely gone from database
        self.assertIsNone(self.q.current_batch(self.db_path))
        self.assertIsNone(self.q.latest_batch(self.db_path))
        self.assertEqual(len(self.q.rows(batch)), 0)

    def test_purge_queue_for_db(self):
        b1 = self.q.create_batch(self.db_path, self._sample_jobs())
        b2 = self.q.create_batch(self.db_path, self._sample_jobs()[:1])

        deleted = self.q.purge_queue(self.db_path)
        self.assertEqual(deleted, 4)
        self.assertIsNone(self.q.latest_batch(self.db_path))

    def test_clean_stale_lock(self):
        lock_path = self.queue_file + ".worker.lock"
        # Write dead PID
        with open(lock_path, "w") as f:
            f.write("999999999")
        self.assertTrue(os.path.exists(lock_path))

        self.q.clean_stale_lock()
        self.assertFalse(os.path.exists(lock_path))


if __name__ == "__main__":
    unittest.main()
