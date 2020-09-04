import json
import logging

from asyncinit import asyncinit

from pykurento import media
from pykurento.media import MediaPipeline


logger = logging.getLogger(__name__)

@asyncinit
class UserSession:
    async def __init__(self, name: str, room_name: str, session, pipeline: MediaPipeline):
        self.name = name
        self.session = session

        self.pipeline = pipeline

        self.room_name = room_name

        self.__outgoing_media = await media.WebRtcEndpoint(pipeline)
        self.__incoming_media = {}


    async def create(self):
        await self.__outgoing_media.on_ice_candidate_found_event(self.ice_candidate_found_event, session=self.session,
                                                                     name=self.name)

    @staticmethod
    async def ice_candidate_found_event(*args, **kwargs):
        res = dict(id="iceCandidate", name=args[3], candidate=args[0]['data']['candidate'])
        await args[2].write_message(json.dumps(res))

    def get_outgoing_web_rtc_peer(self) -> media.WebRtcEndpoint:
        return self.__outgoing_media

    def get_name(self) -> str:
        return self.name

    def get_session(self):
        return self.session

    def get_room_name(self) -> str:
        return self.room_name

    async def receive_video_from(self, sender: 'UserSession', sdp_offer: str):
        logger.info("USER {name}: connecting with {sender} in room {room_name}".format(name=self.name,
                                                                                       sender=sender.get_name(),
                                                                                       room_name=self.room_name))

        logger.debug("USER {name}: SdpOffer for {sender} is {sdp}".format(name=self.name,
                                                                          sender=sender.get_name(), sdp=sdp_offer))

        en = await self.get_endpoint_for_user(sender)
        ip_sdp_answer = await en.process_offer(sdp_offer)

        sc_params = dict(
            id="receiveVideoAnswer",
            name=sender.get_name(),
            sdpAnswer=ip_sdp_answer[1]
        )

        logger.debug("USER {name}: SdpAnswer for {sender} is {sdp}".format(name=self.name,
                                                                           sender=sender.get_name(),
                                                                           sdp=ip_sdp_answer))

        await self.send_message(sc_params)
        logger.debug("gather candidates")
        en = await self.get_endpoint_for_user(sender)
        await en.gather_candidates()

    async def get_endpoint_for_user(self, sender: 'UserSession'):
        if sender.get_name() == self.name:
            logger.debug("PARTICIPANT {}: configuring loopback".format(self.name))
            return self.__outgoing_media

        logger.debug(
            "PARTICIPANT {name}: receiving video from {sender}".format(name=self.name, sender=sender.get_name()))

        incoming = self.__incoming_media.get(sender.get_name())
        if incoming is None:
            logger.debug("PARTICIPANT {name}: creating new incoming endpoint for {sender}".format(name=self.name,
                                                                                                  sender=sender.get_name()))

            incoming = await media.WebRtcEndpoint(parent=self.pipeline)

            await incoming.on_ice_candidate_found_event(self.ice_candidate_found_event, session=self.session,
                                                      name=sender.get_name())
            self.__incoming_media.update({
                sender.get_name(): incoming
            })

        logger.debug("PARTICIPANT {name}: obtained endpoint for {sender}".format(name=self.name,
                                                                                 sender=sender.get_name()))
        await sender.get_outgoing_web_rtc_peer().connect(incoming)

        return incoming

    async def cancel_video_from(self, sender_name: str):
        logger.debug("PARTICIPANT {room_name}: Canceling video reception from {sender}".format(room_name=self.name,
                                                                                               sender=sender_name))
        incoming = self.__incoming_media.__delitem__(sender_name)
        logger.debug \
            ("PARTICIPANT {room_name}: Removing endpoint for {sender}".format(room_name=self.name, sender=sender_name))
        await incoming.release()

    async def close(self):
        logger.debug("PARTICIPANT {name}: Releasing resources".format(name=self.name))
        for remote_participant_name in self.__incoming_media.keys():
            logger.debug("PARTICIPANT {name}: Released incoming EP for {remote_participant}".format(
                name=self.name, remote_participant=remote_participant_name))
            ep = self.__incoming_media.get(remote_participant_name)
            await ep.release()
        await self.__outgoing_media.release()

    async def send_message(self, message: dict):
        logger.debug("USER {name}: Sending message {message}".format(name=self.name, message=message))
        await self.session.write_message(json.dumps(message))

    async def add_candidate(self, candidate, name:str):
        if self.name == name:
            await self.__outgoing_media.add_ice_candidate(candidate)
        else:
            web_rtc:media.WebRtcEndpoint =self.__incoming_media.get(name)
            if web_rtc is not None:
                await web_rtc.add_ice_candidate(candidate)


    def __eq__(self, other):
        if isinstance(other, UserSession):
            return self.name == other.name and self.room_name == other.room_name
        return False
