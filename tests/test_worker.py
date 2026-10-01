import unittest
import logging
from unittest.mock import Mock, patch

from teamcity import is_running_under_teamcity
from teamcity.unittestpy import TeamcityTestRunner

# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ltc_client import worker
from ltc_client.worker import StandardWorker, addLoggingLevel


class TestStandardWorkerLogVhost(unittest.TestCase):
    def test_log_handler_uses_webclients_vhost_without_moving_worker_connection(self):
        connection = Mock()
        mock_handler = Mock()

        with (
            patch.object(
                worker, "_rabbitmq_connect", return_value=connection
            ) as connect,
            patch.object(worker, "start_health_server"),
            patch.object(
                worker, "RabbitMQHandler", return_value=mock_handler
            ) as handler,
        ):
            StandardWorker(
                node_id="node",
                worker_name="worker",
                queue_host="rabbitmq",
                queue_port=5672,
                queue_user="taequeue",
                queue_password="secret",
                queue_use_ssl=False,
                queue_exchange="jobs",
            )

        self.assertIsNone(connect.call_args.args[-1])
        self.assertEqual(
            handler.call_args.kwargs["connection_params"]["virtual_host"],
            "/webclients",
        )
        logging.getLogger().removeHandler(mock_handler)


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
