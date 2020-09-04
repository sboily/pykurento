import logging

from pykurento.media import MediaPipeline
from rooms.user_session import UserSession

logger = logging.getLogger(__name__)


class Room:
    def __init__(self, room_name: str, pipeline: MediaPipeline):
        self.__participants = {}
        self.__pipeline = pipeline
        self.__name = room_name


    def get_name(self):
        return self.__name

    async def shutdown(self):
        await self.close()

    async def join(self, user_name: str, session):
        logger.info("ROOM {room_name}: adding participant {name}".format(room_name=self.__name, name=user_name))

        participant = await UserSession(name=user_name, room_name=self.__name, session=session, pipeline=self.__pipeline)
        await participant.create()
        await self.join_room(participant)
        self.__participants.update({participant.get_name(): participant})
        await self.send_participant_names(participant)
        return participant

    def leave(self, user: UserSession):
        logger.info("PARTICIPANT {name}: Leaving room {room_name}".format(name=user.get_name(), room_name=self.__name))
        self.remove_participant(user.get_name())
        user.close()

    async def join_room(self, new_participant: UserSession):
        new_participant_msg = dict(
            id="newParticipantArrived",
            name=new_participant.get_name()
        )

        participant_list = []
        logger.debug("ROOM {room_name}: notifying other participants of new participant {name}".format(
            room_name=self.__name,
            name=new_participant.get_name()
        ))
        # خبر دادن به بقیه که یک نفر جدید اومد توی گروه
        for participant in self.__participants.values():
            try:
                await participant.send_message(new_participant_msg)
            except Exception as e:
                logger.debug("ROOM {room_name}: participant {name} could not be notified, {e}".format(
                    room_name=self.__name,
                    name=new_participant.get_name(),
                    e=e
                ))
            participant_list.append(participant.get_name())

        return participant_list

    def remove_participant(self, name: str):
        self.__participants.__delitem__(name)

        logger.debug("ROOM {room_name}: notify all users that {name} is leaving the room".format(
            room_name=self.__name,
            name=name
        ))

        unnotified_participants = []

        participant_left = dict(
            id='participantLeft',
            name=name
        )

        for participant in self.__participants.values():
            try:
                participant.cancel_video_from(name)
                participant.send_message(participant_left)
            except Exception as e:
                unnotified_participants.append(participant.get_name())

        if unnotified_participants:
            logger.debug("ROOM {room_name}: The users {users} could not be notified that {name} left the room".format(
                room_name=self.__name,
                users=unnotified_participants,
                name=name
            ))

    async def send_participant_names(self, user: UserSession):

        participants_array = []

        for participant in self.get_participants():
            if not (participant == user):
                participants_array.append(participant.get_name())

        existing_participants_msg = dict(
            id="existingParticipants",
            data=participants_array
        )

        logger.debug("PARTICIPANT {name}: sending a list of {length} participants".format(
            name=user.get_name(),
            length=len(participants_array)
        ))
        # خبر دادن به کاربر ک چه کسایی هستن توی این گروه
        await user.send_message(existing_participants_msg)

    def get_participants(self) -> list:
        return list(self.__participants.values())

    def get_participant(self, name: str) -> UserSession:
        return self.__participants.get(name)

    async def close(self):
        for user in self.__participants.values():
            try:
                await user.close()
            except Exception as e:
                logger.debug("ROOM {room_name}: Could not invoke close on participant {participant}".format(
                    room_name=self.__name,
                    participant=user.get_name()
                ))

        self.__participants.clear()

        await self.__pipeline.release()

        logger.debug("ROOM {room_name}: closed".format(room_name=self.__name))
