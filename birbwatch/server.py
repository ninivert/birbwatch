import subprocess


def get_server_proc(url, quality, port):
	proc = subprocess.Popen([
		'python',
		'-m', 'streamlink', '--loglevel', 'debug', '--player-external-http', f'--player-external-http-port={port}', f'{url}', f'{quality}'
	])

	return proc


if __name__ == '__main__':
	import time

	proc = get_server_proc('https://youtu.be/MMbTUvSjnB4', '360p,240p,480p,worst', 6969)

	while True:
		try:
			time.sleep(0.01)
		except KeyboardInterrupt:
			proc.terminate()
			break
