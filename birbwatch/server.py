import subprocess
from typing import Optional

__all__ = ['StreamServer']

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
		return self._proc is not None

	def start(self, stream_url: str):
		if self.running:
			self.stop()

		self._proc = subprocess.Popen(
			[
				'python',
				'-m', 'streamlink', '--loglevel', 'debug', '--player-external-http', f'--player-external-http-port={self.port}', f'{stream_url}', f'{self.quality}',
			],
			# stdout=subprocess.PIPE
		)  # TODO : logging and remove debug

	def stop(self):
		if self.running:
			try:
				self._proc.terminate()
			except OSError:
				# process has already terminated
				pass
		self._proc = None

	def __del__(self):
		self.stop()
