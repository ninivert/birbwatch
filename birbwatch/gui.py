import functools
from collections import namedtuple
import concurrent.futures
from optparse import Option

from typing import Callable, Optional

from .stream import *
from .server import *

from PySide6.QtCore import Signal, Slot, QObject
from PySide6 import QtWidgets, QtGui, QtMultimedia, QtMultimediaWidgets

class Communicate(QObject):
	refresh_streams = Signal()
	refresh_streams_getting = Signal()
	refresh_streams_validating = Signal()
	refresh_streams_validating_partial = Signal(int, int)
	refresh_streams_done = Signal()
	selected_stream_update = Signal(Stream)
	start_stream = Signal()
	stop_stream = Signal()
	show_player = Signal()
	show_settings = Signal()


C = Communicate()


TaskResult = namedtuple('TaskResult', ('data', 'status'))

class TaskManager(QObject):
	finished = Signal(TaskResult)

	def __init__(self, max_workers: int = 1, name: str = ''):
		super().__init__()
		self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=name)

	def submit(self, fn: Callable[[], TaskResult], *args, **kwargs):
		future = self.executor.submit(fn, *args, **kwargs)
		future.add_done_callback(self.forward_result)

	def forward_result(self, future):
		data: TaskResult = future.result()
		self.finished.emit(data)


class StreamItem(QtWidgets.QTreeWidgetItem):
	def __init__(self, stream: Stream):
		super().__init__([stream.name, '?', ''])

		self.stream: Stream = stream

		self.validation_worker = TaskManager(max_workers=1, name=f'validate')
		self.validation_worker.finished.connect(self.validate_callback)

	def update(self):
		self.setText(0, self.stream.name)
		self.setText(1, 'OK' if self.stream.healthy else 'ERR')
		self.setText(2, '')

	def validate(self) -> TaskResult:
		try:
			sl_streams = get_streamlink_streams(self.stream.url)
			sl_stream = sl_streams['worst']  # TODO : unhardcode this
			healthy = is_healthy(sl_stream)
		except Exception as e:
			print(f'could not get stream {self.stream.url} : {e}')  # TODO : logging !!
			healthy = False
		
		return TaskResult(healthy, 0)

	def validate_callback(self, result: TaskResult):
		self.stream.healthy = result.data
		self.update()


class StreamListWidget(QtWidgets.QTreeWidget):
	def __init__(self):
		super().__init__()

		self.setItemsExpandable(False)
		self.setRootIsDecorated(False)
		self.setHeaderLabels(['stream', 'ok', 'playing'])

		self.refresh_worker = TaskManager(max_workers=1, name='refresh')  # TODO : put max_workers in config file
		self.refresh_worker.finished.connect(self.refresh_callback)
		C.refresh_streams.connect(lambda: self.refresh_worker.submit(self.refresh))

		self.currentItemChanged.connect(lambda curr, prev: C.selected_stream_update.emit(None if curr is None else curr.stream))

	@property
	def stream_items(self) -> list[StreamItem]:
		return [self.topLevelItem(streamitem_idx) for streamitem_idx in range(self.topLevelItemCount())]

	def refresh(self) -> TaskResult:
		C.refresh_streams_getting.emit()
		streams: list[Stream] = get_streams_db()
		return TaskResult(streams, 0)

	def refresh_callback(self, result: TaskResult):
		self.clear()

		# Repopulate with new streams
		for stream in result.data:
			self.insertTopLevelItem(0, StreamItem(stream))

		# Validate all
		C.refresh_streams_validating.emit()
		self.num_validated = 0
		for stream_item in self.stream_items:
			stream_item.validation_worker.finished.connect(self.validate_partial_callback)
			stream_item.validation_worker.submit(stream_item.validate)
		C.refresh_streams_validating_partial.emit(self.num_validated, len(self.stream_items))

	def validate_partial_callback(self, result: TaskResult):
		self.num_validated += 1
		C.refresh_streams_validating_partial.emit(self.num_validated, len(self.stream_items))

		if self.num_validated == len(self.stream_items):
			# And we're done !
			C.refresh_streams_done.emit()


class StreamActionWidget(QtWidgets.QWidget):
	def __init__(self):
		super().__init__()

		self.setLayout(QtWidgets.QHBoxLayout())
		self.layout().setContentsMargins(0, 0, 0, 0)

		self.q_showplayerbtn = QtWidgets.QPushButton('Back')
		self.q_showplayerbtn.setIcon(QtGui.QIcon.fromTheme('arrow-left'))
		self.q_playbtn = QtWidgets.QPushButton('Play')
		self.q_playbtn.setIcon(QtGui.QIcon.fromTheme('media-playback-start'))
		self.q_playbtn.setEnabled(False)
		self.q_stopbtn = QtWidgets.QPushButton('Stop')
		self.q_stopbtn.setIcon(QtGui.QIcon.fromTheme('media-playback-stop'))
		self.q_stopbtn.setEnabled(False)
		self.q_refreshbtn = QtWidgets.QPushButton('Refresh')
		self.q_refreshbtn.setIcon(QtGui.QIcon.fromTheme('browser-reload'))  # TODO : another icon
		self.q_playstop = QtWidgets.QStackedWidget()

		self.q_showplayerbtn.clicked.connect(C.show_player.emit)
		self.q_playbtn.clicked.connect(C.start_stream.emit)
		self.q_stopbtn.clicked.connect(C.stop_stream.emit)
		self.q_refreshbtn.clicked.connect(C.refresh_streams.emit)

		self.q_playstop.addWidget(self.q_playbtn)
		self.q_playstop.addWidget(self.q_stopbtn)
		self.layout().addWidget(self.q_showplayerbtn)
		self.layout().addWidget(self.q_playstop)
		self.layout().addWidget(self.q_refreshbtn)

		C.selected_stream_update.connect(self.update_playstop)

	def update_playstop(self, stream: Stream):
		self.q_playbtn.setEnabled(bool(stream.healthy))
		self.q_stopbtn.setEnabled(bool(stream.playing))
		
		if not stream.playing:
			self.q_playstop.setCurrentWidget(self.q_playbtn)
		else:
			self.q_playstop.setCurrentWidget(self.q_stopbtn)

