import functools
import json
import logging
import pika
import platform
import ssl
import sys
import threading
import time

from python_logging_rabbitmq import RabbitMQHandler


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
        if not hasattr(tld, "jobid"):
            record.id = "NoJobId"
        else:
            record.id = tld.job_id
        return True
    

stream_handler = logging.StreamHandler(stream=sys.stdout)
stream_handler.addFilter(HostnameFilter())
stream_handler.addFilter(DefaultIdLogFilter())
stream_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s - %(id)s - %(levelname)s - %(hostname)s - %(filename)s->%(funcName)s() - %(message)s"
    )
)

# file_handler = logging.FileHandler(filename="mesher.log", mode="a")
# file_handler.addFilter(HostnameFilter())
# file_handler.addFilter(DefaultIdLogFilter())
# file_handler.setFormatter(
#     logging.Formatter(
#         "%(asctime)s - %(id)s - %(levelname)s - %(hostname)s - %(funcName)s - %(message)s"
#     )
# )

logger.addHandler(stream_handler)
# logger.addHandler(file_handler)


class StandardWorker:
    """
    The standard TAE worker class
    """

    def __init__(
        self,
        worker_name,
        queue_host,
        queue_port,
        queue_user,
        queue_password,
        queue_use_ssl,
        queue_exchange,
        queue_prefetch_count=RABBIT_DEFAULT_PRE_FETCH_COUNT,
    ):
        self._threads = []
        self._exchange = queue_exchange

        if queue_use_ssl:
            ssl_options = pika.SSLOptions(context=ssl.create_default_context())
        else:
            ssl_options = None

        self._connection = _rabbitmq_connect(
            worker_name,
            queue_host,
            queue_port,
            queue_user,
            queue_password,
            ssl_options,
        )

        self._channel = self._connection.channel()
        self._channel.basic_qos(prefetch_count=queue_prefetch_count, global_qos=True)
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
                "{jobid}.mesher.{type}.{level}".format(
                    jobid=r.id, type="python", level=r.levelname.lower()
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
        logger.info(
            "Thread id: %s Delivery tag: %s Message body: %s",
            thread_id,
            delivery_tag,
            body,
        )

        logger.info(f"checking body for a job id")
        payload = json.loads(body.decode())
        tld.job_id = payload["id"]

        logger.info(f"setting this thread: {thread_id} job id to: {tld.job_id}")

        next_routing_key = func(body)

        if next_routing_key is not None:
            logger.info(f"next routing key: {next_routing_key}")
            cbq = functools.partial(self.queue_message, next_routing_key, body)
            conn.add_callback_threadsafe(cbq)

        cb = functools.partial(_rabbitmq_ack_message, ch, delivery_tag)
        conn.add_callback_threadsafe(cb)


def _rabbitmq_connect(worker_name, host, port, user, password, ssl_options):
    client_properties = {"connection_name": f"{worker_name}-{platform.node()}"}

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
        logger.info(f"Sending to {body} to {routing_key}")
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
