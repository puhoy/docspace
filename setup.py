from setuptools import setup, find_packages

requirements = [
    "click==7.1.2",
    "pdf2image==1.14.0",
    "Pillow==8.0.1",
    "python-magic==0.4.18",
]

test_requirements = [
    "pytest==5.3.2",
    "pytest-cov==2.8.1",
    "pytest-cover==3.0.0",
    "codecov==2.0.15"
]


setup(
    name='docspace',
    packages=find_packages(),
    include_package_data=True,
    version='0.0.1',
    entry_points='''
        [console_scripts]
        docspace=docspace.app:cli
    ''',
    description='a ebook manager built around isbnlib',
    url='https://github.com/puhoy/docspace',
    author='jan',
    author_email='stuff@kwoh.de',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    extras_require={
        'test': test_requirements
    },
    install_requires=requirements,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        "Intended Audience :: End Users/Desktop",
        "Natural Language :: English",
        "Topic :: Utilities",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
)
