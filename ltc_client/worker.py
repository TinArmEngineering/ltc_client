import functools
import json
import logging
import os
import pika
from socket import gaierror
import platform
import ssl
import sys
import threading
import time

from pathlib import Path
from python_logging_rabbitmq import RabbitMQHandler

from ltc_client.api import Api

RABBIT_DEFAULT_PRE_FETCH_COUNT = 1
RABBIT_FIRST_WAIT_BEFORE_RERTY_SECS = 0.5
RABBIT_MAX_WAIT_BEFORE_RERTY_SECS = 64
LOGGING_LEVEL = logging.INFO


### Configure Logging
logger = logging.getLogger()  # get the root logger?
logger.setLevel(LOGGING_LEVEL)
tld = threading.local()
tld.job_id = "NoJobId"


class HostnameFilter(logging.Filter):
    """Used for logging the hostname
    https://stackoverflow.com/a/55584223/20882432
    """

    hostname = platform.node()

    def filter(self, record):
        record.hostname = HostnameFilter.hostname
        return True


class DefaultIdLogFilter(logging.Filter):
    """Used for logging the job id"""

    def filter(self, record):
        if not hasattr(tld, "job_id"):
            record.id = "NoJobId"
        else:
            record.id = tld.job_id
        return True


def addLoggingLevel(levelName: str, levelNum: int, methodName: str = None) -> None:
    """
    Comprehensively adds a new logging level to the `logging` module and the
    currently configured logging class.

    `levelName` becomes an attribute of the `logging` module with the value
    `levelNum`. `methodName` becomes a convenience method for both `logging`
    itself and the class returned by `logging.getLoggerClass()` (usually just
    `logging.Logger`). If `methodName` is not specified, `levelName.lower()` is
    used.

    To avoid accidental clobberings of existing attributes, this method will
    raise an `AttributeError` if the level name is already an attribute of the
    `logging` module or if the method name is already present

    Example
    -------
    >>> addLoggingLevel('TRACE', logging.DEBUG - 5)
    >>> logging.getLogger(__name__).setLevel("TRACE")
    >>> logging.getLogger(__name__).trace('that worked')
    >>> logging.trace('so did this')
    >>> logging.TRACE
    5

    """
    if not methodName:
        methodName = levelName.lower()

    if hasattr(logging, levelName):
        raise AttributeError("{} already defined in logging module".format(levelName))
    if hasattr(logging, methodName):
        raise AttributeError("{} already defined in logging module".format(methodName))
    if hasattr(logging.getLoggerClass(), methodName):
        raise AttributeError("{} already defined in logger class".format(methodName))

    # raise a value error if the level number is not an integer
    if not isinstance(levelNum, int):
        raise ValueError("levelNum must be an integer")

    # This method was inspired by the answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def logForLevel(self, message: str, *args, **kwargs) -> None:
        if self.isEnabledFor(levelNum):
            self._log(levelNum, message, args, **kwargs)

    def logToRoot(message: str, *args, **kwargs) -> None:
        logging.log(levelNum, message, *args, **kwargs)

    logging.addLevelName(levelNum, levelName)
    setattr(logging, levelName, levelNum)
    setattr(logging.getLoggerClass(), methodName, logForLevel)
    setattr(logging, methodName, logToRoot)


addLoggingLevel("PROGRESS", logging.INFO + 2)

stream_handler = logging.StreamHandler(stream=sys.stdout)
stream_handler.addFilter(HostnameFilter())
stream_handler.addFilter(DefaultIdLogFilter())
stream_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s - %(id)s - %(levelname)s - %(hostname)s - %(filename)s->%(funcName)s() - %(message)s"
    )
)

logger.addHandler(stream_handler)


