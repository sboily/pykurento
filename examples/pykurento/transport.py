import asyncio

import websockets
import json
import time
import threading
import logging
import os
import sys

from queue import Queue
from collections import defaultdict

logger = logging.getLogger(__name__)


class TimeoutException(Exception):
    pass


class Timeout(object):
    def __init__(self, seconds=1, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message
        self.timer = None

    def handle_timeout(self):
        raise TimeoutException(self.error_message)

    def __enter__(self):
        self.timer = threading.Timer(self.seconds, self.handle_timeout)

    def __exit__(self, type, value, traceback):
        if self.timer:
            self.timer.cancel()


class KurentoTransportException(Exception):
    def __init__(self, message, response=None):
        super(KurentoTransportException, self).__init__(message)
        if response is None:
            response = {}
        self.response = response
        self.message = message

    def __str__(self):
        return "%s - %s" % (str(self.message), json.dumps(self.response))


class KurentoTransport(object):
    def __init__(self, url, **kwargs):
        logger.debug("Creating new KurentoTransport with url: %s" % url)
        self.url = url
        self.current_id = 0
        self.session_id = None
        self.pending_operations = {}
        self.subscriptions = {}
        self.subscriptions_by_event_type = defaultdict(list)
        self.stopped = False

        # self.event_loop_a = asyncio.new_event_loop()

        # self.thread = threading.Thread(target=self._callback_a)
        # self.thread.daemon = True
        # self.thread.start()

        # queue for messages received from Kurento; this is to decouple
        # message handing from the pykurento transport message receiving
        # thread (and avoid potential deadlock);
        self.kms_queue = asyncio.Queue(kwargs.get('kms_queue_size', 64))

        # self.event_loop_b = asyncio.new_event_loop()
        # self.messaging_thread = threading.Thread(target=self._callback_b)
        # self.messaging_thread.daemon = True
        # self.messaging_thread.start()

    # def _callback_a(self):
    #     asyncio.set_event_loop(self.event_loop_a)
    #     asyncio.get_event_loop().call_soon_threadsafe(lambda: self._run_thread())
    #     self.event_loop_a.run_forever()
    #
    # def _callback_b(self):
    #     asyncio.set_event_loop(self.event_loop_b)
    #     asyncio.get_event_loop().call_soon_threadsafe(lambda: self._process_messages())
    #     self.event_loop_b.run_forever()

    async def connect(self):
        '''
            Connecting to webSocket server

            websockets.client.connect returns a WebSocketClientProtocol, which is used to send and receive messages
        '''
        self.connection = await websockets.client.connect(self.url)
        if self.connection.open:
            print('Connection stablished. Client correcly connected')
            # send ping
            # await self.sendMessage('Hey server, this is webSocket client')
            return self.connection

    async def a_send_message(self, message):
        '''
            Sending message to webSocket server
        '''
        await self.connection.send(message)

    def __del__(self):
        logger.debug("Destroying KurentoTransport with url: %s" % self.url)
        self.stopped = True
        # self.connection.close()

    async def _check_connection(self):
        if hasattr(self, 'connection'):
            if self.connection.open:
                return

        else:
            logger.info("Kurento Client websocket is not connected, reconnecting")
            try:
                with Timeout(seconds=5):
                    self.connection = await websockets.client.connect(self.url)
                    logger.info("Kurento Client websocket connected!")
            except TimeoutException:
                # modifying this exception so we can differentiate in the receiver thread
                raise KurentoTransportException("Timeout: Kurento Client websocket connection timed out")

    async def heartbeat(self, connection):
        '''
        Sending heartbeat to server every 5 seconds
        Ping - pong messages to verify connection is alive
        '''
        while True:
            try:
                await connection.send('ping')
                interval = 60 * 4
                await asyncio.sleep(interval)
            except websockets.exceptions.ConnectionClosed:
                print('Connection with server closed')
                break

    async def receive_message(self):
        while not self.stopped:
            try:
                await self._check_connection()
                with Timeout(seconds=1):
                    msg = await self.connection.recv()
                    resp = json.loads(msg)
                    if 'result' in resp and 'sessionId' in resp['result']:
                        self.session_id = resp['result']['sessionId']
                        self.pending_operations["%d_response" % resp["id"]] = resp
                    else:
                        self.kms_queue.put_nowait(msg)

            except TimeoutException:
                logger.debug("WS Receiver Timeout")
            except Exception as ex:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]

                logger.error("WS Receiver Thread %s: %s in file %s:%s" %
                             (exc_type, str(ex), fname, exc_tb.tb_lineno))

    async def process_messages(self):
        '''Process messages asynchroneously from receiver thread'''
        while not self.stopped:
            try:
                item = await self.kms_queue.get()
                await self._on_message(item)
                self.kms_queue.task_done()

            except Exception as ex:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                logger.error("KMS Messaging Thread %s: %s in file %s:%s" %
                             (exc_type, str(ex), fname, exc_tb.tb_lineno))

    def _next_id(self):
        self.current_id += 1
        return self.current_id

    async def _on_message(self, message):
        resp = json.loads(message)
        logger.debug("received message: %s" % message)

        if 'method' in resp:
            if (resp['method'] == 'onEvent'
                    and 'params' in resp
                    and 'value' in resp['params']
                    and 'data' in resp['params']['value']
                    and 'type' in resp['params']['value']['data']
                    and resp['params']['value']['data']['type'] in self.subscriptions_by_event_type.keys()):

                event_source = resp['params']['value']['data']['source']
                event_type = resp['params']['value']['data']['type']
                event_subscriptions = self.subscriptions_by_event_type[event_type]

                for sub_id in event_subscriptions:
                    _, fn, name, session = self.subscriptions[sub_id]
                    self.session_id = resp['params']['sessionId'] if 'sessionId' in resp['params'] else self.session_id
                    await fn(resp["params"]["value"], name, session)

    async def _rpc(self, rpc_type, **args):
        if self.session_id:
            args["sessionId"] = self.session_id

        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": rpc_type,
            "params": args
        }
        req_key = "%d_request" % request["id"]
        resp_key = "%d_response" % request["id"]

        self.pending_operations[req_key] = request

        await self._check_connection()

        logger.debug("sending message:  %s" % json.dumps(request))
        await self.a_send_message(json.dumps(request))

        while resp_key not in self.pending_operations:
            await asyncio.sleep(0.005)

        resp = self.pending_operations[resp_key]

        del self.pending_operations[req_key]
        del self.pending_operations[resp_key]

        if 'error' in resp:
            raise KurentoTransportException(resp['error']['message'] if 'message' in resp['error'] else 'Unknown Error',
                                            resp)
        elif 'result' in resp:
            assert 'sessionId' in resp['result'], 'KMS should return sessionId as part of the response'

            session_id = resp['result']['sessionId']
            value = resp['result'].get('value')
            result = (session_id, value,) if value else session_id

            return result
        else:
            return None  # just to be explicit

    async def create(self, obj_type, **args):
        return await self._rpc("create", type=obj_type, constructorParams=args)

    async def invoke(self, object_id, operation, **args):
        return await self._rpc("invoke", object=object_id, operation=operation, operationParams=args)

    async def subscribe(self, object_id, event_type, fn, name, session):
        session_id, subscription_id =  await self._rpc("subscribe", object=object_id, type=event_type)
        self.subscriptions[subscription_id] = (event_type, fn, name, session)
        self.subscriptions_by_event_type[event_type].append(subscription_id)
        return session_id, subscription_id

    async def unsubscribe(self, object_id, subscription_id):
        event_type, _ = self.subscriptions[subscription_id]
        event_subscriptions = self.subscriptions_by_event_type[event_type]
        event_subscriptions.remove(subscription_id)

        del self.subscriptions[subscription_id]
        return await self._rpc("unsubscribe", object=object_id, subscription=subscription_id)

    async def release(self, object_id):
        return await self._rpc("release", object=object_id)
