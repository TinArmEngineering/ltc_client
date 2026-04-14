# ltc_client
![TeamCity build status](https://build.tinarmengineering.com/app/rest/builds/buildType:id:LonelyToolCult_LtcClientModule/statusIcon.svg)

Node creation tool for TAE workers

Creating and Monitoring Jobs with ltc_client
This guide provides a minimal, working example of how to create one or more jobs and monitor their progress asynchronously using ltc_client.

1. Setup
First, ensure you have the necessary libraries installed and import them. You will also need to configure the API connections, preferably using environment variables.

You can configure credentials using environment variables or a local YAML file.

**Using Environment Variables**

*   **API Credentials**: `API_ROOT_URL`, `API_KEY`, `ORG_ID`

**Using a YAML Configuration File**

Alternatively, create a file named `configurations.yaml`:
```yaml
api:
  root_url: https://api.ltc.tinarmengineering.com
  api_key: XXXXXXXXXXXXX # Your API key from your account page
  org_id: XXXXXXXXXXXXX  # Your organization ID from your account page

stomp:
  host: queue.ltc.tinarmengineering.com
  port: 15671
  user: XXXXXXXX
  password: XXXXXXXXXX
```

You can then load it in your Python script (you may need to `pip install pyyaml`):
```python
import yaml

with open("configurations.yaml", "r") as f:
    config = yaml.safe_load(f)
# example usage
api = ltc_client.Api(**config['api'])
```

2. Create a machine
For detils of each section see the example files.
```python
m = ltc_client.Machine(
    stator=stator_parameters,
    rotor=rotor_parameters,
    winding=winding_parameters,
    materials=materials,
)
```
we also need to get the netlist.
```python
netlist #we will give an example later
```

3. Create multiple jobs
```python
jobs = []
for idx in range(3):
    job = ltc_client.Job(machine=m, simulation=sim_param,  
        mesh_reuse_series=mesh_reuse_series,
        title=f"Job_{idx}",
        netlist=net)
    job.type = "electromagnetic_spmarc_fscwseg"
    jobs.append(job)
```

## Progress monitoring

`ltc_client` supports two complementary progress-monitoring styles:

1. **Default progress bars** using `tqdm` for scripts and notebooks
2. **Structured progress events** using `ProgressEvent` callbacks for marimo,
   Jupyter widgets, logging, or custom UIs

### Default behaviour

If you do not provide a callback, `async_job_monitor()` and `monitor_jobs()`
will create `tqdm` progress bars automatically.

```python
import asyncio
import ltc_client

async def main():
    connection = ltc_client.make_stomp_connection(config["stomp"])

    status = await ltc_client.async_job_monitor(
        api,
        job,
        connection,
    )

    print("Final status:", status)

asyncio.run(main())
```

### Explicit `tqdm` reporter

You can also provide a reporter explicitly. This is useful if you want to
control the bar description, layout, or lifetime yourself.

```python
import asyncio
import ltc_client

async def main():
    connection = ltc_client.make_stomp_connection(config["stomp"])

    with ltc_client.TqdmProgressReporter(
        desc=f"Job {job.title}",
        position=0,
    ) as reporter:
        status = await ltc_client.async_job_monitor(
            api,
            job,
            connection,
            progress_callback=reporter,
        )

    print("Final status:", status)

asyncio.run(main())
```

### Custom progress callback

For marimo, Jupyter widgets, logging, or any custom UI, pass a callback that
accepts a single `ProgressEvent`.

```python
import asyncio
import ltc_client

events = []

def on_progress(event: ltc_client.ProgressEvent):
    events.append(event)
    print(
        f"job={event.job_id} worker={event.worker} kind={event.kind} "
        f"done={event.done} total={event.total} status={event.status_name}"
    )

async def main():
    connection = ltc_client.make_stomp_connection(config["stomp"])

    status = await ltc_client.async_job_monitor(
        api,
        job,
        connection,
        progress_callback=on_progress,
    )

    print("Final status:", status)

asyncio.run(main())
```

### `ProgressEvent`

Callbacks receive a `ProgressEvent` object with fields such as:

- `job_id`
- `worker`
- `kind` (`"progress"`, `"status"`, `"remaining"`, `"time_remaining"`)
- `done`
- `total`
- `status`
- `status_name`
- `remaining_time`
- `raw`

### Monitoring multiple jobs

`monitor_jobs()` returns a dictionary mapping job IDs to final status names.
If no callback is provided, a batch `tqdm` progress bar is shown automatically.

```python
import asyncio
import ltc_client

async def main():
    connection = ltc_client.make_stomp_connection(config["stomp"])

    final_statuses = await ltc_client.monitor_jobs(
        api,
        jobs,
        connection,
    )

    for job_id, status in final_statuses.items():
        print(job_id, status)

asyncio.run(main())
```

### Marimo / reactive UI pattern

A simple marimo-friendly pattern is to store the latest event per job and render
your UI from that state.

```python
latest = {}

def on_progress(event: ltc_client.ProgressEvent):
    latest[event.job_id] = {
        "worker": event.worker,
        "kind": event.kind,
        "done": event.done,
        "total": event.total,
        "status": event.status_name,
        "remaining_time": event.remaining_time,
    }

await ltc_client.monitor_jobs(
    api,
    jobs,
    connection,
    progress_callback=on_progress,
)
```

This keeps `ltc_client` responsible for STOMP monitoring while your marimo app
controls presentation.

 4. Make a stomp connection
```python
 def make_connection(stomp_conf):
    ws_echo = create_connection(
        f"{stomp_conf["protocol"]}://{stomp_conf["host"]}:{stomp_conf["port"]}/ws"
    )
    connection = webstompy.StompConnection(connector=ws_echo)
    connection.connect(login=stomp_conf["user"], passcode=stomp_conf["password"])
    
    return connection
connection = make_connection(config["stomp"])
```


Development with Poetry https://python-poetry.org/docs/basic-usage/

Before starting development:
```bash
sudo apt install pipx
pipx install poetry
pipx ensurepath

# restart terminal

poetry config virtualenvs.in-project true
poetry install --with test,dev
```

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
git tag 0.2.58
git push --atomic origin main 0.2.58
```
