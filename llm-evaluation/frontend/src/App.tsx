import { useState, useEffect } from 'react';
import { apiClient } from './api';
import type {
  DatasetInfo,
  Example,
  EvaluateResponse,
  ModelInfo,
  ModelOption,
} from './types';

function App() {
  // State
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<string>('');
  const [currentExample, setCurrentExample] = useState<Example | null>(null);
  const [systemPrompt, setSystemPrompt] = useState<string>('');
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [evaluationResult, setEvaluationResult] = useState<EvaluateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  // Model configuration
  const [availableModels, setAvailableModels] = useState<ModelOption[]>([]);
  const [modelName, setModelName] = useState('');
  const [useCustomModel, setUseCustomModel] = useState(false);
  const [vllmUrl, setVllmUrl] = useState('http://localhost:8001');

  // Load datasets and models on mount
  useEffect(() => {
    loadDatasets();
    loadModels();
    loadCurrentModel();
  }, []);

  const loadDatasets = async () => {
    try {
      const data = await apiClient.getDatasets();
      setDatasets(data);
      if (data.length > 0) {
        setSelectedDataset(data[0].name);
      }
    } catch (err) {
      setError('Failed to load datasets');
      console.error(err);
    }
  };

  const loadModels = async () => {
    try {
      const data = await apiClient.getModels();
      setAvailableModels(data);
      if (data.length > 0) {
        setModelName(data[0].name);
      }
    } catch (err) {
      console.error('Failed to load models:', err);
    }
  };

  const loadCurrentModel = async () => {
    try {
      const model = await apiClient.getCurrentModel();
      setModelInfo(model);
    } catch (err) {
      console.error('Failed to load current model:', err);
    }
  };

  const handleDatasetChange = async (datasetName: string) => {
    setSelectedDataset(datasetName);
    setCurrentExample(null);
    setEvaluationResult(null);
    setError('');
  };

  const loadExample = async () => {
    if (!selectedDataset) return;

    setLoading(true);
    setError('');
    setEvaluationResult(null);

    try {
      const example = await apiClient.getExample(selectedDataset);
      setCurrentExample(example);
      setSystemPrompt(example.system_prompt);
    } catch (err) {
      setError('Failed to load example');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleLoadModel = async () => {
    if (!modelName) {
      setError('Please provide a model name');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const model = await apiClient.loadModel({
        model_name: modelName,
        vllm_url: vllmUrl || undefined,
      });
      setModelInfo(model);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load model');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleEvaluate = async () => {
    if (!currentExample) return;

    if (!modelInfo?.loaded) {
      setError('Please load a model first');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const result = await apiClient.evaluate({
        dataset: currentExample.dataset,
        prompt: currentExample.prompt,
        system_prompt: systemPrompt,
        choices: currentExample.choices,
        gold_answer: currentExample.gold_answer,
      });
      setEvaluationResult(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to evaluate');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-4xl font-bold text-gray-800 dark:text-white mb-8 text-center">
          LLM Evaluation Demo
        </h1>

        {/* Model Configuration */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-2xl font-semibold text-gray-800 dark:text-white mb-4">
            Model Configuration
          </h2>

          {modelInfo?.loaded ? (
            <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-700 rounded p-4 mb-4">
              <p className="text-green-800 dark:text-green-200">
                <strong>🤗 Model Loaded:</strong> {modelInfo.model_name}
              </p>
              <p className="text-green-800 dark:text-green-200 text-sm">
                <strong>Backend:</strong> {modelInfo.backend || 'Hugging Face'} | <strong>Device:</strong> {modelInfo.device || 'local'}
              </p>
            </div>
          ) : (
            <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded p-4 mb-4">
              <p className="text-yellow-800 dark:text-yellow-200">
                No model loaded. Select a model and click "Load Model" to begin.
              </p>
              <p className="text-yellow-800 dark:text-yellow-200 text-xs mt-1">
                Models will be downloaded from Hugging Face and run locally.
              </p>
            </div>
          )}

          <div className="mb-4">
            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={useCustomModel}
                onChange={(e) => setUseCustomModel(e.target.checked)}
                className="mr-2 h-4 w-4"
              />
              <span className="text-sm text-gray-700 dark:text-gray-300">
                Use custom model name
              </span>
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Model Name
            </label>
            {useCustomModel ? (
              <input
                type="text"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                placeholder="e.g., microsoft/phi-2"
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
              />
            ) : (
              <select
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
              >
                {availableModels.map((model) => (
                  <option key={model.name} value={model.name}>
                    {model.display_name} - {model.description}
                  </option>
                ))}
              </select>
            )}
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
              💡 Model will be downloaded from Hugging Face and cached locally
            </p>
          </div>
          <button
            onClick={handleLoadModel}
            disabled={loading}
            className="mt-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-6 rounded-lg disabled:opacity-50"
          >
            {loading ? 'Loading...' : 'Load Model'}
          </button>
        </div>

        {/* Dataset Selection */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 mb-6">
          <h2 className="text-2xl font-semibold text-gray-800 dark:text-white mb-4">
            Select Dataset
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {datasets.map((dataset) => (
              <button
                key={dataset.name}
                onClick={() => handleDatasetChange(dataset.name)}
                className={`p-4 rounded-lg border-2 transition-all ${
                  selectedDataset === dataset.name
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-blue-300'
                }`}
              >
                <h3 className="font-semibold text-lg text-gray-800 dark:text-white">
                  {dataset.name}
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  {dataset.description}
                </p>
                <span className="inline-block mt-2 px-2 py-1 text-xs bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded">
                  {dataset.task_type}
                </span>
              </button>
            ))}
          </div>

          <button
            onClick={loadExample}
            disabled={!selectedDataset || loading}
            className="mt-6 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 px-6 rounded-lg disabled:opacity-50"
          >
            {loading ? 'Loading...' : 'Load Random Example'}
          </button>
        </div>

        {/* Example Display */}
        {currentExample && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 mb-6">
            <h2 className="text-2xl font-semibold text-gray-800 dark:text-white mb-4">
              Example from {currentExample.dataset}
            </h2>

            {/* System Prompt Editor */}
            <div className="mb-4">
              <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                📝 System Prompt (Editable)
              </label>
              <textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                rows={3}
                className="w-full px-4 py-3 border border-blue-300 dark:border-blue-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white font-mono text-sm"
                placeholder="Enter system prompt to guide the model..."
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                💡 Edit this prompt to customize how the model should respond
              </p>
            </div>

            {/* User Prompt */}
            <div className="mb-4">
              <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                ❓ Question / Prompt
              </label>
              <div className="bg-gray-50 dark:bg-gray-900 rounded p-4 border border-gray-200 dark:border-gray-700">
                <pre className="whitespace-pre-wrap text-gray-800 dark:text-gray-200 font-mono text-sm">
                  {currentExample.prompt}
                </pre>
              </div>
            </div>

            {currentExample.metadata && (
              <div className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                <strong>Metadata:</strong> {JSON.stringify(currentExample.metadata)}
              </div>
            )}

            <button
              onClick={handleEvaluate}
              disabled={loading || !modelInfo?.loaded}
              className="bg-green-600 hover:bg-green-700 text-white font-semibold py-3 px-6 rounded-lg disabled:opacity-50 transition-all"
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Running Prediction...
                </span>
              ) : (
                '🚀 Run Prediction'
              )}
            </button>
          </div>
        )}

        {/* Prediction & Evaluation Results */}
        {evaluationResult && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
            <h2 className="text-2xl font-semibold text-gray-800 dark:text-white mb-6">
              🤖 Prediction & Evaluation Results
            </h2>

            {/* Model Prediction - Prominent Display */}
            <div className="mb-6 p-6 bg-gradient-to-r from-purple-50 to-pink-50 dark:from-purple-900/20 dark:to-pink-900/20 rounded-lg border-2 border-purple-200 dark:border-purple-700">
              <h3 className="text-lg font-bold text-purple-900 dark:text-purple-200 mb-3 flex items-center">
                <span className="mr-2">🎯</span>
                Model Prediction
              </h3>
              <div className="bg-white dark:bg-gray-800 rounded p-4">
                <p className="text-xl font-semibold text-gray-800 dark:text-white break-words">
                  {evaluationResult.predicted_answer}
                </p>
              </div>
            </div>

            {/* Comparison Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 border border-blue-200 dark:border-blue-700">
                <h3 className="text-sm font-medium text-blue-900 dark:text-blue-300 mb-2 flex items-center">
                  <span className="mr-1">✅</span>
                  Gold Answer
                </h3>
                <p className="text-lg font-semibold text-gray-800 dark:text-white break-words">
                  {evaluationResult.gold_answer}
                </p>
              </div>

              <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-4 border border-purple-200 dark:border-purple-700">
                <h3 className="text-sm font-medium text-purple-900 dark:text-purple-300 mb-2 flex items-center">
                  <span className="mr-1">🤖</span>
                  Model Answer
                </h3>
                <p className="text-lg font-semibold text-gray-800 dark:text-white break-words">
                  {evaluationResult.predicted_answer}
                </p>
              </div>

              <div
                className={`rounded-lg p-4 border-2 ${
                  evaluationResult.score === 1
                    ? 'bg-green-50 dark:bg-green-900/20 border-green-500'
                    : 'bg-red-50 dark:bg-red-900/20 border-red-500'
                }`}
              >
                <h3 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2 flex items-center">
                  <span className="mr-1">{evaluationResult.score === 1 ? '🎉' : '📊'}</span>
                  Score ({evaluationResult.metric})
                </h3>
                <p className="text-4xl font-bold text-gray-800 dark:text-white">
                  {(evaluationResult.score * 100).toFixed(0)}%
                </p>
                <p className="text-sm mt-2 text-gray-600 dark:text-gray-400">
                  {evaluationResult.score === 1 ? 'Correct! ✓' : 'Incorrect ✗'}
                </p>
              </div>
            </div>

            {/* Evaluation Details */}
            {evaluationResult.details && (
              <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3 flex items-center">
                  <span className="mr-1">📋</span>
                  Evaluation Details
                </h3>
                <pre className="text-xs text-gray-600 dark:text-gray-400 overflow-x-auto">
                  {JSON.stringify(evaluationResult.details, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded p-4 mb-6">
            <p className="text-red-800 dark:text-red-200">{error}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
