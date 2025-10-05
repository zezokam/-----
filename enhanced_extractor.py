#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import re
import subprocess
from pathlib import Path
from collections import defaultdict
from docx import Document

def extract_text_from_doc(file_path):
    """استخراج النص من ملف Word (.doc) باستخدام antiword"""
    try:
        result = subprocess.run(['antiword', file_path], 
                              capture_output=True, text=True, encoding='utf-8')
        if result.returncode == 0:
            return result.stdout
        else:
            print(f"خطأ في antiword: {result.stderr}")
            return None
    except Exception as e:
        print(f"خطأ في استخراج النص من {file_path}: {e}")
        return None

def extract_text_from_docx(file_path):
    """استخراج النص من ملف Word (.docx) باستخدام python-docx"""
    try:
        doc = Document(file_path)
        text = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text.append(paragraph.text.strip())
        return '\n'.join(text)
    except Exception as e:
        print(f"خطأ في استخراج النص من {file_path}: {e}")
        return None

def extract_text_from_file(file_path):
    """استخراج النص من ملف Word حسب نوعه"""
    if file_path.suffix.lower() == '.docx':
        return extract_text_from_docx(file_path)
    else:
        return extract_text_from_doc(str(file_path))

def clean_arabic_text(text):
    """تنظيف النص العربي"""
    if not text:
        return ""
    
    # إزالة الأحرف غير المرغوب فيها مع الاحتفاظ بعلامات الترقيم المهمة
    text = re.sub(r'[^\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF\s\.\،\؛\:\(\)\[\]\-\d\/\"\'\«\»]', '', text)
    
    # تنظيف المسافات الزائدة
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text

