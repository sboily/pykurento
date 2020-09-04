#!/usr/bin/env python

import os
import sys
import logging
import signal
from abc import ABC

import tornado.ioloop
import tornado.web

import loopback.handlers
import rooms.handlers
import multires.handlers
import tornado.httpserver

from tornado.platform.asyncio import AsyncIOMainLoop
import asyncio
from pykurento import KurentoClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# ignore websockets log
requests_logger = logging.getLogger('websockets')
requests_logger.setLevel(logging.ERROR)

handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
logger.addHandler(handler)
requests_logger.addHandler(handler)


class IndexHandler(tornado.web.RequestHandler, ABC):
    async def get(self):
        await self.render("index.html")


if __name__ == "__main__":
    aio = AsyncIOMainLoop()
    aio.install()
    loop = asyncio.get_event_loop()

    application = tornado.web.Application([
        (r"/", IndexHandler),
        (r"/loopback/websocket", loopback.handlers.LoopbackWebSocketHandler),
        (r"/groupcall", rooms.handlers.GroupCallWebSocketHandler),
        (r"/loopback", loopback.handlers.LoopbackHandler),
        (r"/multires", multires.handlers.MultiResHandler),
        (r"/room", rooms.handlers.RoomIndexHandler),
        # (r"/room/(?P<room_id>\d*)", rooms.handlers.RoomHandler),
        # (r"/room/(?P<room_id>[^/]*)/subscribe/(?P<from_participant_id>[^/]*)/(?P<to_participant_id>[^/]*)",
        #  rooms.handlers.SubscribeToParticipantHandler),
        (r'/static/(.*)', tornado.web.StaticFileHandler, {'path': os.path.join(os.path.dirname(__file__), "static")}),
    ],
        static_path=os.path.join(os.path.dirname(__file__), "static"),
        template_path=os.path.join(os.path.dirname(__file__), "views"),
        debug=True)

    logging.basicConfig(level=logging.DEBUG)

    kurento = KurentoClient(url="wss://jitsimk.ir/kurento")

    # Start connection and get client connection protocol
    connection = loop.run_until_complete(kurento.get_transport().connect())

    setattr(application, "kurento", kurento)

    http_server = tornado.httpserver.HTTPServer(application, ssl_options={
        "certfile": os.path.join(os.path.dirname(__file__), "server.crt"),
        "keyfile": os.path.join(os.path.dirname(__file__), "server.key"),
    })

    http_server.listen(8080)
    http_server.start()

    # port = int(os.environ.get("PORT", 8080))
    # application.listen(port)
    # print("WebServer now listening on port %d" % port)
    # io_loop = tornado.ioloop.IOLoop.instance()
    # signal.signal(signal.SIGINT, lambda sig, frame: io_loop.stop())
    # io_loop.start()

    # concurrent

    try:
        tasks = [
            asyncio.ensure_future(kurento.get_transport().receive_message()),
            asyncio.ensure_future(kurento.get_transport().process_messages()),
        ]

        asyncio.gather(*tasks)

        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        print("Closing Loop")
        loop.close()
