__all__ = ['config']

import configparser

config = configparser.ConfigParser(interpolation=None)
config.read('config.ini')