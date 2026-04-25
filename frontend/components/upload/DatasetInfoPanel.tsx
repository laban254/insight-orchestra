"use client";

import { X, ChevronDown } from "lucide-react";
import { useState } from "react";

interface DatasetInfo {
  name: string;
  type: "uploaded" | "demo";
  rows: number | string;
  columns: number | string;
  description?: string;
  use_cases?: string[];
}

export function DatasetInfoPanel({
  info,
  onReset,
  onSwitch,
  availableDatasets
}: {
  info: DatasetInfo | null;
  onReset: () => void;
  onSwitch?: (datasetId: string) => void | Promise<void>;
  availableDatasets?: any;
}) {
  const [showMenu, setShowMenu] = useState(false);

  if (!info) return null;

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-gradient-to-r from-blue-50 to-blue-50/50 border-r border-gray-200 min-w-max">
      {/* Dataset Badge */}
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-2 bg-white rounded-lg px-3 py-2 shadow-sm border border-gray-100">
          <div className="w-2 h-2 rounded-full bg-blue-500" />
          <div className="text-xs">
            <p className="font-medium text-gray-900 leading-tight">{info.name}</p>
            <p className="text-gray-500 text-[10px]">
              {info.rows} rows • {info.columns} cols
            </p>
          </div>
        </div>

        {/* Info Tooltip */}
        {info.description && (
          <div className="group relative">
            <div className="w-5 h-5 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-bold cursor-help">
              ?
            </div>
            <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 hidden group-hover:block z-50">
              <div className="bg-gray-900 text-white text-xs rounded-lg px-3 py-2 whitespace-nowrap shadow-lg">
                <p className="font-medium">{info.description}</p>
                {info.use_cases && info.use_cases.length > 0 && (
                  <p className="text-gray-300 text-[10px] mt-1">
                    Try: {info.use_cases.slice(0, 2).join(", ")}
                  </p>
                )}
                <div className="absolute top-full left-1/2 transform -translate-x-1/2 -mt-1">
                  <div className="border-4 border-transparent border-t-gray-900" />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 ml-auto">
        {onSwitch && availableDatasets && (
          <div className="relative">
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="p-1.5 rounded-lg hover:bg-white/50 transition-colors text-gray-600 hover:text-gray-900 text-xs font-medium flex items-center gap-1"
              title="Switch dataset"
            >
              <span>Switch</span>
              <ChevronDown size={14} className={`transition-transform ${showMenu ? 'rotate-180' : ''}`} />
            </button>

            {showMenu && (
              <div className="absolute right-0 mt-1 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
                {Object.entries(availableDatasets).map(([id, config]: [string, any]) => (
                  <button
                    key={id}
                    onClick={() => {
                      onSwitch?.(id);
                      setShowMenu(false);
                    }}
                    className="w-full text-left px-3 py-2 hover:bg-gray-50 border-b border-gray-100 last:border-b-0 text-xs"
                  >
                    <p className="font-medium text-gray-900">{config.name}</p>
                    <p className="text-gray-500 text-[10px]">{config.rows} rows</p>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <button
          onClick={onReset}
          className="p-1.5 rounded-lg hover:bg-red-50 transition-colors text-gray-600 hover:text-red-600"
          title="Reset and upload new file"
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
}
