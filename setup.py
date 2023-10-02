import setuptools

setuptools.setup(
    name="tinarm",
    version="0.1.0",
    author="Martin West, Chris Wallis",
    description="TINARM - Node creation tool for TAE workers",
    url="https://github.com/TinArmEngineering/tinarm",
    author_email="chris@tinarmengineering.com",
    license="MIT",
    packages=["tinarm", "tinarm.pbmodel"],
    install_requires=[
        "pika",
        "protobuf",
        "python_logging_rabbitmq",
        "requests"
    ],
    classifiers=[
        "Development Status :: 1 - Planning",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
    ],
)
