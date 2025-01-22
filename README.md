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

To push a release with a tag, 
```
git tag 0.2.15
git push --atomic origin main 0.2.15
```
