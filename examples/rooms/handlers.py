import json
import tornado.web
import logging

from abc import ABC
from tornado import websocket
from pykurento import KurentoClient
from rooms.room_manager import RoomManager
from rooms.user_registry import UserRegistry
from rooms.user_session import UserSession

logger = logging.getLogger(__name__)


class RoomIndexHandler(tornado.web.RequestHandler):
    async def get(self):
        await self.render("group_call.html")


class GroupCallWebSocketHandler(tornado.websocket.WebSocketHandler, ABC):

    room_manager = RoomManager()
    registry = UserRegistry()

    def open(self):
        print("open")

    # called when message receive from socket
    async def on_message(self, message):
        # parse json to python object
        pack = json.loads(message)

        user:UserSession = self.registry.get_by_session(self)

        if user is not None:
            logger.debug("Incoming message from user '{name}': {message}".format(name=user.get_name(), message=pack))
        else:
            logger.debug("Incoming message from new user: {message}".format(message=pack))

        _id = pack["id"]

        if _id == "joinRoom":
            await self.join_room(pack, self)

        elif _id == "receiveVideoFrom":
            sender_name = pack['sender']
            sender = self.registry.get_by_name(sender_name)
            sdp_offer = pack['sdpOffer']
            await user.receive_video_from(sender, sdp_offer)

        elif _id == "leaveRoom":
            pass

        elif _id == "onIceCandidate":
            if user:
                # add ice candidate
                if pack.get('candidate', {'candidate': ''}).get('candidate'):
                    await user.add_candidate(pack['candidate'], pack.get('name'))

        else:
            # error
            logger.error("error")

    def on_close(self):
        print("close")


    def check_origin(self, origin):
        print(origin)
        return True

    async def ice_candidate_found_event(self, *args, **kwargs):
        print('ice found from server and send to client ', kwargs)
        res = dict(id="iceCandidate", name=kwargs['name'], candidate=args[0]['data']['candidate'])
        await kwargs['session'].write_message(json.dumps(res))

    def get_kurento_client(self):
        if self.application.kurento.get_transport().connection.open:
            return self.application.kurento
        else:
            return KurentoClient(url="wss://jitsimk.ir/kurento")

    async def join_room(self, params:dict, session:'GroupCallWebSocketHandler'):
        room_name = params['room']
        name = params['name']
        logger.info("PARTICIPANT {name}: trying to join room {room_name}".format(name=name, room_name=room_name))

        room = await self.room_manager.get_room(room_name, self.application.kurento)
        user = await room.join(name, session)
        self.registry.register(user)





