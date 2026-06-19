import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from graph.workflow import workflow
from schemas import AnalyzeRequest, AnalyzeResponse

load_dotenv()

app = FastAPI(
    title=os.getenv("APP_NAME"),
    version=os.getenv("APP_VERSION"),
)


@app.get("/")
async def index() -> dict:
    return {
        "status": "success",
        "message": "DenuncIAI API",
    }


@app.get("/health")
async def healthcheck() -> dict:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    try:
        final_answer = None

        for chunk in workflow.stream(
            {"query": payload.query},
            stream_mode="updates",
        ):
            for step, data in chunk.items():
                answer = data.get("final_answer")
                if answer is not None:
                    final_answer = answer

        return AnalyzeResponse(query=payload.query, final_answer=final_answer)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Falha ao executar o workflow de analise.",
        ) from exc
