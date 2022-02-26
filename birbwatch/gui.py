import sys
import functools

import asyncio
import concurrent.futures

from PySide6.QtWidgets import QWidget, QTreeWidget, QTreeWidgetItem, QListWidgetItem, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QStyle, QStackedWidget
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtCore import Signal, Slot, QObject
from PySide6.QtGui import QIcon
from qasync import asyncSlot, asyncClose, QApplication
from .streams import Stream, get_streams_db, get_sl_streams, is_healthy


class Communicate(QObject):
	refresh_streams = Signal()
	refresh_streams_getting = Signal()
	refresh_streams_validating = Signal()
	refresh_streams_done = Signal()
	show_player = Signal()
	reset_player = Signal()
	show_settings = Signal()


C = Communicate()


class StreamItem(QTreeWidgetItem):
	def __init__(self, stream: Stream):
		super().__init__([stream.name, '?', ''])

		self.stream = stream

	def validate(self):
		print(f'validating {self.stream.url}')
		sl_streams = get_sl_streams(self.stream.url)
		sl_stream = sl_streams['worst']  # TODO : unhardcode this
		healthy = is_healthy(sl_stream)

		if healthy:
			self.setText(1, '✓')  # TODO : QIcon
		else:
			self.setText(1, 'ERR')


class StreamListWidget(QTreeWidget):
	def __init__(self):
		super().__init__()

		self.setItemsExpandable(False)
		self.setRootIsDecorated(False)

		self.setHeaderLabels(['stream', 'ok', 'playing'])
		# TODO : resize columns

		C.refresh_streams.connect(self.refresh_streams)

		# TODO : enable by default
		# self.refresh_streams()

	@asyncSlot()
	async def refresh_streams(self):
		streams: list[Stream] = await get_streams_db()

		self.clear()

		# Insert streams
		C.refresh_streams_getting.emit()
		for stream in streams:
			self.insertTopLevelItem(0, StreamItem(stream))

		# Validate each stream
		# TODO : this needs some work with the user interface which hangs
		C.refresh_streams_validating.emit()

		async def do():
			with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
				executor.map(
					lambda streamitem: streamitem.validate(),
					[self.topLevelItem(streamitem_idx) for streamitem_idx in range(self.topLevelItemCount())]
				)
		await do()

		# async does not work because the Streams from streamlink are not async
		# tasks = (self.topLevelItem(streamitem_idx).validate() for streamitem_idx in range(self.topLevelItemCount()))
		# await asyncio.gather(*tasks)

		C.refresh_streams_done.emit()


class StreamActionWidget(QWidget):
	def __init__(self):
		super().__init__()

		self.q_layout = QHBoxLayout()  # TODO : change to self.layout()
		self.q_layout.setContentsMargins(0, 0, 0, 0)
		self.setLayout(self.q_layout)

		self.q_showplayerbtn = QPushButton('Back')
		self.q_showplayerbtn.setIcon(QIcon.fromTheme('arrow-left'))
		self.q_playbtn = QPushButton('Play')
		self.q_playbtn.setIcon(QIcon.fromTheme('media-playback-start'))
		self.q_refreshbtn = QPushButton('Refresh')
		self.q_refreshbtn.setIcon(QIcon.fromTheme('browser-reload'))

		self.q_showplayerbtn.clicked.connect(C.show_player.emit)
		self.q_playbtn.clicked.connect(C.reset_player.emit)  # TODO
		self.q_refreshbtn.clicked.connect(C.refresh_streams.emit)

		self.q_layout.addWidget(self.q_showplayerbtn)
		self.q_layout.addWidget(self.q_playbtn)
		self.q_layout.addWidget(self.q_refreshbtn)


class SettingsWidget(QWidget):
	def __init__(self):
		super().__init__()

		self.q_layout = QVBoxLayout()
		self.setLayout(self.q_layout)

		self.q_layout.addWidget(StreamListWidget())
		self.q_layout.addWidget(StreamActionWidget())


class PlayerWidget(QWidget):
	def __init__(self):
		super().__init__()

		# TODO : loader

		self.q_layout = QVBoxLayout()
		self.q_layout.setContentsMargins(0, 0, 0, 0)
		self.setLayout(self.q_layout)

		self.q_media = QMediaPlayer()
		self.q_audio = QAudioOutput()
		self.q_video = QVideoWidget()

		self.q_media.setSource('http://127.0.0.1:6969/')  # TODO : move this to config file
		self.q_media.setAudioOutput(self.q_audio)
		self.q_media.setVideoOutput(self.q_video)

		self.q_settingsbtn = QPushButton('Settings')
		self.q_settingsbtn.clicked.connect(C.show_settings)
		self.q_settingsbtn.setIcon(QIcon.fromTheme('arrow-left'))

		self.q_layout.addWidget(self.q_video)
		self.q_layout.addWidget(self.q_settingsbtn)

	def set_source(self, url):
		self.q_media.setSource(url)

	def play(self):
		self.q_media.play()

	def stop(self):
		self.q_media.stop()


class BirbwatchMain(QMainWindow):
	def __init__(self):
		super().__init__()

		self.q_status = self.statusBar()
		self.q_status.setSizeGripEnabled(False)
		self.update_status('Ready.')

		self.setCentralWidget(QStackedWidget())  # WARNING: takes ownership !

		self.settings_widget = SettingsWidget()
		self.player_widget = PlayerWidget()

		self.centralWidget().addWidget(self.settings_widget)
		self.centralWidget().addWidget(self.player_widget)

		C.refresh_streams.connect(functools.partial(self.update_status, 'Refreshing streams...'))
		C.refresh_streams_getting.connect(functools.partial(self.update_status, 'Getting streams...'))
		C.refresh_streams_validating.connect(functools.partial(self.update_status, 'Validating streams...'))
		C.refresh_streams_done.connect(functools.partial(self.update_status, 'Done refreshing streams.'))
		C.show_player.connect(self.show_player)
		C.show_settings.connect(self.show_settings)

		self.show_settings()

	def update_status(self, msg):
		self.q_status.showMessage(msg)

	def hide_status(self, hidden=True):
		self.q_status.setVisible(not hidden)

	def show_player(self):
		self.centralWidget().setCurrentWidget(self.player_widget)
		self.player_widget.play()
		self.update_status('Streaming...')
		self.hide_status()  # TODO : turn status off or on in config

	def show_settings(self):
		self.centralWidget().setCurrentWidget(self.settings_widget)
		self.player_widget.stop()
		self.update_status('Ready')
		self.hide_status(False)


async def main():
	def close_future(future, loop):
		loop.call_later(10, future.cancel)
		future.cancel()

	loop = asyncio.get_event_loop()
	future = asyncio.Future()

	app = QApplication.instance()
	if hasattr(app, "aboutToQuit"):
		getattr(app, "aboutToQuit").connect(
			functools.partial(close_future, future, loop)
		)

	w = BirbwatchMain()
	w.resize(320, 240)
	w.setFixedSize(w.size())
	w.setWindowTitle('birbwatch')
	w.show()

	await future
	return True
