from dataclasses import dataclass
import functools
from typing import Optional
import logging

from .stream import *
from .server import *
from .config import *

from PySide6.QtCore import Signal, QObject, QRunnable, QThreadPool, QUrl
from PySide6 import QtWidgets, QtGui, QtMultimedia, QtMultimediaWidgets

logging.basicConfig(filename=config.get('logging', 'logfile'), format=config.get('logging', 'format'))
_logger = logging.getLogger(__name__)
_logger.setLevel(config.getint('logging', 'level'))

class Communicate(QObject):
	refresh_streams = Signal()
	refresh_streams_getting = Signal()
	refresh_streams_validating = Signal()
	refresh_streams_validating_partial = Signal(int, int)
	refresh_streams_done = Signal()
	selected_stream_update = Signal(Stream)
	show_player = Signal()
	show_settings = Signal()


C = Communicate()
SERVER = StreamServer(
	config.getint('streamserver', 'port'),
	','.join(config.get('streamlink', 'quality').strip().split('\n'))
)


@dataclass
class State:
	streaming: bool = False
	getting: bool = False
	validating: bool = False

	@property
	def idle(self) -> bool:
		return not self.streaming and not self.refreshing

	@property
	def refreshing(self) -> bool:
		return self.getting or self.validating

STATE = State()

# TODO : hook this with the status bar
C.refresh_streams.connect(lambda: STATE.__setattr__('getting', True))
C.refresh_streams_validating.connect(lambda: STATE.__setattr__('getting', False))
C.refresh_streams_validating.connect(lambda: STATE.__setattr__('validating', True))
C.refresh_streams_done.connect(lambda: STATE.__setattr__('getting', False))
C.refresh_streams_done.connect(lambda: STATE.__setattr__('validating', False))
C.show_player.connect(lambda: STATE.__setattr__('streaming', True))
C.show_settings.connect(lambda: STATE.__setattr__('streaming', False))


class StreamItem(QtWidgets.QTreeWidgetItem):
	def __init__(self, parent, stream: Stream):
		super().__init__(parent)

		self.stream: Stream = stream

		self.treeWidget().setItemWidget(self, 0, QtWidgets.QLabel())
		self.treeWidget().setItemWidget(self, 1, QtWidgets.QLabel())
		self.treeWidget().setItemWidget(self, 2, QtWidgets.QLabel())

		self.update()

	def update(self):
		self.treeWidget().itemWidget(self, 0).setText(f'{self.stream.name}<br><i>{self.stream.description}</i>')
		self.treeWidget().itemWidget(self, 1).setText('?' if self.stream.healthy is None else 'OK' if self.stream.healthy else 'ERR')
		self.treeWidget().itemWidget(self, 2).setText('?' if self.stream.quality is None else self.stream.quality)

	def validate_callback(self, healthy: bool, quality: str):
		self.stream.healthy = healthy
		self.stream.quality = quality
		self.update()