def extract_principles_from_text(text, source_file):
    """استخراج المبادئ من النص بدقة عالية"""
    principles = []
    
    if not text:
        return principles
    
    # تقسيم النص إلى فقرات
    paragraphs = text.split('\n')
    
    current_case = {}
    current_principle_parts = []
    collecting_principle = False
    
    # تحديد نوع المحكمة من اسم الملف
    court_type = 'غير محدد'
    if 'جزائي' in source_file.lower():
        court_type = 'جزائي'
    elif 'مدني' in source_file.lower():
        court_type = 'مدني'
    elif 'شرعي' in source_file.lower():
        court_type = 'شرعي'
    
    for i, paragraph in enumerate(paragraphs):
        paragraph = clean_arabic_text(paragraph)
        if not paragraph or len(paragraph) < 5:
            continue
        
        # البحث عن رقم الطعن
        case_patterns = [
            r'(?:طعن|الطعن)\s*(?:رقم|مقر)?\s*(\d+/\d+)',
            r'(\d+/\d+)\s*(?:مقر|رقم)?\s*(?:نعطلا|الطعن|طعن)',
            r'في\s+الطعن\s+رقم\s+(\d+/\d+)',
        ]
        
        case_number = None
        for pattern in case_patterns:
            match = re.search(pattern, paragraph)
            if match:
                case_number = match.group(1)
                break
        
        # البحث عن التاريخ
        date_patterns = [
            r'(\d{1,2}/\d{1,2}/\d{4})',
            r'(\d{4}/\d{1,2}/\d{1,2})',
        ]
        
        date = None
        for pattern in date_patterns:
            match = re.search(pattern, paragraph)
            if match:
                date = match.group(1)
                break
        
        # إذا وُجد رقم طعن جديد، احفظ المبدأ السابق
        if case_number and current_principle_parts and current_case:
            principle_text = ' '.join(current_principle_parts).strip()
            if len(principle_text) > 30:  # تأكد من أن المبدأ ليس قصيراً جداً
                current_case['text'] = principle_text
                current_case['source_file'] = source_file
                current_case['court_type'] = court_type
                principles.append(current_case.copy())
            
            # إعادة تعيين للمبدأ الجديد
            current_case = {}
            current_principle_parts = []
            collecting_principle = False
        
        # تحديث معلومات القضية الحالية
        if case_number:
            current_case['case_number'] = case_number
        if date:
            current_case['date'] = date
        
        # البحث عن بداية المبدأ
        # المبدأ عادة يبدأ بعد رقم الطعن والتاريخ
        principle_indicators = [
            r'^-\s*[^\d]',  # يبدأ بشرطة متبوعة بنص
            r'^\d+\s*-\s*[^\d]',  # يبدأ برقم وشرطة
            r'[\.؛]\s*[^\d\s]',  # جملة تنتهي بنقطة أو فاصلة منقوطة
        ]
        
        # تحديد ما إذا كان هذا جزءاً من المبدأ
        is_principle_part = False
        
        # إذا كان يحتوي على كلمات قانونية مهمة
        legal_keywords = [
            'المحكمة', 'القاضي', 'الحكم', 'القانون', 'المادة', 'الفقرة',
            'الدعوى', 'المدعي', 'المدعى', 'الطعن', 'الاستئناف',
            'الإثبات', 'البينة', 'الشهادة', 'الخبرة', 'التقدير',
            'المسؤولية', 'الضرر', 'التعويض', 'الحق', 'الالتزام',
            'العقد', 'البيع', 'الشراء', 'الإيجار', 'الملكية',
            'الجريمة', 'العقوبة', 'المتهم', 'الجاني', 'القصد',
            'الطلاق', 'النفقة', 'الحضانة', 'الميراث', 'الوصية'
        ]
        
        if (any(keyword in paragraph for keyword in legal_keywords) and
            len(paragraph) > 20 and
            not paragraph.startswith('ص') and
            not re.match(r'^\d+\s*$', paragraph) and
            'صفحة' not in paragraph):
            is_principle_part = True
            collecting_principle = True
        
        # إذا كنا نجمع المبدأ وهذه فقرة مناسبة
        if collecting_principle and is_principle_part:
            current_principle_parts.append(paragraph)
            
            # التحقق من نهاية المبدأ
            if (paragraph.endswith('.') or paragraph.endswith('؛')) and len(' '.join(current_principle_parts)) > 100:
                # البحث في الفقرات التالية للتأكد من نهاية المبدأ
                next_paragraphs = paragraphs[i+1:i+3] if i+1 < len(paragraphs) else []
                has_new_case = any(re.search(r'طعن|الطعن|\d+/\d+', clean_arabic_text(p)) for p in next_paragraphs)
                
                if has_new_case or not next_paragraphs:
                    collecting_principle = False
    
    # حفظ المبدأ الأخير
    if current_principle_parts and current_case:
        principle_text = ' '.join(current_principle_parts).strip()
        if len(principle_text) > 30:
            current_case['text'] = principle_text
            current_case['source_file'] = source_file
            current_case['court_type'] = court_type
            principles.append(current_case.copy())
    
    return principles

