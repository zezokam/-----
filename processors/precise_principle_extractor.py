#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
معالج دقيق لاستخراج مبادئ المحكمة العليا
يركز على النصوص السوداء فقط (المبادئ الفعلية)
"""

import os
import re
import json
from pathlib import Path
import subprocess
from typing import List, Dict, Tuple, Optional
from docx import Document
import zipfile

class PrecisePrincipleExtractor:
    """معالج دقيق لاستخراج المبادئ القضائية"""
    
    def __init__(self, upload_dir="/home/ubuntu/upload"):
        self.upload_dir = Path(upload_dir)
        self.principles = []
        
        # أنماط تحديد المبادئ
        self.principle_patterns = [
            # نمط المبدأ المحاط بعلامات اقتباس
            r'"([^"]+)"',
            # نمط المبدأ بعد نقطة وقبل نقطة
            r'\.([^.]+)\.',
            # نمط المبدأ بعد شرطة
            r'ـ\s*([^ـ\n]+?)(?=\s*ـ|\n|$)',
            # نمط المبدأ في بداية الفقرة
            r'^([^.\n]+\.)',
        ]
        
        # كلمات مفتاحية تدل على بداية المبدأ
        self.principle_indicators = [
            'المحكمة', 'القاضي', 'الحكم', 'المبدأ', 'قررت', 'انتهت',
            'خلصت', 'اعتبرت', 'رأت', 'قضت', 'حكمت', 'فصلت'
        ]
        
        # كلمات تدل على نهاية المبدأ
        self.principle_terminators = [
            'الطعن رقم', 'القضية رقم', 'الجلسة', 'التاريخ',
            'المحكمة العليا', 'انتهى', 'والله أعلم'
        ]
    
    def extract_text_from_doc(self, file_path: Path) -> str:
        """استخراج النص من ملف .doc باستخدام antiword"""
        try:
            result = subprocess.run(
                ['antiword', str(file_path)],
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            if result.returncode == 0:
                return result.stdout
        except Exception as e:
            print(f"خطأ في antiword: {e}")
        
        # محاولة بديلة باستخدام catdoc
        try:
            result = subprocess.run(
                ['catdoc', str(file_path)],
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            if result.returncode == 0:
                return result.stdout
        except Exception as e:
            print(f"خطأ في catdoc: {e}")
        
        return ""
    
    def extract_text_from_docx(self, file_path: Path) -> str:
        """استخراج النص من ملف .docx"""
        try:
            doc = Document(file_path)
            full_text = []
            
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    full_text.append(paragraph.text.strip())
            
            return '\n'.join(full_text)
        except Exception as e:
            print(f"خطأ في قراءة {file_path}: {e}")
            return ""
    
    def clean_arabic_text(self, text: str) -> str:
        """تنظيف النص العربي"""
        if not text:
            return ""
        
        # إزالة الأحرف غير المرغوب فيها
        text = re.sub(r'[^\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF\w\s\.\,\:\;\!\?\(\)\[\]\-\+\=\/\\\"\'\n]', ' ', text)
        
        # توحيد المسافات
        text = re.sub(r'\s+', ' ', text)
        
        # إزالة الأسطر الفارغة المتعددة
        text = re.sub(r'\n\s*\n', '\n', text)
        
        return text.strip()
    
    def extract_case_info(self, text: str) -> Dict[str, str]:
        """استخراج معلومات القضية (رقم الطعن والتاريخ)"""
        info = {'case_number': '', 'date': '', 'court_type': ''}
        
        # استخراج رقم الطعن
        case_patterns = [
            r'(?:الطعن|طعن)\s*(?:رقم|#)?\s*(\d+/\d+)',
            r'(?:القضية|قضية)\s*(?:رقم|#)?\s*(\d+/\d+)',
            r'(\d+/\d{4})\s*(?:الطعن|طعن)',
        ]
        
        for pattern in case_patterns:
            match = re.search(pattern, text)
            if match:
                info['case_number'] = match.group(1)
                break
        
        # استخراج التاريخ
        date_patterns = [
            r'(\d{1,2}/\d{1,2}/\d{4})',
            r'(\d{4}/\d{1,2}/\d{1,2})',
            r'(\d{1,2}-\d{1,2}-\d{4})',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                info['date'] = match.group(1)
                break
        
        # تحديد نوع المحكمة
        if any(word in text for word in ['جزائي', 'جنائي', 'عقوبات', 'جريمة']):
            info['court_type'] = 'جزائي'
        elif any(word in text for word in ['مدني', 'تجاري', 'عقد', 'التزام']):
            info['court_type'] = 'مدني'
        elif any(word in text for word in ['شرعي', 'أحوال شخصية', 'زواج', 'طلاق']):
            info['court_type'] = 'شرعي'
        elif any(word in text for word in ['إداري', 'موظف', 'قرار إداري']):
            info['court_type'] = 'إداري'
        
        return info
    
    def identify_principle_text(self, paragraph: str) -> Optional[str]:
        """تحديد النص الذي يحتوي على المبدأ القضائي"""
        paragraph = paragraph.strip()
        
        if len(paragraph) < 20:  # تجاهل الفقرات القصيرة جداً
            return None
        
        # تجاهل الفقرات التي تحتوي على معلومات إجرائية فقط
        procedural_keywords = [
            'الجلسة', 'الموافق', 'برئاسة', 'وعضوية', 'الكاتب',
            'الحضور', 'الغياب', 'المرافعة', 'النطق بالحكم'
        ]
        
        if any(keyword in paragraph for keyword in procedural_keywords):
            return None
        
        # البحث عن المبادئ باستخدام الأنماط
        for pattern in self.principle_patterns:
            matches = re.findall(pattern, paragraph, re.MULTILINE | re.DOTALL)
            for match in matches:
                match = match.strip()
                if self.is_valid_principle(match):
                    return match
        
        # إذا لم نجد نمط محدد، نتحقق من محتوى الفقرة
        if self.contains_principle_indicators(paragraph):
            # استخراج الجملة الرئيسية
            sentences = re.split(r'[.؟!]', paragraph)
            for sentence in sentences:
                sentence = sentence.strip()
                if self.is_valid_principle(sentence):
                    return sentence
        
        return None
    
    def is_valid_principle(self, text: str) -> bool:
        """التحقق من صحة النص كمبدأ قضائي"""
        if not text or len(text) < 15:
            return False
        
        # يجب أن يحتوي على كلمات قانونية
        legal_keywords = [
            'المحكمة', 'القاضي', 'الحكم', 'القانون', 'الدعوى', 'الطعن',
            'المدعي', 'المدعى عليه', 'الحق', 'الالتزام', 'المسؤولية',
            'الضرر', 'التعويض', 'العقد', 'الجريمة', 'العقوبة'
        ]
        
        if not any(keyword in text for keyword in legal_keywords):
            return False
        
        # تجاهل النصوص التي تحتوي على معلومات شخصية أو إجرائية فقط
        exclude_patterns = [
            r'^\d+$',  # أرقام فقط
            r'^[أ-ي]\s*\)',  # ترقيم أبجدي
            r'^\d+\s*\)',  # ترقيم رقمي
            r'الصفحة\s*\d+',  # رقم الصفحة
        ]
        
        for pattern in exclude_patterns:
            if re.match(pattern, text):
                return False
        
        return True
    
    def contains_principle_indicators(self, text: str) -> bool:
        """التحقق من وجود مؤشرات المبدأ القضائي"""
        return any(indicator in text for indicator in self.principle_indicators)
    
    def extract_principles_from_text(self, text: str, source_file: str) -> List[Dict]:
        """استخراج المبادئ من النص"""
        principles = []
        
        # تقسيم النص إلى فقرات
        paragraphs = text.split('\n')
        
        current_case_info = {'case_number': '', 'date': '', 'court_type': ''}
        
        for paragraph in paragraphs:
            paragraph = self.clean_arabic_text(paragraph)
            
            if not paragraph:
                continue
            
            # تحديث معلومات القضية إذا وجدت
            case_info = self.extract_case_info(paragraph)
            if case_info['case_number']:
                current_case_info.update(case_info)
            
            # البحث عن المبدأ
            principle_text = self.identify_principle_text(paragraph)
            
            if principle_text:
                # استخراج الكلمات المفتاحية
                keywords = self.extract_keywords(principle_text)
                
                principle = {
                    'text': principle_text,
                    'case_number': current_case_info.get('case_number', ''),
                    'date': current_case_info.get('date', ''),
                    'court_type': current_case_info.get('court_type', ''),
                    'source_file': source_file,
                    'keywords': keywords,
                    'length': len(principle_text)
                }
                
                principles.append(principle)
        
        return principles
    
    def extract_keywords(self, text: str) -> List[str]:
        """استخراج الكلمات المفتاحية من النص"""
        # إزالة كلمات الوصل والضمائر
        stop_words = {
            'في', 'من', 'إلى', 'على', 'عن', 'مع', 'بين', 'تحت', 'فوق',
            'هذا', 'هذه', 'ذلك', 'تلك', 'التي', 'الذي', 'التي', 'اللذان',
            'هو', 'هي', 'هم', 'هن', 'أن', 'إن', 'كان', 'كانت', 'يكون',
            'لم', 'لن', 'لا', 'ما', 'قد', 'كل', 'بعض', 'جميع'
        }
        
        # استخراج الكلمات
        words = re.findall(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+', text)
        
        # تصفية الكلمات
        keywords = []
        for word in words:
            if len(word) > 2 and word not in stop_words:
                keywords.append(word)
        
        # إزالة التكرارات والاحتفاظ بأهم الكلمات
        unique_keywords = list(set(keywords))
        
        # ترتيب حسب الطول (الكلمات الأطول أهم)
        unique_keywords.sort(key=len, reverse=True)
        
        return unique_keywords[:15]  # أهم 15 كلمة
    
    def process_all_files(self) -> Dict:
        """معالجة جميع الملفات"""
        print("🔍 بدء المعالجة الدقيقة للملفات...")
        
        all_principles = []
        file_stats = {}
        
        for file_path in self.upload_dir.glob("*.doc*"):
            print(f"معالجة: {file_path.name}")
            
            # استخراج النص
            if file_path.suffix.lower() == '.docx':
                text = self.extract_text_from_docx(file_path)
            else:
                text = self.extract_text_from_doc(file_path)
            
            if not text:
                print(f"  ❌ فشل في استخراج النص من {file_path.name}")
                continue
            
            print(f"  📄 تم استخراج {len(text)} حرف")
            
            # استخراج المبادئ
            principles = self.extract_principles_from_text(text, file_path.name)
            
            print(f"  ⚖️ تم استخراج {len(principles)} مبدأ")
            
            all_principles.extend(principles)
            file_stats[file_path.name] = len(principles)
        
        # حفظ النتائج
        output_file = "precise_principles.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_principles, f, ensure_ascii=False, indent=2)
        
        # إنشاء فهرس البحث
        search_index = self.create_search_index(all_principles)
        with open("precise_search_index.json", 'w', encoding='utf-8') as f:
            json.dump(search_index, f, ensure_ascii=False, indent=2)
        
        # إحصائيات
        stats = self.generate_statistics(all_principles, file_stats)
        with open("precise_stats.json", 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ تم استخراج {len(all_principles)} مبدأ إجمالي")
        print(f"💾 تم حفظ قاعدة البيانات في: {output_file}")
        print(f"🔍 تم إنشاء فهرس البحث مع {len(search_index)} كلمة")
        
        return {
            'principles': all_principles,
            'stats': stats,
            'search_index': search_index
        }
    
    def create_search_index(self, principles: List[Dict]) -> Dict:
        """إنشاء فهرس البحث"""
        index = {}
        
        for i, principle in enumerate(principles):
            # فهرسة النص الرئيسي
            words = re.findall(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+', 
                             principle['text'].lower())
            
            for word in words:
                if len(word) > 2:
                    if word not in index:
                        index[word] = []
                    if i not in index[word]:
                        index[word].append(i)
            
            # فهرسة الكلمات المفتاحية
            for keyword in principle.get('keywords', []):
                keyword = keyword.lower()
                if keyword not in index:
                    index[keyword] = []
                if i not in index[keyword]:
                    index[keyword].append(i)
        
        return index
    
    def generate_statistics(self, principles: List[Dict], file_stats: Dict) -> Dict:
        """إنشاء إحصائيات قاعدة البيانات"""
        stats = {
            'total_principles': len(principles),
            'principles_with_case_numbers': len([p for p in principles if p.get('case_number')]),
            'principles_with_dates': len([p for p in principles if p.get('date')]),
            'file_distribution': file_stats,
            'court_type_distribution': {},
            'average_principle_length': 0,
            'top_keywords': {}
        }
        
        # توزيع أنواع المحاكم
        court_types = {}
        total_length = 0
        all_keywords = {}
        
        for principle in principles:
            court_type = principle.get('court_type', 'غير محدد')
            court_types[court_type] = court_types.get(court_type, 0) + 1
            
            total_length += principle.get('length', 0)
            
            for keyword in principle.get('keywords', []):
                all_keywords[keyword] = all_keywords.get(keyword, 0) + 1
        
        stats['court_type_distribution'] = court_types
        stats['average_principle_length'] = total_length // len(principles) if principles else 0
        
        # أهم الكلمات المفتاحية
        sorted_keywords = sorted(all_keywords.items(), key=lambda x: x[1], reverse=True)
        stats['top_keywords'] = dict(sorted_keywords[:20])
        
        return stats

def main():
    """تشغيل المعالج الدقيق"""
    extractor = PrecisePrincipleExtractor()
    results = extractor.process_all_files()
    
    # طباعة الإحصائيات
    stats = results['stats']
    print("\n" + "="*60)
    print("📊 إحصائيات قاعدة البيانات المحسنة")
    print("="*60)
    
    print(f"إجمالي المبادئ: {stats['total_principles']}")
    print(f"المبادئ مع أرقام طعون: {stats['principles_with_case_numbers']}")
    print(f"المبادئ مع تواريخ: {stats['principles_with_dates']}")
    print(f"متوسط طول المبدأ: {stats['average_principle_length']} حرف")
    
    print(f"\n📂 توزيع المبادئ حسب الملف المصدر:")
    for file_name, count in stats['file_distribution'].items():
        print(f"  {file_name}: {count}")
    
    print(f"\n⚖️ توزيع المبادئ حسب نوع المحكمة:")
    for court_type, count in stats['court_type_distribution'].items():
        print(f"  {court_type}: {count}")
    
    print(f"\n🔑 أهم الكلمات المفتاحية:")
    for keyword, count in list(stats['top_keywords'].items())[:10]:
        print(f"  {keyword}: {count}")

if __name__ == "__main__":
    main()
