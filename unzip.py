#!/usr/bin/env python3

import json
import shutil
import sys
import zipfile
from pathlib import Path

from calibre.utils.config import config_dir
from calibre_plugins.worddumb.config import prefs

NUMPY_VERSION = '1.20.1'
PLUGIN_PATH = Path(config_dir).joinpath('plugins/WordDumb.zip')


def check_folder(folder_name, version):
    extract_path = Path(config_dir).joinpath('plugins/'
                                             + folder_name + version)
    if not extract_path.is_dir():
        for f in Path(config_dir).joinpath('plugins').iterdir():
            if folder_name in f.name and f.is_dir():
                shutil.rmtree(f)  # delete old folder

    return extract_path


def load_json(filepath):
    with zipfile.ZipFile(PLUGIN_PATH) as zf:
        with zf.open(filepath) as f:
            return json.load(f)


def install_libs():
    for d in zipfile.Path(PLUGIN_PATH).joinpath('.venv/lib').iterdir():
        if (p := str(d.joinpath('site-packages'))) not in sys.path:
            sys.path.append(p)

    download_nltk_data()
    if prefs['x-ray']:
        download_numpy()


def download_nltk_data():
    nltk_path = Path(config_dir).joinpath('plugins/worddumb-nltk')
    nltk_path_str = str(nltk_path)

    import nltk
    if not nltk_path.joinpath('corpora/wordnet').is_dir():
        nltk.download('wordnet', nltk_path_str)  # morphy

    if prefs['x-ray']:
        if not nltk_path.joinpath('tokenizers/punkt').is_dir():
            nltk.download('punkt', nltk_path_str)  # word_tokenize
        # pos_tag
        averaged = 'averaged_perceptron_tagger'
        if not nltk_path.joinpath('taggers/' + averaged).is_dir():
            nltk.download(averaged, nltk_path_str)
        # ne_chunk
        if not nltk_path.joinpath('chunkers/maxent_ne_chunker').is_dir():
            nltk.download('maxent_ne_chunker', nltk_path_str)
        if not nltk_path.joinpath('corpora/words').is_dir():
            nltk.download('words', nltk_path_str)

    if nltk_path_str not in nltk.data.path:
        nltk.data.path.append(nltk_path_str)


def download_numpy():
    numpy_path = check_folder('worddumb-numpy', NUMPY_VERSION)
    if not numpy_path.joinpath('numpy').is_dir():
        import platform
        import subprocess
        py_version = '{}{}'.format(
            sys.version_info.major, sys.version_info.minor)
        pip = 'pip3'
        if platform.system() == 'Darwin':
            pip = '/usr/local/bin/pip3'
        subprocess.check_call(
            [pip, 'install', '-U', 'pip', 'setuptools', 'wheel'])
        subprocess.check_call(
            [pip, 'download', '-d', numpy_path, '--python-version',
             py_version, '--no-deps', 'numpy==' + NUMPY_VERSION])
        for wheel in numpy_path.iterdir():
            with zipfile.ZipFile(wheel) as zf:
                zf.extractall(numpy_path)
            wheel.unlink()

    if (p := str(numpy_path)) not in sys.path:
        sys.path.append(p)
