__all__ = ['TaskResult', 'TaskManager']

from PySide6.QtCore import Signal, Slot, QObject
from collections import namedtuple
from typing import Callable, Optional
import concurrent.futures
import functools

TaskResult = namedtuple('TaskResult', ('data', 'status'))

class TaskManager(QObject):
	finished = Signal(TaskResult)

	def __init__(self, name: str = ''):
		super().__init__()
		self.name = name
		self.executor: Optional[concurrent.futures.ThreadPoolExecutor] = None

	def submit(self, fn: Callable[[], TaskResult], *args, **kwargs):
		if self.executor is not None:
			self.stop()
			
		self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix=self.name)
		future = self.executor.submit(fn, *args, **kwargs)
		future.add_done_callback(self.forward_result)

	def forward_result(self, future):
		data: TaskResult = future.result()
		self.finished.emit(data)
		self.stop()

	def stop(self):
		self.executor.shutdown()  # cleanup memory and terminate thread
		self.executor = None