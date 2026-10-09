"use client";

import { useEffect, useState } from "react";
import { ArrowLeft, BookOpen, User, Calendar, CheckCircle } from "lucide-react";
import Link from "next/link";

interface Homework {
    id: number;
    student_name: string;
    lesson: string;
    book?: string;
    subject?: string;
    due_date?: string;
    is_completed: boolean;
}

export default function HomeworkPage() {
    const [homeworks, setHomeworks] = useState<Homework[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch("http://localhost:8000/api/homework?limit=50")
            .then((res) => res.json())
            .then((data) => {
                setHomeworks(data);
                setLoading(false);
            })
            .catch((err) => {
                console.error(err);
                setLoading(false);
            });
    }, []);

    const handleComplete = async (id: number) => {
        try {
            const res = await fetch(`http://localhost:8000/api/homework/${id}/complete`, {
                method: "POST",
            });
            if (res.ok) {
                // Remove from list
                setHomeworks((prev) => prev.filter((h) => h.id !== id));
            } else {
                alert("Hata oluştu");
            }
        } catch (err) {
            console.error(err);
            alert("Bağlantı hatası");
        }
    };

    return (
        <main className="min-h-screen bg-gray-50 p-4 md:p-8 font-sans">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-4">
                    <Link href="/" className="p-2 bg-white rounded-full shadow-sm hover:bg-gray-100 transition">
                        <ArrowLeft size={24} className="text-gray-600" />
                    </Link>
                    <h1 className="text-2xl font-bold text-gray-800">Bekleyen Ödevler</h1>
                </div>
                <div className="bg-blue-100 text-blue-800 text-sm font-semibold px-3 py-1 rounded-full">
                    Son 50 Ödev
                </div>
            </div>

            {/* List */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {loading ? (
                    <div className="col-span-full text-center py-10 text-gray-500">Yükleniyor...</div>
                ) : homeworks.length === 0 ? (
                    <div className="col-span-full text-center py-10 text-gray-500">Bekleyen ödev yok 🎉</div>
                ) : (
                    homeworks.map((hw) => (
                        <div
                            key={hw.id}
                            className="bg-white p-5 rounded-2xl shadow-sm border border-gray-100 hover:shadow-md transition relative overflow-hidden group"
                        >
                            <div className="absolute top-0 left-0 w-1 h-full bg-orange-400 group-hover:bg-orange-500 transition-colors"></div>

                            <div className="mb-3 flex justify-between items-start">
                                <div className="flex items-center gap-2 text-gray-600 text-sm font-medium">
                                    <User size={16} />
                                    <span>{hw.student_name}</span>
                                </div>
                                {hw.due_date && (
                                    <div className="flex items-center gap-1 text-xs text-red-500 font-semibold bg-red-50 px-2 py-1 rounded-lg">
                                        <Calendar size={12} />
                                        {hw.due_date.split(" ")[0]}
                                    </div>
                                )}
                            </div>

                            <h3 className="text-lg font-bold text-gray-800 mb-1">{hw.subject || "Konu Belirtilmemiş"}</h3>
                            <p className="text-sm text-gray-500 mb-4 flex items-center gap-2">
                                <BookOpen size={14} />
                                {hw.lesson} • {hw.book || "Kitap yok"}
                            </p>

                            <button
                                onClick={() => handleComplete(hw.id)}
                                className="w-full py-2.5 bg-gray-50 hover:bg-green-50 text-gray-600 hover:text-green-600 font-medium rounded-xl border border-gray-200 hover:border-green-200 transition flex items-center justify-center gap-2 group-hover:bg-green-600 group-hover:text-white group-hover:border-green-600">
                                <CheckCircle size={18} />
                                Tamamla
                            </button>
                        </div>
                    ))
                )}
            </div>
        </main>
    );
}
