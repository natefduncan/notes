from setuptools import setup, find_packages

def read_reqs():
    with open("requirements.txt", "r") as f:
        return f.readlines()

setup(
    name='notes',
    version='0.1.0',
    py_modules=['notes'],
    packages=find_packages(), 
    install_requires=read_reqs(), 
    entry_points={
        'console_scripts': [
            'note = notes.main:cli',
        ],
    },
)
