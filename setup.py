from setuptools import setup, find_packages


setup(
    name="notes",
    version="1.0",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'notes=notes.main:main'
        ]
    }
)
