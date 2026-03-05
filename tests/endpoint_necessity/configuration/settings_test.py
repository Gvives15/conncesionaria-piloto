from config.settings import *

# Override Database to use SQLite for tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Disable WhiteNoise for tests to speed up
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