class StreamListWidget(QtWidgets.QTreeWidget):
	class RefreshRunnable(QObject, QRunnable):
		result = Signal(list)

		def __init__(self):
			QObject.__init__(self)
			QRunnable.__init__(self)
	
		def run(self):
			C.refresh_streams_getting.emit()
			streams: list[Stream] = get_streams_db()
			self.result.emit(streams)

	class ValidatorRunnable(QObject, QRunnable):
		result = Signal(bool, str)  # return data from the run function

		def __init__(self, stream: Stream):
			QObject.__init__(self)
			QRunnable.__init__(self)
			self._stream = stream
	
		def run(self):
			try:
				sl_streams = get_streamlink_streams(self._stream.url)
				sl_stream = None

				# query the streams to try to get the highest priority quality (defined in config.ini)
				for quality in config.get('streamlink', 'quality').strip().split('\n'):
					if quality in sl_streams:
						sl_stream = sl_streams[quality]
						_logger.debug(f'found quality {quality} for stream url {self._stream.url}')
						break

				# failed to get a stream (should never happen, 'worst' is a fallback already)
				if sl_stream is None:
					raise Exception(f'could not find a stream quality from {sl_streams}')

				healthy = is_healthy(sl_stream)

			except Exception as e:
				_logger.info(f'could not get stream {self._stream.url} : {e}')
				healthy = False
				quality = None
			
			self.result.emit(healthy, quality)

	def __init__(self):
		super().__init__()

		self.setItemsExpandable(False)
		self.setRootIsDecorated(False)
		self.setHeaderLabels(['stream', 'status', 'quality'])
		self.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
		self.header().setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
		self.header().setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
		self.header().setStretchLastSection(False)
		self.header().resizeSection(1, 60)
		self.header().resizeSection(2, 60)

		self._refresh_pool = QThreadPool(self)
		self._validate_pool = QThreadPool(self)
		self._refresh_pool.setMaxThreadCount(1)

		C.refresh_streams.connect(self.refresh)

		self.currentItemChanged.connect(lambda curr, prev: C.selected_stream_update.emit(None if curr is None else curr.stream))

	@property
	def stream_items(self) -> list[StreamItem]:
		return [self.topLevelItem(streamitem_idx) for streamitem_idx in range(self.topLevelItemCount())]

	def refresh(self):
		C.refresh_streams_getting.emit()
		refresh_runnable = StreamListWidget.RefreshRunnable()
		refresh_runnable.result.connect(self.validate)
		self._refresh_pool.start(refresh_runnable)
		# self._refresh_pool.waitForDone()

	def validate(self, streams: list[Stream]):
		self.clear()

		# Repopulate with new streams
		for stream in streams:
			self.insertTopLevelItem(0, StreamItem(self, stream))

		# Validate all
		C.refresh_streams_validating.emit()
		self.num_validated = 0
		for stream_item in self.stream_items:
			validate_runnable = StreamListWidget.ValidatorRunnable(stream_item.stream)
			validate_runnable.result.connect(self.validate_partial_callback)
			validate_runnable.result.connect(stream_item.validate_callback)
			self._validate_pool.start(validate_runnable)
		C.refresh_streams_validating_partial.emit(self.num_validated, len(self.stream_items))

	def validate_partial_callback(self, healthy: bool, quality: str):
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

		self.q_refreshbtn = QtWidgets.QPushButton('Refresh')
		self.q_refreshbtn.setIcon(QtGui.QIcon.fromTheme('browser-reload'))  # TODO : another icon
		self.q_playbtn = QtWidgets.QPushButton('Play')
		self.q_playbtn.setIcon(QtGui.QIcon.fromTheme('media-playback-start'))
		self.q_playbtn.setEnabled(False)

		self.layout().addWidget(self.q_refreshbtn)
		self.layout().addWidget(self.q_playbtn)

		self.q_refreshbtn.clicked.connect(C.refresh_streams.emit)
		self.q_playbtn.clicked.connect(C.show_player.emit)

		C.selected_stream_update.connect(self.update_playbtn)
		C.refresh_streams_validating_partial.connect(lambda: self.update_playbtn(self._current_stream))
		C.refresh_streams.connect(lambda: self.q_refreshbtn.setEnabled(False))
		C.refresh_streams_done.connect(lambda: self.q_refreshbtn.setEnabled(True))
		C.show_player.connect(lambda: self.q_playbtn.setEnabled(False))
		SERVER.started.connect(lambda: self.q_playbtn.setEnabled(True))

		self._current_stream = None

	def update_playbtn(self, stream: Stream = None):
		self._current_stream = stream
		self.q_playbtn.setEnabled(bool(False if stream is None else self._current_stream.healthy))


class SettingsWidget(QtWidgets.QWidget):
	def __init__(self):
		super().__init__()

		self.setLayout(QtWidgets.QVBoxLayout())
		self.layout().addWidget(StreamListWidget())
		self.layout().addWidget(StreamActionWidget())


