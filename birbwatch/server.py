import subprocess
from typing import Optional
from PySide6.QtCore import QObject, Signal
from .thread import *

__all__ = ['StreamServer']

class StreamServer(QObject):
	started = Signal()

	def __init__(self, port: int, quality: str):
		super().__init__()

		self.port: int = port
		self.quality: str = quality
		self._proc: Optional[subprocess.Popen] = None
		self._worker = TaskManager(name='emit_when_stream_server_started')

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
				'-m', 'streamlink', '--loglevel', 'info', '--player-external-http', f'--player-external-http-port={self.port}', f'{stream_url}', f'{self.quality}',
			],
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			text=True
		)

		self._worker.submit(self.emit_when_started)

	def emit_when_started(self):
		# a very hacky way to tell when the server has started :
		# read the stdout of the streamlink subprocess and look for message confirming server started
		for line in self._proc.stdout:
			# example log :
			# [cli][info] Available streams: 144p (worst), 240p, 360p, 480p, 720p, 1080p (best)
			# [cli][info] Starting server, access with one of:
			# [cli][info]  http://127.0.0.1:6969/
			# [cli][info]  http://127.0.1.1:6969/
			if 'http://127.0.0.1' in line:
				self.started.emit()
				return

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
