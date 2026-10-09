# -*- coding: utf-8 -*-
"""
YKS/LGS Profesyonel Öğrenci Tanıma, Bilimsel Envanterler ve Koçluk Analiz Sistemi
Rehberlik, Psikolojik Danışmanlık (PDR) ve Eğitim Koçluğu standartlarına uygun
9 adet bilimsel envanter, alt boyut analizi ve pedagojik koçluk reçetesi motoru.
"""
from __future__ import annotations

import sys
import os
import json
import sqlite3
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
                title="1. VARK Öğrenme Stilleri Envanteri",
                description="Öğrencinin bilgiyi alma, işleme ve zihinde tutma kanalını (Görsel, İşitsel, Okuma/Yazma, Kinestetik) tespit eden bilimsel envanter.",
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
    Profesyonel Öğrenci Anket ve Bilimsel Profil Analiz Sistemi
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
        # 1. Üst Yönetici Araç Çubuğu (Kompakt, Zengin, Canlı KPI'lı)
        # -------------------------------------------------------------
        top_card = QFrame()
        top_card.setStyleSheet("""
            QFrame#topCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 10px 14px;
            }
        """)
        top_card.setObjectName("topCard")
        from PyQt6.QtWidgets import QSizePolicy
        top_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        top_vlay = QVBoxLayout(top_card)
        top_vlay.setContentsMargins(4, 4, 4, 4)
        top_vlay.setSpacing(8)

        # 1. Satır: Başlık & Aksiyon Butonları
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        v_head = QVBoxLayout()
        v_head.setSpacing(2)
        lbl_title = QLabel("🧠 <span style='color:#1e3a8a; font-weight:800; font-size:16px;'>Bilimsel Öğrenci Tanıma & Koçluk Envanterleri</span>")
        lbl_subtitle = QLabel("PDR ve Eğitim Koçluğu standartlarında 9 büyük envanter, alt boyut analizi ve pedagojik reçete motoru")
        lbl_subtitle.setStyleSheet("color: #64748b; font-size: 11px;")
        v_head.addWidget(lbl_title)
        v_head.addWidget(lbl_subtitle)
        row1.addLayout(v_head)

        row1.addStretch()

        # Buton 1: 360 Raporu
        btn_analyze = QPushButton("📊 360° Öğrenci Analiz Raporu")
        btn_analyze.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_analyze.setFixedHeight(34)
        btn_analyze.setToolTip("Öğrencinin tüm tamamlanmış anketlerini bütüncül olarak analiz eden ve koçluk reçetesi sunan 360° rapor")
        btn_analyze.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1);
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 6px;
                padding: 0 14px;
                border: none;
            }
            QPushButton:hover { background: #4338ca; }
        """)
        btn_analyze.clicked.connect(self._show_general_analysis)
        row1.addWidget(btn_analyze)

        # Buton 2: Yazdır
        btn_print = QPushButton("🖨️ Yazdır / PDF")
        btn_print.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_print.setFixedHeight(34)
        btn_print.setToolTip("Gelişim raporunu yazdırın veya PDF olarak dışa aktarın")
        btn_print.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc;
                color: #334155;
                font-weight: bold;
                font-size: 11px;
                border-radius: 6px;
                padding: 0 12px;
                border: 1px solid #cbd5e1;
            }
            QPushButton:hover { background-color: #f1f5f9; }
        """)
        btn_print.clicked.connect(self._print_results)
        row1.addWidget(btn_print)

        # Buton 3: WhatsApp Özeti
        btn_copy_wa = QPushButton("📱 WhatsApp Özeti")
        btn_copy_wa.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy_wa.setFixedHeight(34)
        btn_copy_wa.setToolTip("Veli ve öğrenciye gönderilmeye hazır şık formatlı analiz özetini panoya kopyalar")
        btn_copy_wa.setStyleSheet("""
            QPushButton {
                background-color: #25D366;
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 6px;
                padding: 0 12px;
                border: none;
            }
            QPushButton:hover { background-color: #1ebd5b; }
        """)
        btn_copy_wa.clicked.connect(self._copy_current_whatsapp)
        row1.addWidget(btn_copy_wa)

        # Buton 4: Öğrenciye Testi Gönder
        btn_send_student = QPushButton("📲 Öğrenciye Gönder")
        btn_send_student.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_send_student.setFixedHeight(34)
        btn_send_student.setToolTip("Seçili anketin sorularını öğrencinin uzaktan telefondan yanıtlaması için WhatsApp metni olarak hazırlar")
        btn_send_student.setStyleSheet("""
            QPushButton {
                background-color: #eff6ff;
                color: #1d4ed8;
                font-weight: bold;
                font-size: 11px;
                border-radius: 6px;
                padding: 0 12px;
                border: 1px solid #bfdbfe;
            }
            QPushButton:hover { background-color: #dbeafe; }
        """)
        btn_send_student.clicked.connect(self._send_survey_via_whatsapp)
        row1.addWidget(btn_send_student)

        top_vlay.addLayout(row1)

        # 2. Satır: Envanter Seçici ve Canlı KPI İstatistikleri
        row2 = QHBoxLayout()
        row2.setSpacing(10)

        row2.addWidget(QLabel("<b>Envanter / Ölçek:</b>"))
        self.cmb_survey = QComboBox()
        self.cmb_survey.setMinimumWidth(320)
        self.cmb_survey.setStyleSheet("""
            QComboBox {
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 12px;
                font-weight: 600;
                color: #1e293b;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #e2e8f0;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background: transparent;
            }
            QComboBox::drop-down:hover { background: #f1f5f9; }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #64748b;
            }
        """)
        self.cmb_survey.addItem("-- Envanter / Anket Seçiniz --", "")
        for code, defn in self.catalog.items():
            self.cmb_survey.addItem(f"[{defn.category}] {defn.title}", code)
        self.cmb_survey.currentTextChanged.connect(self._load_survey_form_wrapper)
        row2.addWidget(self.cmb_survey)

        row2.addSpacing(15)

        # Canlı Rozetler (KPI Badges)
        self.lbl_badge_total = QLabel("📋 9 Bilimsel Ölçek")
        self.lbl_badge_total.setStyleSheet("background: #f1f5f9; color: #475569; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 11px;")
        row2.addWidget(self.lbl_badge_total)

        self.lbl_badge_completed = QLabel("✅ 0 / 9 Tamamlandı")
        self.lbl_badge_completed.setStyleSheet("background: #f0fdf4; color: #166534; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 11px; border: 1px solid #bbf7d0;")
        row2.addWidget(self.lbl_badge_completed)

        self.lbl_badge_health = QLabel("🎯 Akademik Sağlık: --")
        self.lbl_badge_health.setStyleSheet("background: #eff6ff; color: #1e40af; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 11px; border: 1px solid #bfdbfe;")
        row2.addWidget(self.lbl_badge_health)

        self.lbl_badge_risk = QLabel("🛡️ Risk İndeksi: --")
        self.lbl_badge_risk.setStyleSheet("background: #fef2f2; color: #991b1b; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 11px; border: 1px solid #fecaca;")
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

        # 1. Başlık ve İlerleme Kartı (Sticky Top)
        self.survey_hdr_frame = QFrame()
        self.survey_hdr_frame.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 14px; }")
        self.survey_hdr_frame.setVisible(False)
        sh_lay = QVBoxLayout(self.survey_hdr_frame)
        sh_lay.setContentsMargins(2, 2, 2, 2)
        sh_lay.setSpacing(4)

        self.lbl_survey_cat = QLabel("KATEGORİ")
        self.lbl_survey_cat.setStyleSheet("font-size: 10px; font-weight: bold; color: #166534; letter-spacing: 1px;")
        sh_lay.addWidget(self.lbl_survey_cat)

        self.lbl_survey_tit = QLabel("Envanter Başlığı")
        self.lbl_survey_tit.setStyleSheet("font-size: 16px; font-weight: bold; color: #0f172a;")
        sh_lay.addWidget(self.lbl_survey_tit)

        self.lbl_survey_dsc = QLabel("Açıklama...")
        self.lbl_survey_dsc.setStyleSheet("font-size: 12px; color: #475569;")
        self.lbl_survey_dsc.setWordWrap(True)
        sh_lay.addWidget(self.lbl_survey_dsc)

        # İlerleme Göstergesi
        prog_row = QHBoxLayout()
        prog_row.setSpacing(8)
        self.lbl_survey_prog = QLabel("🎯 Cevaplanan: 0 / 0 (%0)")
        self.lbl_survey_prog.setStyleSheet("font-size: 11px; font-weight: bold; color: #1e40af;")
        prog_row.addWidget(self.lbl_survey_prog)

        self.survey_pbar = QProgressBar()
        self.survey_pbar.setRange(0, 100)
        self.survey_pbar.setValue(0)
        self.survey_pbar.setFixedHeight(8)
        self.survey_pbar.setTextVisible(False)
        self.survey_pbar.setStyleSheet("QProgressBar { background: #f1f5f9; border-radius: 4px; } QProgressBar::chunk { background: #22c55e; border-radius: 4px; }")
        prog_row.addWidget(self.survey_pbar)
        sh_lay.addLayout(prog_row)

        left_vlay.addWidget(self.survey_hdr_frame)

        # 2. Sorular Kaydırma Alanı (Scroll Area)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: 1px solid #e2e8f0; border-radius: 8px; background: white; }")
        self.content_widget = QWidget()
        self.content_lay = QVBoxLayout(self.content_widget)
        self.content_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.content_lay.setContentsMargins(14, 14, 14, 14)
        self.content_lay.setSpacing(10)
        self.scroll.setWidget(self.content_widget)
        left_vlay.addWidget(self.scroll, 1)

        # 3. SABİT ALT EYLEM BARI (Ekran boyutu ne olursa olsun daima görünür!)
        self.bottom_dock = QFrame()
        self.bottom_dock.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 6px 12px;
            }
        """)
        self.bottom_dock.setVisible(False)
        bot_lay = QHBoxLayout(self.bottom_dock)
        bot_lay.setContentsMargins(6, 4, 6, 4)
        bot_lay.setSpacing(10)

        self.btn_reset_survey = QPushButton("🔄 Temizle")
        self.btn_reset_survey.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset_survey.setFixedHeight(36)
        self.btn_reset_survey.setToolTip("Bu anket için işaretlenen tüm şıkları temizle")
        self.btn_reset_survey.setStyleSheet("""
            QPushButton {
                background: #f8fafc;
                color: #64748b;
                font-weight: 600;
                font-size: 11px;
                border-radius: 6px;
                padding: 0 14px;
                border: 1px solid #cbd5e1;
            }
            QPushButton:hover { background: #fee2e2; color: #b91c1c; border-color: #fca5a5; }
        """)
        self.btn_reset_survey.clicked.connect(self._clear_current_form)
        bot_lay.addWidget(self.btn_reset_survey)

        self.btn_quick = QPushButton("⚡ Hızlı 4 Puan Doldur")
        self.btn_quick.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_quick.setFixedHeight(36)
        self.btn_quick.setToolTip("Koç olarak hızlı değerlendirme için tüm sorulara varsayılan 4 (İyi) atar, istediğinizi değiştirebilirsiniz")
        self.btn_quick.setStyleSheet("""
            QPushButton {
                background: #eff6ff;
                color: #1d4ed8;
                font-weight: 600;
                font-size: 11px;
                border-radius: 6px;
                padding: 0 14px;
                border: 1px solid #bfdbfe;
            }
            QPushButton:hover { background: #dbeafe; }
        """)
        self.btn_quick.clicked.connect(self._quick_fill_average)
        bot_lay.addWidget(self.btn_quick)

        self.lbl_dock_status = QLabel("Lütfen soruları yanıtlayınız...")
        self.lbl_dock_status.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 500;")
        bot_lay.addWidget(self.lbl_dock_status)

        bot_lay.addStretch()

        self.btn_finish = QPushButton("✅ Cevapları Kaydet ve Bilimsel Analizi Gör")
        self.btn_finish.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_finish.setFixedHeight(38)
        self.btn_finish.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16a34a, stop:1 #15803d);
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
                padding: 0 20px;
                border: none;
            }
            QPushButton:hover { background: #15803d; }
        """)
        self.btn_finish.clicked.connect(self._complete_survey)
        bot_lay.addWidget(self.btn_finish)

        left_vlay.addWidget(self.bottom_dock, 0)
        splitter.addWidget(left_container)

        # --- SAĞ PANEL: Geçmiş Listesi ve Hızlı Koçluk Reçetesi Kartı ---
        right_panel = QFrame()
        right_panel.setMinimumWidth(320)
        right_panel.setMaximumWidth(400)
        right_panel.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; }")
        r_lay = QVBoxLayout(right_panel)
        r_lay.setContentsMargins(12, 12, 12, 12)
        r_lay.setSpacing(8)

        lbl_hist_title = QLabel("📋 <b>Tamamlanan Envanterler</b>")
        lbl_hist_title.setStyleSheet("font-size: 13px; color: #0f172a; border: none;")
        r_lay.addWidget(lbl_hist_title)

        lbl_hist_desc = QLabel("Geçmiş cevapları görmek veya analizi açmak için tıklayın.")
        lbl_hist_desc.setStyleSheet("font-size: 11px; color: #64748b; border: none; margin-bottom: 4px;")
        r_lay.addWidget(lbl_hist_desc)

        self.history_list = QListWidget()
        self.history_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                background: #f8fafc;
                padding: 4px;
            }
            QListWidget::item {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 8px;
                margin-bottom: 6px;
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
        self.pdr_tip_box.setStyleSheet("QFrame { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 10px; }")
        pt_lay = QVBoxLayout(self.pdr_tip_box)
        pt_lay.setContentsMargins(6, 6, 6, 6)
        pt_lay.setSpacing(4)

        lbl_pt_tit = QLabel("💡 <b>PDR & Koçluk Strateji Notu:</b>")
        lbl_pt_tit.setStyleSheet("font-size: 11px; color: #166534; border: none;")
        pt_lay.addWidget(lbl_pt_tit)

        self.lbl_pdr_tip = QLabel("Bir envanter seçildiğinde o alana özel pedagojik yaklaşım ipuçları burada görünür.")
        self.lbl_pdr_tip.setStyleSheet("font-size: 11px; color: #15803d; border: none;")
        self.lbl_pdr_tip.setWordWrap(True)
        pt_lay.addWidget(self.lbl_pdr_tip)
        r_lay.addWidget(self.pdr_tip_box)

        # Sağ Panel Alt Buton: Sil
        btn_del_hist = QPushButton("🗑️ Seçili Anketi Sil")
        btn_del_hist.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del_hist.setFixedHeight(30)
        btn_del_hist.setStyleSheet("""
            QPushButton {
                background: #ffffff;
                color: #b91c1c;
                font-size: 11px;
                font-weight: 600;
                border: 1px solid #fecaca;
                border-radius: 6px;
            }
            QPushButton:hover { background: #fee2e2; }
        """)
        btn_del_hist.clicked.connect(self._delete_selected_history)
        r_lay.addWidget(btn_del_hist)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 72)
        splitter.setStretchFactor(1, 28)

        main.addWidget(splitter, 1)
        self._show_empty_intro()

    def _show_empty_intro(self):
        while self.content_lay.count():
            child = self.content_lay.takeAt(0)
            if child.widget(): child.widget().deleteLater()

        if hasattr(self, 'survey_hdr_frame'):
            self.survey_hdr_frame.setVisible(False)
        if hasattr(self, 'bottom_dock'):
            self.bottom_dock.setVisible(False)
        if hasattr(self, 'lbl_pdr_tip'):
            self.lbl_pdr_tip.setText("Yukarıdan bir envanter seçerek öğrencinin bilişsel, duygusal ve davranışsal özelliklerini analiz edebilirsiniz.")

        frame = QFrame()
        frame.setStyleSheet("background: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 12px; padding: 36px;")
        l = QVBoxLayout(frame)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.setSpacing(12)

        icon = QLabel("🧠")
        icon.setStyleSheet("font-size: 44px; border: none; background: transparent;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(icon)

        t = QLabel("<b>Bilimsel Öğrenci Tanıma ve Koçluk Envanterleri</b>")
        t.setStyleSheet("font-size: 16px; color: #0f172a; border: none; background: transparent;")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(t)
        info_txt = (
            "Yukarıdaki menüden bir envanter seçerek öğrencinin;<br>"
            "• VARK Öğrenme Stilini (Görsel, İşitsel, Kinestetik, Okuma/Yazma)<br>"
            "• Akademik Erteleme Nedenlerini ve Zaman Hırsızlarını<br>"
            "• Sınav Kaygısı ve Bedensel Stres Faktörlerini<br>"
            "• Masa Başı Odaklanma ve Gelişim Zihniyetini (Growth Mindset)<br>"
            "bilimsel olarak test edebilir, tek tıkla koçluk reçetesi çıkarabilirsiniz."
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
            if child.widget(): child.widget().deleteLater()
            
        if not code or code not in self.catalog:
            self._show_empty_intro()
            return

        self.current_survey_code = code
        defn = self.catalog[code]
        self.answers = saved_answers.copy() if saved_answers else {}

        # 1. Sticky Header Frame Bilgilerini Doldur
        if hasattr(self, 'survey_hdr_frame'):
            self.survey_hdr_frame.setVisible(True)
            self.lbl_survey_cat.setText(f"KATEGORİ: {defn.category.upper()}")
            self.lbl_survey_tit.setText(defn.title)
            self.lbl_survey_dsc.setText(defn.description)
            self._update_progress_display()

        # 2. PDR İpucu Notunu Güncelle
        pdr_notes = {
            "vark_learning": "VARK analizi öğrencinin bilgiyi en rahat işlediği duyusal kanalı gösterir. Baskın stile göre ders çalışma materyali seçiniz.",
            "procrastination": "Erteleme genellikle tembellikten değil, mükemmeliyetçilik veya başarısızlık korkusundan kaynaklanır. Kök nedeni tespit ediniz.",
            "exam_anxiety": "Sınav kaygısı yüksekse nefes egzersizleri ve sınav anı zihinsel blokajları yönetme teknikleri uygulayınız.",
            "study_habits": "Masa başı disiplini ve deneme analizi alışkanlığı eksikse haftalık somut blok planlama yapınız.",
            "self_efficacy": "Öz-yeterlik düşüklüğünde küçük başarılabilir adımlarla başarı hazzını yeniden inşa ediniz.",
            "time_management": "Pomodoro veya 50+10 blok yöntemini öğrencinin odaklanma süresine göre kalibre ediniz.",
            "growth_mindset": "Hataları 'yetersizlik' değil, beynin öğrenme fırsatı olarak görmesini sağlayan koçluk dili kullanınız.",
            "digital_distraction": "Çalışma masasında telefon bulundurmama kuralı ve ekran süresi sınırlandırması getirin.",
            "sleep_energy": "Uyku kalitesi zihinsel zindeliğin %50'sidir. Sınav döneminde uyku hijyeni asla feda edilmemelidir."
        }
        if hasattr(self, 'lbl_pdr_tip'):
            self.lbl_pdr_tip.setText(pdr_notes.get(code, "Bu envanter öğrencinin akademik başarısını doğrudan etkileyen kritik bir boyutu analiz eder."))

        # 3. Sabit Alt Eylem Barını Aç ve Güncelle
        if hasattr(self, 'bottom_dock'):
            self.bottom_dock.setVisible(True)
            if saved_answers:
                self.btn_finish.setText("📊 Bilimsel Analiz Raporunu Tekrar Gör")
            else:
                self.btn_finish.setText("✅ Cevapları Kaydet ve Bilimsel Analizi Gör")

        # 4. Soruları Oluştur
        self.button_groups = {}

        for idx, q in enumerate(defn.questions):
            q_card = QFrame()
            q_card.setStyleSheet("""
                QFrame {
                    background: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    padding: 10px 12px;
                }
                QFrame:hover {
                    border-color: #93c5fd;
                }
            """)
            q_lay = QVBoxLayout(q_card)
            q_lay.setSpacing(8)

            dim_label = ""
            if q.dimension and q.dimension in defn.dimensions:
                dim_name = defn.dimensions[q.dimension]
                dim_label = f" <span style='color: #6366f1; font-size: 11px; font-weight: 600;'>[{dim_name}]</span>"

            lbl_q = QLabel(f"<b>{idx+1}.</b> {q.text}{dim_label}")
            lbl_q.setStyleSheet("font-size: 13px; color: #1e293b; line-height: 1.4;")
            lbl_q.setWordWrap(True)
            q_lay.addWidget(lbl_q)

            row = QHBoxLayout()
            row.setSpacing(8)
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
                        font-size: 11px;
                        color: #475569;
                        spacing: 5px;
                        padding: 2px 6px;
                    }
                    QRadioButton:hover {
                        color: #1e293b;
                        background: #f1f5f9;
                        border-radius: 4px;
                    }
                    QRadioButton::indicator:checked {
                        background-color: #2563eb;
                        border: 2px solid white;
                        border-radius: 6px;
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
        if not self.current_survey_code: return
        defn = self.catalog[self.current_survey_code]
        for q in defn.questions:
            bg = self.button_groups.get(q.key)
            if bg:
                for btn in bg.buttons():
                    if btn.property("val") == 4:
                        btn.setChecked(True)
                        self.answers[q.key] = 4
                        break

    def _on_answer_changed(self, key, btn):
        val = btn.property("val")
        self.answers[key] = val
        self._update_progress_display()

    def _complete_survey(self):
        if not self.current_survey_code: return
        if not self.current_student_id:
            QMessageBox.warning(self, "Hata", "Lütfen önce sol listeden bir öğrenci seçiniz.")
            return

        defn = self.catalog[self.current_survey_code]
        if len(self.answers) < len(defn.questions):
            unanswered = len(defn.questions) - len(self.answers)
            res = QMessageBox.question(
                self, "Eksik Sorular",
                f"Henüz cevaplanmamış {unanswered} soru var. Yine de kaydedip mevcut cevaplarla analiz edilsin mi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if res != QMessageBox.StandardButton.Yes:
                return

        con = db.get_conn()
        try:
            answers_json = json.dumps(self.answers)
            cur = con.execute("""
                INSERT INTO ogrenci_anket (ogrenci_id, anket_kodu, cevaplar)
                VALUES (?, ?, ?)
            """, (self.current_student_id, self.current_survey_code, answers_json))
            con.commit()

            self.completed_surveys_data[self.current_survey_code] = {
                "answers": self.answers.copy(),
                "date": str(datetime.now())
            }
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kaydedilemedi: {e}")
            return
            if self.completed_surveys_data and hasattr(self, 'lbl_badge_health'):
                try:
                    prof = StudentProfileAnalyzerV2.analyze(self.completed_surveys_data, student_name=self.current_student_name)
                    ah = prof.get('academic_health', 0)
                    ri = prof.get('risk_index', 0)
                    h_color = "#16a34a" if ah >= 70 else ("#d97706" if ah >= 45 else "#dc2626")
                    r_color = "#16a34a" if ri <= 35 else ("#d97706" if ri <= 65 else "#dc2626")
                    self.lbl_badge_health.setText(f"🎯 Sağlık: <b style='color:{h_color}'>%{ah}</b>")
                    self.lbl_badge_risk.setText(f"🛡️ Risk: <b style='color:{r_color}'>%{ri}</b>")
                except Exception:
                    pass
            elif hasattr(self, 'lbl_badge_health'):
                self.lbl_badge_health.setText("🎯 Sağlık: <b>--</b>")
                self.lbl_badge_risk.setText("🛡️ Risk: <b>--</b>")
        finally:
            con.close()

        self._load_history()
        self._show_survey_result_modal(self.current_survey_code, self.answers)

    def _show_survey_result_modal(self, code: str, answers: Dict[str, Any]):
        defn = self.catalog.get(code)
        if not defn: return

        sc = SurveyCatalog.score_likert_answers(defn, answers)
        pct = sc["pct"]
        is_risk = defn.risk_inverted

        if is_risk:
            if pct <= 35:
                status_text = f"🟢 {defn.low_label}"
                status_color = "#15803d"
            elif pct <= 65:
                status_text = f"🟡 {defn.mid_label}"
                status_color = "#b45309"
            else:
                status_text = f"🔴 {defn.high_label}"
                status_color = "#b91c1c"
        else:
            if pct >= 70:
                status_text = f"🟢 {defn.high_label}"
                status_color = "#15803d"
            elif pct >= 45:
                status_text = f"🟡 {defn.mid_label}"
                status_color = "#b45309"
            else:
                status_text = f"🔴 {defn.low_label}"
                status_color = "#b91c1c"

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Analiz Raporu: {defn.title}")
        dlg.resize(650, 520)
        l = QVBoxLayout(dlg)
        l.setSpacing(12)

        top_box = QFrame()
        top_box.setStyleSheet(f"background: #f8fafc; border: 1px solid #e2e8f0; border-left: 6px solid {status_color}; border-radius: 8px; padding: 14px;")
        tb_lay = QVBoxLayout(top_box)
        
        lbl_h = QLabel(f"<b>{defn.title} - Değerlendirme Sonucu</b>")
        lbl_h.setStyleSheet("font-size: 15px; color: #0f172a;")
        tb_lay.addWidget(lbl_h)

        score_lbl = QLabel(f"Skor: <b>{sc['score']} / {sc['max']}</b> (%{pct}) — <span style='color:{status_color}; font-weight:bold;'>{status_text}</span>")
        score_lbl.setStyleSheet("font-size: 14px; margin-top: 4px;")
        tb_lay.addWidget(score_lbl)

        pbar = QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(pct)
        pbar.setFixedHeight(14)
        pbar.setTextVisible(False)
        pbar.setStyleSheet(f"""
            QProgressBar {{
                background: #e2e8f0;
                border-radius: 7px;
            }}
            QProgressBar::chunk {{
                background: {status_color};
                border-radius: 7px;
            }}
        """)
        tb_lay.addWidget(pbar)
        l.addWidget(top_box)

        dims = sc.get("dimensions", {})
        if dims:
            dim_box = QFrame()
            dim_box.setStyleSheet("background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px;")
            dim_lay = QVBoxLayout(dim_box)
            dim_lay.addWidget(QLabel("<b>📊 Alt Boyut Analizi:</b>"))

            grid = QGridLayout()
            row_idx = 0
            for k, ddata in dims.items():
                grid.addWidget(QLabel(f"• <b>{ddata['name']}</b>:"), row_idx, 0)
                grid.addWidget(QLabel(f"%{ddata['pct']} ({ddata['score']}/{ddata['max']} Puan)"), row_idx, 1)
                
                dpbar = QProgressBar()
                dpbar.setRange(0, 100)
                dpbar.setValue(ddata['pct'])
                dpbar.setFixedHeight(10)
                dpbar.setTextVisible(False)
                dpbar.setStyleSheet("QProgressBar { background: #f1f5f9; border-radius: 5px; } QProgressBar::chunk { background: #6366f1; border-radius: 5px; }")
                grid.addWidget(dpbar, row_idx, 2)
                row_idx += 1

            dim_lay.addLayout(grid)
            l.addWidget(dim_box)

        full_profile = StudentProfileAnalyzerV2.analyze({code: {"answers": answers}})
        strat = full_profile.get("coach_strategy", [])
        tasks = full_profile.get("student_action_tasks", [])

        info_txt = QTextEdit()
        info_txt.setReadOnly(True)
        html_report = "<div style='font-size: 13px; color: #1e293b;'>"
        if strat:
            html_report += "<h4 style='color:#1e40af; margin-bottom: 6px;'>🎯 Bu Öğrenci İçin Koçluk Stratejisi:</h4>"
            for s in strat:
                html_report += f"<p style='margin: 4px 0;'>{s}</p>"
        if tasks:
            html_report += "<h4 style='color:#15803d; margin-top: 12px; margin-bottom: 6px;'>📋 Öğrenciye Verilecek Somut Eylem Görevleri:</h4>"
            for t in tasks:
                html_report += f"<p style='margin: 4px 0;'>• {t}</p>"
        html_report += "</div>"
        info_txt.setHtml(html_report)
        l.addWidget(info_txt)

        b_lay = QHBoxLayout()
        b_lay.addStretch()
        btn_close = QPushButton("Tamam / Kapat")
        btn_close.setFixedWidth(120)
        btn_close.setFixedHeight(34)
        btn_close.setStyleSheet("background: #0f172a; color: white; font-weight: bold; border-radius: 6px;")
        btn_close.clicked.connect(dlg.accept)
        b_lay.addWidget(btn_close)
        l.addLayout(b_lay)

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
        profile = StudentProfileAnalyzerV2.analyze(self.completed_surveys_data, student_name=self.current_student_name)
        self._copy_whatsapp_summary(profile)

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
        if not self.current_student_id: return

        con = db.get_conn()
        try:
            rows = con.execute("""
                SELECT id, anket_kodu, cevaplar, tarih FROM ogrenci_anket 
                WHERE ogrenci_id=? ORDER BY tarih DESC
            """, (self.current_student_id,)).fetchall()

            self.completed_surveys_data = {}

            # Update live header badges
            completed_count = len(rows)
            if hasattr(self, 'lbl_badge_completed'):
                # Unique completed
                unique_codes = {r["anket_kodu"] for r in rows}
                self.lbl_badge_completed.setText(f"✅ {len(unique_codes)} / 9 Tamamlandı")

            for r in rows:
                code = r["anket_kodu"]
                try:
                    ans = json.loads(r["cevaplar"])
                    if code not in self.completed_surveys_data:
                        self.completed_surveys_data[code] = {"answers": ans, "date": r["tarih"]}

                    defn = self.catalog.get(code)
                    title = defn.title if defn else code
                    
                    score_info = ""
                    if defn:
                        sc = SurveyCatalog.score_likert_answers(defn, ans)
                        pct = sc["pct"]
                        if defn.risk_inverted:
                            badge = "🟢" if pct <= 35 else ("🟡" if pct <= 65 else "🔴")
                        else:
                            badge = "🟢" if pct >= 70 else ("🟡" if pct >= 45 else "🔴")
                        score_info = f" {badge} (%{pct})"

                    date_str = str(r["tarih"])[:16]
                    item_text = f"{title}{score_info}\n📅 {date_str}"
                    item = QListWidgetItem(item_text)
                    item_data = {"code": code, "answers": ans, "date": r["tarih"], "db_id": r["id"]}
                    item.setData(Qt.ItemDataRole.UserRole, item_data)
                    self.history_list.addItem(item)
                except Exception:
                    pass
            if self.completed_surveys_data and hasattr(self, 'lbl_badge_health'):
                try:
                    prof = StudentProfileAnalyzerV2.analyze(self.completed_surveys_data, student_name=self.current_student_name)
                    ah = prof.get('academic_health', 0)
                    ri = prof.get('risk_index', 0)
                    h_color = "#16a34a" if ah >= 70 else ("#d97706" if ah >= 45 else "#dc2626")
                    r_color = "#16a34a" if ri <= 35 else ("#d97706" if ri <= 65 else "#dc2626")
                    self.lbl_badge_health.setText(f"🎯 Sağlık: <b style='color:{h_color}'>%{ah}</b>")
                    self.lbl_badge_risk.setText(f"🛡️ Risk: <b style='color:{r_color}'>%{ri}</b>")
                except Exception:
                    pass
            elif hasattr(self, 'lbl_badge_health'):
                self.lbl_badge_health.setText("🎯 Sağlık: <b>--</b>")
                self.lbl_badge_risk.setText("🛡️ Risk: <b>--</b>")
        finally:
            con.close()

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
        self.history_list.clear()
        self.cmb_survey.blockSignals(True)
        self.cmb_survey.setCurrentIndex(0)
        self.cmb_survey.blockSignals(False)
        self._show_empty_intro()

    def _show_general_analysis(self):
        if not self.completed_surveys_data:
            QMessageBox.warning(self, "Veri Yok", "Bu öğrenci için henüz tamamlanmış anket bulunmuyor.\nLütfen yukarıdan en az 1 anket seçip doldurunuz.")
            return

        profile = StudentProfileAnalyzerV2.analyze(
            self.completed_surveys_data,
            student_name=self.current_student_name
        )

        dlg = QDialog(self)
        dlg.setWindowTitle("360° Öğrenci Bilimsel Profil ve Koçluk Analiz Raporu")
        dlg.resize(750, 620)
        l = QVBoxLayout(dlg)
        l.setSpacing(12)

        hdr = QFrame()
        hdr.setStyleSheet("background: #0f172a; color: white; border-radius: 8px; padding: 14px;")
        hl = QVBoxLayout(hdr)
        
        std_name = self.current_student_name or "Öğrenci"
        hl.addWidget(QLabel(f"<span style='font-size: 16px; font-weight: bold;'>👤 {std_name} — 360° Bütüncül Koçluk Profili</span>"))
        hl.addWidget(QLabel(f"<span style='font-size: 12px; color: #94a3b8;'>{profile['summary_text']}</span>"))

        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(15)

        h_box = QFrame()
        h_box.setStyleSheet("background: #1e293b; border-radius: 6px; padding: 8px;")
        h_lay = QVBoxLayout(h_box)
        h_lay.addWidget(QLabel(f"Akademik Sağlık İndeksi: <b>%{profile['academic_health']}</b>"))
        hp = QProgressBar()
        hp.setValue(profile['academic_health'])
        hp.setFixedHeight(8)
        hp.setTextVisible(False)
        hp.setStyleSheet("QProgressBar { background: #334155; border-radius: 4px; } QProgressBar::chunk { background: #22c55e; border-radius: 4px; }")
        h_lay.addWidget(hp)
        kpi_row.addWidget(h_box)

        r_box = QFrame()
        r_box.setStyleSheet("background: #1e293b; border-radius: 6px; padding: 8px;")
        r_lay = QVBoxLayout(r_box)
        r_lay.addWidget(QLabel(f"Bileşik Risk Düzeyi: <b>%{profile['risk_index']}</b>"))
        rp = QProgressBar()
        rp.setValue(profile['risk_index'])
        rp.setFixedHeight(8)
        rp.setTextVisible(False)
        rp.setStyleSheet("QProgressBar { background: #334155; border-radius: 4px; } QProgressBar::chunk { background: #ef4444; border-radius: 4px; }")
        r_lay.addWidget(rp)
        kpi_row.addWidget(r_box)

        hl.addLayout(kpi_row)
        l.addWidget(hdr)

        txt = QTextEdit()
        txt.setReadOnly(True)

        html = "<div style='font-family: sans-serif; font-size: 13px; line-height: 1.6;'>"
        
        labels = profile.get("labels", [])
        if labels:
            html += "<h3 style='color: #1e40af; border-bottom: 2px solid #e2e8f0; padding-bottom: 4px;'>🔍 Bilişsel ve Davranışsal Bulgular</h3><ul>"
            for lab in labels:
                html += f"<li><b>{lab}</b></li>"
            html += "</ul>"

        vark = profile["scores"]["vark"]
        if any(v > 0 for v in vark.values()):
            html += "<h3 style='color: #1e40af; border-bottom: 2px solid #e2e8f0; padding-bottom: 4px;'>🎨 VARK Öğrenme Kanalı Dağılımı</h3>"
            html += f"<p>• Görsel: <b>%{vark['visual']}</b> | İşitsel: <b>%{vark['auditory']}</b> | Okuma/Yazma: <b>%{vark['read_write']}</b> | Kinestetik: <b>%{vark['kinesthetic']}</b></p>"
            html += f"<p><i>Baskın Kanal: <b>{profile['dominant_style']}</b> (Öğrencinin en yüksek kavrama sağladığı yöntemdir).</i></p>"

        strat = profile.get("coach_strategy", [])
        if strat:
            html += "<h3 style='color: #15803d; border-bottom: 2px solid #e2e8f0; padding-bottom: 4px;'>🎯 Koç İçin Pedagojik Strateji Reçetesi</h3>"
            for s in strat:
                html += f"<p style='margin: 6px 0;'>{s}</p>"

        tasks = profile.get("student_action_tasks", [])
        if tasks:
            html += "<h3 style='color: #b45309; border-bottom: 2px solid #e2e8f0; padding-bottom: 4px;'>📋 Öğrenciye Verilecek Haftalık Görevler</h3><ul>"
            for t in tasks:
                html += f"<li>{t}</li>"
            html += "</ul>"

        html += f"<br><p style='color: #64748b; font-size: 11px;'>Rapor Oluşturulma Tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p></div>"

        txt.setHtml(html)
        l.addWidget(txt)

        btn_bar = QHBoxLayout()
        btn_copy_wa = QPushButton("📱 WhatsApp Metni Kopyala")
        btn_copy_wa.setStyleSheet("background-color: #25D366; color: white; font-weight: bold; padding: 8px 16px; border-radius: 6px;")
        btn_copy_wa.clicked.connect(lambda: self._copy_whatsapp_summary(profile))
        btn_bar.addWidget(btn_copy_wa)

        btn_bar.addStretch()

        btn_close = QPushButton("Kapat")
        btn_close.setFixedWidth(100)
        btn_close.setStyleSheet("background: #0f172a; color: white; font-weight: bold; padding: 8px 16px; border-radius: 6px;")
        btn_close.clicked.connect(dlg.accept)
        btn_bar.addWidget(btn_close)

        l.addLayout(btn_bar)
        dlg.exec()

    def _copy_whatsapp_summary(self, profile: Dict[str, Any]):
        from PyQt6.QtWidgets import QApplication
        std_name = self.current_student_name or "Değerli Öğrencimiz"
        wa_text = (
            f"🧠 *{std_name} — 360° Öğrenci Profil ve Koçluk Özeti*\n\n"
            f"🎯 *Baskın Öğrenme Stili:* {profile['dominant_style']}\n"
            f"📊 *Genel Akademik Sağlık:* %{profile['academic_health']}\n"
            f"🛡️ *Risk İndeksi:* %{profile['risk_index']}\n\n"
            f"*Öne Çıkan Bulgular:*\n"
        )
        for lab in profile.get("labels", []):
            wa_text += f"• {lab}\n"

        tasks = profile.get("student_action_tasks", [])
        if tasks:
            wa_text += f"\n*📋 Bu Haftaki Koçluk Görevlerin:*\n"
            for t in tasks:
                wa_text += f"• {t}\n"

        wa_text += "\n_Başarı, doğru yöntem ve istikrarlı adımlarla gelir! 🚀_"

        QApplication.clipboard().setText(wa_text)
        QMessageBox.information(self, "Kopyalandı", "WhatsApp paylaşım metni panoya kopyalandı!\nİstediğiniz veli veya öğrenci sohbetine yapıştırabilirsiniz.")

    def _print_results(self):
        if not self.completed_surveys_data:
            QMessageBox.warning(self, "Uyarı", "Yazdırılacak veri yok. Lütfen en az bir anket tamamlayınız.")
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)

        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            profile = StudentProfileAnalyzerV2.analyze(self.completed_surveys_data, student_name=self.current_student_name)
            std_name = self.current_student_name or "Öğrenci"

            html = f"""
            <h1 style='color: #0f172a;'>YKS/LGS Öğrenci Tanıma ve Koçluk Gelişim Raporu</h1>
            <p><b>Öğrenci:</b> {std_name} | <b>Tarih:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
            <hr>
            <h3>1. Genel Bilişsel ve Davranışsal Durum</h3>
            <p>• <b>Baskın Öğrenme Stili:</b> {profile['dominant_style']}</p>
            <p>• <b>Akademik Sağlık İndeksi:</b> %{profile['academic_health']} | <b>Risk İndeksi:</b> %{profile['risk_index']}</p>
            <h4>Tespit Edilen Göstergeler:</h4>
            <ul>
                {''.join(f'<li>{t}</li>' for t in profile['labels'])}
            </ul>
            <hr>
            <h3>2. Pedagojik Koçluk Stratejisi</h3>
            {''.join(f'<p>{s}</p>' for s in profile['coach_strategy'])}
            <hr>
            <h3>3. Öğrenci Haftalık Eylem Planı</h3>
            <ul>
                {''.join(f'<li>{t}</li>' for t in profile['student_action_tasks'])}
            </ul>
            <br><br>
            <p><i>Eğitim Koçu İmzası: ____________________</i></p>
            """
            doc = QTextEdit()
            doc.setHtml(html)
            doc.print(printer)