class PlayerWidget(QtWidgets.QWidget):
	def __init__(self):
		super().__init__()

		self.setLayout(QtWidgets.QVBoxLayout())
		self.layout().setContentsMargins(0, 0, 0, 0)

		self.q_audio = QtMultimedia.QAudioOutput()
		self.q_video = QtMultimediaWidgets.QVideoWidget()

		# self.q_settingsbtn = QtWidgets.QPushButton('Settings')
		# self.q_settingsbtn.clicked.connect(C.show_settings)
		# self.q_settingsbtn.setIcon(QtGui.QIcon.fromTheme('arrow-left'))

		self.layout().addWidget(self.q_video)
		# self.layout().addWidget(self.q_settingsbtn)

		self.q_media = QtMultimedia.QMediaPlayer()
		self.q_media.setAudioOutput(self.q_audio)
		self.q_media.setVideoOutput(self.q_video)

	def mousePressEvent(self, event: QtGui.QMouseEvent):
		C.show_settings.emit()  # close on click

	def restart(self):
		self.q_media.stop()
		# Setting the media to a null QUrl will cause the player to discard all information relating to the current media source and to cease all I/O operations related to that media.
		self.q_media.setSource(QUrl())
		self.q_media.setSource(f'http://127.0.0.1:{config.get("streamserver", "port")}/')
		self.q_media.play()

	def stop(self):
		if self.q_media.playbackState() != QtMultimedia.QMediaPlayer.StoppedState:
			self.q_media.stop()


class BirbwatchMain(QtWidgets.QMainWindow):
	def __init__(self):
		super().__init__()

		self.selected_stream: Optional[Stream] = None

		self.statusBar().setSizeGripEnabled(False)
		self.statusBar().showMessage('Ready.')

		self.setCentralWidget(QtWidgets.QStackedWidget())  # WARNING: takes ownership !
		self.settings_widget = SettingsWidget()
		self.player_widget = PlayerWidget()
		self.centralWidget().addWidget(self.settings_widget)
		self.centralWidget().addWidget(self.player_widget)

		# TODO : when entering and exiting the player while the streams are still refreshing,
		# the statusbar displays "Ready." -> FIX : application status
		C.refresh_streams.connect(functools.partial(self.statusBar().showMessage, 'Refreshing streams...'))  # TODO: loading spinner
		C.refresh_streams_getting.connect(functools.partial(self.statusBar().showMessage, 'Getting streams...'))
		C.refresh_streams_validating.connect(functools.partial(self.statusBar().showMessage, 'Validating streams...'))
		C.refresh_streams_done.connect(functools.partial(self.statusBar().showMessage, 'Done refreshing streams.'))
		C.refresh_streams_validating_partial.connect(functools.partial(lambda msg, curr, tot: self.statusBar().showMessage(msg.format(curr, tot)), 'Validating streams ({}/{})'))
		C.show_player.connect(self.show_player)
		C.show_settings.connect(self.show_settings)
		C.selected_stream_update.connect(self.set_selected_stream)
		SERVER.started.connect(self.show_player_callback)

		self.show_settings()

		if config.getboolean('behavior', 'refresh_on_start'):
			C.refresh_streams.emit()

	def start_stream(self):
		_logger.debug(f'attempting to start stream {self.selected_stream}')
		self.stop_stream()
		
		if self.selected_stream is not None and self.selected_stream.healthy:
			SERVER.start(self.selected_stream.url)
			_logger.debug(f'started stream {self.selected_stream}')
		else:
			_logger.warning(f'stream {self.selected_stream} is not playable')

	def stop_stream(self):
		_logger.debug('stopping stream')
		self.player_widget.stop()
		SERVER.stop()

	def show_player(self):
		self.start_stream()
		self.statusBar().showMessage('Starting stream...')

	def show_player_callback(self):
		self.centralWidget().setCurrentWidget(self.player_widget)
		self.player_widget.restart()
		self.statusBar().showMessage('Streaming...')
		self.statusBar().setVisible(config.getboolean('behavior', 'show_statusbar_streaming'))

	def show_settings(self):
		self.centralWidget().setCurrentWidget(self.settings_widget)
		self.player_widget.stop()
		self.stop_stream()
		self.statusBar().setVisible(True)  # restore statusbar visibility after returning from streaming
		self.statusBar().showMessage('Ready.')

	def set_selected_stream(self, stream: Optional[Stream]):
		# TODO : selection can still change when stream is loading, either block it or add a cancel button
		self.selected_stream = stream