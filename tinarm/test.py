import api

api = api.TaeApi(
    "https://api.build.tinarmengineering.com",
    "********-****-****-****-************"
)

resp = api.get_job("651ad87d159a4930f2bd60cb")
resp = api.post_job_artifact("651ad87d159a4930f2bd60cb")
print(resp)


