from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Prueba exitosa"}

@app.post("/test/")
def create_test():
    return {"message": "Endpoint funcionando"}
