#/bin/bash
python3 -m venv ./testenv
. testenv/bin/activate
pip install .
MODULE_VERSION=$(pip show ltc_client | grep Version: | grep -Eo "([0-9]{1,}\.)+[0-9]{1,}")
echo "##teamcity[buildNumber '$MODULE_VERSION.%build.counter%']"
pip install -r ./tests/requirements.txt
python3 ./tests/test_api.py
deactivate
rm -rf testenv/
