#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ملف التشغيل السريع لقاعدة بيانات مبادئ المحكمة العليا
"""

import os
import sys
import subprocess

def install_requirements():
    """تثبيت المتطلبات"""
    print("📦 تثبيت المتطلبات...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        print("✅ تم تثبيت المتطلبات بنجاح")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ خطأ في تثبيت المتطلبات: {e}")
        return False

def check_data_files():
    """فحص وجود ملفات قاعدة البيانات"""
    required_files = [
        'data/precise_principles.json',
        'data/precise_search_index.json', 
        'data/precise_stats.json'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        print("⚠️ ملفات قاعدة البيانات التالية مفقودة:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        print("💡 سيتم استخدام بيانات تجريبية")
        return False
    else:
        print("✅ جميع ملفات قاعدة البيانات موجودة")
        return True

def run_server():
    """تشغيل الخادم"""
    print("🚀 بدء تشغيل الخادم...")
    try:
        from app import app, search_engine
        print(f"📊 تم تحميل {len(search_engine.principles)} مبدأ قضائي")
        print(f"🔍 تم فهرسة {len(search_engine.search_index)} كلمة")
        print("🌐 الخادم متاح على: http://localhost:5000")
        print("⏹️  اضغط Ctrl+C لإيقاف الخادم")
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n👋 تم إيقاف الخادم")
    except Exception as e:
        print(f"❌ خطأ في تشغيل الخادم: {e}")

def main():
    """الوظيفة الرئيسية"""
    print("=" * 60)
    print("🏛️  قاعدة بيانات مبادئ المحكمة العليا العمانية")
    print("=" * 60)
    
    # فحص ملفات قاعدة البيانات
    check_data_files()
    
    # تثبيت المتطلبات
    if not install_requirements():
        return
    
    # تشغيل الخادم
    run_server()

if __name__ == '__main__':
    main()
