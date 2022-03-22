from setuptools import setup

setup(
    name='dmf',
    version='0.1',
    packages=['dmf'],
    url='https://github.com/LayneInNL/dmf',
    license='Apache-2.0 License',
    author='Layne Liu',
    author_email='layne.liu@outlook.com',
    description='An instance of a dynamic monotone framework for type analysis for Python.',
    entry_points={
        'console_scripts': [
            'dmf = dmf.main:main'
        ]
    }
)
