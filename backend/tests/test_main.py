import tempfile
import unittest
from pathlib import Path

from app.main import _claim_background_workers


class BackgroundWorkerLockTests(unittest.TestCase):
    def test_only_one_owner_claims_background_workers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "workers.lock"
            first = _claim_background_workers(lock_path)
            self.assertIsNotNone(first)
            self.assertIsNone(_claim_background_workers(lock_path))
            first.close()
            replacement = _claim_background_workers(lock_path)
            self.assertIsNotNone(replacement)
            replacement.close()


if __name__ == "__main__":
    unittest.main()