class StandardWorker:
    """
    The standard TAE worker class
    """

    def __init__(
        self,
        node_id,
        worker_name,
        queue_host,
        queue_port,
        queue_user,
        queue_password,
        queue_use_ssl,
        queue_exchange,
        queue_prefetch_count=RABBIT_DEFAULT_PRE_FETCH_COUNT,
        x_priority=0,
        projects_path=os.getenv("PROJECTS_PATH"),
    ):
        self._threads = []
        self._node_id = node_id
        self._worker_name = worker_name
        self._exchange = queue_exchange
        self._x_priority = x_priority
        self._projects_path = projects_path
        self._send_log_as_artifact = True

        if queue_use_ssl:
            ssl_options = pika.SSLOptions(context=ssl.create_default_context())
        else:
            ssl_options = None

        self._connection = _rabbitmq_connect(
            node_id,
            worker_name,
            queue_host,
            queue_port,
            queue_user,
            queue_password,
            ssl_options,
        )

        self._channel = self._connection.channel()
        self._channel.basic_qos(prefetch_count=queue_prefetch_count, global_qos=False)
        self._channel.exchange_declare(
            exchange=queue_exchange, exchange_type="topic", durable=True
        )

        rabbit_handler = RabbitMQHandler(
            host=queue_host,
            port=queue_port,
            username=queue_user,
            password=queue_password,
            connection_params={"ssl_options": ssl_options},
            exchange="amq.topic",
            declare_exchange=True,
            routing_key_formatter=lambda r: (
                "{jobid}.{worker_name}.{type}.{level}".format(
                    jobid=r.id,
                    worker_name=worker_name,
                    type="python",
                    level=r.levelname.lower(),
                )
            ),
        )

        rabbit_handler.addFilter(HostnameFilter())
        rabbit_handler.addFilter(DefaultIdLogFilter())
        rabbit_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(levelname)s  - %(message)s", datefmt="%H:%M:%S"
            )
        )

        logger.addHandler(rabbit_handler)

    def bind(self, queue, routing_key, func):
        ch = self._channel

        ch.queue_declare(
            queue=queue,
            durable=True,
            exclusive=False,
        )
        ch.queue_bind(exchange=self._exchange, queue=queue, routing_key=routing_key)

        # If func was provided, register the callback
        if func is not None:
            ch.basic_consume(
                queue=queue,
                on_message_callback=functools.partial(
                    self._threaded_callback,
                    args=(func, self._connection, ch, self._threads),
                ),
                arguments={"x-priority": self._x_priority},
            )

        logger.info(f"Declare::Bind, Q::RK, {queue}::{routing_key}")

    def start(self):
        try:
            logger.info("Starting to consume messages")
            self._channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Stopping consuming ...")
            self._channel.stop_consuming()
            logger.info("Stopped consuming messages")

        # Wait for all to complete
        for thread in self._threads:
            thread.join()

        # Close connection
        self._connection.close()

    def queue_message(self, routing_key, body):
        _rabbitmq_queue_message(self._channel, self._exchange, routing_key, body)

    def _threaded_callback(self, ch, method_frame, _header_frame, body, args):
        (func, conn, ch, thrds) = args
        delivery_tag = method_frame.delivery_tag
        t = threading.Thread(
            target=self._do_threaded_callback,
            args=(conn, ch, delivery_tag, func, body),
        )
        t.start()
        thrds.append(t)
        logger.info(
            "Thread count: %i of which %i active", len(thrds), threading.active_count()
        )

    def _do_threaded_callback(self, conn, ch, delivery_tag, func, body):

        thread_id = threading.get_ident()
        payload = json.loads(body.decode())
        tld.job_id = payload["id"]

        api_root = os.getenv("API_ROOT_URL")
        api_key = payload.get("apikey", None)

        can_send_log_as_artifact = self._send_log_as_artifact and api_root and api_key

        job_log_directory = f"{self._projects_path}/jobs/{tld.job_id}"
        job_log_filename = f"{job_log_directory}/{self._worker_name}.log"

        if can_send_log_as_artifact:

            # Emsure the job directory exists
            Path(job_log_directory).mkdir(parents=True, exist_ok=True)

            # Set up the log file handler for this job
            file_handler = logging.FileHandler(filename=job_log_filename, mode="a")
            file_handler.addFilter(HostnameFilter())
            file_handler.addFilter(DefaultIdLogFilter())
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(id)s - %(levelname)s - %(hostname)s - %(filename)s->%(funcName)s() - %(message)s"
                )
            )

            logger.addHandler(file_handler)

        logger.info(
            "Thread id: %s Delivery tag: %s Message body: %s Job id: %s",
            thread_id,
            delivery_tag,
            body,
            tld.job_id,
        )

        next_routing_key, new_body = func(body)
        if new_body is not None:
            body = new_body
        if next_routing_key is not None:
            logger.info(f"next routing key: {next_routing_key}")
            cbq = functools.partial(self.queue_message, next_routing_key, body)
            conn.add_callback_threadsafe(cbq)

        cb = functools.partial(_rabbitmq_ack_message, ch, delivery_tag)
        conn.add_callback_threadsafe(cb)

        if can_send_log_as_artifact:
            logger.removeHandler(file_handler)
            try:
                logger.info("Creating artifact from job log")
                api = Api(root_url=api_root, api_key=api_key, node_id=self._node_id)
                api.create_job_artifact_from_file(
                    tld.job_id, f"{self._worker_name}_log", job_log_filename
                )
            except Exception as e:
                logger.error(f"Failed to create artifact from job log: {e}")


