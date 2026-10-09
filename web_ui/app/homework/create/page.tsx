"use client";

import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { ArrowLeft, Save, Trash2, Filter, Printer, MessageCircle, FileText, Download, Check, RefreshCw, Plus, BookOpen, Loader2, X } from "lucide-react";

// Types
interface MatrixItem {
    topic: string;
    books: { [bookName: string]: boolean };
}

interface AssignedItem {
    id?: number;
    lesson: string;
    book: string;
    topic: string;
    duration: number;
}

interface Student {
    id: number;
    ad_soyad: string;
}

interface LessonGroup {
    [groupName: string]: { table: string; name: string }[];
}

interface MatrixData {
    topics: { id: number; name: string }[];
    books: string[];
}

export default function CreateHomeworkPage() {
    const [students, setStudents] = useState<Student[]>([]);
    const [studentId, setStudentId] = useState("");
    const [dueDate, setDueDate] = useState("2025-12-24");

    // Header Inputs (Mocking Desktop)
    const [searchName, setSearchName] = useState("osman");
    const [searchSurname, setSearchSurname] = useState("fizik");

    // Matrix State
    const [groups, setGroups] = useState<LessonGroup>({});
    const [selectedGroup, setSelectedGroup] = useState("YKS");
    const [selectedLesson, setSelectedLesson] = useState<{ table: string, name: string } | null>(null);
    const [matrixData, setMatrixData] = useState<MatrixData | null>(null);

    // Selections: { topic_id: { book_name: boolean } } for NEW selections
    const [selections, setSelections] = useState<Record<number, Record<string, boolean>>>({});

    // Existing Assignments: { topic_id: { book_name: boolean } } for READ-ONLY
    const [existing, setExisting] = useState<Record<number, Record<string, boolean>>>({});

    // Right Panel Data
    const [targetDuration, setTargetDuration] = useState(90);

    const [loading, setLoading] = useState(true);
    const [loadingMatrix, setLoadingMatrix] = useState(false);
    const [saving, setSaving] = useState(false);

    // Load Init Data
    useEffect(() => {
        Promise.all([
            fetch("http://localhost:8000/api/students").then(res => res.json()),
            fetch("http://localhost:8000/api/matrix/init").then(res => res.json())
        ]).then(([studentsData, groupsData]) => {
            if (Array.isArray(studentsData)) {
                setStudents(studentsData);
                if (studentsData.length > 0) setStudentId(studentsData[0].id.toString());
            } else {
                console.error("Invalid students data:", studentsData);
            }

            if (groupsData && typeof groupsData === 'object') {
                setGroups(groupsData);
                if (groupsData["YKS"]?.length > 0) {
                    setSelectedLesson(groupsData["YKS"][0]);
                }
            } else {
                console.error("Invalid groups data:", groupsData);
            }
            setLoading(false);
        }).catch(err => {
            console.error("Failed to load init data:", err);
            setLoading(false);
            // Optional: Set a UI error state here if I had one, for now alert or let it render empty
        });
    }, []);

    // Load Matrix Data when Lesson Changes
    useEffect(() => {
        if (!selectedLesson) return;
        setLoadingMatrix(true);
        setMatrixData(null);
        setSelections({});
        setExisting({});

        let url = `http://localhost:8000/api/matrix/${selectedLesson.table}`;
        if (studentId) {
            url += `?student_id=${studentId}`;
        }

        fetch(url)
            .then(res => res.json())
            .then((data: any) => {
                setMatrixData(data);

                // Parse existing
                const existMap: Record<number, Record<string, boolean>> = {};
                if (data.existing) {
                    data.existing.forEach((item: any) => {
                        if (!existMap[item.topic_id]) existMap[item.topic_id] = {};
                        existMap[item.topic_id][item.book] = true;
                    });
                }
                setExisting(existMap);
                setLoadingMatrix(false);
            })
            .catch(err => {
                console.error(err);
                setLoadingMatrix(false);
            });
    }, [selectedLesson, studentId]);

    const toggleSelection = (topicId: number, bookName: string) => {
        // Prevent toggling if existing
        if (existing[topicId]?.[bookName]) return;

        setSelections(prev => ({
            ...prev,
            [topicId]: {
                ...prev[topicId],
                [bookName]: !prev[topicId]?.[bookName]
            }
        }));
    };

    // Derived Assigned List (Only NEW selections)
    const assignedList = useMemo(() => {
        const list: AssignedItem[] = [];
        if (!matrixData || !selectedLesson) return list;

        for (const topic of matrixData.topics) {
            if (selections[topic.id]) {
                for (const book of matrixData.books) {
                    if (selections[topic.id][book]) {
                        list.push({
                            lesson: selectedLesson.name,
                            book: book,
                            topic: topic.name,
                            duration: 20 // Mock
                        });
                    }
                }
            }
        }
        return list;
    }, [selections, matrixData, selectedLesson]);

    const handleSave = async () => {
        if (!studentId) return alert("Öğrenci seçiniz.");
        if (assignedList.length === 0) return alert("Kaydedilecek yeni ödev yok.");

        setSaving(true);
        try {
            const items = assignedList.map(a => {
                // Find topic ID from name (inefficient but works for small lists)
                const t = matrixData?.topics.find(t => t.name === a.topic);
                return {
                    topic_id: t?.id || 0,
                    topic_name: a.topic,
                    book_name: a.book
                };
            });

            const res = await fetch("http://localhost:8000/api/homework/bulk", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    student_id: parseInt(studentId),
                    lesson_table: selectedLesson?.table,
                    lesson_name: selectedLesson?.name,
                    items: items,
                    due_date: dueDate
                })
            });

            if (res.ok) {
                alert("Ödevler Başarıyla Kaydedildi! ✅");
                setSelections({}); // Clear new selections
                // Ideally refresh matrix to confirm they are now "locked"
                // Trigger refresh by re-setting lesson or refetching
                const currentL = selectedLesson;
                setSelectedLesson(null);
                setTimeout(() => setSelectedLesson(currentL), 50);
            } else {
                alert("Hata oluştu.");
            }
        } catch (err) {
            alert("Sunucu Hatası");
        } finally {
            setSaving(false);
        }
    };

    return (
        // FIXED OVERLAY to hide global sidebar and emulate desktop window
        <div className="fixed inset-0 z-50 bg-white flex flex-col font-sans overflow-hidden">

            {/* === HEADER === */}
            <header className="bg-white px-2 py-2 flex items-center justify-between shrink-0 border-b shadow-sm gap-2 h-14">

                {/* Close/Back Button */}
                <Link href="/" className="mr-2 text-gray-400 hover:text-gray-700">
                    <X size={20} />
                </Link>

                {/* Left Inputs */}
                <div className="flex items-center gap-2">
                    <div className="flex flex-col">
                        <label className="text-[10px] text-blue-600 font-bold ml-1">Ad</label>
                        <input type="text" className="border rounded px-2 py-0.5 w-24 text-xs h-7" defaultValue="osman" />
                    </div>
                    <div className="flex flex-col">
                        <label className="text-[10px] text-blue-600 font-bold ml-1">Soyad</label>
                        <input type="text" className="border rounded px-2 py-0.5 w-24 text-xs h-7" defaultValue="fizik" />
                    </div>

                    <div className="flex flex-col ml-2">
                        <label className="text-[10px] text-blue-600 font-bold ml-1">Öğrenci Seçimi</label>
                        <select
                            value={studentId}
                            onChange={(e) => setStudentId(e.target.value)}
                            className="border rounded px-2 py-0.5 w-40 text-xs h-7 bg-gray-50 font-semibold"
                        >
                            {students.map(s => <option key={s.id} value={s.id}>{s.ad_soyad}</option>)}
                        </select>
                    </div>
                </div>

                {/* Center-Right: Date & Actions */}
                <div className="flex items-center gap-2 ml-auto">
                    <div className="flex items-center gap-1 mr-2">
                        <span className="text-blue-600 font-bold text-xs">Bitiş:</span>
                        <input type="date" value={dueDate} onChange={e => setDueDate(e.target.value)} className="border rounded px-2 py-0.5 text-xs h-7" />
                    </div>

                    <button className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-md font-bold text-xs shadow-sm h-8 whitespace-nowrap">
                        Bilgileri Getir
                    </button>
                    <Link href="/books" target="_blank" className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-md font-bold text-xs shadow-sm h-8 flex items-center whitespace-nowrap">
                        Kitap Ekle/Sil
                    </Link>
                    <button onClick={handleSave} className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-md font-bold text-xs shadow-sm h-8 whitespace-nowrap">
                        Ödevi Kaydet
                    </button>
                    <button className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-md font-bold text-xs shadow-sm h-8 whitespace-nowrap">
                        Haftalık Plan
                    </button>
                    <Link href={`/students/${studentId}`} className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-md font-bold text-xs shadow-sm h-8 flex items-center whitespace-nowrap">
                        Ödev Kontrol
                    </Link>
                </div>
            </header>

            {/* === SPLIT VIEW === */}
            <div className="flex flex-1 overflow-hidden">

                {/* LEFT: MATRIX */}
                <div className="flex-1 flex flex-col min-w-0 border-r relative bg-white">
                    {/* Top Tabs */}
                    <div className="bg-white border-b flex px-2 pt-2 shrink-0">
                        {Object.keys(groups).map(grp => (
                            <button
                                key={grp}
                                onClick={() => setSelectedGroup(grp)}
                                className={`px-4 py-1.5 text-xs font-bold rounded-t border border-b-0 mr-1 transition-all ${selectedGroup === grp ? "bg-blue-50 text-blue-700 border-blue-200 z-10 relative top-[1px]" : "bg-gray-100 text-gray-500 hover:bg-gray-50"}`}
                            >
                                {grp}
                            </button>
                        ))}
                    </div>

                    {/* Sub-Tabs (Lessons) */}
                    <div className="bg-blue-50 border-b flex px-1 py-1 gap-1 overflow-x-auto scrollbar-hide whitespace-nowrap shadow-inner box-border h-10 items-center shrink-0">
                        {groups[selectedGroup]?.map(lesson => (
                            <button
                                key={lesson.table}
                                onClick={() => setSelectedLesson(lesson)}
                                className={`px-3 py-1 rounded border text-[10px] font-bold uppercase transition shadow-sm shrink-0 
                                    ${selectedLesson?.table === lesson.table ? "bg-white border-blue-400 text-blue-700 ring-1 ring-blue-200" : "bg-gray-100 border-gray-300 text-gray-600 hover:bg-white"}`}
                            >
                                {lesson.name}
                            </button>
                        ))}
                    </div>

                    {/* Matrix Grid */}
                    <div className="flex-1 overflow-auto bg-white relative">
                        {loadingMatrix && <div className="absolute inset-0 bg-white/60 z-10 flex items-center justify-center"><Loader2 className="animate-spin text-blue-600" /></div>}

                        {matrixData && matrixData.books.length > 0 ? (
                            <div className="inline-block min-w-full">
                                {/* Table Header */}
                                <div className="flex sticky top-0 z-20 bg-white shadow-sm border-b h-10">
                                    <div className="w-[220px] shrink-0 px-2 font-bold text-gray-700 text-xs border-r bg-gray-50 flex items-center text-ellipsis overflow-hidden whitespace-nowrap">
                                        Konu Listesi
                                    </div>
                                    {matrixData.books.map((book, i) => (
                                        <div key={i} className="w-[100px] shrink-0 px-1 text-center text-[10px] font-bold text-gray-700 border-r bg-white truncate flex items-center justify-center" title={book}>
                                            {book}
                                        </div>
                                    ))}
                                </div>

                                {/* Rows */}
                                {matrixData.topics.map((topic, i) => (
                                    <div key={topic.id} className={`flex border-b hover:bg-blue-50/50 h-9 items-center ${i % 2 === 0 ? "bg-white" : "bg-gray-50/30"}`}>
                                        {/* Sticky Topic Name */}
                                        <div className={`w-[220px] shrink-0 px-2 text-[11px] font-medium text-gray-800 border-r sticky left-0 z-10 flex items-center h-full bg-inherit`}>
                                            <span className="truncate">{i + 1}. {topic.name}</span>
                                        </div>

                                        {/* Cells */}
                                        {matrixData.books.map((book, j) => {
                                            const isExisting = existing[topic.id]?.[book];
                                            const isSelected = selections[topic.id]?.[book];

                                            // Background Logic
                                            let bgClass = "";
                                            if (isExisting) {
                                                bgClass = "bg-yellow-100/50"; // Locked Yellow
                                            } else if (isSelected) {
                                                bgClass = "bg-blue-100"; // New Selection
                                            } else {
                                                // Alternating stripes (optional, keep clean for now)
                                            }

                                            return (
                                                <div
                                                    key={book}
                                                    onClick={() => toggleSelection(topic.id, book)}
                                                    className={`w-[100px] shrink-0 border-r flex items-center justify-center h-full transition-colors cursor-pointer select-none
                                                     ${bgClass} ${isExisting ? 'cursor-not-allowed opacity-80' : 'hover:bg-blue-50'}
                                                 `}
                                                >
                                                    {/* Custom Icon Logic */}
                                                    {isExisting ? (
                                                        <Check size={18} className="text-gray-500 font-bold opacity-70" strokeWidth={3} />
                                                    ) : isSelected ? (
                                                        <Check size={18} className="text-blue-600 font-bold drop-shadow-sm" strokeWidth={3} />
                                                    ) : (
                                                        <div className="w-4 h-4 rounded border border-gray-300 hover:border-blue-400 bg-white"></div>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="p-10 text-center text-gray-500 italic">Veri yok veya yükleniyor...</div>
                        )}
                    </div>
                </div>

                {/* RIGHT: ASSIGNED LIST (Fixed Width: 350px) */}
                <div className="w-[350px] flex flex-col border-l bg-white shrink-0 shadow-[0_0_20px_rgba(0,0,0,0.1)] z-20">
                    {/* List Header */}
                    <div className="flex bg-gray-100 border-b text-[10px] font-bold text-gray-600 h-8 items-center">
                        <div className="flex-1 px-2 border-r">Ders</div>
                        <div className="flex-1 px-2 border-r">Kitap</div>
                        <div className="w-16 px-2 border-r">Konu</div>
                        <div className="w-12 px-2 text-center">Süre</div>
                    </div>

                    {/* List Content */}
                    <div className="flex-1 overflow-auto bg-white">
                        {assignedList.length === 0 ? (
                            <div className="h-full flex flex-col items-center justify-center text-gray-300 gap-2">
                                <Filter size={32} />
                                <span className="text-xs">Seçim yapınız</span>
                            </div>
                        ) : (
                            assignedList.map((item, i) => (
                                <div key={i} className="flex border-b text-[10px] hover:bg-gray-50 h-8 items-center">
                                    <div className="flex-1 px-2 truncate border-r">{item.lesson}</div>
                                    <div className="flex-1 px-2 truncate border-r">{item.book}</div>
                                    <div className="w-16 px-2 truncate border-r">{item.topic}</div>
                                    <div className="w-12 px-2 text-center">{item.duration}</div>
                                </div>
                            ))
                        )}
                    </div>

                    {/* Right Footer Actions */}
                    <div className="p-3 bg-white border-t flex flex-col gap-3 shadow-inner">
                        {/* Row 1 */}
                        <div className="flex justify-between items-center text-xs">
                            <button className="text-blue-600 font-bold hover:bg-blue-50 px-2 py-1 rounded flex items-center gap-1">
                                <Filter size={12} /> Filtreler
                            </button>
                            <button onClick={() => setSelections({})} className="bg-red-50 text-red-600 hover:bg-red-100 px-3 py-1 rounded text-[10px] font-bold">
                                Temizle
                            </button>
                        </div>

                        {/* Row 2 */}
                        <div className="flex justify-between items-center text-xs bg-gray-50 p-2 rounded border">
                            <div className="flex items-center gap-2">
                                <span className="text-gray-600 font-bold">Hedef:</span>
                                <input type="number" value={targetDuration} className="w-12 border rounded p-1 text-center font-bold bg-white" onChange={e => setTargetDuration(Number(e.target.value))} />
                            </div>
                            <span className="text-gray-800 font-bold">Toplam: <span className="text-blue-600">0 dk</span></span>
                        </div>

                        {/* Row 3 */}
                        <div className="flex gap-2">
                            <button className="flex-1 bg-cyan-50 text-cyan-700 border border-cyan-100 px-3 py-2 rounded font-bold text-xs hover:bg-cyan-100 flex items-center justify-center gap-1">
                                <Check size={14} /> Öneriler
                            </button>
                            <button className="flex-1 bg-gray-50 text-gray-700 border border-gray-200 px-3 py-2 rounded font-bold text-xs hover:bg-gray-100 flex items-center justify-center gap-1">
                                <Printer size={14} /> Yazdır
                            </button>
                        </div>

                        {/* Row 4 */}
                        <button className="w-full bg-blue-600 text-white py-2.5 rounded font-bold text-sm hover:bg-blue-700 flex items-center justify-center gap-2 shadow-sm transition-transform hover:scale-[1.02]">
                            <MessageCircle size={16} /> WhatsApp
                        </button>
                    </div>
                </div>
            </div>

            {/* === FOOTER === */}
            <footer className="bg-white border-t p-2 flex gap-3 justify-center shrink-0 shadow-[0_-4px_20px_rgba(0,0,0,0.05)] z-30 h-12 items-center">
                {[
                    "Listeleri Excel'e Aktar",
                    "PDF Ayarları",
                    "Detaylı Rapor PDF",
                    "Eksik Konuları Getir",
                    "Yaklaşan Bitişe Takviye"
                ].map(btn => (
                    <button key={btn} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-1.5 rounded-full font-bold text-[11px] shadow-sm whitespace-nowrap">
                        {btn}
                    </button>
                ))}
            </footer>
        </div>
    );
}
