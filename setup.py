"""
Manage FaaSPacks via Command Line
"""
from setuptools import find_packages, setup
import re

dependencies = ['Click', 'boto3', 'PyYaml']

version = re.search(
    '^__version__\s*=\s*"(.*)"',
    open('fspk/cli.py').read(),
    re.M
    ).group(1)

setup(
    name='fspk',
    version=version,
    url='https://github.com/floodfx/fspk-cli',
    license='Apache2.0',
    author='Donnie Flood',
    author_email='pypi@floodfx.com',
    description='Manage FaaSPacks via Command Line',
    long_description=__doc__,
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=dependencies,
    entry_points={
        'console_scripts': [
            'fspk = fspk.cli:fp',
        ],
    },
    classifiers=[
        # As from http://pypi.python.org/pypi?%3Aaction=list_classifiers
        # 'Development Status :: 1 - Planning',
        # 'Development Status :: 2 - Pre-Alpha',
        'Development Status :: 3 - Alpha',
        # 'Development Status :: 4 - Beta',
        # 'Development Status :: 5 - Production/Stable',
        # 'Development Status :: 6 - Mature',
        # 'Development Status :: 7 - Inactive',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX',
        'Operating System :: MacOS',
        'Operating System :: Unix',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
