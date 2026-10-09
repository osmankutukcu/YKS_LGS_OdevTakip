"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, Save, Trash2, Plus, Copy, BookOpen, Check } from "lucide-react";

interface Student {
    id: number;
    ad_soyad: string;
}

interface LessonGroup {
    [groupName: string]: { table: string; name: string }[];
}

export default function BookManagerPage() {
    const [students, setStudents] = useState<Student[]>([]);
    const [filteredStudents, setFilteredStudents] = useState<Student[]>([]);
    const [studentSearch, setStudentSearch] = useState("");

    const [groups, setGroups] = useState<LessonGroup>({});

    // Selections
    const [selectedLessonTable, setSelectedLessonTable] = useState("tyt_matematik");
    const [poolBooks, setPoolBooks] = useState<string[]>([]);
    const [textBooks, setTextBooks] = useState("");

    const [selectedPoolBooks, setSelectedPoolBooks] = useState<string[]>([]);
    const [selectedStudentIds, setSelectedStudentIds] = useState<number[]>([]);

    // Loading
    const [loading, setLoading] = useState(true);

    // Initial Data
    useEffect(() => {
        Promise.all([
            fetch("http://localhost:8000/api/students").then(res => res.json()),
            fetch("http://localhost:8000/api/matrix/init").then(res => res.json())
        ]).then(([studentsData, groupsData]) => {
            setStudents(studentsData);
            setFilteredStudents(studentsData);
            setGroups(groupsData);
            setLoading(false);
        });
    }, []);

    // Fetch Pool on Lesson Change
    useEffect(() => {
        fetchPool();
    }, [selectedLessonTable]);

    const fetchPool = () => {
        fetch(`http://localhost:8000/api/books/${selectedLessonTable}`)
            .then(res => res.json())
            .then(data => setPoolBooks(data));
    };

    // Filter Students
    useEffect(() => {
        const lower = studentSearch.toLowerCase();
        setFilteredStudents(
            students.filter(s => s.ad_soyad.toLowerCase().includes(lower))
        );
    }, [studentSearch, students]);

    // Actions
    const addToPool = async () => {
        const lines = textBooks.split("\n").map(l => l.trim()).filter(l => l);
        if (lines.length === 0) return;

        // We only add new ones to DB 'kitap' table, assignments happen later
        // But Desktop app 'Ekle' does both? Screenshot 3 seems to 'Ekle' books to students.
        // Let's assume 'Ekle' button at bottom assigns selected books (from Pool or Text) to Selected Students.

        // First, ensure books exist in pool
        for (const bookInfo of [...lines]) { // Handle lines as new books
            await fetch("http://localhost:8000/api/books", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ lesson_table: selectedLessonTable, book_name: bookInfo })
            });
        }

        // Creating final list of books to assign (Selected Pool + Text Lines)
        const booksToAssign = new Set([...selectedPoolBooks, ...lines]);

        if (booksToAssign.size === 0 || selectedStudentIds.length === 0) {
            alert("Lütfen atanacak kitapları VE öğrencileri seçiniz.");
            fetchPool(); // refresh pool at least
            return;
        }

        // Assign
        let count = 0;
        for (const sid of selectedStudentIds) {
            for (const b of Array.from(booksToAssign)) {
                await fetch("http://localhost:8000/api/student/books", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        student_id: sid,
                        lesson_table: selectedLessonTable,
                        book_name: b,
                        action: "add"
                    })
                });
                count++;
            }
        }
        alert(`İşlem tamam! ${count} kayıt eklendi.`);
        setTextBooks("");
        setSelectedPoolBooks([]);
        fetchPool();
    };

    const removeFromStudents = async () => {
        // Logic to remove selected books from selected students
        const booksToData = new Set([...selectedPoolBooks]);
        if (booksToData.size === 0 || selectedStudentIds.length === 0) {
            alert("Silinecek kitapları ve ogrencileri seçiniz.");
            return;
        }

        let count = 0;
        for (const sid of selectedStudentIds) {
            for (const b of Array.from(booksToData)) {
                await fetch("http://localhost:8000/api/student/books", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        student_id: sid,
                        lesson_table: selectedLessonTable,
                        book_name: b,
                        action: "remove"
                    })
                });
                count++;
            }
        }
        alert(`İşlem tamam! ${count} kayıt silindi.`);
    };

    const togglePoolSelection = (book: string) => {
        if (selectedPoolBooks.includes(book)) {
            setSelectedPoolBooks(prev => prev.filter(b => b !== book));
        } else {
            setSelectedPoolBooks(prev => [...prev, book]);
        }
    };

    const toggleStudentSelection = (sid: number) => {
        if (selectedStudentIds.includes(sid)) {
            setSelectedStudentIds(prev => prev.filter(i => i !== sid));
        } else {
            setSelectedStudentIds(prev => [...prev, sid]);
        }
    };

    // Flatten lessons for dropdown
    const allLessons = [];
    Object.keys(groups).forEach(grp => {
        allLessons.push(...groups[grp]);
    });

    return (
        <main className="min-h-screen bg-gray-50 flex flex-col font-sans h-screen overflow-hidden">
            {/* Header */}
            <header className="bg-white border-b border-gray-200 p-4 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-4">
                    <Link href="/" className="p-2 hover:bg-gray-100 rounded-full transition">
                        <ArrowLeft size={24} className="text-gray-600" />
                    </Link>
                    <h1 className="text-xl font-bold text-gray-800">Kitap Yönetimi / Atama</h1>
                </div>

                <div className="flex items-center gap-2">
                    <label className="text-sm font-semibold text-gray-700">Ders:</label>
                    <select
                        value={selectedLessonTable}
                        onChange={e => setSelectedLessonTable(e.target.value)}
                        className="p-2 border rounded-lg bg-gray-50 font-medium"
                    >
                        {Object.keys(groups).map(grp => (
                            <optgroup key={grp} label={grp}>
                                {groups[grp].map(l => (
                                    <option key={l.table} value={l.table}>{l.name}</option>
                                ))}
                            </optgroup>
                        ))}
                    </select>
                </div>
            </header>

            {/* Content Split */}
            <div className="flex flex-1 overflow-hidden">

                {/* Left: Books */}
                <div className="flex-1 p-6 border-r border-gray-200 flex flex-col min-w-[300px] bg-white">
                    <h3 className="font-semibold text-gray-700 mb-2">Yeni Kitaplar (Satır satır yazın)</h3>
                    <textarea
                        className="w-full h-32 p-3 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none mb-4 text-sm"
                        placeholder="Örn: 345 TYT Matematik&#10;Karekök Geometri"
                        value={textBooks}
                        onChange={(e) => setTextBooks(e.target.value)}
                    ></textarea>

                    <h3 className="font-semibold text-gray-700 mb-2 flex justify-between items-center">
                        <span>Kitap Havuzu ({poolBooks.length})</span>
                        <span className="text-xs text-blue-600 cursor-pointer" onClick={() => setSelectedPoolBooks(poolBooks)}>Tümünü Seç</span>
                    </h3>
                    <div className="flex-1 overflow-y-auto border rounded-lg p-2 bg-gray-50">
                        {poolBooks.map(book => (
                            <div
                                key={book}
                                onClick={() => togglePoolSelection(book)}
                                className={`p-2 rounded cursor-pointer text-sm mb-1 flex items-center gap-2 ${selectedPoolBooks.includes(book) ? "bg-blue-100 text-blue-700 font-medium" : "hover:bg-white"}`}
                            >
                                <div className={`w-4 h-4 rounded border flex items-center justify-center ${selectedPoolBooks.includes(book) ? "bg-blue-600 border-blue-600" : "border-gray-400"}`}>
                                    {selectedPoolBooks.includes(book) && <Check size={12} className="text-white" />}
                                </div>
                                {book}
                            </div>
                        ))}
                    </div>
                </div>

                {/* Right: Students */}
                <div className="w-[450px] p-6 flex flex-col bg-white">
                    <h3 className="font-semibold text-gray-700 mb-2">Öğrenciler</h3>
                    <input
                        type="text"
                        placeholder="Öğrenci Ara..."
                        className="w-full p-2 border rounded-lg mb-3"
                        value={studentSearch}
                        onChange={e => setStudentSearch(e.target.value)}
                    />

                    <div className="flex justify-between items-center mb-2 px-1">
                        <span className="text-xs text-gray-500">{filteredStudents.length} öğrenci</span>
                        <div className="space-x-2">
                            <button onClick={() => setSelectedStudentIds(filteredStudents.map(s => s.id))} className="text-xs text-blue-600 hover:underline">Tümünü Seç</button>
                            <button onClick={() => setSelectedStudentIds([])} className="text-xs text-red-600 hover:underline">Temizle</button>
                        </div>
                    </div>

                    <div className="flex-1 overflow-y-auto border rounded-lg p-2 bg-gray-50">
                        {filteredStudents.map(s => (
                            <div
                                key={s.id}
                                onClick={() => toggleStudentSelection(s.id)}
                                className={`p-2 rounded cursor-pointer text-sm mb-1 flex items-center gap-2 ${selectedStudentIds.includes(s.id) ? "bg-green-100 text-green-700 font-medium" : "hover:bg-white"}`}
                            >
                                <div className={`w-4 h-4 rounded border flex items-center justify-center ${selectedStudentIds.includes(s.id) ? "bg-green-600 border-green-600" : "border-gray-400"}`}>
                                    {selectedStudentIds.includes(s.id) && <Check size={12} className="text-white" />}
                                </div>
                                {s.ad_soyad}
                            </div>
                        ))}
                    </div>
                </div>

            </div>

            {/* Footer Actions */}
            <div className="p-4 border-t border-gray-200 bg-gray-50 flex justify-end gap-3 shrink-0">
                <button
                    onClick={removeFromStudents}
                    className="px-6 py-3 bg-red-100 text-red-700 font-bold rounded-lg hover:bg-red-200 transition flex items-center gap-2"
                >
                    <Trash2 size={18} />
                    Seçileni Sil (Öğrenciden)
                </button>
                <button
                    onClick={addToPool}
                    className="px-8 py-3 bg-green-600 text-white font-bold rounded-lg hover:bg-green-700 shadow-md transition flex items-center gap-2"
                >
                    <Plus size={18} />
                    EKLE (Öğrenciye Ata)
                </button>
            </div>
        </main>
    );
}
