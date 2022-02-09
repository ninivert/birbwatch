import requests
from collections import namedtuple

Stream = namedtuple('Stream', ('name', 'description', 'url'))


async def get_streams() -> list[Stream]:
	# TODO : put this in a config file
	url = 'https://raw.githubusercontent.com/ninivert/birbwatch/main/streams.json'

	res = requests.get(url)
	data = res.json()

	streams = [Stream(name=stream['name'], description=stream['description'], url=stream['url']) for stream in data['streamlist']]

	return streams


if __name__ == '__main__':
	print(get_streams())
