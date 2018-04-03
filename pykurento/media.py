import logging

from functools import wraps
from inspect import getcallargs

logger = logging.getLogger(__name__)

# This is the object graph as described at http://www.kurento.org/docs/5.0.3/mastering/kurento_API.html
# We dont mimic it precisely yet as its still being built out, not all abstractions are necessary
#                   MediaObject
# Hub               MediaElement                MediaPipeline
#          HubPort    Endpoint    Filter

def grab_session_id(f):
  '''Decorator to grab session id from kurento response'''

  @wraps(f)
  def decorator(*args, **kwargs):
    call_args = getcallargs(f, *args, **kwargs)

    result = f(*args, **kwargs)
    if isinstance(result, tuple):
      session_id, result = result

      if 'self' in call_args and not call_args['self'].session_id:
        call_args['self'].session_id = session_id

    return result
  return decorator


class MediaType(object):
  AUDIO = "AUDIO"
  VIDEO = "VIDEO"
  DATA = "DATA"

class MediaObject(object):
  def __init__(self, parent, **args):
    self.parent = parent
    self.options = args
    if 'id' in args:
      logger.debug("Creating existing %s with id=%s", self.__class__.__name__, args['id'])
      self.id = args['id']
      self.session_id = None
    else:
      logger.debug("Creating new %s", self.__class__.__name__)
      self.session_id, self.id = self.get_transport().create(self.__class__.__name__, **args)

  def get_transport(self):
    return self.parent.get_transport()

  def get_pipeline(self):
    return self.parent.get_pipeline()

  # todo: remove arguments that have a value of None to let optional params work seamlessly
  @grab_session_id
  def invoke(self, method, **args):
    return self.get_transport().invoke(self.id, method, **args)

  @grab_session_id
  def subscribe(self, event, fn):
    def _callback(value):
      fn(value, self)
    return self.get_transport().subscribe(self.id, event, _callback)

  @grab_session_id
  def unsubscribe(self, subscription_id):
    self.get_transport().unsubscribe(self.id, subscription_id)

  @grab_session_id
  def release(self):
    return self.get_transport().release(self.id)


class MediaPipeline(MediaObject):
  def get_pipeline(self):
    return self


class MediaElement(MediaObject):
  def __init__(self, parent, **args):
    args["mediaPipeline"] = parent.get_pipeline().id
    super(MediaElement, self).__init__(parent, **args)

  def connect(self, sink):
    return self.invoke("connect", sink=sink.id)

  def disconnect(self, sink):
    return self.invoke("disconnect", sink=sink.id)

  def set_audio_format(self, caps):
    return self.invoke("setAudioFormat", caps=caps)

  def set_video_format(self, caps):
    return self.invoke("setVideoFormat", caps=caps)

  def get_source_connections(self, media_type):
    return self.invoke("getSourceConnections", mediaType=media_type)

  def get_sink_connections(self, media_type):
    return self.invoke("getSinkConnections", mediaType=media_type)

# ENDPOINTS

class UriEndpoint(MediaElement):
  def get_uri(self):
    return self.invoke("getUri")

  def pause(self):
    return self.invoke("pause")

  def stop(self):
    return self.invoke("stop")


class PlayerEndpoint(UriEndpoint):
  def play(self):
    return self.invoke("play")

  def on_end_of_stream_event(self, fn):
    return self.subscribe("EndOfStream", fn)


class RecorderEndpoint(UriEndpoint):
  def record(self):
    return self.invoke("record")


class SessionEndpoint(MediaElement):
  def on_media_session_started_event(self, fn):
    return self.subscribe("MediaSessionStarted", fn)

  def on_media_session_terminated_event(self, fn):
    return self.subscribe("MediaSessionTerminated", fn)


class HttpEndpoint(SessionEndpoint):
  def get_url(self):
    return self.invoke("getUrl")


class HttpGetEndpoint(HttpEndpoint):
  pass


class HttpPostEndpoint(HttpEndpoint):
  def on_end_of_stream_event(self, fn):
    return self.subscribe("EndOfStream", fn)


class SdpEndpoint(SessionEndpoint):
  def generate_offer(self):
    return self.invoke("generateOffer")

  def process_offer(self, offer):
    return self.invoke("processOffer", offer=offer)

  def process_answer(self, answer):
    return self.invoke("processAnswer", answer=answer)

  def get_local_session_descriptor(self):
    return self.invoke("getLocalSessionDescriptor")

  def get_remote_session_descriptor(self):
    return self.invoke("getRemoteSessionDescriptor")

  def add_ice_candidate(self, ice_candidate_data):
      self.invoke("addIceCandidate", candidate=ice_candidate_data)

  def gather_candidates(self):
      self.invoke("gatherCandidates")

  def on_ice_component_state_change_event(self, fn):
    return self.subscribe("IceComponentStateChange", fn)

  def on_ice_candidate_found_event(self, fn):
    return self.subscribe("IceCandidateFound", fn)

  def on_ice_gathering_done_event(self, fn):
    return self.subscribe("IceGatheringDone", fn)

  def on_new_candidate_pair_selected_event(self, fn):
    return self.subscribe("NewCandidatePairSelected", fn)

  def on_data_channgel_open_event(self, fn):
    return self.subscribe("DataChannelOpen", fn)

  def on_data_channgel_close_event(self, fn):
    return self.subscribe("DataChannelClose", fn)


class BaseRtpEndpoint(SdpEndpoint):
  def on_connection_state_changed_event(self, fn):
    return self.subscribe("ConnectionStateChanged", fn)

  def on_media_state_changed_event(self, fn):
    return self.subscribe("MediaStateChanged", fn)


class RtpEndpoint(BaseRtpEndpoint):
  pass

class WebRtcEndpoint(BaseRtpEndpoint):
  pass


# FILTERS

class GStreamerFilter(MediaElement):
  pass


class FaceOverlayFilter(MediaElement):
  def set_overlayed_image(self, uri, offset_x, offset_y, width, height):
    return self.invoke("setOverlayedImage", uri=uri, offsetXPercent=offset_x, offsetYPercent=offset_y, widthPercent=width, heightPercent=height)


class ZBarFilter(MediaElement):
  def on_code_found_event(self, fn):
    return self.subscribe("CodeFound", fn)


# HUBS

class Composite(MediaElement):
  pass


class Dispatcher(MediaElement):
  pass


class DispatcherOneToMany(MediaElement):
  pass