def _rabbitmq_connect(node_id, worker_name, host, port, user, password, ssl_options):
    client_properties = {
        "connection_name": f"{node_id}-{worker_name}-{platform.node()}"
    }

    connection_params = pika.ConnectionParameters(
        host=host,
        port=port,
        credentials=pika.PlainCredentials(user, password),
        client_properties=client_properties,
        heartbeat=10,
        ssl_options=ssl_options,
    )

    sleepTime = RABBIT_FIRST_WAIT_BEFORE_RERTY_SECS
    connected = False

    while not connected:
        try:
            logger.info("Trying to connect to the rabbitmq server")
            connection = pika.BlockingConnection(connection_params)

        except pika.exceptions.AMQPConnectionError as err:
            sleepTime *= 2
            if sleepTime >= RABBIT_MAX_WAIT_BEFORE_RERTY_SECS:
                logger.error(f"Failed to connect to the rabbitmq after {sleepTime} s")
                raise err
            else:
                logger.warning(
                    f"Failed to connect to the rabbitmq, retry in {sleepTime} s"
                )
                time.sleep(sleepTime)
        except gaierror as err:
            sleepTime *= 2
            if sleepTime >= RABBIT_MAX_WAIT_BEFORE_RERTY_SECS:
                logger.error(f"Failed to connect to the rabbitmq after {sleepTime} s")
                raise err
            else:
                logger.warning(
                    f"Failed to connect to the rabbitmq, [{err}] retry in {sleepTime} s"
                )
                time.sleep(sleepTime)
        except Exception as err:
            logger.error(f"Failed to connect to the rabbitmq: {err}")
            raise err

        else:
            connected = True

    return connection


def _rabbitmq_ack_message(ch, delivery_tag):
    """Note that `ch` must be the same pika channel instance via which
    the message being ACKed was retrieved (AMQP protocol constraint).
    """
    if ch.is_open:
        logger.info("Acknowledging message %s", delivery_tag)
        ch.basic_ack(delivery_tag)
    else:
        # Channel is already closed, so we can't ACK this message;
        # log and/or do something that makes sense for your app in this case.
        logger.error("Channel is closed, cannot ack message")


def _rabbitmq_queue_message(ch, exchange, routing_key, body):
    if ch.is_open:
        logger.info(f"Sending {body} to {routing_key}")
        ch.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            ),
        )
    else:
        logger.error("Channel is closed, cannot queue message")
