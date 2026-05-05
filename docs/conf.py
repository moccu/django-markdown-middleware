import datetime
import os
import sys

year = datetime.datetime.now().strftime("%Y")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")

sys.path.insert(0, os.path.abspath('..'))

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
]

templates_path = ['_templates']

source_suffix = '.rst'

master_doc = 'index'

project = 'django-markdown-middleware'
copyright = '%s, Moccu GmbH & Co. KG' % year

exclude_patterns = ['_build']

pygments_style = 'sphinx'

autodoc_default_flags = ['members', 'show-inheritance']
autodoc_member_order = 'bysource'

html_theme = 'default'
