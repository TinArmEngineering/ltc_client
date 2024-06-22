import unittest
import logging

from teamcity import is_running_under_teamcity
from teamcity.unittestpy import TeamcityTestRunner

# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ltc_client.worker import addLoggingLevel


class TestAddLoggingLevel(unittest.TestCase):
    def setUp(self):
        self.level_name = "WHAT_THE_HECK"
        self.level_num = 35
        self.class_name = "wth_log"

    def test_addLoggingLevel(self):
        addLoggingLevel(self.level_name, self.level_num, self.class_name)
        self.assertTrue(hasattr(logging, self.level_name))
        self.assertEqual(getattr(logging, self.level_name), self.level_num)

    def test_addLoggingLevel_invalid_level(self):
        with self.assertRaises(ValueError):
            addLoggingLevel(self.level_name + "next", "invalid")

    def test_addLoggingLevel_duplicate_level(self):
        addLoggingLevel(self.level_name + "next" * 2, self.level_num)
        with self.assertRaises(AttributeError):
            addLoggingLevel(self.level_name + "next" * 2, self.level_num)


if __name__ == "__main__":
    if is_running_under_teamcity():
        runner = TeamcityTestRunner()
    else:
        runner = unittest.TextTestRunner()
    unittest.main(testRunner=runner)
