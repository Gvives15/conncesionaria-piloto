import sys
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / 'apps'))

from config.settings import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'scripts' / 'data' / 'db_test_manual.sqlite3',
    }
}
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
