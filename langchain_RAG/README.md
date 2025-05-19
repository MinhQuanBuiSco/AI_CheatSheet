# 🧠 RAG Q&A API with LangChain, FastAPI & LangSmith

A lightweight Retrieval-Augmented Generation (RAG) API built using **FastAPI**, **LangChain**, **LangSmith**, and **OpenAI**. This app allows you to upload documents and query them with GPT-powered answers.

---

## 🚀 Features

- 📄 **Document Ingestion** with chunking & embedding (ChromaDB + OpenAI Embeddings)
- 🤖 **GPT-4o-mini Answering Engine** with context-aware prompting
- 🔍 **Semantic Search** using vector similarity
- 📊 **LangSmith Integration** for observability and tracing
- ⚡ FastAPI-powered RESTful API with async support

---

## 📁 Project Structure

```
.
├── main.py            # FastAPI app with endpoints
├── documents/         # Directory for your .txt files
├── .env               # Environment variables
└── requirements.txt   # Python dependencies
```

---

## ⚙️ Setup

### 1. Install dependencies

```bash
uv venv --python 3.10
uv sync
```

### 2. Prepare your `.env` file

```env
OPENAI_API_KEY=your_openai_key
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_PROJECT=rag_project
```

### 3. Add your documents

Place `.txt` files in the `./documents` directory. Example:

```
documents/
└── product_policy.txt
```

---

## ▶️ Running the App

### Local development

```bash
python main.py
```

The app will be available at:  
`http://localhost:8000`

---

## 📈 Observability with LangSmith

Traces of each query and document ingestion are sent to your [LangSmith](https://smith.langchain.com/) dashboard for easy debugging and monitoring.

---

## 📄 License

MIT License. Free to use and adapt for personal and commercial projects.

---

## 🔁 Using `curl` to Test API

### Ingest Documents

Default ingestion from `./documents`:

```bash
curl -X POST "http://localhost:8000/ingest"
```

### Ingest from Custom Directory (Optional)

```bash
curl -X POST "http://localhost:8000/ingest" \
     -H "Content-Type: application/json" \
     -d '{"directory": "./your-custom-folder"}'
```

> ⚠️ Ensure the directory exists and contains `.txt` files.


### Query

```bash
curl -X POST http://localhost:8000/query -d '{"query": "Summary the product policy please"}' -H "Content-Type: application/json"
```