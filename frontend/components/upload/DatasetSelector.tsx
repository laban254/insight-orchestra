"use client";

import { useState, useCallback } from "react";
import { api } from "@/lib/api";
import { ChevronDown } from "lucide-react";

interface DatasetInfo {
  name: string;
  description: string;
  rows: number;
  columns: number;
  use_cases: string[];
}

export function DatasetSelector({ 
  onUploadSuccess,
  datasets
}: { 
  onUploadSuccess: (filePath: string, info: any) => void;
  datasets: Record<string, any>;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showDatasets, setShowDatasets] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState<string | null>(null);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(e.type === "dragenter" || e.type === "dragover");
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await uploadFile(e.dataTransfer.files[0]);
    }
  }, []);

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      await uploadFile(e.target.files[0]);
    }
  };

  const uploadFile = async (file: File) => {
    setError(null);
    setIsUploading(true);
    try {
      const result = await api.uploadFile(file);
      onUploadSuccess(result.file_path, {
        name: file.name,
        type: "uploaded",
        rows: result.rows || "Unknown",
        columns: result.columns || "Unknown",
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  const loadDemo = async (datasetId: string) => {
    setError(null);
    setIsUploading(true);
    setSelectedDataset(datasetId);
    try {
      const result = await api.loadDemoData(datasetId);
      onUploadSuccess(result.file_path, {
        name: result.dataset_name,
        type: "demo",
        rows: result.row_count,
        columns: result.column_count,
        description: result.description,
        use_cases: result.use_cases,
      });
      setShowDatasets(false);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Failed to load demo");
    } finally {
      setIsUploading(false);
      setSelectedDataset(null);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto space-y-4">
      {/* Upload Section */}
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer
          ${isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}
        `}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          type="file"
          accept=".csv"
          className="hidden"
          id="file-upload"
          onChange={handleChange}
        />
        <label htmlFor="file-upload" className="cursor-pointer">
          <div className="space-y-2">
            <div className="flex justify-center">
              <span className="text-4xl text-gray-400">📄</span>
            </div>
            {isUploading ? (
              <p className="text-blue-500 font-medium">Uploading...</p>
            ) : (
              <>
                <p className="text-sm font-medium text-gray-700">Click to upload or drag and drop</p>
                <p className="text-xs text-gray-500">CSV files only</p>
              </>
            )}
          </div>
        </label>
      </div>

      {error && (
        <div className="p-3 text-sm text-red-500 bg-red-50 rounded-md">
          {error}
        </div>
      )}

      {/* Demo Datasets Selector */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600 font-medium">Or try a demo:</span>
        </div>

        {/* Dataset Dropdown */}
        <div className="relative">
          <button
            onClick={() => setShowDatasets(!showDatasets)}
            disabled={isUploading}
            className="w-full px-4 py-3 bg-white border border-gray-200 rounded-lg flex items-center justify-between hover:border-gray-300 disabled:opacity-50 text-left"
          >
            <span className="text-sm font-medium text-gray-700">
              {selectedDataset ? `Loading ${datasets[selectedDataset]?.name || 'Dataset'}...` : 'Select a demo dataset'}
            </span>
            <ChevronDown size={16} className={`transition-transform ${showDatasets ? 'rotate-180' : ''}`} />
          </button>

          {showDatasets && (
            <div className="absolute top-full left-0 right-0 mt-2 bg-white border border-gray-200 rounded-lg shadow-lg z-10">
              {Object.entries(datasets).map(([id, config]) => (
                <button
                  key={id}
                  onClick={() => loadDemo(id)}
                  disabled={isUploading}
                  className="w-full px-4 py-3 text-left hover:bg-gray-50 border-b border-gray-100 last:border-b-0 disabled:opacity-50"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <p className="font-medium text-sm text-gray-900">{config.name}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{config.description}</p>
                      <div className="flex gap-2 mt-2">
                        <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded">
                          {config.rows} rows
                        </span>
                        <span className="text-xs bg-purple-50 text-purple-700 px-2 py-1 rounded">
                          {config.columns} cols
                        </span>
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Info Text */}
      <p className="text-xs text-gray-500 text-center">
        💡 Demo datasets are perfect for trying out Insight Orchestra before uploading your own data
      </p>
    </div>
  );
}
