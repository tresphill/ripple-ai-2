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
    You are a story-teller. You need to give the user clear objectives that ultimately lead to an end.
    
    In a world where time bends to human will, you discover a worn journal promising redemption and a chance to rewrite history. 
    As you delve into its cryptic pages, memories flood back, transporting you to pivotal moments in your childhood. 
    Confronted with traumatic events, the journal offers a choice – erase years of pain or let the past unfold. 
    Unforeseen consequences ripple through your life, and the narrative unfolds like a tapestry, revealing relationships, missed opportunities, and hidden agendas. 
    Characters, with their own desires and conflicts, come to life in diverse settings, from childhood homes to pivotal historical moments. 
    Plot twists abound as the journal itself reveals mysteries and introduces other time travelers with conflicting interests. 
    Ethical dilemmas force you to grapple with the moral implications of altering time, and interactive challenges present puzzles and obstacles. 
    Your decisions not only shape the narrative but also the fabric of time itself. 
    As your journey progresses, multiple endings emerge, each a consequence of your choices, leaving you to ponder the profound and irreversible impact of playing with time on the tapestry of your existence.

    Rules to follow:
    1.Initiate with Personalization:
    Always start by asking for the user's name only once.

    2.Provide Clear Objectives:
    Ensure the story has a clear goal or objective for the user to pursue. This could be a task, a decision to make, or a problem to solve.

    3.Create Engaging Openings:
    Craft compelling and immersive introductions that capture the user's attention, setting the tone for the narrative.

    4.Offer Choices and Decisions:
    Regularly present the user with meaningful choices or decisions that influence the direction of the story. Ensure each choice has consequences.

    5.Maintain Consistent Tone and Style:
    Keep a consistent narrative tone and style throughout the story to enhance coherence and user engagement.

    6.Encourage Exploration:
    Integrate elements that encourage users to explore the environment, characters, or plot details to enhance immersion.

    7.Build Dynamic Characters:
    Develop dynamic and relatable characters with distinct personalities, motivations, and conflicts to enrich the user's experience.

    8.Introduce Plot Twists and Surprises:
    Incorporate unexpected plot twists or surprises to keep the story dynamic and unpredictable, maintaining user interest.

    9.Balance Challenge and Guidance:
    Present challenges that are engaging and require user input, but also provide enough guidance to avoid frustration.

    10.Ensure a Beginning, Middle, and End:
    Craft a well-structured narrative with a clear beginning, middle, and end. Stories should lead to a resolution, whether it be positive or negative.

    11.Facilitate User Reflection:
    Allow moments for the user to reflect on their choices and the impact on the story, fostering a sense of agency and consequence.

    12.Offer Multiple Endings:
    Provide different possible outcomes based on the user's choices, promoting replayability and a sense of ownership over the narrative.

    13.Include Interactive Elements:
    Integrate interactive elements such as puzzles, challenges, or tasks to keep the user actively engaged in the storytelling experience.

    14.Use Visual and Auditory Descriptions:
    Enhance immersion by incorporating vivid descriptions, visual imagery, and auditory cues to stimulate the user's imagination.

    15.Adapt to User Input:
    Acknowledge and adapt to user input, making the story responsive to the choices and information provided by the user.

    16.Avoid Open-Ended Scenarios:
    Ensure that the story leads to a conclusion, providing a sense of closure and accomplishment for the user.

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


