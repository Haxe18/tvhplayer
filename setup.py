from setuptools import setup, find_packages

setup(
    name="tvhplayer",
    version="4.0.0",
    description="Desktop client for TVHeadend",
    author="mFat",
    author_email="mah.fat@gmail.com",
    url="https://github.com/mfat/tvhplayer",
    install_requires=[
        'PyQt6>=6.6.0',
        'python-vlc>=3.0.12122',
        'requests>=2.28.0',
        'python-dateutil>=2.8.2',
    ],
    python_requires='>=3.6',
    packages=find_packages(),
    package_data={
        'tvhplayer': ['*.py', 'icons/*'],
    },
    entry_points={
        'console_scripts': [
            'tvhplayer=tvhplayer.tvhplayer:main',
        ],
    },
    data_files=[
        ('share/applications', ['debian/tvhplayer.desktop']),
        ('share/icons/hicolor/256x256/apps', ['icons/tvhplayer.png']),
    ],
)
