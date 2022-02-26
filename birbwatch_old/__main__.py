import qasync
import asyncio
import sys
from .gui import main

if __name__ == "__main__":
	try:
		qasync.run(main())
	except asyncio.exceptions.CancelledError:
		sys.exit(0)
