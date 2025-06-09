from setuptools import setup, find_packages

setup(
    name="webplugin",
    version="1.0",
    packages=find_packages(),
    install_requires=[
        'flask',
        'flask-cors',
        'whisper',
        'torch'
    ],
    python_requires='>=3.7',
    options={
        'build_py': {
            'exclude': ['__pycache__', '*.pyc', '*.pyo', '*.pyd'],
        },
    },
) 