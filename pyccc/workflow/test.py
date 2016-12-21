from pyccc import workflow

app = workflow.Workflow('my app',
                        default_docker_image='moldesign_complete')


@app.task(n=app.input('startingnumber'))
def addone(n):
    return {'num': n+1}


@app.task(num=addone['num'])
def multiplier(num):
    return {'num': num*2}


@app.task(num=multiplier['num'])
def printnum(num):
    print num


app.set_outputs(result=multiplier['num'])

runner = workflow.SerialWorkflowExecutor(app, startingnumber=4)
result = runner.run()
print result
