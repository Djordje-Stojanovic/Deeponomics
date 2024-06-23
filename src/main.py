from fastapi import FastAPI

app = FastAPI()

@app.get('/')
async def root():
    return {'message': 'Welcome to Deeponomics!'}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)