def extract_keywords(text):
    """استخراج الكلمات المفتاحية من النص"""
    if not text:
        return []
    
    # قائمة الكلمات الشائعة التي يجب تجاهلها
    stop_words = {
        'في', 'من', 'إلى', 'على', 'عن', 'مع', 'بين', 'تحت', 'فوق', 'أمام', 'خلف',
        'هذا', 'هذه', 'ذلك', 'تلك', 'التي', 'الذي', 'اللذان', 'اللتان',
        'هو', 'هي', 'هم', 'هن', 'أنت', 'أنتم', 'أنتن', 'أنا', 'نحن',
        'كان', 'كانت', 'يكون', 'تكون', 'أكون', 'نكون', 'يكونوا', 'تكن',
        'قد', 'لقد', 'قال', 'قالت', 'يقول', 'تقول', 'أقول', 'نقول',
        'كل', 'بعض', 'جميع', 'معظم', 'أكثر', 'أقل', 'غير', 'سوى',
        'أو', 'أم', 'لكن', 'إذا', 'إذ', 'حيث', 'بينما', 'عندما',
        'ما', 'ماذا', 'متى', 'أين', 'كيف', 'لماذا', 'أي', 'أية',
        'يجب', 'ينبغي', 'يمكن', 'يجوز', 'لا', 'لم', 'لن', 'ليس'
    }
    
    # استخراج الكلمات العربية
    words = re.findall(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+', text)
    
    # تصفية الكلمات
    keywords = []
    for word in words:
        if (len(word) > 2 and 
            word not in stop_words and 
            not word.isdigit()):
            keywords.append(word)
    
    # إرجاع أهم الكلمات (الأكثر تكراراً)
    word_count = defaultdict(int)
    for word in keywords:
        word_count[word] += 1
    
    # ترتيب حسب التكرار وأخذ أهم 15 كلمة
    sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
    return [word for word, count in sorted_words[:15]]

def create_search_index(principles):
    """إنشاء فهرس البحث"""
    index = defaultdict(list)
    
    for i, principle in enumerate(principles):
        text = principle.get('text', '')
        
        # فهرسة الكلمات في النص
        words = re.findall(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+', text.lower())
        
        for word in words:
            if len(word) > 2:
                if i not in index[word]:
                    index[word].append(i)
    
    return dict(index)

def main():
    print("🔄 بدء استخراج المبادئ بدقة عالية (محسن)...")
    
    # مجلد الملفات المصدرية
    documents_dir = Path("documents")
    if not documents_dir.exists():
        print("❌ مجلد documents غير موجود")
        return
    
    all_principles = []
    stats = {
        'total_files': 0,
        'processed_files': 0,
        'total_principles': 0,
        'by_court_type': defaultdict(int)
    }
    
    # معالجة كل ملف
    for file_path in documents_dir.glob("*.doc*"):
        stats['total_files'] += 1
        print(f"📄 معالجة ملف: {file_path.name}")
        
        # استخراج النص
        text = extract_text_from_file(file_path)
        if not text:
            print(f"⚠️ فشل في استخراج النص من {file_path.name}")
            continue
        
        # استخراج المبادئ
        principles = extract_principles_from_text(text, file_path.name)
        
        # إضافة الكلمات المفتاحية
        for principle in principles:
            principle['keywords'] = extract_keywords(principle['text'])
            stats['by_court_type'][principle['court_type']] += 1
        
        all_principles.extend(principles)
        stats['processed_files'] += 1
        stats['total_principles'] += len(principles)
        
        print(f"✅ تم استخراج {len(principles)} مبدأ من {file_path.name}")
    
    # إنشاء فهرس البحث
    print("🔍 إنشاء فهرس البحث...")
    search_index = create_search_index(all_principles)
    
    # حفظ النتائج
    print("💾 حفظ النتائج...")
    
    # حفظ المبادئ
    with open('data/enhanced_principles.json', 'w', encoding='utf-8') as f:
        json.dump(all_principles, f, ensure_ascii=False, indent=2)
    
    # حفظ فهرس البحث
    with open('data/enhanced_search_index.json', 'w', encoding='utf-8') as f:
        json.dump(search_index, f, ensure_ascii=False, indent=2)
    
    # حفظ الإحصائيات
    stats['by_court_type'] = dict(stats['by_court_type'])
    with open('data/enhanced_stats.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    # طباعة النتائج
    print("\n" + "="*50)
    print("📊 تقرير الاستخراج المحسن:")
    print(f"📁 إجمالي الملفات: {stats['total_files']}")
    print(f"✅ الملفات المعالجة: {stats['processed_files']}")
    print(f"📋 إجمالي المبادئ: {stats['total_principles']}")
    print(f"🔍 الكلمات المفهرسة: {len(search_index)}")
    print("\n📈 التوزيع حسب نوع المحكمة:")
    for court_type, count in stats['by_court_type'].items():
        print(f"  {court_type}: {count} مبدأ")
    
    print("\n✅ تم الانتهاء من الاستخراج بنجاح!")
    
    # عرض عينات من المبادئ المستخرجة
    print("\n📝 عينات من المبادئ المستخرجة:")
    for i, principle in enumerate(all_principles[:5]):
        print(f"\n--- مبدأ {i+1} ---")
        print(f"رقم الطعن: {principle.get('case_number', 'غير محدد')}")
        print(f"التاريخ: {principle.get('date', 'غير محدد')}")
        print(f"نوع المحكمة: {principle.get('court_type', 'غير محدد')}")
        print(f"النص: {principle.get('text', '')[:300]}...")
        print(f"الكلمات المفتاحية: {', '.join(principle.get('keywords', [])[:8])}")

if __name__ == "__main__":
    main()
