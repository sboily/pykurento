import logging

from pykurento import KurentoClient
from rooms.room import Room

logger = logging.getLogger(__name__)


class RoomManager:
    def __init__(self):

        self.__kurento_client = None

        self.__rooms = {}


    async def get_room(self, room_name: str, kurento):
        self.__kurento_client = kurento
        logger.debug("Searching for room {}".format(room_name))
        room = self.__rooms.get(room_name, None)

        if room is None:
            logger.debug("Room {} not existent. Will create now!".format(room_name))
            pipeline = await self.__kurento_client.create_pipeline()
            room = Room(room_name, pipeline)
            self.__rooms[room_name] = room

            logger.info("ROOM {room_name} has been created".format(room_name=room_name))

        logger.debug("Room {} found!".format(room_name))
        return room

    async def remove_room(self, room: 'Room'):
        self.__rooms.__delitem__(room.get_name())
        await room.close()
        logger.info("ROOM {room_name} removed and closed".format(room_name=room.get_name()))
