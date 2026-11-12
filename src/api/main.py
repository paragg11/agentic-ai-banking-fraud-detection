
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.agents.fraud_investigation_agent import FraudInvestigationAgent

app = FastAPI(
    title="AI Banking Fraud Detection API",
    description="Graph-based fraud detection and AI investigation",
    version="1.0.0"
)


class InvestigationRequest(BaseModel):
    transaction_id: str


@app.get("/")
def home():
    return {
        "message": "Banking Fraud Detection API is running"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/investigate")
def investigate(request: InvestigationRequest):

    agent = None

    try:
        agent = FraudInvestigationAgent()

        result = agent.run_investigation(
            request.transaction_id
        )

        if "error" in result:
            raise HTTPException(
                status_code=500,
                detail=result["error"]
            )

        return {
            "transaction_id": request.transaction_id,
            "status": "completed",
            "investigation": result
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )

    finally:
        if agent:
            agent.close()
