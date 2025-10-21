import { useState, useEffect, useRef } from 'react';
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
  const [streamingTokens, setStreamingTokens] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState(false);

  // Ref to accumulate tokens in real-time
  const tokenBufferRef = useRef<string>('');
  const streamingIntervalRef = useRef<number | null>(null);

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

  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
      if (streamingIntervalRef.current) {
        clearInterval(streamingIntervalRef.current);
      }
    };
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
    setStreamingTokens('');
    setIsStreaming(false);
    setError('');
  };

  const loadExample = async () => {
    if (!selectedDataset) return;

    setLoading(true);
    setError('');
    setEvaluationResult(null);
    setStreamingTokens('');
    setIsStreaming(false);

    // Clear any ongoing streaming
    if (streamingIntervalRef.current) {
      clearInterval(streamingIntervalRef.current);
      streamingIntervalRef.current = null;
    }
    tokenBufferRef.current = '';

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
    setIsStreaming(true);
    setError('');
    setStreamingTokens('');
    setEvaluationResult(null);
    tokenBufferRef.current = '';

    // Start render loop to update UI from buffer
    if (streamingIntervalRef.current) {
      clearInterval(streamingIntervalRef.current);
    }

    streamingIntervalRef.current = window.setInterval(() => {
      if (tokenBufferRef.current !== '') {
        setStreamingTokens(tokenBufferRef.current);
      }
    }, 50); // Update UI every 50ms

    try {
      await apiClient.evaluateStream(
        {
          dataset: currentExample.dataset,
          prompt: currentExample.prompt,
          system_prompt: systemPrompt,
          choices: currentExample.choices,
          gold_answer: currentExample.gold_answer,
        },
        // onToken callback - accumulate in buffer
        (token: string) => {
          tokenBufferRef.current += token;
        },
        // onResult callback
        (result: EvaluateResponse) => {
          // Stop render loop
          if (streamingIntervalRef.current) {
            clearInterval(streamingIntervalRef.current);
            streamingIntervalRef.current = null;
          }
          // Final update
          setStreamingTokens(tokenBufferRef.current);
          setEvaluationResult(result);
          setIsStreaming(false);
          setLoading(false);
        },
        // onError callback
        (errorMsg: string) => {
          // Stop render loop
          if (streamingIntervalRef.current) {
            clearInterval(streamingIntervalRef.current);
            streamingIntervalRef.current = null;
          }
          setError(errorMsg);
          setIsStreaming(false);
          setLoading(false);
        }
      );
    } catch (err: any) {
      setError(err.message || 'Failed to evaluate');
      // Stop render loop
      if (streamingIntervalRef.current) {
        clearInterval(streamingIntervalRef.current);
        streamingIntervalRef.current = null;
      }
      setIsStreaming(false);
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-purple-50 to-indigo-100 dark:from-gray-950 dark:via-purple-950 dark:to-slate-900 p-4 md:p-8">
      {/* Animated gradient background overlay */}
      <div className="fixed inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-purple-200/20 via-transparent to-transparent pointer-events-none"></div>

      <div className="max-w-7xl mx-auto relative z-10">
        {/* Header with glassmorphism */}
        <div className="mb-8 backdrop-blur-xl bg-white/40 dark:bg-gray-900/40 rounded-3xl p-8 border border-white/20 dark:border-gray-700/30 shadow-2xl">
          <div className="flex items-center justify-center gap-4 mb-2">
            <div className="text-5xl">🤖</div>
            <h1 className="text-5xl md:text-6xl font-black bg-gradient-to-r from-purple-600 via-pink-600 to-indigo-600 bg-clip-text text-transparent">
              LLM Evaluation
            </h1>
          </div>
          <p className="text-center text-gray-600 dark:text-gray-300 text-lg font-medium">
            Benchmark AI Models on Industry Standards
          </p>
        </div>

        {/* Model Configuration - Glassmorphism Card */}
        <div className="backdrop-blur-xl bg-white/60 dark:bg-gray-900/60 rounded-3xl border border-white/20 dark:border-gray-700/30 shadow-2xl p-8 mb-8 transition-all hover:shadow-purple-500/10">
          <h2 className="text-3xl font-bold text-gray-800 dark:text-white mb-6 flex items-center gap-3">
            <span className="text-3xl">⚙️</span>
            Model Configuration
          </h2>

          {modelInfo?.loaded ? (
            <div className="bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/30 dark:to-emerald-900/30 border-2 border-green-300/50 dark:border-green-600/50 rounded-2xl p-5 mb-6 backdrop-blur-sm">
              <div className="flex items-center gap-3 mb-2">
                <span className="text-2xl">✅</span>
                <p className="text-green-900 dark:text-green-100 font-bold text-lg">
                  Model Ready: {modelInfo.model_name}
                </p>
              </div>
              <p className="text-green-700 dark:text-green-300 text-sm ml-11">
                <strong>Backend:</strong> {modelInfo.backend || 'Hugging Face'} • <strong>Device:</strong> {modelInfo.device || 'local'}
              </p>
            </div>
          ) : (
            <div className="bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-900/30 dark:to-orange-900/30 border-2 border-amber-300/50 dark:border-amber-600/50 rounded-2xl p-5 mb-6 backdrop-blur-sm">
              <div className="flex items-center gap-3 mb-2">
                <span className="text-2xl">⚠️</span>
                <p className="text-amber-900 dark:text-amber-100 font-bold">
                  No model loaded
                </p>
              </div>
              <p className="text-amber-700 dark:text-amber-300 text-sm ml-11">
                Select a model and click "Load Model" to begin. Models are downloaded from Hugging Face and run locally.
              </p>
            </div>
          )}

          <div className="mb-5">
            <label className="flex items-center cursor-pointer group">
              <input
                type="checkbox"
                checked={useCustomModel}
                onChange={(e) => setUseCustomModel(e.target.checked)}
                className="mr-3 h-5 w-5 rounded border-gray-300 text-purple-600 focus:ring-2 focus:ring-purple-500"
              />
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300 group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors">
                Use custom model name
              </span>
            </label>
          </div>

          <div>
            <label className="block text-sm font-bold text-gray-700 dark:text-gray-300 mb-3">
              Model Selection
            </label>
            {useCustomModel ? (
              <input
                type="text"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                placeholder="e.g., microsoft/phi-2"
                className="w-full px-5 py-3 border-2 border-gray-200 dark:border-gray-700 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-purple-500 dark:bg-gray-800 dark:text-white font-mono text-sm transition-all"
              />
            ) : (
              <select
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                className="w-full px-5 py-3 border-2 border-gray-200 dark:border-gray-700 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-purple-500 dark:bg-gray-800 dark:text-white transition-all cursor-pointer"
              >
                {availableModels.map((model) => (
                  <option key={model.name} value={model.name}>
                    {model.display_name} - {model.description}
                  </option>
                ))}
              </select>
            )}
          </div>
          <button
            onClick={handleLoadModel}
            disabled={loading}
            className="mt-6 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-bold py-3 px-8 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg hover:shadow-purple-500/50 transform hover:scale-105 active:scale-95"
          >
            {loading ? '⏳ Loading...' : '🚀 Load Model'}
          </button>
        </div>

        {/* Dataset Selection - Bento Box Grid */}
        <div className="backdrop-blur-xl bg-white/60 dark:bg-gray-900/60 rounded-3xl border border-white/20 dark:border-gray-700/30 shadow-2xl p-8 mb-8">
          <h2 className="text-3xl font-bold text-gray-800 dark:text-white mb-6 flex items-center gap-3">
            <span className="text-3xl">📚</span>
            Select Benchmark Dataset
          </h2>

          {/* Bento-box grid layout */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
            {datasets.map((dataset) => (
              <button
                key={dataset.name}
                onClick={() => handleDatasetChange(dataset.name)}
                className={`group p-5 rounded-2xl border-2 transition-all duration-300 text-left transform hover:scale-105 active:scale-95 ${
                  selectedDataset === dataset.name
                    ? 'border-purple-500 bg-gradient-to-br from-purple-50 to-pink-50 dark:from-purple-900/40 dark:to-pink-900/40 shadow-lg shadow-purple-500/30'
                    : 'border-gray-200 dark:border-gray-700 bg-white/50 dark:bg-gray-800/50 hover:border-purple-300 dark:hover:border-purple-600 hover:shadow-lg'
                }`}
              >
                <div className="flex items-start justify-between mb-3">
                  <h3 className="font-bold text-xl text-gray-800 dark:text-white group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors">
                    {dataset.name}
                  </h3>
                  {selectedDataset === dataset.name && (
                    <span className="text-xl">✓</span>
                  )}
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-3 line-clamp-2">
                  {dataset.description}
                </p>
                <span className="inline-block px-3 py-1 text-xs font-semibold bg-gradient-to-r from-purple-100 to-pink-100 dark:from-purple-900/50 dark:to-pink-900/50 text-purple-700 dark:text-purple-300 rounded-full">
                  {dataset.task_type}
                </span>
              </button>
            ))}
          </div>

          <button
            onClick={loadExample}
            disabled={!selectedDataset || loading}
            className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-bold py-4 px-8 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg hover:shadow-indigo-500/50 transform hover:scale-105 active:scale-95"
          >
            {loading ? '⏳ Loading Example...' : '🎲 Load Random Example'}
          </button>
        </div>

        {/* Example Display - Modern Card */}
        {currentExample && (
          <div className="backdrop-blur-xl bg-white/60 dark:bg-gray-900/60 rounded-3xl border border-white/20 dark:border-gray-700/30 shadow-2xl p-8 mb-8">
            <h2 className="text-3xl font-bold text-gray-800 dark:text-white mb-6 flex items-center gap-3">
              <span className="text-3xl">🎯</span>
              Example from {currentExample.dataset}
            </h2>

            {/* System Prompt Editor */}
            <div className="mb-6">
              <label className="block text-lg font-bold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
                <span>📝</span>
                System Prompt (Editable)
              </label>
              <div className="relative">
                <textarea
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  rows={10}
                  className="w-full px-5 py-4 border-2 border-purple-200 dark:border-purple-700 rounded-2xl focus:ring-2 focus:ring-purple-500 focus:border-purple-500 dark:bg-gray-800/80 dark:text-white font-mono text-sm resize-y min-h-[200px] max-h-[400px] overflow-y-auto backdrop-blur-sm transition-all"
                  placeholder="Enter system prompt to guide the model..."
                  style={{ lineHeight: '1.6' }}
                />
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 flex items-start gap-2">
                <span className="text-base">💡</span>
                <span>Edit this prompt to customize how the model should respond. The prompt includes examples and instructions for the model.</span>
              </p>
            </div>

            {/* User Prompt */}
            <div className="mb-6">
              <label className="block text-lg font-bold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
                <span>❓</span>
                Question / Prompt
              </label>
              <div className="bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-900 rounded-2xl p-5 border-2 border-gray-200 dark:border-gray-700">
                <pre className="whitespace-pre-wrap text-gray-800 dark:text-gray-200 font-mono text-sm leading-relaxed">
                  {currentExample.prompt}
                </pre>
              </div>
            </div>

            {currentExample.metadata && (
              <div className="mb-6 p-4 bg-blue-50/50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl">
                <span className="text-sm font-semibold text-blue-900 dark:text-blue-200">Metadata: </span>
                <span className="text-sm text-blue-700 dark:text-blue-300 font-mono">{JSON.stringify(currentExample.metadata)}</span>
              </div>
            )}

            <button
              onClick={handleEvaluate}
              disabled={loading || !modelInfo?.loaded}
              className="w-full bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 text-white font-bold py-4 px-8 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg hover:shadow-green-500/50 transform hover:scale-105 active:scale-95"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-3">
                  <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Running Prediction...
                </span>
              ) : (
                <span className="flex items-center justify-center gap-2">
                  <span className="text-xl">🚀</span>
                  Run Prediction
                </span>
              )}
            </button>
          </div>
        )}

        {/* Streaming Output - Live Response */}
        {isStreaming && (
          <div className="backdrop-blur-xl bg-gradient-to-br from-blue-50/80 to-purple-50/80 dark:from-blue-900/40 dark:to-purple-900/40 rounded-3xl border-2 border-blue-300/50 dark:border-blue-700/50 shadow-2xl shadow-blue-500/20 p-8 mb-8 animate-pulse-slow">
            <h2 className="text-3xl font-bold text-gray-800 dark:text-white mb-6 flex items-center gap-3">
              <svg className="animate-spin h-8 w-8 text-purple-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span className="bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">
                AI Thinking...
              </span>
            </h2>
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-r from-purple-500/10 to-pink-500/10 rounded-2xl blur-xl"></div>
              <div className="relative bg-white/80 dark:bg-gray-900/80 backdrop-blur-md rounded-2xl p-6 border border-purple-200 dark:border-purple-800">
                <p className="text-lg text-gray-800 dark:text-white break-words font-mono whitespace-pre-wrap leading-relaxed">
                  {streamingTokens || 'Waiting for response...'}
                  <span className="inline-block w-0.5 h-6 bg-gradient-to-b from-purple-600 to-pink-600 animate-pulse ml-1"></span>
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Prediction & Evaluation Results - Premium Display */}
        {evaluationResult && (
          <div className="backdrop-blur-xl bg-white/60 dark:bg-gray-900/60 rounded-3xl border border-white/20 dark:border-gray-700/30 shadow-2xl p-8">
            <h2 className="text-4xl font-black text-gray-800 dark:text-white mb-8 flex items-center gap-3">
              <span className="text-4xl">🎯</span>
              <span className="bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">
                Evaluation Results
              </span>
            </h2>

            {/* Score Badge - Hero Element */}
            <div className={`mb-8 relative overflow-hidden rounded-3xl ${
              evaluationResult.score === 1
                ? 'bg-gradient-to-br from-green-400 via-emerald-500 to-teal-600'
                : 'bg-gradient-to-br from-orange-400 via-red-500 to-pink-600'
            }`}>
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent animate-shimmer"></div>
              <div className="relative p-8 text-center">
                <div className="text-8xl font-black text-white mb-2">
                  {(evaluationResult.score * 100).toFixed(0)}%
                </div>
                <div className="text-2xl font-bold text-white/90 mb-1">
                  {evaluationResult.score === 1 ? '✓ Perfect Match!' : '× Needs Review'}
                </div>
                <div className="text-white/70 font-medium">
                  Metric: {evaluationResult.metric}
                </div>
              </div>
            </div>

            {/* Comparison Bento Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
              {/* Gold Answer Card */}
              <div className="group backdrop-blur-md bg-gradient-to-br from-emerald-50/80 to-teal-50/80 dark:from-emerald-900/30 dark:to-teal-900/30 rounded-2xl p-6 border-2 border-emerald-300/50 dark:border-emerald-700/50 shadow-xl hover:shadow-emerald-500/20 transition-all">
                <h3 className="text-lg font-bold text-emerald-900 dark:text-emerald-200 mb-4 flex items-center gap-2">
                  <span className="text-2xl">✅</span>
                  Gold Standard
                </h3>
                <div className="bg-white/60 dark:bg-gray-900/60 backdrop-blur-sm rounded-xl p-4 border border-emerald-200 dark:border-emerald-800">
                  <p className="text-xl font-bold text-gray-800 dark:text-white break-words">
                    {evaluationResult.gold_answer}
                  </p>
                </div>
              </div>

              {/* Model Prediction Card */}
              <div className="group backdrop-blur-md bg-gradient-to-br from-purple-50/80 to-pink-50/80 dark:from-purple-900/30 dark:to-pink-900/30 rounded-2xl p-6 border-2 border-purple-300/50 dark:border-purple-700/50 shadow-xl hover:shadow-purple-500/20 transition-all">
                <h3 className="text-lg font-bold text-purple-900 dark:text-purple-200 mb-4 flex items-center gap-2">
                  <span className="text-2xl">🤖</span>
                  AI Prediction
                </h3>
                <div className="bg-white/60 dark:bg-gray-900/60 backdrop-blur-sm rounded-xl p-4 border border-purple-200 dark:border-purple-800">
                  <p className="text-xl font-bold text-gray-800 dark:text-white break-words">
                    {evaluationResult.predicted_answer}
                  </p>
                </div>
              </div>
            </div>

            {/* Evaluation Details - Collapsible */}
            {evaluationResult.details && (
              <details className="group">
                <summary className="cursor-pointer list-none">
                  <div className="bg-gradient-to-r from-gray-50 to-slate-50 dark:from-gray-800 dark:to-slate-900 rounded-2xl p-5 border-2 border-gray-200 dark:border-gray-700 hover:border-purple-300 dark:hover:border-purple-700 transition-all">
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-bold text-gray-700 dark:text-gray-300 flex items-center gap-2">
                        <span className="text-xl">📋</span>
                        Detailed Metrics
                      </h3>
                      <span className="text-gray-400 group-open:rotate-180 transition-transform">▼</span>
                    </div>
                  </div>
                </summary>
                <div className="mt-4 bg-gray-900/95 dark:bg-black/95 backdrop-blur-sm rounded-2xl p-6 border border-gray-700">
                  <pre className="text-sm text-green-400 font-mono overflow-x-auto leading-relaxed">
                    {JSON.stringify(evaluationResult.details, null, 2)}
                  </pre>
                </div>
              </details>
            )}
          </div>
        )}

        {/* Error Display - Modern Alert */}
        {error && (
          <div className="backdrop-blur-xl bg-gradient-to-r from-red-50/90 to-orange-50/90 dark:from-red-900/40 dark:to-orange-900/40 border-2 border-red-300 dark:border-red-700 rounded-3xl p-6 mb-8 shadow-2xl shadow-red-500/20">
            <div className="flex items-start gap-4">
              <span className="text-3xl">⚠️</span>
              <div>
                <h3 className="text-xl font-bold text-red-900 dark:text-red-200 mb-2">Error</h3>
                <p className="text-red-800 dark:text-red-300 font-medium">{error}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
