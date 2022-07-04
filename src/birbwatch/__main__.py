import sys
from .gui import BirbwatchMain
from PySide6 import QtWidgets

if __name__ == '__main__':
	app = QtWidgets.QApplication(sys.argv)

	w = BirbwatchMain()
	w.resize(320, 240)
	w.setFixedSize(w.size())
	w.setWindowTitle('birbwatch')
	w.show()

	sys.exit(app.exec())