from fastapi import FastAPI

app = FastAPI(title="Notes API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
