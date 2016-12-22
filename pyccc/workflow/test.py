import pyccc
from pyccc import workflow

app = workflow.Workflow('my app',
                        default_docker_image='moldesign_complete')


@app.task(n=app.input('startingnumber'))
def addone(n):
    return {'num': n+1}


@app.task(num=addone['num'],
          factor=3)
def multiply(num, factor):
    return {'num': num*factor}


@app.task(num=multiply['num'])
def printnum(num):
    print num


app.set_outputs(result=multiply['num'])
engine = pyccc.Docker()
runner = workflow.SerialCCCRunner(app, engine, startingnumber=1)
result = runner.run()
print result
