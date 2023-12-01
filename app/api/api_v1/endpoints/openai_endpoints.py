from datetime import timedelta
from typing import Any
from fastapi import FastAPI, APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from langchain.memory import CassandraChatMessageHistory, ConversationBufferMemory
from langchain.llms import OpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
import json
import openai
import time
import os
import sys

router = APIRouter()

# Getting OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
if not len(OPENAI_API_KEY):
    print("Please set OPENAI_API_KEY environment variable. Exiting.")
    sys.exit(1)

openai.api_key = OPENAI_API_KEY

# Defining error in case of 503 from OpenAI
error503 = "OpenAI server is busy, try again later"

@router.post("/stream", )
async def stream_prompt(human_input_str: str) -> Any:
    print(human_input_str)
    cloud_config= {
    'secure_connect_bundle': 'app/secure-connect-ripple-ai.zip'
    }

    with open("app/ripple_ai-token.json") as f:
        secrets = json.load(f)

    CLIENT_ID = secrets["clientId"]
    CLIENT_SECRET = secrets["secret"]
    ASTRA_DB_KEYSPACE = "database"

    auth_provider = PlainTextAuthProvider(CLIENT_ID, CLIENT_SECRET)
    cluster = Cluster(cloud=cloud_config, auth_provider=auth_provider)
    session = cluster.connect()

    # this is creating memory of the story and saving it for 60 mins
    message_history = CassandraChatMessageHistory(
        session_id = "ripplesession",
        session = session,
        keyspace = ASTRA_DB_KEYSPACE,
        ttl_seconds = 3600
    )

    message_history.clear()

    cass_buff_memory = ConversationBufferMemory(
        memory_key = "chat_history",
        chat_memory = message_history
    )

    #template given to AI 
    template = """
    In a world where time travel is possible, you discover a mysterious journal that allows you to revisit pivotal moments in your life. However, each alteration you make has unforeseen consequences, creating a ripple effect that changes your present reality.

    You start with a choice: travel back to a traumatic event in your childhood and prevent it, potentially erasing years of pain, or let the past remain unchanged and focus on your present life. The journal warns that altering the past may lead to unintended and unpredictable outcomes.

    As you delve deeper into your own history, you face increasingly difficult decisions. Do you mend broken relationships, pursue missed opportunities, or right past wrongs? Each choice alters the course of your life in unexpected ways.

    Your goal is to navigate this temporal labyrinth and reach a resolution. Will your journey through time lead to a brighter, happier existence, or will the ever-expanding butterfly effect result in a darker, more twisted reality? The power to shape your destiny is in your hands, but be cautious – the consequences of playing with time are profound and irreversible.

    Here are some rules to follow:
    1. Always begin by asking for a name.
    2. Always end each response with a question for the user.
    3. Stories should lead to an ending, whether that be good or bad.

    Here is the chat history, use this to understand what to say next: {chat_history}
    Human: {human_input}
    AI:
    """
    try:

        prompt = PromptTemplate(
            input_variables = ["chat_history", "human_input"],
            template = template
        )

        # initializing connection to openai
        llm = OpenAI(openai_api_key=OPENAI_API_KEY)
        llm_chain = LLMChain(
            llm = llm,
            prompt = prompt,
            memory = cass_buff_memory
        )

        response = llm_chain.predict(human_input=human_input_str)
        
    except Exception as e:
        print("Error in creating campaigns from openAI:", str(e))
        raise HTTPException(503, error503)
    
    return StreamingResponse(get_response_openai(response), media_type="text/event-stream")

def get_response_openai(response: str):
    # print(response)
    current_content = response
    try:
        yield current_content
    except Exception as e:
        print("OpenAI Response (Streaming) Error: " + str(e))
        raise HTTPException(503, error503)


