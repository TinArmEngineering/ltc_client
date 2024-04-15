import unittest
import logging
import unittest

from teamcity import is_running_under_teamcity
from teamcity.unittestpy import TeamcityTestRunner

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tinarm.worker import addLoggingLevel


class TestAddLoggingLevel(unittest.TestCase):
    def setUp(self):
        self.level_name = "CUSTOM"
        self.level_num = 35

    def test_addLoggingLevel(self):
        addLoggingLevel(self.level_name, self.level_num)
        self.assertTrue(hasattr(logging, self.level_name))
        self.assertEqual(getattr(logging, self.level_name), self.level_num)

    def test_addLoggingLevel_invalid_level(self):
        with self.assertRaises(ValueError):
            addLoggingLevel(self.level_name, "invalid")

    def test_addLoggingLevel_duplicate_level(self):
        addLoggingLevel(self.level_name, self.level_num)
        with self.assertRaises(ValueError):
            addLoggingLevel(self.level_name, self.level_num)


if __name__ == "__main__":
    if is_running_under_teamcity():
        runner = TeamcityTestRunner()
    else:
        runner = unittest.TextTestRunner()
    unittest.main(testRunner=runner)
