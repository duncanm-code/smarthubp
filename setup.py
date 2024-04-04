from setuptools import setup, find_packages

setup(
    name='smarthubp',
    version='1.0.0',
    author='Duncan Miller',
    author_email='duncan.code@fastmail.com',
    description='A library for parsing electric meter usage out of the smarthub web application.',
    long_description='Smarthub is a portal used by many electric coops to give access to meter data in graph format. '
                     'This library parses the meter names, readings, and timestamps from the response.',
    url='https://github.com/duncan.code/smarthubp',
    packages=find_packages(),
    classifiers=[
        'Development Status :: 1 - Release',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
    ],
    keywords='smarthub electric',
    python_requires='>=3.10',
)

