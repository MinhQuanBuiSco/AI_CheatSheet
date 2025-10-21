# LLM Evaluation Demo

A full-stack application for evaluating Large Language Models on various benchmark datasets using vLLM for model serving.

## Features

- **Multiple Benchmark Datasets**: Evaluate models on MMLU, GSM8K, HumanEval, HellaSwag, TruthfulQA, MATH-500, and GPQA
- **Interactive UI**: Select datasets, view example prompts, and see evaluation results
- **Model Selection**: Load different models dynamically via vLLM
- **Automated Evaluation**: Compare model predictions with gold answers using dataset-specific metrics
- **Real-time Results**: View gold answers, predicted answers, and scores

## Architecture

### Backend (Python + FastAPI)
- FastAPI server with REST API endpoints
- Integration with vLLM for model inference
- Dataset loaders for 7 popular benchmarks
- Evaluation metrics tailored to each dataset type

### Frontend (React + TypeScript + Vite)
- Modern React UI with TypeScript
- Tailwind CSS for styling
- Axios for API communication

## Prerequisites

- **Python 3.12+** (for backend)
- **Node.js 22+** (for frontend)
- **GPU** (optional - recommended for faster inference, CPU also works)
- **MOCK MODE** available for testing without loading real models

## Setup Instructions

### 1. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Install dependencies using uv (recommended) or pip
uv sync
# or
pip install -e .
```

**Option A: Run in MOCK MODE (for testing without loading models)**
```bash
# Quick start with mock predictions (recommended for first-time setup)
./run_mock.sh
# or
MOCK_MODE=true uvicorn backend.main:app --reload --port 8000
```

**Option B: Run with Hugging Face Models (Real Inference)**
```bash
# Models will be downloaded from Hugging Face and run locally
uvicorn backend.main:app --reload --port 8000
```

The backend API will be available at `http://localhost:8000`

### 2. Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Run the development server
npm run dev
```

The frontend will be available at `http://localhost:5173`

### 3. Install Dependencies and Models

After installing backend dependencies (step 1), models will be automatically downloaded from Hugging Face when you first load them in the UI.

**Note**:
- Models are cached in `~/.cache/huggingface/` after first download
- Smaller models like `microsoft/phi-2` (~5GB) work well on CPU
- Larger models benefit from GPU (CUDA support)

## Usage

### Quick Start (MOCK MODE)
1. **Start Backend**: `cd backend && ./run_mock.sh`
2. **Start Frontend**: `cd frontend && npm run dev`
3. **Open Browser**: Navigate to `http://localhost:5173`
4. Load any model (simulated) and start testing!

### Production Mode (Real Hugging Face Models)
1. **Start Backend**: `cd backend && uvicorn backend.main:app --reload --port 8000`
2. **Start Frontend**: `cd frontend && npm run dev`
3. **Open Browser**: Navigate to `http://localhost:5173`
4. **Select and Load Model**: Choose a model from the dropdown (e.g., `microsoft/phi-2`)
5. **Wait for Download**: First time will download the model from Hugging Face
6. **Start Evaluating**: Select dataset, load example, and run predictions!

### Workflow

1. **Load Model**:
   - Select a model from the dropdown or enter a custom Hugging Face model ID
   - Click "Load Model" (first time will download ~3-15GB depending on model)
   - Wait for model to load (shown in terminal)

2. **Select Dataset**:
   - Choose from 7 available benchmarks (MMLU, GSM8K, HumanEval, etc.)
   - Click "Load Random Example"

3. **Evaluate**:
   - Review the example prompt
   - Click "🚀 Run Prediction"
   - View results showing:
     - **Model's Prediction** (highlighted)
     - **Gold Answer** (correct answer)
     - **Score** (0% or 100%)
     - **Evaluation Details**

## API Endpoints

- `GET /` - API information
- `GET /datasets` - List available datasets
- `GET /datasets/{name}/example` - Get random example from dataset
- `POST /evaluate` - Evaluate model prediction
- `POST /model/load` - Load/configure model
- `GET /model/current` - Get current model info

## Supported Datasets

| Dataset | Type | Description |
|---------|------|-------------|
| **MMLU** | Multiple Choice | 57 subjects across STEM, humanities, social sciences |
| **GSM8K** | Math | Grade school math word problems |
| **HumanEval** | Code Generation | Python programming problems |
| **HellaSwag** | Multiple Choice | Commonsense reasoning |
| **TruthfulQA** | Multiple Choice | Questions testing truthfulness |
| **MATH-500** | Math | Competition mathematics problems |
| **GPQA** | Multiple Choice | Graduate-level science questions |

## Evaluation Metrics

- **Multiple Choice** (MMLU, HellaSwag, TruthfulQA, GPQA): Accuracy
- **Math** (GSM8K, MATH-500): Numeric match with tolerance / String match
- **Code** (HumanEval): Simplified similarity (Note: Production would use unit test execution)

## Configuration

### Frontend Environment Variables

Create a `.env` file in the `frontend` directory:

```env
VITE_API_URL=http://localhost:8000
```

### Backend Configuration

The backend can be configured through environment variables:

- **MOCK_MODE**: Set to `true` to run without vLLM (simulated predictions)
  - Multiple choice: Returns random A/B/C/D
  - Math questions: Returns random numbers
  - Code questions: Returns simple code snippets
- **Default Port**: 8000
- **CORS**: Currently allows all origins (configure for production)

Example:
```bash
MOCK_MODE=true uvicorn backend.main:app --reload --port 8000
```

## Development

### Backend Development

```bash
cd backend

# Install dev dependencies
uv sync

# Run with auto-reload
uvicorn backend.main:app --reload

# Run tests (if available)
pytest
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Run dev server with hot reload
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Troubleshooting

### Backend Issues

- **Dataset Loading Errors**: Some datasets are loaded in streaming mode. The first load may take time.
- **vLLM Connection**: Ensure vLLM server is running and accessible at the configured URL.

### Frontend Issues

- **API Connection**: Check that backend is running on `http://localhost:8000`
- **CORS Errors**: Ensure CORS is properly configured in backend

### Model Loading

- **Model Not Loading**: Verify vLLM server is running and model name is correct
- **Timeout**: Large models may take time to load in vLLM

## Future Enhancements

- [ ] Batch evaluation support
- [ ] Custom dataset upload
- [ ] Persistent evaluation history
- [ ] Advanced metrics and visualizations
- [ ] User authentication
- [ ] Multi-model comparison
- [ ] Export results to CSV/JSON

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
