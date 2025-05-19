import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from langchain.chat_models import init_chat_model
from langchain.document_loaders import TextLoader
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langsmith import Client as LangSmithClient
from langsmith import traceable
from pydantic import BaseModel

load_dotenv()

project_name = os.getenv("LANGSMITH_PROJECT", "rag_project")

# Initialize FastAPI app
app = FastAPI(title="RAG Q&A API")

# Initialize LangSmith for observability
langsmith_client = LangSmithClient()

# Initialize the language model
llm = init_chat_model("gpt-4o-mini", model_provider="openai")

# Initialize embeddings
embeddings = OpenAIEmbeddings()

# Initialize vector store (ChromaDB)
vector_store = None


# Document ingestion function
async def ingest_documents(directory: str):
    global vector_store
    documents = []
    for filename in os.listdir(directory):
        if filename.endswith(".txt"):
            loader = TextLoader(os.path.join(directory, filename))
            documents.extend(loader.load())

    # Split documents into chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(documents)

    # Create vector store
    vector_store = Chroma.from_documents(chunks, embeddings)
    print(f"Ingested {len(chunks)} document chunks into vector store.")


# Pydantic model for API input
class QueryRequest(BaseModel):
    query: str


# Prompt template for RAG
prompt_template = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant. Answer the user's question based on the provided context. If the context doesn't contain relevant information, say so and provide a general answer.",
        ),
        ("human", "Context: {context} \n\n Questions: {question}"),
    ]
)


@traceable(run_type="chain", project_name=os.getenv("LANGSMITH_PROJECT", "rag_project"))
async def process_query(query: str):
    if vector_store is None:
        raise ValueError("Vector store not initialized. Please ingest documents first.")
    try:
        docs = vector_store.similarity_search(query, k=3)
        context = "\n".join([doc.page_content for doc in docs])
        # print(f"Query: {query}")
        # print(f"Retrieved context: {context}")
        prompt = prompt_template.format_messages(context=context, question=query)
        print(prompt)
        response = await llm.ainvoke(prompt)
        return response.content
    except Exception as e:
        print(f"Error processing query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


# FastAPI endpoint for querying
@app.post("/query")
async def query_endpoint(request: QueryRequest):
    response = await process_query(request.query)
    return {"answer": response}


# FastAPI endpoint for ingesting documents
@app.post("/ingest")
async def ingest_endpoint(directory: str = "./documents"):
    try:
        await ingest_documents(directory)
        return {"message": f"Successfully ingested documents from {directory}"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error ingesting documents: {str(e)}"
        )


# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Run the application
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
