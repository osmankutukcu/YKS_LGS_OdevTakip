"use client";

import { Home, Users, BookOpen, Settings, Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

export default function Navigation() {
    const pathname = usePathname();
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

    const navItems = [
        { name: "Dashboard", href: "/", icon: Home },
        { name: "Öğrenciler", href: "/students", icon: Users },
        { name: "Ödevler", href: "/homework", icon: BookOpen }, // Will implement next
        { name: "Ayarlar", href: "/settings", icon: Settings },
    ];

    const isActive = (path: string) => pathname === path;

    return (
        <>
            {/* Desktop Sidebar (Left) */}
            <aside className="hidden md:flex flex-col w-64 bg-white border-r border-gray-200 h-screen fixed left-0 top-0 z-50">
                <div className="p-6 border-b border-gray-100 flex items-center gap-2">
                    <div className="h-8 w-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold">
                        Y
                    </div>
                    <span className="font-bold text-xl text-gray-800 tracking-tight">YKS/LGS Pro</span>
                </div>

                <nav className="flex-1 p-4 space-y-2">
                    {navItems.map((item) => (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 font-medium ${isActive(item.href)
                                    ? "bg-blue-50 text-blue-600 shadow-sm"
                                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                                }`}
                        >
                            <item.icon size={20} />
                            {item.name}
                        </Link>
                    ))}
                </nav>

                <div className="p-4 border-t border-gray-100">
                    <div className="bg-gradient-to-r from-blue-500 to-indigo-600 rounded-xl p-4 text-white text-center">
                        <p className="text-sm font-medium opacity-90">Premium Paket</p>
                        <p className="text-xs opacity-75 mt-1">Aktif</p>
                    </div>
                </div>
            </aside>

            {/* Mobile Bottom Navigation */}
            <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 z-50 pb-safe">
                <div className="flex justify-around items-center h-16">
                    {navItems.map((item) => (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={`flex flex-col items-center justify-center w-full h-full space-y-1 ${isActive(item.href) ? "text-blue-600" : "text-gray-400"
                                }`}
                        >
                            <item.icon size={22} strokeWidth={isActive(item.href) ? 2.5 : 2} />
                            <span className="text-[10px] font-medium">{item.name}</span>
                        </Link>
                    ))}
                </div>
            </nav>
        </>
    );
}
