"use client";

import { useEffect } from "react";
import { AlertCircle } from "lucide-react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-gray-50 text-gray-800 p-4">
      <div className="bg-white p-6 rounded-lg shadow-md max-w-md w-full text-center border">
        <div className="flex justify-center mb-4">
            <div className="p-3 bg-red-100 rounded-full">
                <AlertCircle size={32} className="text-red-500" />
            </div>
        </div>
        <h2 className="text-lg font-bold mb-2">Bir şeyler ters gitti!</h2>
        <p className="text-sm text-gray-500 mb-6 font-mono bg-gray-100 p-2 rounded text-left overflow-auto max-h-32">
            {error.message || "Beklenmedik bir hata oluştu."}
        </p>
        <button
          onClick={() => reset()}
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded w-full transition-colors"
        >
          Tekrar Dene
        </button>
      </div>
    </div>
  );
}
