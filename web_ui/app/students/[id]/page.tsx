"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Save, Filter, Smartphone, Check, Layout, Trash2 } from "lucide-react";

interface HomeworkItem {
    id: number;
    lesson: string;
    book: string;
    topic: string;
    duration: number;
    status: string; // 'tamam' | 'devam'
    date: string;
}

interface Cluster {
    id: number;
    given_date: string;
    due_date: string;
    total_items: number;
    completed_items: number;
    percent: number;
    status_label: string;
}

interface Stats {
    total: number;
    completed: number;
    percent: number;
    active: number;
}

export default function StudentTrackingPage() {
    const params = useParams();
    const studentId = params.id;

    const [studentName, setStudentName] = useState("");
    const [clusters, setClusters] = useState<Cluster[]>([]);
    const [items, setItems] = useState<HomeworkItem[]>([]);
    const [globalStats, setGlobalStats] = useState<Stats | null>(null);

    // Selection
    const [selectedClusterId, setSelectedClusterId] = useState<number | null>(null);
    const [filterLesson, setFilterLesson] = useState("Hepsi");
    const [filterStatus, setFilterStatus] = useState("Hepsi");

    // Changes
    const [changedItems, setChangedItems] = useState<Record<number, string>>({});
    const [saving, setSaving] = useState(false);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        // 1. Student Name
        fetch(`http://localhost:8000/api/students`)
            .then(res => res.json())
            .then((data: any[]) => {
                const s = data.find(x => x.id == Number(studentId));
                if (s) setStudentName(s.ad_soyad);
            });

        // 2. Clusters
        fetch(`http://localhost:8000/api/student/${studentId}/clusters`)
            .then(res => res.json())
            .then(data => {
                setClusters(data);
                if (data.length > 0) setSelectedClusterId(data[0].id); // Select first by default
            });

        // 3. Global Stats (Fetch all once)
        fetch(`http://localhost:8000/api/student/${studentId}/tracking`)
            .then(res => res.json())
            .then(data => setGlobalStats(data.stats));

    }, [studentId]);

    // Fetch items when selection/filters change
    useEffect(() => {
        fetchItems();
    }, [selectedClusterId, filterLesson, filterStatus]);

    const fetchItems = () => {
        if (!selectedClusterId && clusters.length === 0) return;

        setLoading(true);
        let url = `http://localhost:8000/api/student/${studentId}/tracking?`;
        if (selectedClusterId) url += `cluster_id=${selectedClusterId}&`;
        if (filterLesson !== "Hepsi") url += `lesson=${encodeURIComponent(filterLesson)}&`;
        if (filterStatus !== "Hepsi") url += `status=${encodeURIComponent(filterStatus)}`;

        fetch(url)
            .then(res => res.json())
            .then(data => {
                setItems(data.items);
                setChangedItems({});
                setLoading(false);
            });
    };

    const toggleStatus = (id: number, currentStatus: string) => {
        const oldStatus = changedItems[id] || currentStatus;
        const newStatus = oldStatus === 'tamam' ? 'devam' : 'tamam';
        setChangedItems(prev => ({ ...prev, [id]: newStatus }));
    };

    const handleSave = async () => {
        if (Object.keys(changedItems).length === 0) return;
        setSaving(true);

        const toComplete = [];
        const toIncomplete = [];
        Object.entries(changedItems).forEach(([id, status]) => {
            if (status === 'tamam') toComplete.push(Number(id));
            else toIncomplete.push(Number(id));
        });

        try {
            if (toComplete.length > 0) await fetch("http://localhost:8000/api/homework/status/bulk", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ homework_ids: toComplete, status: "tamam" })
            });
            if (toIncomplete.length > 0) await fetch("http://localhost:8000/api/homework/status/bulk", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ homework_ids: toIncomplete, status: "devam" })
            });
            alert("Kaydedildi.");

            // Refresh everything
            fetchItems();
            // Also refresh clusters to update progress bars
            fetch(`http://localhost:8000/api/student/${studentId}/clusters`)
                .then(res => res.json())
                .then(setClusters);

        } catch (e) {
            alert("Hata");
        } finally {
            setSaving(false);
        }
    };

    const handleWhatsApp = async () => {
        // WhatsApp needs logic
        alert("WhatsApp entegrasyonu backend'de hazır. Bağlantı açılıyor...");
        let url = `http://localhost:8000/api/student/${studentId}/whatsapp?`;
        // Should we send filter? Typically reports are comprehensive or current view?
        // Desktop app generates based on view.
        if (selectedClusterId) {
            // Wait, does whatsapp endpoint support cluster_id? Not yet.
            // But desktop screenshot implies "Ödev Kontrol" generates report for current view?
            // Actually user asked for "Visual Check". I'll pass basic filters.
        }
        if (filterLesson !== "Hepsi") url += `lesson=${encodeURIComponent(filterLesson)}&`;
        if (filterStatus !== "Hepsi") url += `status=${encodeURIComponent(filterStatus)}`;

        try {
            const res = await fetch(url, { method: "POST" });
            const data = await res.json();
            if (data.text) {
                const waUrl = `https://wa.me/?text=${encodeURIComponent(data.text)}`;
                window.open(waUrl, '_blank');
            }
        } catch (e) {
            alert("Hata");
        }
    };

    const lessons = Array.from(new Set(items.map(i => i.lesson))).sort();

    return (
        <main className="h-screen bg-gray-100 flex flex-col font-sans overflow-hidden text-sm">
            {/* Top Bar: Stats & Actions */}
            <header className="bg-white border-b p-3 flex items-center justify-between shrink-0 shadow-sm z-10">
                <div className="flex items-center gap-4">
                    <Link href="/students" className="p-1.5 hover:bg-gray-100 rounded-md transition text-gray-600">
                        <ArrowLeft size={20} />
                    </Link>
                    <div>
                        <h1 className="font-bold text-gray-800 text-lg leading-tight">Ödev Kontrol</h1>
                        <div className="text-xs text-blue-600 font-medium">{studentName}</div>
                    </div>
                </div>

                {/* Global Stats Bar */}
                {globalStats && (
                    <div className="hidden md:flex items-center gap-6 bg-gray-50 px-4 py-1.5 rounded-full border">
                        <div className="flex items-center gap-2">
                            <span className="text-gray-500 font-medium">Tamamlanma:</span>
                            {/* Visual Progress Bar Dots style */}
                            <div className="flex gap-0.5">
                                {[...Array(10)].map((_, i) => (
                                    <div key={i} className={`w-1.5 h-3 rounded-sm ${i < (globalStats.percent / 10) ? 'bg-red-500' : 'bg-gray-200'}`}></div>
                                ))}
                            </div>
                            <span className="text-blue-600 font-bold ml-1">%{globalStats.percent}</span>
                        </div>
                        <div className="w-px h-4 bg-gray-300"></div>
                        <div className="flex gap-3 text-gray-600">
                            <span>Aktif: <b>%{100 - globalStats.percent}</b></span>
                            <span><span className="text-green-600">✔</span> {globalStats.completed}</span>
                            <span><span className="text-red-600">✘</span> {globalStats.active}</span>
                            <span>Top: {globalStats.total}</span>
                        </div>
                    </div>
                )}

                <div className="flex gap-2">
                    <button className="bg-green-100 text-green-700 px-3 py-1.5 rounded font-semibold hover:bg-green-200 text-xs flex items-center gap-1">
                        <Check size={14} /> Hepsi
                    </button>
                    <button
                        onClick={handleSave}
                        className={`px-4 py-1.5 rounded font-bold text-xs flex items-center gap-1 text-white transition ${Object.keys(changedItems).length > 0 ? 'bg-green-600 hover:bg-green-700' : 'bg-gray-400'}`}
                    >
                        <Save size={14} /> Kaydet
                    </button>
                    <button onClick={handleWhatsApp} className="bg-green-500 text-white px-3 py-1.5 rounded font-semibold hover:bg-green-600 text-xs flex items-center gap-1">
                        <Smartphone size={14} /> WhatsApp
                    </button>
                    <button className="bg-gray-100 text-gray-700 px-3 py-1.5 rounded font-semibold hover:bg-gray-200 text-xs">
                        Kapat
                    </button>
                </div>
            </header>

            <div className="flex flex-1 overflow-hidden">
                {/* LEFT SIDEBAR: Clusters */}
                <aside className="w-[320px] bg-gray-200/50 border-r border-gray-300 flex flex-col overflow-hidden shrink-0">
                    <div className="p-2 border-b bg-gray-100 font-semibold text-gray-600 text-xs uppercase tracking-wider">
                        Ödev Kümeleri
                    </div>
                    <div className="flex-1 overflow-y-auto p-2 space-y-2">
                        {clusters.map(cluster => (
                            <div
                                key={cluster.id}
                                onClick={() => setSelectedClusterId(cluster.id)}
                                className={`p-3 rounded-lg border cursor-pointer transition relative group ${selectedClusterId === cluster.id ? 'bg-white border-blue-400 shadow-md ring-1 ring-blue-100 z-10' : 'bg-white border-gray-200 hover:border-blue-300'}`}
                            >
                                {/* Card Header */}
                                <div className="flex justify-between items-start mb-2">
                                    <span className={`font-bold text-sm ${selectedClusterId === cluster.id ? 'text-blue-700' : 'text-gray-700'}`}>#{cluster.id}</span>
                                    <span className="text-[10px] bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded border border-purple-200 font-medium">
                                        {cluster.status_label}
                                    </span>
                                </div>

                                {/* Dates */}
                                <div className="text-xs text-gray-600 mb-2 space-y-0.5">
                                    <div>Veriliş: {cluster.given_date}</div>
                                    <div>{cluster.total_items} kalem</div>
                                </div>

                                {/* Progress Bar */}
                                <div className="bg-gray-100 rounded-full h-4 relative overflow-hidden flex items-center">
                                    <div
                                        className={`absolute left-0 top-0 bottom-0 transition-all duration-500 ${cluster.percent === 100 ? 'bg-green-500' : 'bg-blue-400'}`}
                                        style={{ width: `${cluster.percent}%` }}
                                    ></div>
                                    <span className="relative w-full text-center text-[10px] font-bold text-gray-700 z-10">%{cluster.percent}</span>
                                </div>
                            </div>
                        ))}
                        {clusters.length === 0 && <div className="p-4 text-center text-gray-500 text-xs">Küme bulunamadı.</div>}
                    </div>
                </aside>

                {/* RIGHT CONTENT: Items Table */}
                <div className="flex-1 flex flex-col bg-white overflow-hidden">
                    {/* Filters Toolbar */}
                    <div className="p-2 border-b bg-gray-50 flex items-center gap-3">
                        <select
                            value={filterLesson}
                            onChange={(e) => setFilterLesson(e.target.value)}
                            className="p-1.5 border rounded text-xs bg-white focus:ring-1 focus:ring-blue-500"
                        >
                            <option value="Hepsi">Ders: Hepsi</option>
                            {lessons.map(l => <option key={l} value={l}>{l}</option>)}
                        </select>

                        <select
                            value={filterStatus}
                            onChange={(e) => setFilterStatus(e.target.value)}
                            className="p-1.5 border rounded text-xs bg-white focus:ring-1 focus:ring-blue-500"
                        >
                            <option value="Hepsi">Durum: Hepsi</option>
                            <option value="Yapılanlar">Yapılanlar</option>
                            <option value="Yapılmayanlar">Yapılmayanlar</option>
                        </select>

                        <input type="text" placeholder="Kitap/Konu ara..." className="p-1.5 border rounded text-xs w-48 bg-white" />

                        <button className="text-xs text-gray-500 hover:text-red-600 underline">Filtreyi Temizle</button>
                    </div>

                    {/* Table */}
                    <div className="flex-1 overflow-auto">
                        <table className="w-full text-left border-collapse">
                            <thead className="bg-gray-50 text-gray-600 font-semibold sticky top-0 z-10 text-xs">
                                <tr>
                                    <th className="p-2 border-b w-10 text-center">Yapıldı</th>
                                    <th className="p-2 border-b">Ders</th>
                                    <th className="p-2 border-b">Kitap</th>
                                    <th className="p-2 border-b">Konu</th>
                                    <th className="p-2 border-b w-16">Süre(dk)</th>
                                    <th className="p-2 border-b">Açıklama</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100 text-xs">
                                {loading ? (
                                    <tr><td colSpan={6} className="p-12 text-center text-gray-500">Yükleniyor...</td></tr>
                                ) : items.length === 0 ? (
                                    <tr><td colSpan={6} className="p-12 text-center text-gray-500">Kayıt bulunamadı.</td></tr>
                                ) : items.map(item => {
                                    const currentStatus = changedItems[item.id] || item.status;
                                    const isDone = currentStatus === 'tamam';

                                    return (
                                        <tr key={item.id} className={`hover:bg-blue-50/50 transition ${isDone ? 'bg-green-50/20' : ''}`}>
                                            <td className="p-2 border-b text-center">
                                                <input
                                                    type="checkbox"
                                                    checked={isDone}
                                                    onChange={() => toggleStatus(item.id, item.status)}
                                                    className="w-4 h-4 rounded border-gray-300 text-green-600 focus:ring-green-500 cursor-pointer"
                                                />
                                            </td>
                                            <td className="p-2 border-b font-medium text-gray-800">{item.lesson}</td>
                                            <td className="p-2 border-b text-gray-600">{item.book}</td>
                                            <td className="p-2 border-b text-gray-700">{item.topic}</td>
                                            <td className="p-2 border-b text-gray-500">{item.duration || 0}</td>
                                            <td className="p-2 border-b border-r-0 text-gray-400 italic"></td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>

                    {/* Footer Status Line */}
                    <div className="p-2 border-t bg-gray-50 text-[10px] text-gray-500 flex justify-between">
                        <span>Toplam: {items.length} kayıt</span>
                        <span>Seçili Küme ID: {selectedClusterId || '-'}</span>
                    </div>
                </div>
            </div>
        </main>
    );
}
