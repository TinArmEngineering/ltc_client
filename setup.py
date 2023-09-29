import setuptools
import tinarm

setuptools.setup(
    name="tinarm",
    version=tinarm.__version__,
    author=tinarm.__author__,
    description=tinarm.__title__,
    url="https://github.com/TinArmEngineering/tinarm",
    author_email="chris@tinarmengineering.com",
    license="MIT",
    packages=["tinarm"],
    install_requires=[
        "pika",
        "python_logging_rabbitmq"
    ],
    classifiers=[
        "Development Status :: 1 - Planning",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
    ],
)
