from workflow import Workflow

app = Workflow('my app',
               default_docker_image='moldesign_complete')


@app.task(n=app.input('startingnumber'))
def addone(n):
    return {'num': n+1}


@app.task
def multiplier(num):
    return {'num': num*2}


@app.task(num=multiplier['num'])
def printnum(num):
    print num


multiplier.set_input_sources(num=addone['num'])

