"""Main entrypoint for the app."""

import asyncio
from typing import Any, List, Optional, Union
from uuid import UUID

import langsmith
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from langserve import APIHandler, add_routes

# from langsmith import Client
from pydantic import BaseModel

from agent import create_agent_executor
from agent import llm_agent
from langchain.memory import ConversationBufferMemory

# client = Client()
origins = [
    "*",
    "http://localhost",
    "http://localhost:3000",
    "http://192.168.3.6:3000",
]
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

from langchain_core.messages import AIMessage, FunctionMessage, HumanMessage


class Input(BaseModel):
    input: str
    image_urls: list[str]
    chat_history: List[Union[HumanMessage, AIMessage, FunctionMessage]]


class Output(BaseModel):
    output: Any

chat_memories = {}
agent_executors = {}


@app.post("/chat/stream", include_in_schema=False)
async def simple_invoke(request: Request) -> Response:
    """Handle a request."""
    # The API Handler validates the parts of the request
    # that are used by the runnnable (e.g., input, config fields)
    body = await request.json()
    conversation_id = body["config"]["metadata"]["conversation_id"]
    is_multimodal = body["config"]["metadata"]["is_multimodal"]
    image_urls = body["input"]["image_urls"]
    if conversation_id in chat_memories:
        # agent_executor = agent_executors[conversation_id]
        memory = chat_memories[conversation_id]
        agent_executor = create_agent_executor(
            llm_agent=llm_agent,
            memory=memory,
            is_multimodal=is_multimodal,
            image_urls=image_urls,
        )
        agent_executors[conversation_id] = {
            "executor": agent_executor,
            "is_multimodal": is_multimodal,
        }
        api_handler = APIHandler(
            agent_executor.with_types(input_type=Input, output_type=Output),
            path="/chat",
            # config_keys=["metadata", "configurable", "tags", "llm"],
        )
    else:
        memory = ConversationBufferMemory(
            input_key="input", memory_key="chat_history", return_messages=True
        )
        agent_executor = create_agent_executor(
            llm_agent=llm_agent,
            memory=memory,
            is_multimodal=is_multimodal,
            image_urls=image_urls,
        )
        chat_memories[conversation_id] = memory
        agent_executors[conversation_id] = {
            "executor": agent_executor,
            "is_multimodal": is_multimodal,
        }
        api_handler = APIHandler(
            agent_executor.with_types(input_type=Input, output_type=Output),
            path="/chat",
            # config_keys=["metadata", "configurable", "tags", "llm"],
        )
    return await api_handler.astream_events(request)


# add_routes(
#     app,
#     agent_executor.with_types(input_type=Input, output_type=Output),
#     path="/chat",
#     input_type=Input,
#     output_type=Output,
#     # config_keys=["metadata", "configurable", "tags"],
# )


class SendFeedbackBody(BaseModel):
    run_id: UUID
    key: str = "user_score"

    score: Union[float, int, bool, None] = None
    feedback_id: Optional[UUID] = None
    comment: Optional[str] = None


@app.post("/feedback")
async def send_feedback(body: SendFeedbackBody):
    # client.create_feedback(
    #     body.run_id,
    #     body.key,
    #     score=body.score,
    #     comment=body.comment,
    #     feedback_id=body.feedback_id,
    # )
    return {"result": "posted feedback successfully", "code": 200}


class UpdateFeedbackBody(BaseModel):
    feedback_id: UUID
    score: Union[float, int, bool, None] = None
    comment: Optional[str] = None


@app.patch("/feedback")
async def update_feedback(body: UpdateFeedbackBody):
    feedback_id = body.feedback_id
    if feedback_id is None:
        return {
            "result": "No feedback ID provided",
            "code": 400,
        }
    # client.update_feedback(
    #     feedback_id,
    #     score=body.score,
    #     comment=body.comment,
    # )
    return {"result": "patched feedback successfully", "code": 200}


# TODO: Update when async API is available
async def _arun(func, *args, **kwargs):
    return await asyncio.get_running_loop().run_in_executor(None, func, *args, **kwargs)


# async def aget_trace_url(run_id: str) -> str:
#     for i in range(5):
#         try:
#             await _arun(client.read_run, run_id)
#             break
#         except langsmith.utils.LangSmithError:
#             await asyncio.sleep(1**i)

#     if await _arun(client.run_is_shared, run_id):
#         return await _arun(client.read_run_shared_link, run_id)
#     return await _arun(client.share_run, run_id)


class GetTraceBody(BaseModel):
    run_id: UUID


# @app.post("/get_trace")
# async def get_trace(body: GetTraceBody):
#     run_id = body.run_id
#     if run_id is None:
#         return {
#             "result": "No LangSmith run ID provided",
#             "code": 400,
#         }
#     return await aget_trace_url(str(run_id))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