class SettingsWidget(QtWidgets.QWidget):
	def __init__(self):
		super().__init__()

		self.setLayout(QtWidgets.QVBoxLayout())
		self.layout().addWidget(StreamListWidget())
		self.layout().addWidget(StreamActionWidget())


class PlayerWidget(QtWidgets.QWidget):
	def __init__(self):
		super().__init__()

		# TODO : loader

		self.setLayout(QtWidgets.QVBoxLayout())
		self.layout().setContentsMargins(0, 0, 0, 0)

		self.q_media = None
		self.q_audio = QtMultimedia.QAudioOutput()
		self.q_video = QtMultimediaWidgets.QVideoWidget()

		self.q_settingsbtn = QtWidgets.QPushButton('Settings')
		self.q_settingsbtn.clicked.connect(C.show_settings)
		self.q_settingsbtn.setIcon(QtGui.QIcon.fromTheme('arrow-left'))

		self.layout().addWidget(self.q_video)
		self.layout().addWidget(self.q_settingsbtn)

	def reset(self):
		# HACK : rebuilding the QMediaPlayer each time
		self.stop()

		if self.q_media is not None:
			del self.q_media

		self.q_media = QtMultimedia.QMediaPlayer()
		self.q_media.setAudioOutput(self.q_audio)
		self.q_media.setVideoOutput(self.q_video)
		self.q_media.setSource('http://127.0.0.1:6969/')  # TODO

	def play(self):
		if self.q_media is not None:
			self.q_media.play()

	def stop(self):
		if self.q_media is not None and self.q_media.playbackState() != QtMultimedia.QMediaPlayer.StoppedState:
			self.q_media.stop()

	def pause(self):
		if self.q_media is not None and self.q_media.playbackState() != QtMultimedia.QMediaPlayer.PausedState:
			self.q_media.pause()


class BirbwatchMain(QtWidgets.QMainWindow):
	def __init__(self):
		super().__init__()

		self.selected_stream: Optional[Stream] = None
		self.playing_stream: Optional[Stream] = None
		self.server = StreamServer(6969, '360p,240p,480p,worst')  # TODO : move this to config file

		self.statusBar().setSizeGripEnabled(False)
		self.statusBar().showMessage('Ready.')

		self.setCentralWidget(QtWidgets.QStackedWidget())  # WARNING: takes ownership !
		self.settings_widget = SettingsWidget()
		self.player_widget = PlayerWidget()
		self.centralWidget().addWidget(self.settings_widget)
		self.centralWidget().addWidget(self.player_widget)

		C.refresh_streams.connect(functools.partial(self.statusBar().showMessage, 'Refreshing streams...'))
		C.refresh_streams_getting.connect(functools.partial(self.statusBar().showMessage, 'Getting streams...'))
		C.refresh_streams_validating.connect(functools.partial(self.statusBar().showMessage, 'Validating streams...'))
		C.refresh_streams_done.connect(functools.partial(self.statusBar().showMessage, 'Done refreshing streams.'))
		C.refresh_streams_validating_partial.connect(functools.partial(lambda msg, curr, tot: self.statusBar().showMessage(msg.format(curr, tot)), 'Validating streams ({}/{})'))
		C.start_stream.connect(self.start_stream)
		C.stop_stream.connect(self.stop_stream)
		C.show_player.connect(self.show_player)
		C.show_settings.connect(self.show_settings)
		C.selected_stream_update.connect(self.set_selected_stream)

		self.show_settings()
		C.refresh_streams.emit()

	def start_stream(self):
		self.stop_stream()

		if self.selected_stream is not None and self.selected_stream.healthy:
			self.playing_stream = self.selected_stream
			self.playing_stream.playing = True
			self.server.start(self.playing_stream.url)
			self.statusBar().showMessage('Streaming...')

		if id(self.playing_stream) == id(self.selected_stream):
			# selected stream might be the one playing, update the UI
			C.selected_stream_update.emit(self.selected_stream)

	def stop_stream(self):
		self.player_widget.stop()
		self.server.stop()

		if self.playing_stream is not None:
			self.playing_stream.playing = False
			
			if id(self.playing_stream) == id(self.selected_stream):
				# selected stream might be the one playing, update the UI
				C.selected_stream_update.emit(self.selected_stream)

		self.statusBar().showMessage('Ready.')

	def show_player(self):
		self.centralWidget().setCurrentWidget(self.player_widget)
		self.player_widget.reset()
		self.player_widget.play()
		self.statusBar().setVisible(False)  # TODO : turn status off or on in config

	def show_settings(self):
		self.centralWidget().setCurrentWidget(self.settings_widget)
		self.player_widget.stop()
		self.statusBar().setVisible(True)

	def set_selected_stream(self, stream: Optional[Stream]):
		self.selected_stream = stream