# exteraGram-compatible file helpers for AyuGram Desktop.

import os

import ayu_plugins


def get_plugins_dir():
    return ayu_plugins._state["plugins_dir"]


def get_cache_dir():
    return ayu_plugins.data_dir("cache")


def get_files_dir():
    return ayu_plugins.data_dir("files")


def ensure_dir_exists(path):
    os.makedirs(path, exist_ok=True)
    return path


def read_file(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def list_dir(path):
    return os.listdir(path)


def delete_file(path):
    os.remove(path)
