__all__ = ['Stream', 'get_streams_db', 'get_streamlink_streams', 'is_healthy']

import requests
import streamlink
from streamlink.stream.stream import Stream as SL_Stream
from collections import namedtuple

Stream = namedtuple('Stream', ('name', 'description', 'url'))
_session = streamlink.Streamlink()


def get_streams_db() -> list[Stream]:
	# TODO : put this in a config file
	url = 'https://raw.githubusercontent.com/ninivert/birbwatch/main/streams.json'

	res = requests.get(url)
	data = res.json()

	streams = [Stream(name=stream['name'], description=stream['description'], url=stream['url']) for stream in data['streamlist']]

	return streams


def get_streamlink_streams(url) -> SL_Stream:
	streams = _session.streams(url)
	return streams


def is_healthy(stream: SL_Stream) -> bool:
	try:
		with stream.open() as stream_fd:
			stream_fd.read(8192)
		return True
	except Exception as err:
		print(err)
		return False