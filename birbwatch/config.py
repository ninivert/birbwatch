__all__ = ['config']

import configparser

config = configparser.ConfigParser()
config.read('config.ini')