# -*- coding: utf-8 -*-
"""
YKS/LGS Öğrenci Öz-Değerlendirme ve Koçluk Görüşmesi Sistemi
Rehberlik, Psikolojik Danışmanlık (PDR) ve Eğitim Koçluğu standartlarına uygun
9 adet öz-değerlendirme formu ve öğretmen görüşmesine destek amaçlı özetler.
"""
from __future__ import annotations

import sys
import os
import json
import sqlite3
from html import escape
from services.survey_integrity_v8 import inspect_answers, complete_self_reports, safe_general_rows
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QRadioButton, 
    QButtonGroup, QScrollArea, QFrame, QMessageBox, QProgressBar, QComboBox,
    QFileDialog, QTextEdit, QDialog, QSplitter, QListWidget, QListWidgetItem,
    QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

import db

# Yardımcı Fonksiyonlar
def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def _to_int(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return default
        if isinstance(v, bool):
            return int(v)
        return int(v)
    except Exception:
        try:
            return int(float(str(v).replace(",", ".")))
        except Exception:
            return default

def _pct(v: Any) -> int:
    return int(_clamp(_to_int(v, 0), 0, 100))

# -----------------------------------------------------------
# 1) Bilimsel ve Pedagojik Anket Tanımları (9 Büyük Envanter)
# -----------------------------------------------------------

@dataclass
class SurveyQuestion:
    key: str
    text: str
    dimension: str = ""     # Alt boyut (örn: visual, auditory, cognitive, perfectionism)
    reverse: bool = False   # Ters madde mi? (1=katılmıyorum, 5=katılıyorum likert)

@dataclass
class SurveyDefinition:
    code: str
    category: str
    title: str
    description: str
    questions: List[SurveyQuestion]
    dimensions: Dict[str, str] = field(default_factory=dict) # {"dim_key": "Görünür İsim"}
    low_label: str = "Düşük Düzey"
    mid_label: str = "Orta Düzey"
    high_label: str = "Güçlü / Yüksek Düzey"
    risk_inverted: bool = False # True ise yüksek puan risk anlamına gelir (örn: Sınav Kaygısı, Erteleme)

class SurveyCatalog:
    """
    Eğitim psikolojisi, öğrenci koçluğu ve PDR literatürüne dayalı 9 ana envanter.
    Her biri YKS ve LGS hazırlık gerçeklerine göre titizlikle kurgulanmıştır.
    """
    LIKERT_MIN = 1
    LIKERT_MAX = 5

    @staticmethod
    def all_surveys() -> Dict[str, SurveyDefinition]:
        return {
            # 1. VARK ÖĞRENME STİLLERİ
            "vark_learning": SurveyDefinition(
                code="vark_learning",
                category="Bilişsel & Öğrenme",
                title="1. Öğrenme Tercihleri Formu",
                description="Öğrencinin tercih ettiği çalışma yöntemlerini sorar; sabit öğrenme türü veya başarı kapasitesi belirlemez.",
                dimensions={
                    "visual": "Görsel (Visual)",
                    "auditory": "İşitsel (Auditory)",
                    "read_write": "Okuma/Yazma (Read/Write)",
                    "kinesthetic": "Kinestetik/Uygulamalı (Kinesthetic)"
                },
                questions=[
                    SurveyQuestion("v_1", "Ders çalışırken renkli şemalar, zihin haritaları, grafikler veya infografikler kullanmak konuyu çok daha hızlı anlamamı sağlar.", dimension="visual"),
                    SurveyQuestion("v_2", "Önemli formülleri, özetleri odamın duvarına veya mantar panoma asıp görsel olarak görmek bana güven verir.", dimension="visual"),
                    SurveyQuestion("v_3", "Bir geometri veya problem sorusunu çözerken şekil çizmeden veya gözümde canlandırmadan çözmekte zorlanırım.", dimension="visual"),
                    SurveyQuestion("a_1", "Bir konuyu öğretmen veya videodaki eğitmen anlatırken dinlediğimde, kitaptan tek başıma okumaktan çok daha iyi kavrarım.", dimension="auditory"),
                    SurveyQuestion("a_2", "Zor bir konuyu veya soru çözümünü kendi kendime sesli tekrar etmek ya da bir başkasına anlatmak aklımda kalmasını sağlar.", dimension="auditory"),
                    SurveyQuestion("a_3", "Soru çözerken veya formül hatırlarken zihnimde öğretmenimin sınıfta o konuyu anlatırken kullandığı ses tonunu hatırlarım.", dimension="auditory"),
                    SurveyQuestion("r_1", "Bir konuyu en iyi kendi cümlelerimle detaylı yazılı not çıkararak ve konu anlatım kitabını satır satır okuyarak öğrenirim.", dimension="read_write"),
                    SurveyQuestion("r_2", "Çözümlü soru bankalarındaki açıklamalı çözümleri ve konu özetlerini dikkatle okumak bana büyük katkı sağlar.", dimension="read_write"),
                    SurveyQuestion("r_3", "Ezberlemem gereken kavramları ve kuralları maddeler halinde listeleyip tekrar tekrar okuyarak çalışmayı tercih ederim.", dimension="read_write"),
                    SurveyQuestion("k_1", "Sadece dinlemek veya okumak beni çabuk sıkar; konuyu ancak hemen arkasından bizzat çok sayıda soru çözüp uygulayarak öğrenebilirim.", dimension="kinesthetic"),
                    SurveyQuestion("k_2", "Ders çalışırken masada sabit oturmak yerine yürümek, elimde kalemle hareket etmek veya kısa molalarla hareketlenmek odaklanmamı artırır.", dimension="kinesthetic"),
                    SurveyQuestion("k_3", "Soyut teorik anlatımlar yerine somut, günlük hayatla ve gerçek deneylerle bağlantılı örneklerle çalışmak beni motive eder.", dimension="kinesthetic"),
                ],
                low_label="Kanal Ayrışmamış (Dengeli)",
                mid_label="Baskın Kanal Belirgin",
                high_label="Net Çoklu Öğrenme Gücü"
            ),

            # 2. AKADEMİK ERTELEME VE ZAMAN HIRSIZLARI
            "procrastination": SurveyDefinition(
                code="procrastination",
                category="Davranışsal & Disiplin",
                title="2. Akademik Erteleme ve Zaman Hırsızları Ölçeği",
                description="Ders çalışmayı erteleme, son dakikacılık, mükemmeliyetçilik ve dikkat dağıtıcılarla ilişkili kök neden analizi.",
                risk_inverted=True,
                dimensions={
                    "avoidance": "Zorluktan Kaçınma",
                    "perfectionism": "Mükemmeliyetçi Felç",
                    "distraction": "Dikkat Dağıtıcılar",
                    "planning": "Planlama Direnci"
                },
                questions=[
                    SurveyQuestion("p_1", "Zorlandığım veya sevmediğim derslerin başına oturmayı sürekli 'birazdan başlarım' diyerek ertelerim.", dimension="avoidance"),
                    SurveyQuestion("p_2", "Bir konuya başlamadan önce masanın, odanın veya şartların 'kusursuz' olmasını beklerim (Mükemmeliyetçi felç).", dimension="perfectionism"),
                    SurveyQuestion("p_3", "Çalışmaya oturacakken 'önce şu videoyu bitireyim' veya 'sosyal medyaya bakayım' derken saatlerin geçtiğini fark ederim.", dimension="distraction"),
                    SurveyQuestion("p_4", "Yapacağım çalışma gözümde çok büyüdüğü için nereden başlayacağımı bilemeyip tamamen bırakırım.", dimension="planning"),
                    SurveyQuestion("p_5", "Ödevlerimi veya deneme hedeflerimi genellikle teslim/kontrol gününden önceki son geceye bırakırım.", dimension="avoidance"),
                    SurveyQuestion("p_6", "Başarısız olmaktan veya soruyu çözememekten korktuğum için o konuyu çalışmaktan bilinçaltında kaçınırım.", dimension="perfectionism"),
                    SurveyQuestion("p_7", "Günde yapmam gereken işleri net bir sıraya koyup ertelemeden zamanında bitiririm.", dimension="planning", reverse=True),
                    SurveyQuestion("p_8", "Bir çalışma planı hazırladığımda ilk 1-2 gün uyar, sonra erteleyerek planı tamamen rafa kaldırırım.", dimension="planning"),
                    SurveyQuestion("p_9", "Çalışmaya başlamak için özel bir 'ilham' veya 'yüksek motivasyon' gelmesini beklerim.", dimension="avoidance"),
                    SurveyQuestion("p_10", "Ertelediğim her an içimde suçluluk hissederim ama yine de derse başlamakta direnç yaşarım.", dimension="avoidance"),
                ],
                low_label="Düşük Erteleme (Yüksek Eyleme Geçme)",
                mid_label="Orta Düzey Erteleme Eğilimi",
                high_label="Kritik Erteleme Riski (Acil Müdahale)"
            ),

            # 3. SINAV KAYGISI VE BİLİŞSEL ÇARPITMALAR
            "exam_anxiety": SurveyDefinition(
                code="exam_anxiety",
                category="Duygusal & Psikolojik",
                title="3. Sınav Kaygısı ve Bilişsel Çarpıtmalar Ölçeği",
                description="Sınav anı zihinsel blokajı, bedensel stres tepkileri ve 'ya kazanamazsam' felaketleştirme düşünceleri.",
                risk_inverted=True,
                dimensions={
                    "catastrophizing": "Felaketleştirme / Zihinsel Kaygı",
                    "somatic": "Bedensel / Fizyolojik Tepkiler",
                    "block": "Sınav Anı Zihinsel Blokaj",
                    "coping": "Sakinleşme ve Baş Etme"
                },
                questions=[
                    SurveyQuestion("ea_1", "Sınav veya zor bir deneme yaklaştığında içimde sürekli kötü bir şey olacakmış hissi oluşur.", dimension="catastrophizing"),
                    SurveyQuestion("ea_2", "Deneme sınavlarında sürenin azaldığını hissettiğim anda paniklerim ve bildiğim basit soruları bile kaçırırım.", dimension="block"),
                    SurveyQuestion("ea_3", "Sınav esnasında veya hemen öncesinde kalp çarpıntısı, mide bulantısı, terleme veya titreme gibi belirtiler yaşarım.", dimension="somatic"),
                    SurveyQuestion("ea_4", "'İstediğim hedefi kazanamazsam hayatım mahvolur ve ailemi hayal kırıklığına uğratırım' düşüncesi aklımdan çıkmaz.", dimension="catastrophizing"),
                    SurveyQuestion("ea_5", "Sınavda bir soruyu yapamadığımda o an 'eyvah hiçbir şeyi yapamayacağım' paniğine kapılırım.", dimension="block"),
                    SurveyQuestion("ea_6", "Sınavda çok iyi bildiğim bir formülü veya bilgiyi heyecandan zihnimin tamamen boşaldığını (blokaj) hissederim.", dimension="block"),
                    SurveyQuestion("ea_7", "Sınav esnasında başkalarının sayfaları hızla çevirdiğini duymak bende yetersizlik ve telaş hissi yaratır.", dimension="catastrophizing"),
                    SurveyQuestion("ea_8", "Deneme sınavından önceki gece heyecandan veya stresten uykuya dalmakta ciddi zorluk çekerim.", dimension="somatic"),
                    SurveyQuestion("ea_9", "Sınav anında derin nefes alarak veya kendimi telkin ederek sakinleşmeyi başarabilirim.", dimension="coping", reverse=True),
                    SurveyQuestion("ea_10", "Bir denemede netim düştüğünde kendimi suçlamak yerine eksiklerimi tespit edip soğukkanlı kalabilirim.", dimension="coping", reverse=True),
                ],
                low_label="Sağlıklı ve Yönetilebilir Kaygı",
                mid_label="Orta Düzey Kaygı (Destek Faydalı)",
                high_label="Yüksek Kaygı ve Blokaj Riski"
            ),

            # 4. ÇALIŞMA ALIŞKANLIKLARI VE MASA DİSİPLİNİ
            "study_habits": SurveyDefinition(
                code="study_habits",
                category="Davranışsal & Disiplin",
                title="4. YKS/LGS Çalışma Alışkanlıkları ve Masa Disiplini",
                description="Aktif öğrenme, soru çözme stratejisi, deneme analizi ve aralıklı tekrar disiplini.",
                dimensions={
                    "planning": "Günlük Planlama",
                    "analysis": "Deneme ve Hata Analizi",
                    "retention": "Aralıklı Tekrar ve Pekiştirme",
                    "focus": "Masa Başı Odaklanma"
                },
                questions=[
                    SurveyQuestion("sh_1", "Her gün hangi dersten kaç soru çözeceğimi ve hangi konuları bitireceğimi planlayarak masaya otururum.", dimension="planning"),
                    SurveyQuestion("sh_2", "Deneme sınavlarından hemen sonra yanlış ve boş sorularımın tek tek çözümlerini inceler, öğrenmeden bırakmam.", dimension="analysis"),
                    SurveyQuestion("sh_3", "Denemelerde veya testlerde yapamadığım zor soruları biriktirdiğim bir 'Hata Defteri / Yanlış Kutusu' tutarım.", dimension="analysis"),
                    SurveyQuestion("sh_4", "Sadece pasif şekilde video izlemekle yetinmem; soru bankalarından yeterli sayıda soru çözerek konuyu pekiştiririm.", dimension="retention"),
                    SurveyQuestion("sh_5", "Öğrendiğim bir konuyu 1 hafta ve 1 ay sonra unutmama adına düzenli aralıklarla tekrar ederim.", dimension="retention"),
                    SurveyQuestion("sh_6", "Soru çözerken takıldığım an hemen cevaba bakmak yerine en az 3-4 dakika kendim uğraşırım.", dimension="focus"),
                    SurveyQuestion("sh_7", "Çalışma masamda yalnızca o an çalışacağım dersin kitapları bulunur; dikkat dağıtıcı eşyalar yer almaz.", dimension="focus"),
                    SurveyQuestion("sh_8", "Zorlandığım bir konu veya ders olduğunda pes etmek yerine o derse daha fazla zaman ayırırım.", dimension="planning"),
                    SurveyQuestion("sh_9", "Haftalık net ve soru hedeflerimi gün gün takip eder, haftanın sonunda kendimi değerlendiririm.", dimension="planning"),
                    SurveyQuestion("sh_10", "Konu eksiğim varken sürekli deneme çözmek yerine, önce temel konu kavramalarını tamamlarım.", dimension="retention"),
                ],
                low_label="Düzensiz ve Verimsiz Çalışma",
                mid_label="Gelişmekte Olan Alışkanlıklar",
                high_label="Yüksek Disiplinli ve Verimli Çalışma"
            ),

            # 5. AKADEMİK ÖZ-YETERLİK VE İÇSEL MOTİVASYON
            "self_efficacy": SurveyDefinition(
                code="self_efficacy",
                category="Duygusal & Psikolojik",
                title="5. Akademik Öz-Yeterlik ve İçsel Motivasyon Ölçeği",
                description="Bandura Öz-Yeterlik teorisi: Öğrencinin kendi potansiyeline inancı, zorluklarla baş etme azmi ve içsel amaç duygusu.",
                dimensions={
                    "confidence": "Akademik Özgüven",
                    "intrinsic": "İçsel Motivasyon / Amaç",
                    "persistence": "Zorlukla Mücadele Azmi"
                },
                questions=[
                    SurveyQuestion("se_1", "Zor ve karmaşık bir konuyu yeterince emek verirsem mutlaka kavrayabileceğime inanırım.", dimension="confidence"),
                    SurveyQuestion("se_2", "Ders çalışmamdaki asıl motivasyonum ailemin ya da çevremin zorlaması değil, kendi geleceğim ve hedeflerimdir.", dimension="intrinsic"),
                    SurveyQuestion("se_3", "Denemelerde hedeflediğim netin altında kalsam bile, daha çok çalışarak bunu düzeltebileceğime inancım tamdır.", dimension="confidence"),
                    SurveyQuestion("se_4", "Ders çalışırken zamanın nasıl geçtiğini unuttuğum ve öğrenmekten keyif aldığım anlar sıklıkla olur.", dimension="intrinsic"),
                    SurveyQuestion("se_5", "Kendime koyduğum hedef üniversiteye veya liseye ulaşabileceğime dair içsel inancım yüksektir.", dimension="confidence"),
                    SurveyQuestion("se_6", "Sınıfımdaki diğer arkadaşlarımla kendimi kıyaslayıp sürekli yetersizlik duygusuna kapılırım.", dimension="confidence", reverse=True),
                    SurveyQuestion("se_7", "Beklenmedik bir program değişikliğinde hızla uyum sağlar, çalışmama devam ederim.", dimension="persistence"),
                    SurveyQuestion("se_8", "Bir hedefe ulaşmak için anlık zevklerimi (oyun, dizi, gezme vb.) erteleyebilme iradesine sahibim.", dimension="persistence"),
                    SurveyQuestion("se_9", "Çalışma tempom düştüğünde kendimi yeniden motive edip masaya oturtabilirim.", dimension="persistence"),
                    SurveyQuestion("se_10", "Hatalarımın beni başarısız yapmadığına, aksine bana neleri öğrenmem gerektiğini gösterdiğine inanırım.", dimension="intrinsic"),
                ],
                low_label="Kırılgan Öz-Yeterlik / Dışsal Bağımlılık",
                mid_label="Dalgalı Motivasyon",
                high_label="Güçlü Öz-Yeterlik ve Sağlam Vizyon"
            ),

            # 6. ZAMAN YÖNETİMİ VE BLOK/POMODORO ODAKLANMA
            "time_management": SurveyDefinition(
                code="time_management",
                category="Davranışsal & Disiplin",
                title="6. Zaman Yönetimi ve Blok/Pomodoro Odaklanma Ölçeği",
                description="Önceliklendirme (Eisenhower Matrisi), günlük zaman bloklama, odaklanma süresi ve mola disiplini.",
                dimensions={
                    "prioritize": "Önceliklendirme",
                    "blocks": "Blok Odaklanma (Pomodoro)",
                    "boundaries": "Sınır Koyma ve Molalar"
                },
                questions=[
                    SurveyQuestion("tm_1", "Günün başında en önemli ve zor dersleri 'Öncelikli İş' olarak belirler, günün verimli saatinde bitiririm.", dimension="prioritize"),
                    SurveyQuestion("tm_2", "Ders çalışırken 40-50 dakikalık bloklar (veya 25 dk Pomodoro) uygular ve süreyi tam verimle doldururum.", dimension="blocks"),
                    SurveyQuestion("tm_3", "Verdiğim 10-15 dakikalık molaları uzatmadan, zil veya zamanlayıcı çaldığında hemen derse dönerim.", dimension="boundaries"),
                    SurveyQuestion("tm_4", "Bir ders çalışırken aklıma başka dersler veya düşünceler geldiğinde odağım tamamen dağılır.", dimension="blocks", reverse=True),
                    SurveyQuestion("tm_5", "Haftalık çalışma çizelgemi hazırlarken okul, dershane, yemek ve uyku saatlerimi gerçekçi planlarım.", dimension="prioritize"),
                    SurveyQuestion("tm_6", "Günün sonunda ne kadar süre verimli çalıştığımı (net çalışma saati) not ederim.", dimension="prioritize"),
                    SurveyQuestion("tm_7", "Çat kapı gelen durumlar veya arkadaşlarımın çağrılarına 'hayır' diyerek çalışma saatimi korurum.", dimension="boundaries"),
                    SurveyQuestion("tm_8", "Aynı anda birden fazla ders veya işle uğraşmak yerine tek bir konuya tam odaklanırım.", dimension="blocks"),
                    SurveyQuestion("tm_9", "Soru çözerken süre tutar (kronometre kullanır), sınav temposuna uygun hız kazanmaya çalışırım.", dimension="blocks"),
                    SurveyQuestion("tm_10", "Günün sonunda bitiremediğim hedefler olduğunda hemen ertesi günün programına telafi eklerim.", dimension="prioritize"),
                ],
                low_label="Zaman Yönetimi Dağınık",
                mid_label="Gelişmekte Olan Zaman Becerisi",
                high_label="Üst Düzey Zaman ve Odak Yönetimi"
            ),

            # 7. ZİHNİYET (MINDSET) VE BİLİŞSEL DAYANIKLILIK
            "mindset_resilience": SurveyDefinition(
                code="mindset_resilience",
                category="Duygusal & Psikolojik",
                title="7. Zihniyet (Mindset) ve Bilişsel Dayanıklılık Ölçeği",
                description="Carol Dweck Gelişim Zihniyeti (Growth Mindset): Hatalara yaklaşım, net dalgalanmalarına direnç ve sebatkarlık.",
                dimensions={
                    "growth": "Gelişim Zihniyeti",
                    "feedback": "Eleştiri ve Geri Bildirime Açıklık",
                    "grit": "Zorluk Karşısında Sebatkarlık"
                },
                questions=[
                    SurveyQuestion("ms_1", "Bir insanın zekası veya yeteneği doğuştan sabittir, ne kadar çalışırsa çalışsın bir noktadan sonra değişmez.", dimension="growth", reverse=True),
                    SurveyQuestion("ms_2", "Deneme sınavında yaptığım her yanlış soru, bana eksik olduğum konuyu gösteren değerli bir rehberdir.", dimension="growth"),
                    SurveyQuestion("ms_3", "Çok çaba harcamama rağmen bir konuyu anlamadığımda 'bu derse yeteneğim yok' deyip vazgeçerim.", dimension="growth", reverse=True),
                    SurveyQuestion("ms_4", "Zorlayıcı ve yeni nesil sorularla uğraşmak beni korkutmaz, aksine zihnimi geliştirdiği için heyecanlandırır.", dimension="grit"),
                    SurveyQuestion("ms_5", "Öğretmenimin veya koçumun eksiklerimle ilgili yaptığı yapıcı eleştirileri gelişimim için memnuniyetle dinlerim.", dimension="feedback"),
                    SurveyQuestion("ms_6", "Netlerimin düştüğü dönemlerde pes etmek yerine çalışma yöntemimi gözden geçirip mücadeleye devam ederim.", dimension="grit"),
                    SurveyQuestion("ms_7", "Benden daha başarılı bir arkadaşımı gördüğümde kıskanmak yerine onun nasıl çalıştığını anlamaya çalışırım.", dimension="feedback"),
                    SurveyQuestion("ms_8", "Bir konuyu 'henüz' yapamıyor olabilirim ama doğru pratikle kesinlikle ustalaşabileceğime inanırım.", dimension="growth"),
                    SurveyQuestion("ms_9", "Hata yapma korkusu yüzünden zor denemelere veya zor kaynaklara başlamaktan kaçınırım.", dimension="grit", reverse=True),
                    SurveyQuestion("ms_10", "Sınav sürecinin bir maraton olduğunun ve iniş çıkışların bu sürecin doğal bir parçası olduğunun farkındayım.", dimension="grit"),
                ],
                low_label="Sabit Zihniyet (Kırılgan)",
                mid_label="Esnek / Gelişime Açık",
                high_label="Güçlü Gelişim Zihniyeti (Growth Mindset)"
            ),

            # 8. DİJİTAL BAĞIMLILIK VE EKRAN HİJYENİ
            "digital_distraction": SurveyDefinition(
                code="digital_distraction",
                category="Davranışsal & Disiplin",
                title="8. Dijital Bağımlılık ve Ekran/Odak Hijyeni Envanteri",
                description="Akıllı telefon, sosyal medya akışları (Reels/Shorts/TikTok), bildirimler ve ders masası odak temizliği.",
                risk_inverted=True,
                dimensions={
                    "phone": "Masa Başı Telefon Kullanımı",
                    "social_media": "Sosyal Medya Döngüleri",
                    "detox": "Dijital Sınır Koyabilme"
                },
                questions=[
                    SurveyQuestion("dd_1", "Ders çalışırken telefonum masanın üzerinde veya elimin hemen altında açık şekilde durur.", dimension="phone"),
                    SurveyQuestion("dd_2", "Ders esnasında gelen mesaj veya bildirim sesini duyduğum anda dayanamayıp derhal telefona bakarım.", dimension="phone"),
                    SurveyQuestion("dd_3", "Bir soru veya konuyu araştırmak için internete girip yarım saat sonra kendimi alakasız videolarda bulurum.", dimension="social_media"),
                    SurveyQuestion("dd_4", "Mola verdiğimde telefonu elime aldığımda planladığım moladan çok daha uzun süre ekrana kilitlenirim.", dimension="social_media"),
                    SurveyQuestion("dd_5", "Ders çalışma saatlerimde telefonumu başka bir odaya bırakabilir veya tamamen sessize / uçak moduna alabilirim.", dimension="detox", reverse=True),
                    SurveyQuestion("dd_6", "Gece yatağa girdiğimde uyuyana kadar telefonda video izler veya sosyal medyada gezinirim.", dimension="social_media"),
                    SurveyQuestion("dd_7", "Günde kaç saat telefon ekranına baktığımı (ekran süresi) takip eder ve sınır koymaya çalışırım.", dimension="detox", reverse=True),
                    SurveyQuestion("dd_8", "Telefonsuz bir tam gün geçirme düşüncesi bile bende huzursuzluk veya eksiklik hissi yaratır.", dimension="phone"),
                ],
                low_label="Düşük Dijital Bağımlılık (Yüksek Odak)",
                mid_label="Orta Düzey Ekran Riski",
                high_label="Yüksek Dijital Dağılma Riski (Detoks Gerekli)"
            ),

            # 9. BİYOLOJİK RİTİM, UYKU VE ENERJİ YÖNETİMİ
            "sleep_energy": SurveyDefinition(
                code="sleep_energy",
                category="Bilişsel & Fizyolojik",
                title="9. Biyolojik Ritim, Uyku Hijyeni ve Enerji Yönetimi",
                description="Sirkadiyen ritim, uyku kalitesi, sabah dinç uyanma, beslenme ve gün içi bilişsel zindelik.",
                dimensions={
                    "sleep": "Uyku Düzeni & Hijyeni",
                    "vitality": "Gün İçi Zihinsel Enerji",
                    "wellness": "Beden ve Beslenme Sağlığı"
                },
                questions=[
                    SurveyQuestion("se_1", "Her gece en az 7-8 saat kesintisiz ve kaliteli bir uyku uyurum.", dimension="sleep"),
                    SurveyQuestion("se_2", "Sabahları uyandığımda kendimi dinlenmiş, enerjik ve ders çalışmaya hazır hissederim.", dimension="vitality"),
                    SurveyQuestion("se_3", "Hafta içi ve hafta sonu uyuma ve uyanma saatlerim birbirine yakındır (düzenli sirkadiyen ritim).", dimension="sleep"),
                    SurveyQuestion("se_4", "Uyumadan en az 45 dakika önce telefon, tablet ve bilgisayar ekranlarına bakmayı bırakırım.", dimension="sleep"),
                    SurveyQuestion("se_5", "Öğleden sonra veya akşam saatlerinde şiddetli zihinsel tükenmişlik ve uyku hali yaşarım.", dimension="vitality", reverse=True),
                    SurveyQuestion("se_6", "Uyanık kalabilmek için aşırı kahve, çay veya enerji içeceği tüketme ihtiyacı duyarım.", dimension="vitality", reverse=True),
                    SurveyQuestion("se_7", "Gün içinde yeterli miktarda su içer ve dengeli beslenmeye özen gösteririm.", dimension="wellness"),
                    SurveyQuestion("se_8", "Haftada en az 2-3 gün yürüyüş, esneme veya hafif spor yaparak bedenimi zinde tutarım.", dimension="wellness"),
                ],
                low_label="Düşük Enerji / Uyku Riski",
                mid_label="Orta Düzey Enerji",
                high_label="Optimum Biyolojik Ritim ve Yüksek Enerji"
            ),
        }

    @staticmethod
    def score_likert_answers(defn: SurveyDefinition, answers: Dict[str, Any]) -> Dict[str, Any]:
        score = 0
        max_score = 0
        dim_scores = {d: {"score": 0, "max": 0} for d in defn.dimensions}

        for q in defn.questions:
            raw = _to_int(answers.get(q.key, 0), 0)
            raw = int(_clamp(raw, SurveyCatalog.LIKERT_MIN, SurveyCatalog.LIKERT_MAX)) if raw else 0
            if raw == 0:
                continue
            val = raw
            if q.reverse:
                val = (SurveyCatalog.LIKERT_MAX + SurveyCatalog.LIKERT_MIN) - raw
            
            score += val
            max_score += SurveyCatalog.LIKERT_MAX

            if q.dimension in dim_scores:
                dim_scores[q.dimension]["score"] += val
                dim_scores[q.dimension]["max"] += SurveyCatalog.LIKERT_MAX

        ratio = (score / max_score) if max_score > 0 else 0.0

        dim_percentages = {}
        for d, data in dim_scores.items():
            dim_ratio = (data["score"] / data["max"]) if data["max"] > 0 else 0.0
            dim_name = defn.dimensions.get(d, d)
            dim_percentages[d] = {
                "name": dim_name,
                "score": data["score"],
                "max": data["max"],
                "pct": int(dim_ratio * 100)
            }

        return {
            "score": score,
            "max": max_score,
            "ratio": ratio,
            "pct": int(ratio * 100),
            "dimensions": dim_percentages,
            "risk_inverted": defn.risk_inverted
        }

# -----------------------------------------------------------
# 2) Gelişmiş Çok Boyutlu Profil Analiz Motoru & Koçluk Reçetesi
# -----------------------------------------------------------

class StudentProfileAnalyzerV2:
    @staticmethod
    def analyze(
        completed_surveys: Dict[str, Any],
        student_name: Optional[str] = None,
        branch: Optional[str] = None
    ) -> Dict[str, Any]:
        completed_surveys = completed_surveys or {}
        surveys = SurveyCatalog.all_surveys()

        def _extract_answers(payload):
            if payload is None: return {}
            if isinstance(payload, dict) and "answers" in payload:
                return payload["answers"]
            return payload

        scored = {}
        for code, defn in surveys.items():
            if code not in completed_surveys:
                continue
            answers = _extract_answers(completed_surveys.get(code))
            if not answers: continue
            
            if not inspect_answers(defn.questions, answers).complete:
                continue
            sc = SurveyCatalog.score_likert_answers(defn, answers)
            scored[code] = {
                "title": defn.title,
                "category": defn.category,
                "score": sc["score"],
                "max": sc["max"],
                "ratio": sc["ratio"],
                "pct": sc["pct"],
                "dimensions": sc["dimensions"],
                "risk_inverted": defn.risk_inverted
            }

        def g_pct(code, default=0):
            return scored.get(code, {}).get("pct", default)

        vark_dims = scored.get("vark_learning", {}).get("dimensions", {})
        v_pct = vark_dims.get("visual", {}).get("pct", 0)
        a_pct = vark_dims.get("auditory", {}).get("pct", 0)
        r_pct = vark_dims.get("read_write", {}).get("pct", 0)
        k_pct = vark_dims.get("kinesthetic", {}).get("pct", 0)

        procrastination = g_pct("procrastination", 0)
        anxiety = g_pct("exam_anxiety", 0)
        habits = g_pct("study_habits", 50)
        efficacy = g_pct("self_efficacy", 50)
        time_mgmt = g_pct("time_management", 50)
        mindset = g_pct("mindset_resilience", 50)
        distraction = g_pct("digital_distraction", 0)
        sleep = g_pct("sleep_energy", 50)

        learning_styles = [("Görsel", v_pct), ("İşitsel", a_pct), ("Okuma/Yazma", r_pct), ("Kinestetik", k_pct)]
        learning_styles.sort(key=lambda x: x[1], reverse=True)
        dominant_style = learning_styles[0][0] if learning_styles[0][1] > 0 else "Henüz Belirlenmedi"

        positive_avg = (habits + efficacy + time_mgmt + mindset + sleep) / 5.0
        risk_index = int(_clamp((anxiety * 0.40 + procrastination * 0.35 + distraction * 0.25), 0, 100))
        academic_health = int(_clamp(positive_avg * 0.70 + (100 - risk_index) * 0.30, 0, 100))

        labels = []
        if dominant_style != "Henüz Belirlenmedi":
            labels.append(f"🎨 Baskın Öğrenme Kanalı: {dominant_style}")
        if anxiety >= 65:
            labels.append("⚠️ Yüksek Sınav Kaygısı")
        elif anxiety <= 30 and "exam_anxiety" in scored:
            labels.append("🧘 Sağlıklı / Sakin Kaygı Düzeyi")

        if procrastination >= 65:
            labels.append("⏳ Ciddi Akademik Erteleme Riski")
        elif procrastination <= 30 and "procrastination" in scored:
            labels.append("🚀 Yüksek Eyleme Geçme Hızı")

        if distraction >= 65:
            labels.append("📱 Dijital Dağılma / Ekran Bağımlılığı")
        if mindset >= 75:
            labels.append("🌟 Güçlü Gelişim Zihniyeti (Growth Mindset)")
        elif mindset <= 40 and "mindset_resilience" in scored:
            labels.append("🧱 Sabit Zihniyet / Hata Korkusu")

        if habits >= 75:
            labels.append("📘 Üst Düzey Çalışma Disiplini")
        if efficacy >= 75:
            labels.append("🎯 Yüksek Akademik Öz-Yeterlik")

        coach_strategy, student_action_tasks = StudentProfileAnalyzerV2._build_prescription(
            dominant_style, v_pct, a_pct, r_pct, k_pct,
            procrastination, anxiety, distraction, mindset, habits, time_mgmt
        )

        return {
            "academic_health": academic_health,
            "risk_index": risk_index,
            "dominant_style": dominant_style,
            "scores": {
                "vark": {"visual": v_pct, "auditory": a_pct, "read_write": r_pct, "kinesthetic": k_pct},
                "procrastination": procrastination,
                "anxiety": anxiety,
                "habits": habits,
                "efficacy": efficacy,
                "time_mgmt": time_mgmt,
                "mindset": mindset,
                "distraction": distraction,
                "sleep": sleep,
            },
            "surveys_scored": scored,
            "labels": labels,
            "coach_strategy": coach_strategy,
            "student_action_tasks": student_action_tasks,
            "summary_text": (
                f"Genel Akademik Sağlık: {academic_health}/100 | Risk İndeksi: {risk_index}/100 | "
                f"Baskın Stil: {dominant_style} | Tamamlanan Envanter: {len(scored)}/9"
            )
        }

    @staticmethod
    def _build_prescription(
        dominant_style, v_pct, a_pct, r_pct, k_pct,
        procrastination, anxiety, distraction, mindset, habits, time_mgmt
    ) -> Tuple[List[str], List[str]]:
        strategy = []
        tasks = []

        if dominant_style == "Görsel":
            strategy.append("• <b>Görsel Hafıza Desteği:</b> Öğrenciye düz metin okutmak yerine zihin haritaları (mind-map), renkli formül kartları ve şematik konu özetleri kullandırın.")
            tasks.append("Bu hafta zorlandığın bir ders için renkli zihin haritası veya formül tablosu çıkarıp çalışma masanın karşısına as.")
        elif dominant_style == "İşitsel":
            strategy.append("• <b>İşitsel Pekiştirme:</b> Konu anlatımlı kaliteli videolardan faydalanmasını ve soru çözerken sesli mantık yürütmesini teşvik edin.")
            tasks.append("Öğrendiğin yeni konuyu bir başkasına veya kendine sesli olarak 5 dakika anlat.")
        elif dominant_style == "Okuma/Yazma":
            strategy.append("• <b>Metin ve Yazarak Kodlama:</b> Konuyu kendi cümleleriyle özetlemesini ve çözümlü soru bankalarındaki açıklamaları satır satır incelemesini sağlayın.")
            tasks.append("Her konu bitiminde 1 sayfalık 'Kendi Cümlelerimle Özet' sayfası hazırla.")
        elif dominant_style == "Kinestetik":
            strategy.append("• <b>Uygulamalı & Soru Odaklı:</b> Uzun teorik dersler yerine 'kısa konu özeti + bol soru çözümü' modelini uygulayın.")
            tasks.append("Konu anlatımını 20 dakikada kesip hemen ardından en az 30 soru çözerek pratik yap.")

        if procrastination >= 60:
            strategy.append("• <b>Mikro-Hedefleme (Erteleme Kırıcı):</b> Büyük ödevler öğrenciyi korkutuyor. Ödevleri 'Günde 20 soru' gibi küçük parçalara bölün ve '5 Dakika Kuralı'nı benimsetin.")
            tasks.append("Zorlandığın dersin başına geçerken 'Sadece 5 dakika bakacağım' diyerek masaya otur; göreceksin ki devamı gelecek.")

        if anxiety >= 60:
            strategy.append("• <b>Süreç Odaklı Geri Bildirim:</b> Net dalgalanmalarına odaklanmak yerine öğrencinin çabasını ve çözdüğü soru sayısını takdir edin. Deneme öncesi 4-7-8 nefes tekniğini çalıştırın.")
            tasks.append("Denemeye başlamadan önce gözlerini kapatıp 3 kez derin diyafram nefesi al (4 sn al, 7 sn tut, 8 sn ver).")
        
        if distraction >= 60:
            strategy.append("• <b>Fiziksel Telefon İzolasyonu:</b> Telefon masada kaldığı sürece odaklanma verimi %50 düşer. Seanslarda ders esnasında telefonu başka odaya bırakma taahhüdü alın.")
            tasks.append("Çalışma seansları boyunca telefonunu tamamen sessize alıp başka bir odaya bırak.")

        if mindset <= 45:
            strategy.append("• <b>Hata Kültürü (Growth Mindset):</b> Yanlış soruların eksikleri kapatan bir hazine olduğunu anlatın. 'Hata Defteri' tutmasını zorunlu kılın.")
            tasks.append("Bu hafta denemede boş ve yanlış bıraktığın tüm soruları kesip 'Yanlış Defteri'ne yapıştır ve çözümlerini öğren.")

        if not tasks:
            tasks.append("Günde en az 40'ar dakikalık 3 odaklanma bloku oluştur ve çalışma süreni not et.")
            tasks.append("Haftalık soru hedefini günlük eşit parçalara bölerek düzenli ilerle.")
            tasks.append("Pazar akşamı haftalık değerlendirme yapıp yeni haftanın planını koçunla netleştir.")

        return strategy, tasks

# -----------------------------------------------------------
# 3) SurveyManager (UI Sınıfı) - Modern Yönetici Paneli
# -----------------------------------------------------------

class SurveyManager(QWidget):
    """
    Öğrenci Öz-Değerlendirme ve Görüşme Desteği
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.catalog = SurveyCatalog.all_surveys()
        self.current_student_id = None
        self.current_student_name = ""
        self.current_survey_code = None
        self.completed_surveys_data = {}
        self.answers = {}
        self._setup_ui()
        self._setup_context_menu()

    def set_student(self, student_id: int, student_name: str = ""):
        """Dışarıdan (CoachingManager) çağrılır."""
        self.current_student_id = student_id
        self.current_student_name = student_name
        self.reset_form()
        if self.current_student_id:
            self._load_history()

    def _setup_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(10, 10, 10, 10)
        main.setSpacing(10)

        # -------------------------------------------------------------
        # 1. Üst Yönetici Araç Çubuğu (Kompakt, Minimalist, Tek Bakışta Yönetim)
        # -------------------------------------------------------------
        top_card = QFrame()
        top_card.setStyleSheet("""
            QFrame#topCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 6px 10px;
            }
        """)
        top_card.setObjectName("topCard")
        from PyQt6.QtWidgets import QSizePolicy
        top_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        top_vlay = QVBoxLayout(top_card)
        top_vlay.setContentsMargins(2, 2, 2, 2)
        top_vlay.setSpacing(4)

        # 1. Satır: Form Seçici (Sol) & Kompakt Aksiyon Butonları (Sağ)
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        lbl_title = QLabel("🧠 <b style='color:#1e3a8a; font-size:12px;'>Öz-Değerlendirme:</b>")
        row1.addWidget(lbl_title)

        self.cmb_survey = QComboBox()
        self.cmb_survey.setMinimumWidth(260)
        self.cmb_survey.setFixedHeight(28)
        self.cmb_survey.setStyleSheet("""
            QComboBox {
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
                color: #1e293b;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #e2e8f0;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
                background: transparent;
            }
            QComboBox::drop-down:hover { background: #f1f5f9; }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #64748b;
            }
        """)
        self.cmb_survey.addItem("-- Envanter / Anket Seçiniz --", "")
        for code, defn in self.catalog.items():
            self.cmb_survey.addItem(f"[{defn.category}] {defn.title}", code)
        self.cmb_survey.currentTextChanged.connect(self._load_survey_form_wrapper)
        row1.addWidget(self.cmb_survey)

        row1.addStretch()

        # Buton 1: 360 Raporu
        btn_analyze = QPushButton("📊 360° Rapor")
        btn_analyze.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_analyze.setFixedHeight(28)
        btn_analyze.setToolTip("Tam yanıtlı, hassas olmayan çalışma anketlerinden görüşmeye yardımcı özet")
        btn_analyze.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1);
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 5px;
                padding: 0 10px;
                border: none;
            }
            QPushButton:hover { background: #4338ca; 
                color: #FFFFFF;}
        """)
        btn_analyze.clicked.connect(self._show_general_analysis)
        row1.addWidget(btn_analyze)

        # Buton 2: Yazdır
        btn_print = QPushButton("🖨️ Yazdır")
        btn_print.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_print.setFixedHeight(28)
        btn_print.setToolTip("Gelişim raporunu yazdırın veya PDF olarak dışa aktarın")
        btn_print.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc;
                color: #334155;
                font-weight: bold;
                font-size: 11px;
                border-radius: 5px;
                padding: 0 10px;
                border: 1px solid #cbd5e1;
            }
            QPushButton:hover { background-color: #f1f5f9; 
                color: #15191E;}
        """)
        btn_print.clicked.connect(self._print_results)
        row1.addWidget(btn_print)

        # Buton 3: WhatsApp Özeti
        btn_copy_wa = QPushButton("📱 WhatsApp")
        btn_copy_wa.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy_wa.setFixedHeight(28)
        btn_copy_wa.setToolTip("Veli ve öğrenciye gönderilmeye hazır şık formatlı analiz özetini panoya kopyalar")
        btn_copy_wa.setStyleSheet("""
            QPushButton {
                background-color: #25D366;
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 5px;
                padding: 0 10px;
                border: none;
            }
            QPushButton:hover { background-color: #1ebd5b; 
                color: #15191E;}
        """)
        btn_copy_wa.clicked.connect(self._copy_current_whatsapp)
        row1.addWidget(btn_copy_wa)

        # Buton 4: Öğrenciye Testi Gönder
        btn_send_student = QPushButton("📲 Gönder")
        btn_send_student.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_send_student.setFixedHeight(28)
        btn_send_student.setToolTip("Seçili anketin sorularını öğrencinin uzaktan telefondan yanıtlaması için WhatsApp metni olarak hazırlar")
        btn_send_student.setStyleSheet("""
            QPushButton {
                background-color: #eff6ff;
                color: #1d4ed8;
                font-weight: bold;
                font-size: 11px;
                border-radius: 5px;
                padding: 0 10px;
                border: 1px solid #bfdbfe;
            }
            QPushButton:hover { background-color: #dbeafe; 
                color: #15191E;}
        """)
        btn_send_student.clicked.connect(self._send_survey_via_whatsapp)
        row1.addWidget(btn_send_student)

        # V9: separate opt-in link action; existing WhatsApp text remains untouched.
        btn_online_survey = QPushButton("🔗 Çevrim İçi")
        btn_online_survey.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_online_survey.setFixedHeight(28)
        btn_online_survey.setToolTip("Tek kullanımlık bağlantıyı panoya kopyalar. HTTPS sunucusu gerektirir.")
        btn_online_survey.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #334155;
                font-weight: bold;
                font-size: 11px;
                border-radius: 5px;
                padding: 0 10px;
                border: 1px solid #cbd5e1;
            }
            QPushButton:hover { background-color: #e2e8f0; 
                color: #15191E;}
        """)
        btn_online_survey.clicked.connect(self._online_survey_menu_v9)
        row1.addWidget(btn_online_survey)

        top_vlay.addLayout(row1)

        # 2. Satır: Kompakt Rozetler (KPI Badges)
        row2 = QHBoxLayout()
        row2.setSpacing(6)

        self.lbl_badge_total = QLabel("📋 9 Form")
        self.lbl_badge_total.setStyleSheet("background: #f1f5f9; color: #475569; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 10px;")
        row2.addWidget(self.lbl_badge_total)

        self.lbl_badge_completed = QLabel("✅ 0 / 9 Tamamlandı")
        self.lbl_badge_completed.setStyleSheet("background: #f0fdf4; color: #166534; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 10px; border: 1px solid #bbf7d0;")
        row2.addWidget(self.lbl_badge_completed)

        self.lbl_badge_health = QLabel("📋 Yanıt Durumu: --")
        self.lbl_badge_health.setStyleSheet("background: #eff6ff; color: #1e40af; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 10px; border: 1px solid #bfdbfe;")
        row2.addWidget(self.lbl_badge_health)

        self.lbl_badge_risk = QLabel("🔒 Hassas veriler ayrı")
        self.lbl_badge_risk.setStyleSheet("background: #fef2f2; color: #991b1b; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 10px; border: 1px solid #fecaca;")
        row2.addWidget(self.lbl_badge_risk)

        row2.addStretch()
        top_vlay.addLayout(row2)

        main.addWidget(top_card, 0)

        # -------------------------------------------------------------
        # 2. Ana Çalışma Alanı: Splitter (Sol: Form & Butonlar, Sağ: Geçmiş & Koçluk Reçetesi)
        # -------------------------------------------------------------
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: #e2e8f0; width: 2px; }")

        # --- SOL PANEL: Form Konteyneri (İlerleme + Sorular Scroll + Sabit Alt Eylem Barı) ---
        left_container = QWidget()
        left_vlay = QVBoxLayout(left_container)
        left_vlay.setContentsMargins(0, 0, 0, 0)
        left_vlay.setSpacing(6)

        # 1. Başlık ve İlerleme Kartı (Kompakt Tek/İki Satır Frame)
        self.survey_hdr_frame = QFrame()
        self.survey_hdr_frame.setStyleSheet("""
            QFrame#surveyHdrFrame {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 4px 8px;
            }
            QFrame#surveyHdrFrame QLabel {
                border: none;
                background: transparent;
            }
        """)
        self.survey_hdr_frame.setObjectName("surveyHdrFrame")
        self.survey_hdr_frame.setVisible(False)
        sh_lay = QVBoxLayout(self.survey_hdr_frame)
        sh_lay.setContentsMargins(4, 3, 4, 3)
        sh_lay.setSpacing(2)

        sh_top = QHBoxLayout()
        sh_top.setSpacing(6)

        self.lbl_survey_cat = QLabel("KATEGORİ")
        self.lbl_survey_cat.setStyleSheet("font-size: 9px; font-weight: bold; color: #166534; background: #dcfce7; padding: 1px 6px; border-radius: 3px;")
        sh_top.addWidget(self.lbl_survey_cat)

        self.lbl_survey_tit = QLabel("Envanter Başlığı")
        self.lbl_survey_tit.setStyleSheet("font-size: 12px; font-weight: bold; color: #0f172a;")
        sh_top.addWidget(self.lbl_survey_tit)

        sh_top.addStretch()

        self.lbl_survey_prog = QLabel("🎯 0 / 0 (%0)")
        self.lbl_survey_prog.setStyleSheet("font-size: 10px; font-weight: bold; color: #1e40af;")
        sh_top.addWidget(self.lbl_survey_prog)

        self.survey_pbar = QProgressBar()
        self.survey_pbar.setRange(0, 100)
        self.survey_pbar.setValue(0)
        self.survey_pbar.setFixedWidth(100)
        self.survey_pbar.setFixedHeight(6)
        self.survey_pbar.setTextVisible(False)
        self.survey_pbar.setStyleSheet("QProgressBar { background: #f1f5f9; border-radius: 3px; border: none; } QProgressBar::chunk { background: #22c55e; border-radius: 3px; }")
        sh_top.addWidget(self.survey_pbar)

        sh_lay.addLayout(sh_top)

        self.lbl_survey_dsc = QLabel("Açıklama...")
        self.lbl_survey_dsc.setStyleSheet("font-size: 10px; color: #64748b;")
        self.lbl_survey_dsc.setWordWrap(True)
        sh_lay.addWidget(self.lbl_survey_dsc)

        left_vlay.addWidget(self.survey_hdr_frame)

        # 2. Sorular Kaydırma Alanı (Scroll Area)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: 1px solid #e2e8f0; border-radius: 8px; background: white; }")
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: #ffffff;")
        self.content_lay = QVBoxLayout(self.content_widget)
        self.content_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.content_lay.setContentsMargins(8, 8, 8, 8)
        self.content_lay.setSpacing(6)
        self.scroll.setWidget(self.content_widget)
        left_vlay.addWidget(self.scroll, 1)

        # 3. SABİT ALT EYLEM BARI (Ekran boyutu ne olursa olsun daima görünür!)
        self.bottom_dock = QFrame()
        self.bottom_dock.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 4px 8px;
            }
        """)
        self.bottom_dock.setVisible(False)
        bot_lay = QHBoxLayout(self.bottom_dock)
        bot_lay.setContentsMargins(4, 2, 4, 2)
        bot_lay.setSpacing(8)

        self.btn_reset_survey = QPushButton("🔄 Temizle")
        self.btn_reset_survey.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset_survey.setFixedHeight(30)
        self.btn_reset_survey.setToolTip("Bu anket için işaretlenen tüm şıkları temizle")
        self.btn_reset_survey.setStyleSheet("""
            QPushButton {
                background: #f8fafc;
                color: #64748b;
                font-weight: 600;
                font-size: 11px;
                border-radius: 5px;
                padding: 0 10px;
                border: 1px solid #cbd5e1;
            }
            QPushButton:hover { background: #fee2e2; color: #b91c1c; border-color: #fca5a5; }
        """)
        self.btn_reset_survey.clicked.connect(self._clear_current_form)
        bot_lay.addWidget(self.btn_reset_survey)

        self.btn_quick = QPushButton("Hazır Cevap Kapalı")
        self.btn_quick.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_quick.setFixedHeight(30)
        self.btn_quick.setToolTip("Gerçek öğrenci cevaplarını taklit etmemek için otomatik doldurma kapalıdır.")
        self.btn_quick.setStyleSheet("""
            QPushButton {
                background: #eff6ff;
                color: #1d4ed8;
                font-weight: 600;
                font-size: 11px;
                border-radius: 5px;
                padding: 0 10px;
                border: 1px solid #bfdbfe;
            }
            QPushButton:hover { background: #dbeafe; 
                color: #15191E;}
        """)
        self.btn_quick.setEnabled(False)
        bot_lay.addWidget(self.btn_quick)

        self.lbl_dock_status = QLabel("Lütfen soruları yanıtlayınız...")
        self.lbl_dock_status.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 500;")
        bot_lay.addWidget(self.lbl_dock_status)

        bot_lay.addStretch()

        self.btn_finish = QPushButton("✅ Yanıtları Kaydet / Özeti Gör")
        self.btn_finish.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_finish.setFixedHeight(32)
        self.btn_finish.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16a34a, stop:1 #15803d);
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 5px;
                padding: 0 16px;
                border: none;
            }
            QPushButton:hover { background: #15803d; 
                color: #FFFFFF;}
        """)
        self.btn_finish.clicked.connect(self._complete_survey)
        bot_lay.addWidget(self.btn_finish)

        left_vlay.addWidget(self.bottom_dock, 0)
        splitter.addWidget(left_container)

        # --- SAĞ PANEL: Geçmiş Listesi ve Hızlı Koçluk Reçetesi Kartı ---
        right_panel = QFrame()
        right_panel.setObjectName("surveyRightPanel")
        right_panel.setMinimumWidth(240)
        right_panel.setMaximumWidth(320)
        right_panel.setStyleSheet("""
            QFrame#surveyRightPanel {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
            QFrame#surveyRightPanel QLabel {
                border: none;
                background: transparent;
            }
        """)
        r_lay = QVBoxLayout(right_panel)
        r_lay.setContentsMargins(8, 8, 8, 8)
        r_lay.setSpacing(6)

        lbl_hist_title = QLabel("📋 <b>Tamamlanan Envanterler</b>")
        lbl_hist_title.setStyleSheet("font-size: 12px; color: #0f172a; border: none;")
        r_lay.addWidget(lbl_hist_title)

        lbl_hist_desc = QLabel("Geçmiş cevapları görmek veya analizi açmak için tıklayın.")
        lbl_hist_desc.setStyleSheet("font-size: 10px; color: #64748b; border: none; margin-bottom: 2px;")
        r_lay.addWidget(lbl_hist_desc)

        self.history_list = QListWidget()
        self.history_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                background: #f8fafc;
                padding: 3px;
            
                color: #15191E;}
            QListWidget::item {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 5px;
                padding: 6px;
                margin-bottom: 4px;
            }
            QListWidget::item:hover {
                background: #f0fdf4;
                border-color: #86efac;
            }
            QListWidget::item:selected {
                background: #eff6ff;
                border: 1px solid #3b82f6;
                color: #1e3a8a;
            }
        """)
        self.history_list.itemClicked.connect(self._on_history_clicked)
        r_lay.addWidget(self.history_list, 1)

        # Sağ Panel Alt: Koçluk Reçetesi Kartı
        self.pdr_tip_box = QFrame()
        self.pdr_tip_box.setStyleSheet("QFrame { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 6px; }")
        pt_lay = QVBoxLayout(self.pdr_tip_box)
        pt_lay.setContentsMargins(4, 4, 4, 4)
        pt_lay.setSpacing(3)

        lbl_pt_tit = QLabel("💡 <b>Görüşme İpucu:</b>")
        lbl_pt_tit.setStyleSheet("font-size: 10px; color: #166534; border: none;")
        pt_lay.addWidget(lbl_pt_tit)

        self.lbl_pdr_tip = QLabel("Bir envanter seçildiğinde o alana özel pedagojik yaklaşım ipuçları burada görünür.")
        self.lbl_pdr_tip.setStyleSheet("font-size: 10px; color: #15803d; border: none;")
        self.lbl_pdr_tip.setWordWrap(True)
        pt_lay.addWidget(self.lbl_pdr_tip)
        r_lay.addWidget(self.pdr_tip_box)

        # Sağ Panel Alt Buton: Sil
        btn_del_hist = QPushButton("🗑️ Seçili Anketi Sil")
        btn_del_hist.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del_hist.setFixedHeight(28)
        btn_del_hist.setStyleSheet("""
            QPushButton {
                background: #ffffff;
                color: #b91c1c;
                font-size: 11px;
                font-weight: 600;
                border: 1px solid #fecaca;
                border-radius: 5px;
            }
            QPushButton:hover { background: #fee2e2; 
                color: #15191E;}
        """)
        btn_del_hist.clicked.connect(self._delete_selected_history)
        r_lay.addWidget(btn_del_hist)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 76)
        splitter.setStretchFactor(1, 24)

        main.addWidget(splitter, 1)
        self._show_empty_intro()

    def _show_empty_intro(self):
        while self.content_lay.count():
            child = self.content_lay.takeAt(0)
            if child:
                w = child.widget()
                if w:
                    w.hide()
                    w.setParent(None)
                    w.deleteLater()

        if hasattr(self, 'survey_hdr_frame'):
            self.survey_hdr_frame.setVisible(False)
        if hasattr(self, 'bottom_dock'):
            self.bottom_dock.setVisible(False)
        if hasattr(self, 'lbl_pdr_tip'):
            self.lbl_pdr_tip.setText("Bir form seçerek öğrenciyle çalışma deneyimleri hakkında konuşabilirsiniz; yanıtlar kesin tanı değildir.")

        frame = QFrame()
        frame.setStyleSheet("background: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 12px; padding: 36px;")
        l = QVBoxLayout(frame)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.setSpacing(12)

        icon = QLabel("🧠")
        icon.setStyleSheet("font-size: 44px; border: none; background: transparent;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(icon)

        t = QLabel("<b>Öğrenci Öz-Değerlendirme ve Koçluk Görüşmeleri</b>")
        t.setStyleSheet("font-size: 16px; color: #0f172a; border: none; background: transparent;")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(t)
        info_txt = (
            "Yukarıdaki menüden bir envanter seçerek öğrencinin;<br>"
            "• Tercih ettiği çalışma yöntemlerini<br>"
            "• Çalışmaya başlamayı zorlaştıran durumları<br>"
            "• Sınavla ilgili kendi deneyimlerini (yetkili görüşmede)<br>"
            "• Odak, zaman ve çalışma alışkanlıklarını<br>"
            "konuşmak üzere kaydedebilirsiniz; sonuçlar tanı veya kesin reçete değildir."
        )
        info = QLabel(info_txt)
        info.setStyleSheet("font-size: 13px; color: #475569; line-height: 1.6; border: none; background: transparent;")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(info)

        self.content_lay.addWidget(frame)

    def _load_survey_form_wrapper(self, text=None):
        self._load_survey_form()

    def _load_survey_form(self, saved_answers=None):
        code = self.cmb_survey.currentData()
        
        while self.content_lay.count():
            child = self.content_lay.takeAt(0)
            if child:
                w = child.widget()
                if w:
                    w.hide()
                    w.setParent(None)
                    w.deleteLater()
            
        if not code or code not in self.catalog:
            self._show_empty_intro()
            return

        self.current_survey_code = code
        defn = self.catalog[code]
        self.answers = saved_answers.copy() if isinstance(saved_answers, dict) else {}
        self._history_preview_mode = saved_answers is not None

        # 1. Sticky Header Frame Bilgilerini Doldur
        if hasattr(self, 'survey_hdr_frame'):
            self.survey_hdr_frame.setVisible(True)
            self.lbl_survey_cat.setText(f"KATEGORİ: {defn.category.upper()}")
            self.lbl_survey_tit.setText(defn.title)
            self.lbl_survey_dsc.setText(defn.description)
            self._update_progress_display()

        # 2. PDR İpucu Notunu Güncelle
        pdr_notes = {
            "vark_learning": "Çalışma tercihlerinden yola çıkarak farklı yöntemleri birlikte deneyin; sabit öğrenme stili varsaymayın.",
            "procrastination": "Öğrenciye hangi durumlarda başlamanın zorlaştığını ve neyin yardımcı olduğunu sorun; nedene karar vermeyin.",
            "exam_anxiety": "Sınav deneyimiyle ilgili yanıtlar hassastır; öğrenciyi etiketlemeden yetkili uzmanla görüşme gereksinimini değerlendirin.",
            "study_habits": "Masa başı disiplini ve deneme analizi alışkanlığı eksikse haftalık somut blok planlama yapınız.",
            "self_efficacy": "Öz-yeterlik düşüklüğünde küçük başarılabilir adımlarla başarı hazzını yeniden inşa ediniz.",
            "time_management": "Pomodoro veya 50+10 blok yöntemini öğrencinin odaklanma süresine göre kalibre ediniz.",
            "growth_mindset": "Hataları 'yetersizlik' değil, beynin öğrenme fırsatı olarak görmesini sağlayan koçluk dili kullanınız.",
            "digital_distraction": "Öğrenciyle dikkat dağıtıcılar konusunda uygulanabilir seçenekleri görüşün.",
            "sleep_energy": "Uyku ve enerjiyle ilgili öz-bildirimler hassastır; gerekirse uygun uzman desteği önerin."
        }
        if hasattr(self, 'lbl_pdr_tip'):
            self.lbl_pdr_tip.setText(pdr_notes.get(code, "Bu form görüşmede ele alınabilecek çalışma deneyimleriyle ilgilidir."))

        # 3. Sabit Alt Eylem Barını Aç ve Güncelle
        if hasattr(self, 'bottom_dock'):
            self.bottom_dock.setVisible(True)
            if saved_answers is not None:
                self.btn_finish.setText("📊 Geçmiş Kaydı İncele (Kaydetme Yok)")
            else:
                self.btn_finish.setText("✅ Yanıtları Kaydet / Özeti Gör")

        # 4. Soruları Oluştur
        self.button_groups = {}

        for idx, q in enumerate(defn.questions):
            q_card = QFrame()
            q_card.setObjectName("qCard")
            q_card.setStyleSheet("""
                QFrame#qCard {
                    background: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 6px;
                }
                QFrame#qCard:hover {
                    border-color: #93c5fd;
                }
                QFrame#qCard QLabel {
                    border: none;
                    background: transparent;
                }
            """)
            q_lay = QVBoxLayout(q_card)
            q_lay.setContentsMargins(10, 6, 10, 6)
            q_lay.setSpacing(4)

            dim_label = ""
            if q.dimension and q.dimension in defn.dimensions:
                dim_name = defn.dimensions[q.dimension]
                dim_label = f" <span style='color: #6366f1; font-size: 10px; font-weight: 600;'>[{dim_name}]</span>"

            lbl_q = QLabel(f"<b>{idx+1}.</b> {q.text}{dim_label}")
            lbl_q.setStyleSheet("font-size: 12px; color: #1e293b; line-height: 1.3;")
            lbl_q.setWordWrap(True)
            q_lay.addWidget(lbl_q)

            row = QHBoxLayout()
            row.setSpacing(6)
            bg = QButtonGroup(q_card)
            bg.buttonClicked.connect(lambda btn, k=q.key: self._on_answer_changed(k, btn))
            self.button_groups[q.key] = bg

            options = [
                ("1: Hiç Katılmıyorum", 1),
                ("2: Katılmıyorum", 2),
                ("3: Kararsızım", 3),
                ("4: Katılıyorum", 4),
                ("5: Tamamen Katılıyorum", 5)
            ]

            saved_val = self.answers.get(q.key, None)

            for txt, val in options:
                rb = QRadioButton(txt)
                rb.setProperty("val", val)
                rb.setCursor(Qt.CursorShape.PointingHandCursor)
                rb.setStyleSheet("""
                    QRadioButton {
                        font-size: 10px;
                        color: #475569;
                        spacing: 4px;
                        padding: 1px 4px;
                    }
                    QRadioButton:hover {
                        color: #1e293b;
                        background: #f1f5f9;
                        border-radius: 4px;
                    }
                    QRadioButton::indicator:checked {
                        background-color: #2563eb;
                        border: 2px solid white;
                        border-radius: 5px;
                    }
                """)
                bg.addButton(rb)
                row.addWidget(rb)

                if saved_val is not None and saved_val == val:
                    rb.setChecked(True)

            q_lay.addLayout(row)
            self.content_lay.addWidget(q_card)

        self._update_progress_display()

    def _quick_fill_average(self):
        """Disabled: artificial responses must never be stored as student answers."""
        QMessageBox.information(self, "Gerçek yanıt koruması",
            "Otomatik 4 puan doldurma kapalıdır. Öğrenci yanıtları tek tek işaretlenmelidir.")

    def _on_answer_changed(self, key, btn):
        val = btn.property("val")
        self.answers[key] = val
        # The original history remains immutable; changing a response explicitly
        # creates a NEW version only if the teacher presses Save.
        if getattr(self, '_history_preview_mode', False):
            self._history_preview_mode = False
            self.btn_finish.setText('✅ Değiştirilen Yanıtları Yeni Kayıt Olarak Kaydet')
        self._update_progress_display()

    def _complete_survey(self):
        if not self.current_survey_code:
            return
        if not self.current_student_id:
            QMessageBox.warning(self, "Hata", "Lütfen önce sol listeden bir öğrenci seçiniz.")
            return
        definition = self.catalog[self.current_survey_code]
        audit = inspect_answers(definition.questions, self.answers)
        if audit.invalid_keys:
            QMessageBox.warning(self, "Geçersiz Yanıt", "Bazı yanıtlar 1–5 aralığında değil; kayıt yapılmadı.")
            return
        if getattr(self, '_history_preview_mode', False):
            self._show_survey_result_modal(self.current_survey_code, audit.valid_answers)
            return
        if audit.partial:
            res = QMessageBox.question(
                self, "Eksik Yanıt — Taslak Kaydı",
                f"Yanıtlanan: {audit.answered}/{audit.expected}. Eksik cevaplar tamamlanmış anket gibi analiz edilmeyecek. Taslak kaydedilsin mi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if res != QMessageBox.StandardButton.Yes:
                return
        connection = db.get_conn()
        try:
            connection.execute(
                "INSERT INTO ogrenci_anket (ogrenci_id, anket_kodu, cevaplar) VALUES (?, ?, ?)",
                (self.current_student_id, self.current_survey_code,
                 json.dumps(audit.valid_answers, ensure_ascii=False)),
            )
            connection.commit()
        except Exception as exc:
            QMessageBox.critical(self, "Kayıt Hatası", f"Anket kaydı yapılamadı: {exc}")
            return
        finally:
            connection.close()
        self._load_history()
        if audit.complete:
            self._show_survey_result_modal(self.current_survey_code, audit.valid_answers)
        else:
            QMessageBox.information(self, "Taslak Kaydedildi",
                "Eksik yanıtlar saklandı; genel profil veya puanlı rapora dahil edilmedi.")

    def _show_survey_result_modal(self, code: str, answers: Dict[str, Any]):
        definition = self.catalog.get(code)
        if definition is None:
            return
        audit = inspect_answers(definition.questions, answers)
        if not audit.complete:
            QMessageBox.information(self, "Eksik Yanıt",
                f"Bu kayıt {audit.answered}/{audit.expected} yanıt içeriyor. Tamamlanmadan özet üretilemez.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Öğrenci Öz-Değerlendirme Özeti")
        dlg.resize(600, 400)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(f"<b>{escape(definition.title)}</b>"))
        layout.addWidget(QLabel(f"Tam yanıt: {audit.answered}/{audit.expected}"))
        avg = sum(audit.valid_answers.values()) / len(audit.valid_answers)
        layout.addWidget(QLabel(f"İfadelere katılım ortalaması: {avg:.2f} / 5"))
        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setHtml("<p>Bu form öğrencinin kendi beyanını yansıtır; psikolojik tanı, "
                    "öğrenme türü veya bilimsel olarak kalibre edilmiş başarı skoru değildir.</p>"
                    "<p>Sonuçları öğrenciyle görüşme sırasında, ölçüm ve ödev "
                    "kanıtlarıyla birlikte değerlendirin. Öğrenciye otomatik ödev atanmaz.</p>")
        layout.addWidget(txt)
        close = QPushButton("Kapat")
        close.clicked.connect(dlg.accept)
        layout.addWidget(close)
        dlg.exec()

    def _update_progress_display(self):
        if not self.current_survey_code or self.current_survey_code not in self.catalog:
            return
        defn = self.catalog[self.current_survey_code]
        total = len(defn.questions)
        answered = len(self.answers)
        pct = int((answered / total) * 100) if total > 0 else 0
        
        if hasattr(self, 'lbl_survey_prog'):
            self.lbl_survey_prog.setText(f"🎯 Cevaplanan: {answered} / {total} Soru (%{pct})")
        if hasattr(self, 'survey_pbar'):
            self.survey_pbar.setValue(pct)
        if hasattr(self, 'lbl_dock_status'):
            if answered == total:
                self.lbl_dock_status.setText(f"<b style='color:#15803d;'>✅ Tüm sorular tamamlandı ({total}/{total}) - Kaydetmeye hazır!</b>")
            else:
                self.lbl_dock_status.setText(f"{answered}/{total} soru yanıtlandı. Kalan: {total - answered} soru")

    def _clear_current_form(self):
        if not self.current_survey_code: return
        self.answers.clear()
        for bg in self.button_groups.values():
            btn = bg.checkedButton()
            if btn:
                bg.setExclusive(False)
                btn.setChecked(False)
                bg.setExclusive(True)
        self._update_progress_display()

    def _copy_current_whatsapp(self):
        if not self.completed_surveys_data:
            QMessageBox.warning(self, "Uyarı", "Henüz tamamlanmış bir anket bulunmuyor. Önce bir anket tamamlayınız.")
            return
        self._copy_whatsapp_summary({})

    def _online_survey_menu_v9(self):
        """Two actions, one button; avoid growing the crowded teacher toolbar."""
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        create_action = menu.addAction("Yeni güvenli bağlantıyı kopyala")
        review_action = menu.addAction("Gelen yanıtları incele")
        revoke_action = menu.addAction("Gönderilmiş bağlantıyı iptal et")
        choice = menu.exec(self.cursor().pos())
        if choice == create_action:
            self._create_online_survey_v9()
        elif choice == review_action:
            self._review_online_surveys_v9()
        elif choice == revoke_action:
            self._revoke_online_survey_v9()

    def _revoke_online_survey_v9(self):
        if not self.current_student_id:
            QMessageBox.warning(self,"Anket","Önce öğrenciyi seçiniz.")
            return
        from PyQt6.QtWidgets import QInputDialog
        from services.survey_invite_writer_v9 import active_links,revoke_link
        try:
            sid=int(self.current_student_id)
            links=active_links(sid)
        except (ValueError,OSError,sqlite3.Error) as exc:
            QMessageBox.warning(self,"Anket",str(exc))
            return
        if not links:
            QMessageBox.information(self,"Anket","Bu öğrenciye ait aktif bağlantı yok.")
            return
        opts=[f"#{r['id']} · {r['survey_code']} · {r['expires_at'][:16]}" for r in links]
        selected,ok=QInputDialog.getItem(self,"Bağlantı İptali",
                 "İptal edilecek bağlantıyı seçiniz:",opts,0,False)
        if not ok:return
        item=links[opts.index(selected)]
        if QMessageBox.question(self,"Bağlantıyı İptal Et",
            "Seçili öğrencinin bu anket bağlantısı kalıcı olarak iptal edilsin mi?") != QMessageBox.StandardButton.Yes:
            return
        try:revoke_link(sid,int(item['id']))
        except (ValueError,OSError,sqlite3.Error) as exc:
            QMessageBox.warning(self,"Anket",str(exc))
            return
        QMessageBox.information(self,"İptal Edildi","Bağlantı artık kullanılamaz.")

    def _review_online_surveys_v9(self):
        """Existing student context, no new scoring or psychometric labels."""
        if not self.current_student_id:
            QMessageBox.warning(self, "Anket", "Önce öğrenciyi seçiniz.")
            return
        from services.survey_review_v9 import pending_for_student, decide
        sid = int(self.current_student_id)
        dialog = QDialog(self)
        dialog.setWindowTitle("Gelen Çevrim İçi Anketler")
        dialog.resize(660, 520)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Öğrenci: " + (self.current_student_name or str(sid)) +
                                " — Yanıtlar öğretmen onayından önce kaydedilmez."))
        items = QListWidget()
        details = QTextEdit()
        details.setReadOnly(True)
        layout.addWidget(items)
        layout.addWidget(details)
        buttons = QHBoxLayout()
        approve_btn = QPushButton("İncele ve Kabul Et")
        reject_btn = QPushButton("Reddet")
        reload_btn = QPushButton("Yenile")
        buttons.addWidget(approve_btn)
        buttons.addWidget(reject_btn)
        buttons.addWidget(reload_btn)
        layout.addLayout(buttons)
        current = []

        def reload():
            items.clear()
            details.clear()
            current.clear()
            try:
                current.extend(pending_for_student(sid))
            except (ValueError, OSError, sqlite3.Error) as exc:
                QMessageBox.warning(dialog, "Anket", str(exc))
                return
            for row in current:
                item = QListWidgetItem(f"{row['survey_title']} · {row['received_at'][:16]}")
                item.setData(Qt.ItemDataRole.UserRole, row['submission_id'])
                items.addItem(item)
            if not current:
                details.setPlainText("Bekleyen anket bulunmuyor.")

        def selected():
            item=items.currentItem()
            if item is None:return None
            return next((r for r in current if r['submission_id']==item.data(Qt.ItemDataRole.UserRole)),None)

        def show_detail():
            row=selected()
            if not row:return
            lines=[row['survey_title'], 'Yanıt tarihi: '+row['received_at'],
                   'Bu cevaplar öğrencinin kendi bildirdiği görüşlerdir; tanı değildir.', '']
            for i,q in enumerate(row['questions'], 1):
                lines.append(f"{i}. {q['text']}\n   Yanıt: {row['answers'].get(q['key'], '—')} / 5")
            details.setPlainText('\n\n'.join(lines))

        def act(decision):
            row=selected()
            if not row:
                QMessageBox.information(dialog,"Anket","Önce gelen bir anketi seçiniz.")
                return
            label='öğrenci anket geçmişine aktarılsın' if decision=='approved' else 'reddedilsin'
            if QMessageBox.question(dialog,"Onay",f"Seçilen yanıt {label}?") != QMessageBox.StandardButton.Yes:
                return
            try:
                decide(int(row['submission_id']),decision)
            except (ValueError,OSError,sqlite3.Error) as exc:
                QMessageBox.warning(dialog,"İşlem gerçekleşmedi",str(exc))
                return
            reload()
            if decision=='approved':
                self._load_history()

        items.currentItemChanged.connect(lambda *_:show_detail())
        reload_btn.clicked.connect(reload)
        approve_btn.clicked.connect(lambda:act('approved'))
        reject_btn.clicked.connect(lambda:act('rejected'))
        reload()
        dialog.exec()

    def _create_online_survey_v9(self):
        """No automatic WhatsApp sending or student answer writes."""
        if not self.current_student_id or not self.current_survey_code:
            QMessageBox.warning(self, "Anket", "Önce öğrenciyi ve anketi seçiniz.")
            return
        try:
            from services.survey_invite_writer_v9 import create_link
            result = create_link(int(self.current_student_id), self.current_survey_code)
        except (ValueError, RuntimeError, OSError, ImportError) as exc:
            QMessageBox.warning(self, "Çevrim İçi Anket", str(exc))
            return
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(result['url'])
        QMessageBox.information(self, "Bağlantı Hazır",
            "3 gün geçerli tek kullanımlık bağlantı panoya kopyalandı. "
            "WhatsApp veya başka bir güvenli kanaldan yalnızca ilgili öğrenciye gönderiniz. "
            "Yanıtlar öğretmen onayı olmadan öğrenci profiline eklenmez.")

    def _send_survey_via_whatsapp(self):
        if not self.current_survey_code or self.current_survey_code not in self.catalog:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce yukarıdan bir anket seçiniz.")
            return
        defn = self.catalog[self.current_survey_code]
        std_name = self.current_student_name or "Değerli Öğrencimiz"
        
        lines = [
            f"📋 *{defn.title}*",
            f"_{defn.description}_\n",
            f"Merhaba *{std_name}*, koçluk görüşmemiz için aşağıdaki soruları 1 ile 5 arasında derecelendirerek yanıtlayabilirsin:\n",
            "*1:* Hiç Katılmıyorum",
            "*2:* Katılmıyorum",
            "*3:* Kararsızım",
            "*4:* Katılıyorum",
            "*5:* Tamamen Katılıyorum\n",
            "*SORULAR:*"
        ]
        for i, q in enumerate(defn.questions, 1):
            dim_tag = f" _({defn.dimensions[q.dimension]})_" if q.dimension and q.dimension in defn.dimensions else ""
            lines.append(f"*{i}.* {q.text}{dim_tag}")
            
        lines.append("\n_Cevaplarını bana liste olarak (Örn: 1-4, 2-5, 3-2...) gönderebilirsin. İyi çalışmalar! 🚀_")
        
        msg = "\n".join(lines)
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(msg)
        QMessageBox.information(
            self, 
            "Sorular Kopyalandı", 
            f"<b>{defn.title}</b> soruları WhatsApp formatında panoya kopyalandı!\n\n"
            f"Öğrencinin WhatsApp sohbetine 'Yapıştır' diyerek doğrudan gönderebilirsiniz."
        )

    def _delete_selected_history(self):
        item = self.history_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Uyarı", "Lütfen sağ listeden silmek istediğiniz bir anketi seçiniz.")
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data or "db_id" not in data:
            return
            
        db_id = data["db_id"]
        code = data.get("code", "")
        
        ans = QMessageBox.question(
            self,
            "Anketi Sil",
            "Bu anket sonucunu silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            con = db.get_conn()
            try:
                con.execute("DELETE FROM ogrenci_anket WHERE id=?", (db_id,))
                con.commit()
                self._load_history()
                if self.current_survey_code == code:
                    self._show_empty_intro()
            finally:
                con.close()

    def _load_history(self):
        self.history_list.clear()
        self.completed_surveys_data = {}
        if not self.current_student_id:
            return
        connection = db.get_conn()
        try:
            rows = connection.execute("""
                SELECT id, anket_kodu, cevaplar, tarih FROM ogrenci_anket
                WHERE ogrenci_id=? ORDER BY tarih DESC, id DESC
            """, (self.current_student_id,)).fetchall()
            latest_seen = set()
            for row in rows:
                code = row['anket_kodu']
                definition = self.catalog.get(code)
                try:
                    answers = json.loads(row['cevaplar'])
                except (ValueError, TypeError):
                    answers = None
                audit = inspect_answers(definition.questions, answers) if definition else None
                if not definition:
                    state = 'Tanımsız form'
                elif audit.complete:
                    state = f'Tamamlandı ({audit.answered}/{audit.expected})'
                elif audit.invalid_keys:
                    state = 'Geçersiz/okunamayan yanıt — inceleme gerekli'
                else:
                    state = f'Taslak ({audit.answered}/{audit.expected})'
                title = definition.title if definition else code
                item = QListWidgetItem(f"{title} · {state}\n📅 {str(row['tarih'])[:16]}")
                item.setData(Qt.ItemDataRole.UserRole, {
                    'code': code, 'answers': answers if isinstance(answers, dict) else {},
                    'date': row['tarih'], 'db_id': row['id']})
                self.history_list.addItem(item)
                # Only the newest record may represent a survey's CURRENT state.
                # Never substitute older full responses if the latest is a draft.
                if code not in latest_seen:
                    latest_seen.add(code)
                    if definition and audit.complete:
                        self.completed_surveys_data[code] = {
                            'answers': audit.valid_answers, 'date': row['tarih']}
            if hasattr(self, 'lbl_badge_completed'):
                self.lbl_badge_completed.setText(
                    f"✅ {len(self.completed_surveys_data)} / {len(self.catalog)} Tamamlandı")
            if hasattr(self, 'lbl_badge_health'):
                self.lbl_badge_health.setText(
                    f"📋 Tam yanıt: {len(self.completed_surveys_data)}/{len(self.catalog)}")
            if hasattr(self, 'lbl_badge_risk'):
                self.lbl_badge_risk.setText('🔒 Hassas yanıtlar özel değerlendirilir')
        finally:
            connection.close()

    def _on_history_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data: return

        code = data["code"]
        ans = data["answers"]

        self.cmb_survey.blockSignals(True)
        idx = self.cmb_survey.findData(code)
        if idx >= 0:
            self.cmb_survey.setCurrentIndex(idx)
        self.cmb_survey.blockSignals(False)

        self._load_survey_form(saved_answers=ans)

    def _setup_context_menu(self):
        self.history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, pos):
        item = self.history_list.itemAt(pos)
        if not item: return

        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        del_action = menu.addAction("🗑️ Bu Anket Kaydını Sil")
        view_action = menu.addAction("📊 Analiz Raporunu Aç")
        action = menu.exec(self.history_list.mapToGlobal(pos))

        if action == del_action:
            self._delete_history_item(item)
        elif action == view_action:
            data = item.data(Qt.ItemDataRole.UserRole)
            if data:
                self._show_survey_result_modal(data["code"], data["answers"])

    def _delete_history_item(self, item):
        res = QMessageBox.question(self, "Onay", "Bu anket kaydını silmek istediğinize emin misiniz?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if res != QMessageBox.StandardButton.Yes: return

        data = item.data(Qt.ItemDataRole.UserRole)
        db_id = data.get("db_id")

        if db_id:
            con = db.get_conn()
            try:
                con.execute("DELETE FROM ogrenci_anket WHERE id=?", (db_id,))
                con.commit()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Silinemedi: {e}")
                return
            finally:
                con.close()

        row = self.history_list.row(item)
        self.history_list.takeItem(row)
        self._load_history()

    def reset_form(self):
        self.current_survey_code = None
        self.completed_surveys_data = {}
        self.answers = {}
        self._history_preview_mode = False
        self.history_list.clear()
        self.cmb_survey.blockSignals(True)
        self.cmb_survey.setCurrentIndex(0)
        self.cmb_survey.blockSignals(False)
        self._show_empty_intro()

    def _show_general_analysis(self):
        rows = safe_general_rows(self.catalog, self.completed_surveys_data)
        if not rows:
            QMessageBox.information(self, 'Özet Yok',
                'Genel özet için tamamlanmış ve paylaşımı uygun çalışma anketi bulunamadı.')
            return
        dlg = QDialog(self)
        dlg.setWindowTitle('Öğrenci Öz-Değerlendirme: Çalışma Alışkanlıkları')
        dlg.resize(720, 520)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel('Öğrencinin kendi bildirdiği çalışma alışkanlıkları'))
        body = QTextEdit()
        body.setReadOnly(True)
        lines = ['<h3>Çalışma alışkanlıkları ve tercihler</h3>',
                 '<p>Yanıt ortalamaları yalnızca 1–5 katılım düzeyidir; '
                 'hâkimiyet, kişilik, öğrenme stili, klinik risk veya başarı puanı değildir.</p>']
        for row in rows:
            lines.append(f"<p><b>{escape(row['title'])}</b> — Yanıt ortalaması: "
                         f"{row['response_mean']:.2f}/5; {row['answered']} yanıt; "
                         f"tarih: {escape(str(row.get('date') or 'belirtilmemiş'))}</p>")
        lines.append('<p>Görüşmede bu yanıtların doğruluğu ve öğrencinin kendi örnekleri sorulmalıdır.</p>')
        body.setHtml('\n'.join(lines))
        layout.addWidget(body)
        close = QPushButton('Kapat')
        close.clicked.connect(dlg.accept)
        layout.addWidget(close)
        dlg.exec()

    def _copy_whatsapp_summary(self, profile: Dict[str, Any]):
        from PyQt6.QtWidgets import QApplication
        rows = safe_general_rows(self.catalog, self.completed_surveys_data)
        if not rows:
            QMessageBox.warning(self, 'Paylaşılacak Özet Yok',
                'Paylaşım için tamamlanmış ve hassas olmayan anket bulunamadı.')
            return
        # No responses about anxiety, sleep, health or psychological labels are shared.
        parts = ['📋 *Çalışma Öz-Değerlendirmesi*',
                 'Öğrencinin bildirdiği tercih/alışkanlıklar; tanı ya da başarı puanı değildir.']
        for row in rows:
            parts.append(f"• {row['title']}: {row['answered']} cevap ({str(row.get('date') or '')[:10]})")
        QApplication.clipboard().setText('\n'.join(parts))
        QMessageBox.information(self, 'Kopyalandı',
            'Yalnızca hassas olmayan anketlerin başlık ve tamamlanma bilgisi kopyalandı.')

    def _print_results(self):
        rows = safe_general_rows(self.catalog, self.completed_surveys_data)
        if not rows:
            QMessageBox.information(self, 'Yazdırılacak Özet Yok',
                'Önce tamamlanmış ve hassas olmayan çalışma anketi gerekir.')
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            body = '<h2>Öğrenci Çalışma Öz-Değerlendirme Özeti</h2>'
            body += '<p>Bu form klinik değerlendirme veya akademik başarı puanı değildir.</p>'
            body += '<ul>'
            for row in rows:
                body += (f"<li>{escape(row['title'])}: yanıt ortalaması "
                         f"{row['response_mean']:.2f}/5, {row['answered']} yanıt</li>")
            body += '</ul><p>Öğretmen görüşmesinde doğrulanmalıdır.</p>'
            doc = QTextEdit()
            doc.setHtml(body)
            doc.print(printer)
