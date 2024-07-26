import os
from setuptools import setup, find_packages

readme_path = os.path.join(os.path.dirname(__file__), 'readme.md')
with open(readme_path, encoding='utf-8') as f:
    long_description = f.read()

setup(
    packages = find_packages(),
    name = 'pyfindlib',
    version='0.0.1',
    author="Stanislav Doronin",
    author_email="mugisbrows@gmail.com",
    url='https://github.com/mugiseyebrows/pyfindlib',
    description='Shell utility resembling findutils, small, extendable and windows-friendly',
    long_description = long_description,
    long_description_content_type = 'text/markdown',
    install_requires = ['python-dateutil','bashrange','shortwalk'],
    entry_points={
        'console_scripts': [
            'pyfind = pyfindlib.cli:main',
        ]
    },
)