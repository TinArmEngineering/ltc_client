# ltc_client
![TeamCity build status](https://build.tinarmengineering.com/app/rest/builds/buildType:id:LonelyToolCult_LtcClientModule/statusIcon.svg)

Node creation tool for TAE workers

Development with Poetry https://python-poetry.org/docs/basic-usage/

Before committing:

Check the formatting is compient with Black:
`poetry run black .`

Run the tests:
`poetry run pytest`

Get the coverage report:
`poetry run coverage report`
Hopefully it should not have gone down lower than this:
```
Name                     Stmts   Miss  Cover   Missing
------------------------------------------------------
ltc_client/__init__.py       7      0   100%
ltc_client/api.py          161     93    42%   38, 48-56, 72, 97-99, 104-106, 112, 118, 123-124, 128, 144, 149-156, 167, 171-173, 180, 191-200, 203-204, 211-212, 218, 223, 226-227, 236, 248-251, 259, 267-274, 278-280, 287-290, 298-301, 309-312, 319-328, 331-335, 340-342, 350-406
ltc_client/helpers.py      119     70    41%   48-57, 86, 89-105, 110-118, 121, 125-144, 147-175, 178, 193-195, 200-203, 207, 211, 214-228, 253-269
ltc_client/worker.py       179    116    35%   48, 85, 87, 97-98, 101, 142-197, 200-220, 223-236, 239, 242-250, 256-313, 317-365, 372-378, 382-393
------------------------------------------------------
TOTAL                      466    279    40%
```
To push a release with a tag, 
make your commits locally, don't push yet, then:
```
git tag 0.2.22
git push --atomic origin main 0.2.22
```
