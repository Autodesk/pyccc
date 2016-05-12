# PyBioWorkflow
A high-level python interface for running jobs using bio/nano workflow manager.

To run a job:
1. Specify where the job will run: create a `Provider` instance from the `providers` module:
```python
provider = providers.Subprocess()
# or maybe
provider = providers.BioNanoPlatform(host='platform.bionano.autodesk.com')
```

2. Launch the job:
```python
job = provider.launch('docker_image_name',command,input_files,output_files)
```

Here's how to run a job with the workflow manager.<br>
To run it locally,  replace `BioNanoPlatform` with `Subprocess`.<br>
To run it in a docker container, replace `BioNanoPlatform` with `Docker`.
```python 
from bioplatform import providers, files
provider = providers.BioNanoPlatform(host='platform.bionano.autodesk.com:8080')
input_files = {'myfile.txt': files.StringContainer('abc123','tempname') }
job = provider.launch('ubuntu',
                     'cp -v myfile.txt newfile.txt && echo done!',
                     inputs=input_files)

job.wait()
print job.stdout 
#prints:
#  >myfile.txt -> newfile.txt
#  >done!

print job.get_output('newfile.txt').contents.strip()
#prints:
#  >abc123
```

