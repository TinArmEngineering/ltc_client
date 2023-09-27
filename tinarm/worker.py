import functools
import logging
import pika
import platform
import ssl
import threading
import time


logging.basicConfig(
    format="%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class StandardWorker:
    """
    The standard TAE worker class
    """

    def __init__(
        self,
        node_name,
        worker_name,
        queue_host,
        queue_port,
        queue_user,
        queue_password,
        queue_use_ssl,
        queue_exchange,
    ):
        self._threads = []
        self._node_name = node_name
        self._exchange = queue_exchange

        self._connection = _rabbitmq_connect(
            node_name,
            worker_name,
            queue_host,
            queue_port,
            queue_user,
            queue_password,
            queue_use_ssl,
        )

        self._channel = self._connection.channel()
        self._channel.basic_qos(prefetch_count=1)
        self._channel.exchange_declare(
            exchange=queue_exchange, exchange_type="topic", durable=True
        )

    def bind(self, queue, routing_key, func):
        if self._node_name is not None:
            queue = f"{self._node_name}.{queue}"
            routing_key = f"{self._node_name}.{routing_key}"

        ch = self._channel

        ch.queue_declare(
            queue=queue,
            durable=True,
            exclusive=False,
        )
        ch.queue_bind(exchange=self._exchange, queue=queue, routing_key=routing_key)
        ch.basic_consume(
            queue=queue,
            on_message_callback=functools.partial(
                _threaded_callback, args=(func, self._connection, ch, self._threads)
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


def _rabbitmq_connect(node_name, worker_name, host, port, user, password, use_ssl):
    client_properties = {
        "connection_name": f"{worker_name}-{node_name}-{platform.node()}"
    }

    if use_ssl:
        ssl_options = pika.SSLOptions(context=ssl.create_default_context())
    else:
        ssl_options = None

    connection_params = pika.ConnectionParameters(
        host=host,
        port=port,
        credentials=pika.PlainCredentials(user, password),
        client_properties=client_properties,
        heartbeat=10,
        ssl_options=ssl_options,
    )

    sleepTime = 0.5
    connected = False

    while not connected:
        try:
            logger.info("Trying to connect to the rabbitmq server")
            connection = pika.BlockingConnection(connection_params)

        except pika.exceptions.AMQPConnectionError as err:
            sleepTime *= 2
            if sleepTime >= 32:
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


def _threaded_callback(ch, method_frame, _header_frame, body, args):
    (func, conn, ch, thrds) = args
    delivery_tag = method_frame.delivery_tag
    t = threading.Thread(
        target=_do_threaded_callback,
        args=(conn, ch, delivery_tag, func, body),
    )
    t.start()
    thrds.append(t)


def _do_threaded_callback(conn, ch, delivery_tag, func, body):
    thread_id = threading.get_ident()
    logger.info(
        "Thread id: %s Delivery tag: %s Message body: %s", thread_id, delivery_tag, body
    )

    func(body)

    cb = functools.partial(_rabbitmq_ack_message, ch, delivery_tag)
    conn.add_callback_threadsafe(cb)


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
