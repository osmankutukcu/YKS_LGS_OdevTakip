"use client";

import { useEffect, useState } from "react";
import { ArrowLeft, Search, User } from "lucide-react";
import Link from "next/link";

interface Student {
    id: number;
    ad_soyad: string;
    sinif: string;
    okul: string;
    telefon: string;
}

export default function StudentsPage() {
    const [students, setStudents] = useState<Student[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState("");

    useEffect(() => {
        fetch("http://localhost:8000/api/students")
            .then((res) => res.json())
            .then((data) => {
                setStudents(data);
                setLoading(false);
            })
            .catch((err) => {
                console.error("Failed to fetch students", err);
                setLoading(false);
            });
    }, []);

    const filteredStudents = students.filter((s) =>
        s.ad_soyad.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <main className="min-h-screen bg-gray-50 p-4 md:p-8 font-sans">
            {/* Header */}
            <div className="flex items-center gap-4 mb-8">
                <Link href="/" className="p-2 bg-white rounded-full shadow-sm hover:bg-gray-100 transition">
                    <ArrowLeft size={24} className="text-gray-600" />
                </Link>
                <h1 className="text-2xl font-bold text-gray-800">Öğrenci Listesi</h1>
            </div>

            {/* Search */}
            <div className="mb-6 relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Search className="text-gray-400" size={20} />
                </div>
                <input
                    type="text"
                    placeholder="Öğrenci ara..."
                    className="w-full pl-10 pr-4 py-3 rounded-xl border-none shadow-sm focus:ring-2 focus:ring-blue-500 outline-none"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                />
            </div>

            {/* List */}
            <div className="space-y-3">
                {loading ? (
                    <div className="text-center py-10 text-gray-500">Yükleniyor...</div>
                ) : filteredStudents.length === 0 ? (
                    <div className="text-center py-10 text-gray-500">Öğrenci bulunamadı.</div>
                ) : (
                    filteredStudents.map((student) => (
                        <Link href={`/students/${student.id}`} key={student.id} className="bg-white p-4 rounded-xl shadow-sm border border-gray-100 hover:shadow-md transition group cursor-pointer block">
                            <div className="flex items-center gap-4">
                                <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center text-gray-500 group-hover:bg-blue-100 group-hover:text-blue-600 transition">
                                    <User size={24} />
                                </div>
                                <div>
                                    <h3 className="font-semibold text-gray-800 group-hover:text-blue-700 transition">
                                        {student.ad_soyad}
                                    </h3>
                                    <p className="text-sm text-gray-500">{student.sinif || "Sınıf Belirtilmemiş"} • {student.okul}</p>
                                </div>
                            </div>
                        </Link>
                    ))
                )}
            </div>
        </main>
    );
}
