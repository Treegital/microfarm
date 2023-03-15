from setuptools import setup


setup(
    name='microfarm.topology',
    install_requires = [
        'pika',
    ],
    extras_require={
        'test': [
            'pytest',
        ]
    }
)
