__all__ = ['TaskResult', 'TaskManager']

from PySide6.QtCore import Signal, Slot, QObject
from collections import namedtuple
from typing import Callable
import concurrent.futures

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