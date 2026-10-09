"use client";

import { useEffect, useState } from "react";
import { Users, BookOpen, Quote, Activity, AlertCircle, Plus } from "lucide-react";
import Link from "next/link";

// Types
interface DashboardStats {
  student_count: number;
  pending_tasks: number;
  success_rate: number;
  quote: string;
}

export default function Home() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("http://localhost:8000/api/dashboard")
      .then((res) => {
        if (!res.ok) throw new Error("API bağlantı hatası");
        return res.json();
      })
      .then((data) => {
        setStats(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="text-blue-600 font-semibold animate-pulse">Yükleniyor...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="text-red-500 flex items-center gap-2">
          <AlertCircle size={20} />
          <span>Hata: Backend sunucusu çalışmıyor olabilir. ({error})</span>
        </div>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50 p-4 md:p-8 font-sans">
      {/* Header */}
      <header className="mb-8">
        <h1 className="text-2xl md:text-3xl font-extrabold text-blue-800 text-center md:text-left">
          YKS/LGS Yönetici Paneli
        </h1>
        <p className="text-gray-500 text-sm text-center md:text-left mt-1">
          Web Arayüzü v1.0
        </p>
      </header>

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">

        {/* Card 1: Students */}
        <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-2xl p-6 text-white shadow-lg shadow-green-200">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-green-100 font-medium mb-1">Aktif Öğrenciler</p>
              <h2 className="text-4xl font-bold">{stats?.student_count}</h2>
            </div>
            <div className="p-3 bg-white/20 rounded-xl">
              <Users size={24} />
            </div>
          </div>
        </div>

        {/* Card 2: Pending Tasks */}
        <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl p-6 text-white shadow-lg shadow-blue-200">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-blue-100 font-medium mb-1">Bekleyen Ödevler</p>
              <h2 className="text-4xl font-bold">{stats?.pending_tasks}</h2>
            </div>
            <div className="p-3 bg-white/20 rounded-xl">
              <BookOpen size={24} />
            </div>
          </div>
        </div>

        {/* Card 3: Quote of the Day */}
        <div className="bg-gradient-to-br from-orange-400 to-orange-500 rounded-2xl p-6 text-white shadow-lg shadow-orange-200 md:col-span-2 lg:col-span-1">
          <div className="flex justify-between items-start mb-4">
            <p className="text-orange-100 font-medium">Günün Sözü</p>
            <div className="p-2 bg-white/20 rounded-lg">
              <Quote size={20} />
            </div>
          </div>
          <p className="text-lg font-medium leading-relaxed italic opacity-95">
            "{stats?.quote}"
          </p>
        </div>

        {/* Card 4: Success Rate (Optional/Extra) */}
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 flex items-center justify-between">
          <div>
            <p className="text-gray-500 font-medium mb-1">Genel Başarı</p>
            <h2 className="text-3xl font-bold text-gray-800">%{stats?.success_rate}</h2>
          </div>
          <div className="h-16 w-16 rounded-full border-4 border-purple-100 border-t-purple-600 flex items-center justify-center">
            <Activity className="text-purple-600" size={24} />
          </div>
        </div>

        {/* Card 5: Add Homework */}
        <Link href="/homework/create" className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 hover:shadow-md transition text-center group cursor-pointer">
          <div className="w-12 h-12 bg-purple-100 text-purple-600 rounded-full flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition">
            <Plus size={24} />
          </div>
          <span className="font-semibold text-gray-700">Ödev Ekle</span>
        </Link>

      </div>

      {/* Navigation Buttons (Mockup for now) */}
      <div className="mt-8 grid grid-cols-2 md:grid-cols-4 gap-4">
        <a href="/students" className="p-4 bg-white rounded-xl shadow-sm border hover:border-blue-500 hover:text-blue-600 transition font-medium flex items-center justify-center">
          Öğrenci Listesi
        </a>
        <button className="p-4 bg-white rounded-xl shadow-sm border hover:border-blue-500 hover:text-blue-600 transition font-medium">
          Ödev Ekle
        </button>
        <Link href="/homework/tracking" className="p-4 bg-white rounded-xl shadow-sm border hover:border-blue-500 hover:text-blue-600 transition font-medium flex items-center justify-center">
          Ödev Takip Formu
        </Link>
        <button className="p-4 bg-white rounded-xl shadow-sm border hover:border-blue-500 hover:text-blue-600 transition font-medium">
          Raporlar
        </button>
        <button className="p-4 bg-white rounded-xl shadow-sm border hover:border-blue-500 hover:text-blue-600 transition font-medium">
          Ayarlar
        </button>
      </div>

    </main>
  );
}
