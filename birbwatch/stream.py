__all__ = ['Stream', 'get_streams_db', 'get_streamlink_streams', 'is_healthy']

import logging
import json
import requests
import streamlink
from streamlink.stream.stream import Stream as SL_Stream
from typing import Optional
from dataclasses import dataclass

from .config import *

_logger = logging.getLogger(__name__)
_logger.setLevel(config.getint('logging', 'level'))

@dataclass
class Stream:
	name: str
	description: str
	url: str
	healthy: Optional[bool] = None
	quality: Optional[str] = None

_session = streamlink.Streamlink()

def get_streams_db() -> list[Stream]:
	data = None

	# try in order of priority to get the stream database .json file from the sources listed in config.ini
	for source in config.get('behavior', 'stream_db_source').strip().split('\n'):
		try:
			if source.startswith('https://') or source.startswith('http://'):
				res = requests.get(source)
				data = res.json()
				break

			elif source.startswith('file://'):
				filepath = source[7:]
				with open(filepath) as file:
					data = json.load(file)
				break

		except Exception as e:
			_logger.warning(f'could not get stream data from {source}\n{e}')
			data = None
	
	if data is None:
		_logger.error('could not get stream data from any source')
		return []

	_logger.debug(f'got stream data from source {source}')
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