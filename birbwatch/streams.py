import http
import httpx
import streamlink
from streamlink.stream.stream import Stream as SL_Stream
from collections import namedtuple

Stream = namedtuple('Stream', ('name', 'description', 'url'))
_session = streamlink.Streamlink()


async def get_streams_db() -> list[Stream]:
	# TODO : put this in a config file
	url = 'https://raw.githubusercontent.com/ninivert/birbwatch/main/streams.json'

	async with httpx.AsyncClient() as client:
		res = await client.get(url)
	data = res.json()

	streams = [Stream(name=stream['name'], description=stream['description'], url=stream['url']) for stream in data['streamlist']]

	return streams


def get_sl_streams(url) -> SL_Stream:
	streams = _session.streams(url)
	return streams


def is_healthy(stream: SL_Stream) -> bool:
	print('launching testing of stream ' + str(stream))
	try:
		with stream.open() as stream_fd:
			stream_fd.read(8192)
		return True
	except Exception as err:
		print(err)
		return False


if __name__ == '__main__':
	import asyncio

	async def main():
		import sys

		quality = 'worst'  # TODO : move to config file

		stream = (await get_sl_streams(sys.argv[1]))[quality]
		print(stream)
		print(await is_healthy(stream))

	asyncio.run(main())