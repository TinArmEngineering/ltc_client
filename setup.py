import setuptools

setuptools.setup(
    name="ltc_client",
    version="0.2",
    author="Martin West, Chris Wallis",
    description="TINARM - Node creation tool for TAE workers",
    url="https://github.com/TinArmEngineering/ltc_client",
    author_email="chris@tinarmengineering.com",
    license="MIT",
    packages=["tinarm"],
    install_requires=["pika", "python_logging_rabbitmq", "requests", "pint", "numpy",
                      "tqdm", "webstompy"],
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
    ],
)
