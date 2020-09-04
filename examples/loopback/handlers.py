from abc import ABC

import tornado.web
from pykurento import media, KurentoClient

from tornado import websocket
import json

class LoopbackHandler(tornado.web.RequestHandler):

  async def get(self):
    await self.render("loopback.html")


class LoopbackWebSocketHandler(tornado.websocket.WebSocketHandler, ABC):
    users = set()
    session_id = None
    sessions = {}

    candidatesQueue = {}

    # kurentoClient = kurento

    def open(self):
        print("open")

        self.users.add(self)

    async def broadcast_message(self, msg=None, ignore_sender=True):
        for user in self.users:
            await user.write_message(msg)

    # called when message receive from socket
    async def on_message(self, message):

        pack = json.loads(message)

        _id = pack["id"]
        if _id == "start":
            sdp_offer = pack["sdpOffer"]
            pipeline = await self.get_kurento_client().create_pipeline()
            wrtc = await media.WebRtcEndpoint(parent=pipeline)
            await wrtc.on_ice_candidate_found_event(self.ice_candidate_found_event, session=self,
                                         name='javad')
            # face = media.FaceOverlayFilter(pipeline)
            # face.set_overlayed_image(
            #     "https://github.com/minervaproject/pykurento/blob/master/examples/static/img/rainbowpox.png",
            #     0, 0,
            #     1, 1)

            # low_res = media.GStreamerFilter(parent=pipeline,
            #                                 command="capsfilter caps=video/x-raw,width=320,height=240",
            #                                 filterType="VIDEO",
            #                                 properties={"command": "capsfilter caps=video/x-raw,width=320,height=240"})

            # connect webrtc source to sink which means loopback source stream to client
            await wrtc.connect(wrtc)

            self.session_id = pipeline.parent.transport.session_id

            self.sessions[self.session_id] = {
                'pipeline': pipeline,
                'webRtcEndpoint': wrtc
            }

            #wrtc.on_media_session_started_event(self.on_event)
            #wrtc.on_media_session_terminated_event(self.on_event)

            sdp_answer = await wrtc.process_offer(sdp_offer)

            # wrtc.connect(face)
            # face.connect(wrtc)


            # low_res.connect(wrtc)

            res = dict(id="startResponse", sdpAnswer=str(sdp_answer[1]))
            await self.broadcast_message(json.dumps(res))



            # get ice from remote
            await wrtc.gather_candidates()



            # setup recording
            # recorder = media.RecorderEndpoint(pipeline, uri="file:///tmp/test.webm")
            # wrtc.connect(recorder)
            # recorder.record()

            # plain old loopback
            # wrtc.connect(wrtc)

            # fun face overlay
            # face = media.FaceOverlayFilter(pipeline)
            # face.set_overlayed_image(
            #     "https://github.com/minervaproject/pykurento/blob/master/examples/static/img/rainbowpox.png",
            #     0, 0,
            #     1, 1)
            # wrtc.connect(face)
            # face.connect(wrtc)

        elif _id == "onIceCandidate":
            # add ice candidate

            if (pack.get('candidate', {'candidate': ''}).get('candidate')):
                await self.sessions[self.session_id]['webRtcEndpoint'].add_ice_candidate(pack['candidate'])

            # self.sessions[self.session_id]['webRtcEndpoint'].ice_candidate_found(self.ice_candidate_found_event)

        elif _id == "stop":
            await self.sessions[self.session_id]['webRtcEndpoint'].release()

        else:
            await self.broadcast_message(json.dumps({
                id: 'error',
                message: 'Invalid message ' + 'message'
            }))
            # errr

    def on_close(self):
        print("close")
        self.users.remove(self)

    def check_origin(self, origin):

        return True

    # def on_event(self, *args, **kwargs):
    #     print("received event!")
    #
    #     print(args)
    #     print(kwargs)

    async def ice_candidate_found_event(self, *args, **kwargs):
        res = dict(id="iceCandidate", candidate=args[0]['data']['candidate'])
        await args[2].broadcast_message(json.dumps(res))

    def get_kurento_client(self):
        if self.application.kurento.get_transport().connection.open:
            return self.application.kurento
        else:
            return KurentoClient(url="wss://jitsimk.ir/kurento")



