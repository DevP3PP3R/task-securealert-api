from fastapi import FastAPI

app = FastAPI(title="SecureAlert API")


@app.get("/")
def read_root():
    return {"message": "SecureAlert API is running"}