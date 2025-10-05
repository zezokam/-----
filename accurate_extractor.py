#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import re
import subprocess
from pathlib import Path
from collections import defaultdict

def extract_text_from_doc(file_path):
    """استخراج النص من ملف Word باستخدام antiword"""
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

def clean_arabic_text(text):
    """تنظيف النص العربي"""
    if not text:
        return ""
    
    # إزالة الأحرف غير المرغوب فيها
    text = re.sub(r'[^\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF\s\.\،\؛\:\(\)\[\]\-\d\/]', '', text)
    
    # تنظيف المسافات الزائدة
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text

def extract_principles_from_text(text, source_file):
    """استخراج المبادئ من النص بدقة عالية"""
    principles = []
    
    if not text:
        return principles
    
    # تقسيم النص إلى أسطر
    lines = text.split('\n')
    
    current_case = {}
    current_principle = []
    in_principle = False
    
    for i, line in enumerate(lines):
        line = clean_arabic_text(line)
        if not line or len(line) < 3:
            continue
            
        # البحث عن رقم الطعن والتاريخ
        case_pattern = r'(\d+/\d+)\s*(?:مقر|رقم)?\s*(?:نعطلا|الطعن)'
        case_match = re.search(case_pattern, line)
        
        date_pattern = r'(\d{1,2}/\d{1,2}/\d{4})'
        date_match = re.search(date_pattern, line)
        
        if case_match:
            # حفظ المبدأ السابق إذا كان موجوداً
            if current_principle and current_case:
                principle_text = ' '.join(current_principle).strip()
                if len(principle_text) > 20:  # تأكد من أن المبدأ ليس قصيراً جداً
                    current_case['text'] = principle_text
                    current_case['source_file'] = source_file
                    principles.append(current_case.copy())
            
            # بدء مبدأ جديد
            current_case = {'case_number': case_match.group(1)}
            current_principle = []
            in_principle = False
            
        if date_match:
            current_case['date'] = date_match.group(1)
            
        # تحديد نوع المحكمة من اسم الملف
        if 'جزائي' in source_file:
            current_case['court_type'] = 'جزائي'
        elif 'مدني' in source_file:
            current_case['court_type'] = 'مدني'
        elif 'شرعي' in source_file:
            current_case['court_type'] = 'شرعي'
        else:
            current_case['court_type'] = 'غير محدد'
        
        # البحث عن بداية المبدأ (النص الأسود)
        # المبدأ عادة يأتي بعد العنوان الأحمر
        if (any(keyword in line for keyword in ['المبدأ', 'مبدأ', 'القاعدة', 'الحكم']) or
            (len(line) > 30 and '.' in line and not line.startswith('ص') and 
             not re.match(r'^\d+', line) and not 'صفحة' in line)):
            in_principle = True
            
        # جمع نص المبدأ
        if in_principle and line:
            # تجاهل الأسطر التي تبدو وكأنها عناوين أو ترقيم صفحات
            if (not line.startswith('ص') and 
                not re.match(r'^\d+\s*$', line) and
                'صفحة' not in line and
                len(line) > 5):
                current_principle.append(line)
                
                # إنهاء المبدأ عند وجود نقطة في نهاية جملة طويلة
                if (line.endswith('.') or line.endswith('؛') or line.endswith('،')) and len(' '.join(current_principle)) > 50:
                    # البحث عن السطر التالي لتأكيد نهاية المبدأ
                    next_lines = lines[i+1:i+3] if i+1 < len(lines) else []
                    if (not next_lines or 
                        any(re.match(r'^\d+/\d+', clean_arabic_text(next_line)) for next_line in next_lines) or
                        any('طعن' in clean_arabic_text(next_line) for next_line in next_lines)):
                        in_principle = False
    
    # حفظ المبدأ الأخير
    if current_principle and current_case:
        principle_text = ' '.join(current_principle).strip()
        if len(principle_text) > 20:
            current_case['text'] = principle_text
            current_case['source_file'] = source_file
            principles.append(current_case.copy())
    
    return principles

def extract_keywords(text):
    """استخراج الكلمات المفتاحية من النص"""
    if not text:
        return []
    
    # قائمة الكلمات الشائعة التي يجب تجاهلها
    stop_words = {
        'في', 'من', 'إلى', 'على', 'عن', 'مع', 'بين', 'تحت', 'فوق', 'أمام', 'خلف',
        'هذا', 'هذه', 'ذلك', 'تلك', 'التي', 'الذي', 'التي', 'اللذان', 'اللتان',
        'هو', 'هي', 'هم', 'هن', 'أنت', 'أنتم', 'أنتن', 'أنا', 'نحن',
        'كان', 'كانت', 'يكون', 'تكون', 'أكون', 'نكون', 'يكونوا', 'تكن',
        'قد', 'لقد', 'قال', 'قالت', 'يقول', 'تقول', 'أقول', 'نقول',
        'كل', 'بعض', 'جميع', 'معظم', 'أكثر', 'أقل', 'غير', 'سوى',
        'أو', 'أم', 'لكن', 'لكن', 'إذا', 'إذ', 'حيث', 'بينما', 'عندما',
        'ما', 'ماذا', 'متى', 'أين', 'كيف', 'لماذا', 'أي', 'أية'
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
    
    # ترتيب حسب التكرار وأخذ أهم 10 كلمات
    sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
    return [word for word, count in sorted_words[:10]]

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
    print("🔄 بدء استخراج المبادئ بدقة عالية...")
    
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
        text = extract_text_from_doc(str(file_path))
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
    with open('data/accurate_principles.json', 'w', encoding='utf-8') as f:
        json.dump(all_principles, f, ensure_ascii=False, indent=2)
    
    # حفظ فهرس البحث
    with open('data/accurate_search_index.json', 'w', encoding='utf-8') as f:
        json.dump(search_index, f, ensure_ascii=False, indent=2)
    
    # حفظ الإحصائيات
    stats['by_court_type'] = dict(stats['by_court_type'])
    with open('data/accurate_stats.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    # طباعة النتائج
    print("\n" + "="*50)
    print("📊 تقرير الاستخراج:")
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
    for i, principle in enumerate(all_principles[:3]):
        print(f"\n--- مبدأ {i+1} ---")
        print(f"رقم الطعن: {principle.get('case_number', 'غير محدد')}")
        print(f"التاريخ: {principle.get('date', 'غير محدد')}")
        print(f"نوع المحكمة: {principle.get('court_type', 'غير محدد')}")
        print(f"النص: {principle.get('text', '')[:200]}...")
        print(f"الكلمات المفتاحية: {', '.join(principle.get('keywords', [])[:5])}")

if __name__ == "__main__":
    main()
