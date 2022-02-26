import subprocess
from typing import Optional

class StreamServer:
	def __init__(self, port: int, quality: str):
		self.port: int = port
		self.quality: str = quality
		self._proc: Optional[subprocess.Popen] = None
		# self._stream_url: Optional[str] = None

	@property
	def loc(self):
		return f'http://127.0.0.1:{self.port}'

	@property
	def running(self):
		return self._proc is not None and self._proc.poll() is not None

	def start(self, stream_url: str):
		if self.running:
			self.stop()

		self._proc = subprocess.Popen([
			'python',
			'-m', 'streamlink', '--loglevel', 'debug', '--player-external-http', f'--player-external-http-port={self.port}', f'{stream_url}', f'{self.quality}',
		], stdout=subprocess.PIPE)  # TODO : logging and remove debug

	def stop(self):
		if self.running:
			self._proc.terminate()
		self._proc = None

	def __del__(self):
		self.stop()

# def get_server_proc(url, quality, port):
# 	proc = subprocess.Popen([
# 		'python',
# 		'-m', 'streamlink', '--loglevel', 'debug', '--player-external-http', f'--player-external-http-port={port}', f'{url}', f'{quality}'
# 	])

# 	return proc


if __name__ == '__main__':
	server = StreamServer(6969, '360p,240p,480p,worst')
	server.start('https://youtu.be/MMbTUvSjnB4')

	import time
	time.sleep(10)

	server.stop()

	# import time

	# proc = get_server_proc('https://youtu.be/MMbTUvSjnB4', '360p,240p,480p,worst', 6969)

	# while True:
	# 	try:
	# 		time.sleep(0.01)
	# 	except KeyboardInterrupt:
	# 		proc.terminate()
	# 		break
